# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#  Andrew Higginson (rugby471)
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

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import WebKit

from gettext import gettext as _

from softwarecenter.ui.gtk3.views.webkit import ScrolledWebkitWindow
from softwarecenter.ui.gtk3.widgets.spinner import SpinnerNotebook
from softwarecenter.enums import SOFTWARE_CENTER_TOS_LINK_NO_HEADER


class DialogTos(Gtk.Dialog):

    def __init__(self, parent):
        Gtk.Dialog.__init__(self)
        self.set_default_size(420, 400)
        self.set_transient_for(parent)
        self.set_title(_("Terms of Use"))
        # buttons
        self.add_button(_("Decline"), Gtk.ResponseType.NO)
        self.add_button(_("Accept"), Gtk.ResponseType.YES)
        # label
        self.label = Gtk.Label(_(u"One moment, please\u2026"))
        self.label.show()
        # add the label
        box = self.get_action_area()
        box.pack_start(self.label, False, False, 0)
        box.set_child_secondary(self.label, True)
        # hrm, hrm, there really should be a better way
        for itm in box.get_children():
            if itm.get_label() == _("Accept"):
                self.button_accept = itm
                break
        self.button_accept.set_sensitive(False)
        # webkit
        wb = ScrolledWebkitWindow()
        wb.show_all()
        self.webkit = wb.webkit
        self.webkit.connect(
            "notify::load-status", self._on_load_status_changed)
        # content
        content = self.get_content_area()
        self.spinner = SpinnerNotebook(wb)
        self.spinner.show_all()
        content.pack_start(self.spinner, True, True, 0)

    def run(self):
        self.spinner.show_spinner()
        self.webkit.load_uri(SOFTWARE_CENTER_TOS_LINK_NO_HEADER)
        return Gtk.Dialog.run(self)

    def _on_load_status_changed(self, view, pspec):
        prop = pspec.name
        status = view.get_property(prop)
        if (status == WebKit.LoadStatus.FINISHED or
            status == WebKit.LoadStatus.FAILED):
            self.spinner.hide_spinner()
        if status == WebKit.LoadStatus.FINISHED:
            self.label.set_text(_("Do you accept these terms?"))
            self.button_accept.set_sensitive(True)

if __name__ == "__main__":
    d = DialogTos(None)
    res = d.run()
    print res
