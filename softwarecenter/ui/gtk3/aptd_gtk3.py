# Copyright (C) 2011 Canonical
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

from gi.repository import Gtk

from aptdaemon.gtk3widgets import (AptMediumRequiredDialog,
                                   AptConfigFileConflictDialog)

from softwarecenter.backend.installbackend import InstallBackendUI


class InstallBackendUI(InstallBackendUI):

    def ask_config_file_conflict(self, old, new):
        dia = AptConfigFileConflictDialog(old, new)
        res = dia.run()
        dia.hide()
        dia.destroy()
        # send result to the daemon
        if res == Gtk.ResponseType.YES:
            return "replace"
        else:
            return "keep"

    def ask_medium_required(self, medium, drive):
        dialog = AptMediumRequiredDialog(medium, drive)
        res = dialog.run()
        dialog.hide()
        if res == Gtk.ResponseType.YES:
            return True
        else:
            return False

    def error(self, parent, primary, secondary, details=None,
        alternative_action=None):
        from dialogs import error
        res = "ok"
        res = error(parent=parent,
                    primary=primary,
                    secondary=secondary,
                    details=details,
                    alternative_action=alternative_action)
        if res == Gtk.ResponseType.YES:
            res = "yes"
        return res

if __name__ == "__main__":
    from softwarecenter.backend import get_install_backend
    from softwarecenter.ui.gtk3.aptd_gtk3 import InstallBackendUI
    from mock import Mock

    aptd = get_install_backend()
    aptd.ui = InstallBackendUI()
    # test config file prompt
    trans = Mock()
    res = aptd._config_file_conflict(trans, "/etc/group", "/etc/group-")
    print (res)

    # test medium required
    trans = Mock()
    res = aptd._medium_required(trans, "medium", "drive")
    print (res)

    # test error dialog
    trans = Mock()
    trans.error_code = 102
    trans.error_details = "details"
    enum = 101
    res = aptd._show_transaction_failed_dialog(trans, enum)
    print (res)
