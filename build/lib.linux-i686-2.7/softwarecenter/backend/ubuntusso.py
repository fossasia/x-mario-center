#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2010 Canonical
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


from gi.repository import GObject

import logging
import os

import softwarecenter.paths

# mostly for testing
from fake_review_settings import FakeReviewSettings, network_delay
from spawn_helper import SpawnHelper

LOG = logging.getLogger(__name__)


class UbuntuSSOAPI(GObject.GObject):
    """ Ubuntu SSO interface using the oauth token from the keyring """

    __gsignals__ = {
        "whoami": (GObject.SIGNAL_RUN_LAST,
                   GObject.TYPE_NONE,
                   (GObject.TYPE_PYOBJECT,),
                   ),
        "error": (GObject.SIGNAL_RUN_LAST,
                  GObject.TYPE_NONE,
                  (GObject.TYPE_PYOBJECT,),
                  ),
        }

    def __init__(self):
        GObject.GObject.__init__(self)

    def _on_whoami_data(self, spawner, piston_whoami):
        self.emit("whoami", piston_whoami)

    def whoami(self):
        """ trigger request for the getting account information, this
            will also verify if the current token is valid and if not
            trigger a cleanup/re-authenticate
        """
        LOG.debug("whoami called")
        spawner = SpawnHelper()
        spawner.connect("data-available", self._on_whoami_data)
        spawner.connect("error", lambda spawner, err: self.emit("error", err))
        spawner.needs_auth = True
        spawner.run_generic_piston_helper("UbuntuSsoAPI", "whoami")


class UbuntuSSOAPIFake(UbuntuSSOAPI):

    def __init__(self):
        GObject.GObject.__init__(self)
        self._fake_settings = FakeReviewSettings()

    @network_delay
    def whoami(self):
        if self._fake_settings.get_setting('whoami_response') == "whoami":
            self.emit("whoami", self._create_whoami_response())
        elif self._fake_settings.get_setting('whoami_response') == "error":
            self.emit("error", self._make_error())

    def _create_whoami_response(self):
        username = (self._fake_settings.get_setting('whoami_username') or
            "anyuser")
        response = {
                    u'username': username.decode('utf-8'),
                    u'preferred_email': u'user@email.com',
                    u'displayname': u'Fake User',
                    u'unverified_emails': [],
                    u'verified_emails': [],
                    u'openid_identifier': u'fnerkWt'
                   }
        return response

    def _make_error():
        return 'HTTP Error 401: Unauthorized'


def get_ubuntu_sso_backend():
    """
    factory that returns an ubuntu sso loader singelton
    """
    if "SOFTWARE_CENTER_FAKE_REVIEW_API" in os.environ:
        ubuntu_sso_class = UbuntuSSOAPIFake()
        LOG.warn('Using fake Ubuntu SSO API. Only meant for testing purposes')
    else:
        ubuntu_sso_class = UbuntuSSOAPI()
    return ubuntu_sso_class


# test code
def _login_success(lp, token):
    print "success", lp, token


def _login_failed(lp):
    print "fail", lp


def _login_need_user_and_password(sso):
    import sys
    sys.stdout.write("user: ")
    sys.stdout.flush()
    user = sys.stdin.readline().strip()
    sys.stdout.write("pass: ")
    sys.stdout.flush()
    password = sys.stdin.readline().strip()
    sso.login(user, password)

# interactive test code
if __name__ == "__main__":
    def _whoami(sso, result):
        print "res: ", result
        Gtk.main_quit()

    def _error(sso, result):
        print "err: ", result
        Gtk.main_quit()

    def _dbus_maybe_login_successful(ssologin, oauth_result):
        print "got token, verify it now"
        sso = UbuntuSSOAPI()
        sso.connect("whoami", _whoami)
        sso.connect("error", _error)
        sso.whoami()

    from gi.repository import Gtk
    logging.basicConfig(level=logging.DEBUG)
    softwarecenter.paths.datadir = "./data"

    from login_sso import get_sso_backend
    backend = get_sso_backend("", "appname", "help_text")
    backend.connect("login-successful", _dbus_maybe_login_successful)
    backend.login_or_register()
    Gtk.main()
