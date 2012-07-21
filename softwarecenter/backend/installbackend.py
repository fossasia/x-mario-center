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

from softwarecenter.utils import UnimplementedError


class InstallBackend(object):
    def __init__(self):
        self.pending_transactions = {}
        self.pending_purchases = []

    def upgrade(self, app, iconname, addons_install=[], addons_remove=[],
        metadata=None):
        pass

    def remove(self, app, iconname, addons_install=[], addons_remove=[],
        metadata=None):
        pass

    def remove_multiple(self, apps, iconnames, addons_install=[],
        addons_remove=[], metadatas=None):
        pass

    def install(self, app, iconname, filename=None, addons_install=[],
        addons_remove=[], metadata=None):
        pass

    def install_multiple(self, apps, iconnames, addons_install=[],
        addons_remove=[], metadatas=None):
        pass

    def apply_changes(self, app, iconname, addons_install=[],
        addons_remove=[], metadata=None):
        pass

    def reload(self, sources_list=None, metadata=None):
        """ reload package list """
        pass


class InstallBackendUI(object):

    def ask_config_file_conflict(self, old, new):
        """ show a conffile conflict and ask what to do
            Return "keep" to keep the old one
                   "replace" to replace the old with the new one
        """
        raise UnimplementedError("need custom ask_config_file_conflict method")

    def ask_medium_required(self, medium, drive):
        """ ask the user to provide a medium in drive
            return True if medium is provided, False to cancel
        """
        raise UnimplementedError("need custom ask_medium_required method")

    def error(self, parent, primary, secondary, details=None,
        alternative_action=None):
        """ show an error dialog """
        raise UnimplementedError("need custom error method")


# singleton
install_backend = None


def get_install_backend():
    global install_backend
    if install_backend is None:
        from softwarecenter.enums import USE_PACKAGEKIT_BACKEND
        if not USE_PACKAGEKIT_BACKEND:
            from softwarecenter.backend.installbackend_impl.aptd import (
                AptdaemonBackend)
            install_backend = AptdaemonBackend()
        else:
            from softwarecenter.backend.installbackend_impl.packagekitd \
                import PackagekitBackend
            install_backend = PackagekitBackend()
    return install_backend
