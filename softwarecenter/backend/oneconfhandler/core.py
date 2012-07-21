# -*- coding: utf-8 -*-
# Copyright (C) 2011 Canonical
#
# Authors:
#  Didier Roche
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

from oneconf.dbusconnect import DbusConnect
from oneconf.enums import MIN_TIME_WITHOUT_ACTIVITY

from softwarecenter.backend.login_sso import get_sso_backend
from softwarecenter.backend.ubuntusso import get_ubuntu_sso_backend
from softwarecenter.enums import SOFTWARE_CENTER_NAME_KEYRING

import datetime
from gi.repository import GObject
import logging

from gettext import gettext as _

LOG = logging.getLogger(__name__)


class OneConfHandler(GObject.GObject):

    __gsignals__ = {
        "show-oneconf-changed": (GObject.SIGNAL_RUN_LAST,
                                 GObject.TYPE_NONE,
                                 (GObject.TYPE_PYOBJECT,),
                                ),
        "last-time-sync-changed": (GObject.SIGNAL_RUN_LAST,
                                   GObject.TYPE_NONE,
                                   (GObject.TYPE_PYOBJECT,),
                                  ),
        }

    def __init__(self, oneconfviewpickler):
        '''Controller of the installed pane'''

        LOG.debug("OneConf Handler init")
        super(OneConfHandler, self).__init__()

        # OneConf stuff
        self.oneconf = DbusConnect()
        self.oneconf.hosts_dbus_object.connect_to_signal('hostlist_changed',
            self.refresh_hosts)
        self.oneconf.hosts_dbus_object.connect_to_signal('packagelist_changed',
            self._on_store_packagelist_changed)
        self.oneconf.hosts_dbus_object.connect_to_signal('latestsync_changed',
            self.on_new_latest_oneconf_sync_timestamp)
        self.already_registered_hostids = []
        self.is_current_registered = False

        self.oneconfviewpickler = oneconfviewpickler

        # refresh host list
        self._refreshing_hosts = False
        GObject.timeout_add_seconds(MIN_TIME_WITHOUT_ACTIVITY,
            self.get_latest_oneconf_sync)
        GObject.idle_add(self.refresh_hosts)

    def refresh_hosts(self):
        """refresh hosts list in the panel view"""
        LOG.debug('oneconf: refresh hosts')

        # this function can be called in different threads
        if self._refreshing_hosts:
            return
        self._refreshing_hosts = True

        #view_switcher = self.app.view_switcher
        #model = view_switcher.get_model()
        #previous_iter = model.installed_iter

        all_hosts = self.oneconf.get_all_hosts()
        for hostid in all_hosts:
            current, hostname, share_inventory = all_hosts[hostid]
            if not hostid in self.already_registered_hostids and not current:
                self.oneconfviewpickler.register_computer(hostid, hostname)
                self.already_registered_hostids.append(hostid)
            if current:
                is_current_registered = share_inventory

        # ensure we are logged to ubuntu sso to activate the view
        if self.is_current_registered != is_current_registered:
            self.sync_between_computers(is_current_registered)

        self._refreshing_hosts = False

    def get_latest_oneconf_sync(self):
        '''Get latest sync state in OneConf.

        This function is also the "ping" letting OneConf service alive'''
        LOG.debug("get latest sync state")
        timestamp = self.oneconf.get_last_sync_date()
        self.on_new_latest_oneconf_sync_timestamp(timestamp)
        return True

    def on_new_latest_oneconf_sync_timestamp(self, timestamp):
        '''Callback computing the right message for latest sync time'''
        try:
            last_sync = datetime.datetime.fromtimestamp(float(timestamp))
            today = datetime.datetime.strptime(str(datetime.date.today()),
                '%Y-%m-%d')
            the_daybefore = today - datetime.timedelta(days=1)

            if last_sync > today:
                msg = _("Last sync %s") % last_sync.strftime('%H:%M')
            elif last_sync < today and last_sync > the_daybefore:
                msg = _("Last sync yesterday %s") % last_sync.strftime('%H:%M')
            else:
                msg = _("Last sync %s") % last_sync.strftime('%Y-%m-%d  %H:%M')
        except (TypeError, ValueError):
            msg = _("To sync with another computer, choose “Sync Between "
                "Computers” from that computer.")
        self.emit("last-time-sync-changed", msg)

    def _share_inventory(self, share_inventory):
        '''set oneconf state and emit signal for installed view to show or
           not oneconf
        '''

        if share_inventory == self.is_current_registered:
            return
        self.is_current_registered = share_inventory
        LOG.debug("change share inventory state to %s", share_inventory)
        self.oneconf.set_share_inventory(share_inventory)
        self.get_latest_oneconf_sync()
        self.emit("show-oneconf-changed", share_inventory)

    def sync_between_computers(self, sync_on, hostid=None):
        '''toggle the sync on and off if needed between computers.

        If hostid is not None, sync_between_computer can be used to stop
        sharing for other computers'''
        LOG.debug("Toggle sync between computers: %s", sync_on)

        if sync_on:
            self._try_login()
        else:
            if hostid:
                self.oneconf.set_share_inventory(False, hostid=hostid)
            else:  # localhost
                self._share_inventory(False)

    def _on_store_packagelist_changed(self, hostid):
        '''pass the message to the view controller'''
        self.oneconfviewpickler.store_packagelist_changed(hostid)

    # SSO login part
    def _try_login(self):
        '''Try to get the credential or login on ubuntu sso'''
        logging.debug("OneConf login()")
        help_text = _("With multiple Ubuntu computers, you can publish "
                      "their inventories online to compare the software "
                      "installed on each\nNo-one else will be able to see "
                      "what you have installed.")
        self.sso = get_sso_backend(
            0, SOFTWARE_CENTER_NAME_KEYRING, help_text)
        self.sso.connect("login-successful", self._maybe_login_successful)
        self.sso.connect("login-canceled", self._login_canceled)
        self.sso.login_or_register()

    def _login_canceled(self, sso):
        self._share_inventory(False)

    def _maybe_login_successful(self, sso, oauth_result):
        """called after we have the token, then we go and figure out our
           name
        """
        logging.debug("_maybe_login_successful")
        self.ssoapi = get_ubuntu_sso_backend()
        self.ssoapi.connect("whoami", self._whoami_done)
        self.ssoapi.connect("error", self._whoami_error)
        # this will automatically verify the keyring token and retrigger
        # login (once) if its expired
        self.ssoapi.whoami()

    def _whoami_done(self, ssologin, result):
        logging.debug("_whoami_done")
        self._share_inventory(True)

    def _whoami_error(self, ssologin, e):
        logging.error("whoami error '%s'" % e)
        self._share_inventory(False)
