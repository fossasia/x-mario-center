#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import os
from gi.repository import GObject
import time
import threading

import logging
from softwarecenter.distro import get_distro

from launchpadlib.launchpad import Launchpad
from launchpadlib.credentials import RequestTokenAuthorizationEngine
from launchpadlib.uris import LPNET_SERVICE_ROOT
from softwarecenter.paths import SOFTWARE_CENTER_CACHE_DIR

# py3 compat
try:
    from queue import Queue
    Queue  # pyflakes
except ImportError:
    from Queue import Queue

from login import LoginBackend

# LP to use
SERVICE_ROOT = LPNET_SERVICE_ROOT

# internal

# the various states that the login can be in
LOGIN_STATE_UNKNOWN = "unkown"
LOGIN_STATE_ASK_USER_AND_PASS = "ask-user-and-pass"
LOGIN_STATE_HAS_USER_AND_PASS = "has-user-pass"
LOGIN_STATE_SUCCESS = "success"
LOGIN_STATE_SUCCESS_PENDING = "success-pending"
LOGIN_STATE_AUTH_FAILURE = "auth-fail"
LOGIN_STATE_USER_CANCEL = "user-cancel"


class UserCancelException(Exception):
    """ user pressed cancel """
    pass


class LaunchpadlibWorker(threading.Thread):
    """The launchpadlib worker thread - it does not touch the UI
       and only communicates via the following:

       "login_state" - the current LOGIN_STATE_* value

       To input reviews call "queue_review()"
       When no longer needed, call "shutdown()"
    """

    def __init__(self):
        # init parent
        threading.Thread.__init__(self)
        # the current login state, this is used accross multiple threads
        self.login_state = LOGIN_STATE_UNKNOWN
        # the username/pw to use
        self.login_username = ""
        self.login_password = ""
        self._launchpad = None
        self._pending_requests = Queue()
        self._shutdown = False
        self._logger = logging.getLogger("softwarecenter.backend")

    def run(self):
        """
        Main thread run interface, logs into launchpad
        """
        self._logger.debug("lp worker thread run")
        # login
        self._lp_login()
        # loop
        self._wait_for_commands()

    def shutdown(self):
        """Request shutdown"""
        self._shutdown = True

    def queue_request(self, func, args, result_callback):
        # FIXME: add support to pass strings instead of callable
        self._pending_requests.put((func, args, result_callback))

    def _wait_for_commands(self):
        """internal helper that waits for commands"""
        while True:
            while not self._pending_requests.empty():
                self._logger.debug("found pending request")
                (func, args, result_callback) = self._pending_requests.get()
                # run func async
                res = func(*args)
                # provide result to the callback
                result_callback(res)
                self._pending_requests.task_done()
            # wait a bit
            time.sleep(0.1)
            if (self._shutdown and
                self._pending_requests.empty()):
                return

    def _lp_login(self, access_level=['READ_PRIVATE']):
        """ internal LP login code """
        self._logger.debug("lp_login")
        # use cachedir
        cachedir = SOFTWARE_CENTER_CACHE_DIR
        if not os.path.exists(cachedir):
            os.makedirs(cachedir)
        # login into LP with GUI
        try:
            self._launchpad = Launchpad.login_with(
                'software-center', SERVICE_ROOT, cachedir,
                allow_access_levels=access_level,
                authorizer_class=AuthorizeRequestTokenFromThread)
            self.display_name = self._launchpad.me.display_name
        except Exception as e:
            if type(e) == UserCancelException:
                return
            self._logger.exception("Launchpad.login_with()")
            # remove token on failure, it may be e.g. expired
            # FIXME: store the token in a different place and to avoid
            #        having to use _get_paths()
            (service_root, launchpadlib_dir, cache_path,
             service_root_dir) = Launchpad._get_paths(SERVICE_ROOT, cachedir)
            credentials_path = os.path.join(service_root_dir, 'credentials')
            consumer_credentials_path = os.path.join(credentials_path,
                'software-center')
            # ---
            if os.path.exists(consumer_credentials_path):
                os.remove(consumer_credentials_path)
            self._lp_login(access_level)
            return
        self.login_state = LOGIN_STATE_SUCCESS
        self._logger.debug("/done %s" % self._launchpad)


