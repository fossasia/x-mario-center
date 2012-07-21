# Copyright (C) 2011 Canonical
#
# Authors:
#  Matthew McGowan
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

import json

try:
    from urllib.parse import urlencode
    urlencode  # pyflakes
except ImportError:
    from urllib import urlencode

from gi.repository import GObject

from softwarecenter.enums import AppActions
from softwarecenter.db import DebFileApplication
from softwarecenter.distro import get_current_arch, get_distro
from softwarecenter.i18n import get_language
from softwarecenter.ui.gtk3.dialogs import dependency_dialogs
from softwarecenter.backend.transactionswatcher import (
    TransactionFinishedResult,
)
import softwarecenter.paths

_appmanager = None  # the global AppManager instance


def get_appmanager():
    """ get a existing appmanager instance (or None if none is created yet) """
    return _appmanager


class ApplicationManager(GObject.GObject):

    __gsignals__ = {
         "purchase-requested": (GObject.SignalFlags.RUN_LAST,
                                None,
                                (GObject.TYPE_PYOBJECT, str, str,)
                               ),
    }

    def __init__(self, db, backend, icons):
        GObject.GObject.__init__(self)
        self._globalise_instance()
        self.db = db
        self.backend = backend
        self.distro = get_distro()
        self.datadir = softwarecenter.paths.datadir
        self.icons = icons
        self.oauth_token = ""

    def _globalise_instance(self):
        global _appmanager
        if _appmanager is not None:
            msg = "Only one instance of ApplicationManager is allowed!"
            raise ValueError(msg)
        else:
            _appmanager = self

    def destroy(self):
        """Destroy the global instance."""
        global _appmanager
        _appmanager = None

    def request_action(self, app, addons_install, addons_remove, action):
        """callback when an app action is requested from the appview,
           if action is "remove", must check if other dependencies have to be
           removed as well and show a dialog in that case
        """
        #~ LOG.debug("on_application_action_requested: '%s' %s"
            #~ % (app, action))
        appdetails = app.get_details(self.db)
        if action == AppActions.REMOVE:
            if not dependency_dialogs.confirm_remove(
                        None, self.datadir, app, self.db, self.icons):
                    # craft an instance of TransactionFinishedResult to send
                    # with the transaction-stopped signal
                    result = TransactionFinishedResult(None, False)
                    result.pkgname = app.pkgname
                    self.backend.emit("transaction-stopped", result)
                    return
        elif action == AppActions.INSTALL:
            # If we are installing a package, check for dependencies that will
            # also be removed and show a dialog for confirmation
            # generic removal text (fixing LP bug #554319)
            if not dependency_dialogs.confirm_install(
                        None, self.datadir, app, self.db, self.icons):
                    # craft an instance of TransactionFinishedResult to send
                    # with the transaction-stopped signal
                    result = TransactionFinishedResult(None, False)
                    result.pkgname = app.pkgname
                    self.backend.emit("transaction-stopped", result)
                    return

        # this allows us to 'upgrade' deb files
        if (action == AppActions.UPGRADE and app.request and
            isinstance(app, DebFileApplication)):
            action = AppActions.INSTALL

        # action_func is one of:
        #     "install", "remove", "upgrade", "apply_changes"
        action_func = getattr(self.backend, action)
        if action == AppActions.INSTALL:
            # the package.deb path name is in the request
            if app.request and isinstance(app, DebFileApplication):
                debfile_name = app.request
            else:
                debfile_name = None

            action_func(app, appdetails.icon,
                        debfile_name, addons_install, addons_remove)
        elif callable(action_func):
            action_func(app, appdetails.icon,
                        addons_install=addons_install,
                        addons_remove=addons_remove)
        #~ else:
            #~ LOG.error("Not a valid action in AptdaemonBackend: '%s'" %
                #~ action)

    # public interface
    def reload(self):
        """ reload the package cache, this goes straight to the backend """
        self.backend.reload()

    def install(self, app, addons_to_install, addons_to_remove):
        """ install the current application, fire an action request """
        self.request_action(
            app, addons_to_install, addons_to_remove, AppActions.INSTALL)

    def remove(self, app, addons_to_install, addons_to_remove):
        """ remove the current application, , fire an action request """
        self.request_action(
            app, addons_to_install, addons_to_remove, AppActions.REMOVE)

    def upgrade(self, app, addons_to_install, addons_to_remove):
        """ upgrade the current application, fire an action request """
        self.request_action(
            app, addons_to_install, addons_to_remove, AppActions.UPGRADE)

    def apply_changes(self, app, addons_to_install, addons_to_remove):
        """ apply changes concerning add-ons """
        self.request_action(
            app, addons_to_install, addons_to_remove, AppActions.APPLY)

    def buy_app(self, app):
        """ initiate the purchase transaction """
        lang = get_language()
        appdetails = app.get_details(self.db)
        url = self.distro.PURCHASE_APP_URL % (
            lang, self.distro.get_codename(), urlencode({
                'archive_id': appdetails.ppaname,
                'arch': get_current_arch()
            })
        )
        self.emit("purchase-requested", app, appdetails.icon, url)

    def reinstall_purchased(self, app):
        """ reinstall a purchased app """
        #~ LOG.debug("reinstall_purchased %s" % self.app)
        appdetails = app.get_details(self.db)
        iconname = appdetails.icon
        deb_line = appdetails.deb_line
        license_key = appdetails.license_key
        license_key_path = appdetails.license_key_path
        signing_key_id = appdetails.signing_key_id
        oauth_token = json.dumps(self.oauth_token)
        self.backend.add_repo_add_key_and_install_app(deb_line,
                                                      signing_key_id,
                                                      app,
                                                      iconname,
                                                      license_key,
                                                      license_key_path,
                                                      oauth_token)

    def enable_software_source(self, app):
        """ enable the software source for the given app """
        appdetails = app.get_details(self.db)
        if appdetails.channelfile and appdetails._unavailable_channel():
            self.backend.enable_channel(appdetails.channelfile)
        elif appdetails.component:
            components = appdetails.component.split('&')
            for component in components:
                self.backend.enable_component(component)
