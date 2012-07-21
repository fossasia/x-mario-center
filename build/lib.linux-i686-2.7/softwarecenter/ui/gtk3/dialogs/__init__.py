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

from gettext import gettext as _

import softwarecenter.paths


class SimpleGtkbuilderDialog(object):
    def __init__(self, datadir, domain):
        # setup ui
        self.builder = Gtk.Builder()
        self.builder.set_translation_domain(domain)
        self.builder.add_from_file(datadir + "/ui/gtk3/dialogs.ui")
        self.builder.connect_signals(self)
        for o in self.builder.get_objects():
            if issubclass(type(o), Gtk.Buildable):
                name = Gtk.Buildable.get_name(o)
                setattr(self, name, o)


# for unitesting only
_DIALOG = None


def show_accept_tos_dialog(parent):
    global _DIALOG
    from dialog_tos import DialogTos
    dialog = DialogTos(parent)
    _DIALOG = dialog
    result = dialog.run()
    dialog.destroy()
    if result == Gtk.ResponseType.YES:
        return True
    return False


def confirm_repair_broken_cache(parent, datadir):
    glade_dialog = SimpleGtkbuilderDialog(datadir, domain="software-center")
    dialog = glade_dialog.dialog_broken_cache
    global _DIALOG
    _DIALOG = dialog
    dialog.set_default_size(380, -1)
    dialog.set_transient_for(parent)
    result = dialog.run()
    dialog.destroy()
    if result == Gtk.ResponseType.ACCEPT:
        return True
    return False


class DetailsMessageDialog(Gtk.MessageDialog):
    """Message dialog with optional details expander"""
    def __init__(self,
                 parent=None,
                 title="",
                 primary=None,
                 secondary=None,
                 details=None,
                 buttons=Gtk.ButtonsType.OK,
                 type=Gtk.MessageType.INFO):
        Gtk.MessageDialog.__init__(self, parent, 0, type, buttons, primary)
        self.set_title(title)
        if secondary:
            self.format_secondary_markup(secondary)
        if details:
            textview = Gtk.TextView()
            textview.get_buffer().set_text(details)
            scroll = Gtk.ScrolledWindow()
            scroll.set_size_request(500, 300)
            scroll.set_policy(Gtk.PolicyType.AUTOMATIC,
                Gtk.PolicyType.AUTOMATIC)
            scroll.add(textview)
            expand = Gtk.Expander().new(_("Details"))
            expand.add(scroll)
            expand.show_all()
            self.get_content_area().pack_start(expand, True, True, 0)
        if parent:
            self.set_modal(True)
            self.set_property("skip-taskbar-hint", True)


def messagedialog(parent=None,
                  title="",
                  primary=None,
                  secondary=None,
                  details=None,
                  buttons=Gtk.ButtonsType.OK,
                  type=Gtk.MessageType.INFO,
                  alternative_action=None):
    """ run a dialog """
    dialog = DetailsMessageDialog(parent=parent, title=title,
                                  primary=primary, secondary=secondary,
                                  details=details, type=type,
                                  buttons=buttons)
    global _DIALOG
    _DIALOG = dialog
    if alternative_action:
        dialog.add_button(alternative_action, Gtk.ResponseType.YES)
    result = dialog.run()
    dialog.destroy()
    return result


def error(parent, primary, secondary, details=None, alternative_action=None):
    """ show a untitled error dialog """
    return messagedialog(parent=parent,
                         primary=primary,
                         secondary=secondary,
                         details=details,
                         type=Gtk.MessageType.ERROR,
                         alternative_action=alternative_action)


if __name__ == "__main__":
    softwarecenter.paths.datadir = "./data"

    print("Showing tos dialog")
    res = show_accept_tos_dialog(None)
    print "accepted: ", res

    print("Running broken apt-cache dialog")
    confirm_repair_broken_cache(None, "./data")

    print("Showing message dialog")
    messagedialog(None, primary="first, no second")
    print("showing error")
    error(None, "first", "second")
    error(None, "first", "second", "details ......")
    res = error(None, "first", "second", "details ......",
        alternative_action="Do Something Else")
    print "res: ", res