class AuthorizeRequestTokenFromThread(RequestTokenAuthorizationEngine):
    """ Internal helper that updates the login_state of
        the modul global lp_worker_thread object
    """
    def __init__(self, *args, **kwargs):
        super(AuthorizeRequestTokenFromThread, self).__init__(*args, **kwargs)
        self._logger = logging.getLogger("softwarecenter.backend")

    # we need this to give the engine a place to store the state
    # for the UI
    def __new__(cls, *args, **kwargs):
        o = object.__new__(cls)
        # keep the state here (the lp_worker_thead global to this module)
        o.lp_worker = lp_worker_thread
        return o

    def input_username(self, cached_username, suggested_message):
        self._logger.debug("input_username: %s" % self.lp_worker.login_state)
        # otherwise go into ASK state
        if not self.lp_worker.login_state in (LOGIN_STATE_ASK_USER_AND_PASS,
                                              LOGIN_STATE_AUTH_FAILURE,
                                              LOGIN_STATE_USER_CANCEL):
            self.lp_worker.login_state = LOGIN_STATE_ASK_USER_AND_PASS
        # check if user canceled and if so just return ""
        if self.lp_worker.login_state == LOGIN_STATE_USER_CANCEL:
            raise UserCancelException
        # wait for username to become available
        while not self.lp_worker.login_state in (LOGIN_STATE_HAS_USER_AND_PASS,
                                                 LOGIN_STATE_USER_CANCEL):
            time.sleep(0.2)
        # note: returning None here make lplib open a registration page
        #       in the browser
        return self.lp_worker.login_username

    def input_password(self, suggested_message):
        self._logger.debug("Input password size %s" %
            len(self.lp_worker.login_password))
        return self.lp_worker.login_password

    def input_access_level(self, available_levels, suggested_message,
                           only_one_option=None):
        """Collect the desired level of access from the end-user."""
        self._logger.debug("input_access_level")
        return "WRITE_PUBLIC"

    def startup(self, suggested_messages):
        self._logger.debug("startup")

    def authentication_failure(self, suggested_message):
        """The user entered invalid credentials."""
        self._logger.debug("auth failure")
        # ignore auth failures if the user canceled
        if self.lp_worker.login_state == LOGIN_STATE_USER_CANCEL:
            return
        self.lp_worker.login_state = LOGIN_STATE_AUTH_FAILURE

    def success(self, suggested_message):
        """The token was successfully authorized."""
        self._logger.debug("success")
        self.lp_worker.login_state = LOGIN_STATE_SUCCESS_PENDING


class GLaunchpad(LoginBackend):
    """ A launchpad connection that uses GObject signals
        for communication and async tasks
    """

    NEW_ACCOUNT_URL = "https://login.launchpad.net/+standalone-login"
    FORGOT_PASSWORD_URL = "https://login.launchpad.net/+standalone-login"

    def __init__(self):
        LoginBackend.__init__(self)
        self.distro = get_distro()
        self.oauth_token = None

    def connect_to_server(self):
        """ Connects to launchpad and emits one of:
            - need-username-password (use enter_username_password() then)
            - login-successful
            - login-failed
        """
        GObject.timeout_add(200, self._wait_for_login)
        lp_worker_thread.start()

    def shutdown(self):
        """ shutdown the server connection thread """
        lp_worker_thread.shutdown()

    def enter_username_password(self, user, password):
        """
        provider username and password, ususally used when the
        need-username-password signal was send
        """
        lp_worker_thread.login_username = user
        lp_worker_thread.login_password = password
        lp_worker_thread.login_state = LOGIN_STATE_HAS_USER_AND_PASS

    def login(self, username=None, password=None):
        if username and password:
            self.enter_username_password(username, password)
        else:
            self.connect_to_server()

    def cancel_login(self):
        lp_worker_thread.login_state = LOGIN_STATE_USER_CANCEL

    def get_subscribed_archives(self):
        """ return list of sources.list entries """
        urls = lp_worker_thread._launchpad.me.getArchiveSubscriptionURLs()
        return self._format_archive_subscription_urls_as_deb_lines(urls)

    def _format_archive_subscription_urls_as_deb_lines(self, urls):
        deb_lines = ["deb %s %s main" % (url, self.distro.get_codename()) \
                     for url in urls]
        return deb_lines

    def get_subscribed_archives_async(self, callback):
        """ get the available subscribed archives and run 'callback' when
            they become availalbe
        """
        def _result_cb(urls):
            # format as deb lines
            callback(self._format_archive_subscription_urls_as_deb_lines(urls))
        #func = "me.getArchiveSubscriptionURLs"
        func = lp_worker_thread._launchpad.me.getArchiveSubscriptionURLs
        lp_worker_thread.queue_request(func, (), _result_cb)

    def _wait_for_login(self):
        state = lp_worker_thread.login_state
        if state == LOGIN_STATE_AUTH_FAILURE:
            self.emit("login-failed")
        elif state == LOGIN_STATE_ASK_USER_AND_PASS:
            self.emit("need-username-password")
        elif state == LOGIN_STATE_SUCCESS:
            self.emit("login-successful", self.oauth_token)
            return False
        elif state == LOGIN_STATE_USER_CANCEL:
            return False
        return True

# IMPORTANT: create one (module) global LP worker thread here
lp_worker_thread = LaunchpadlibWorker()
# daemon threads make it crash on cancel
lp_worker_thread.daemon = True


# test code
def _login_success(lp):
    print ("success %s" % lp)
    print(lp.get_subscribed_archives())
    print(lp.get_subscribed_archives_async(_result_callback))


def _login_failed(lp):
    print ("fail %s" % lp)


def _result_callback(result_list):
    print("_result_callback %s" % result_list)


def _login_need_user_and_password(lp):
    import sys
    sys.stdout.write("user: ")
    sys.stdout.flush()
    user = sys.stdin.readline().strip()
    sys.stdout.write("pass: ")
    sys.stdout.flush()
    password = sys.stdin.readline().strip()
    lp.enter_username_password(user, password)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    lp = GLaunchpad()
    lp.connect("login-successful", _login_success)
    lp.connect("login-failed", _login_failed)
    lp.connect("need-username-password", _login_need_user_and_password)
    lp.connect_to_server()

    # wait
    try:
        GObject.MainLoop().run()
    except KeyboardInterrupt:
        lp_worker_thread.shutdown()
