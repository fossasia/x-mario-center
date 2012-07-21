# coding: utf-8
#
# SearchEntry - An enhanced search entry with timeout
#
# Copyright (C) 2007 Sebastian Heinlein
#               2007-2009 Canonical Ltd.
#
# Authors:
#  Sebastian Heinlein <glatzor@ubuntu.com>
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

from gi.repository import Gtk, GObject
from gettext import gettext as _

from softwarecenter.ui.gtk3.em import em


class SearchEntry(Gtk.Entry):

    # FIMXE: we need "can-undo", "can-redo" signals
    __gsignals__ = {'terms-changed': (GObject.SignalFlags.RUN_FIRST,
                                      None,
                                      (GObject.TYPE_STRING,))}

    SEARCH_TIMEOUT = 600

    def __init__(self, icon_theme=None):
        """
        Creates an enhanced IconEntry that triggers a timeout when typing
        """
        Gtk.Entry.__init__(self)
        self.set_width_chars(25)
        self.set_size_request(0, em(1.7))

        if not icon_theme:
            icon_theme = Gtk.IconTheme.get_default()

        self._handler_changed = self.connect_after("changed",
                                                   self._on_changed)

        self.connect("icon-press", self._on_icon_pressed)

        self.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY,
            'edit-find-symbolic')
        self.set_icon_from_stock(Gtk.EntryIconPosition.SECONDARY, None)

        # set sensible atk name
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Search"))

        # data
        self._timeout_id = 0
        self._undo_stack = [""]
        self._redo_stack = []

    def _on_icon_pressed(self, widget, icon, mouse_button):
        """
        Emit the terms-changed signal without any time out when the clear
        button was clicked
        """
        if icon == Gtk.EntryIconPosition.SECONDARY:
            # clear with no signal and emit manually to avoid the
            # search-timeout
            self.clear_with_no_signal()
            self.grab_focus()
            self.emit("terms-changed", "")

        elif icon == Gtk.EntryIconPosition.PRIMARY:
            self.select_region(0, -1)
            self.grab_focus()

    def undo(self):
        if len(self._undo_stack) <= 1:
            return
        # pop top element and push on redo stack
        text = self._undo_stack.pop()
        self._redo_stack.append(text)
        # the next element is the one we want to display
        text = self._undo_stack.pop()
        self.set_text(text)
        self.set_position(-1)

    def redo(self):
        if not self._redo_stack:
            return
        # just reply the redo stack
        text = self._redo_stack.pop()
        self.set_text(text)
        self.set_position(-1)

    def clear(self):
        self.set_text("")
        self._check_style()

    def set_text(self, text, cursor_to_end=True):
        Gtk.Entry.set_text(self, text)
        self.emit("move-cursor", Gtk.MovementStep.BUFFER_ENDS, 1, False)

    def set_text_with_no_signal(self, text):
        """Clear and do not send a term-changed signal"""
        self.handler_block(self._handler_changed)
        self.set_text(text)
        self.emit("move-cursor", Gtk.MovementStep.BUFFER_ENDS, 1, False)
        self.handler_unblock(self._handler_changed)

    def clear_with_no_signal(self):
        """Clear and do not send a term-changed signal"""
        self.handler_block(self._handler_changed)
        self.clear()
        self.handler_unblock(self._handler_changed)

    def _emit_terms_changed(self):
        text = self.get_text()
        # add to the undo stack once a term changes
        self._undo_stack.append(text)
        self.emit("terms-changed", text)

    def _on_changed(self, widget):
        """
        Call the actual search method after a small timeout to allow the user
        to enter a longer search term
        """
        self._check_style()
        if self._timeout_id > 0:
            GObject.source_remove(self._timeout_id)
        self._timeout_id = GObject.timeout_add(self.SEARCH_TIMEOUT,
                                               self._emit_terms_changed)

    def _check_style(self):
        """
        Show the clear icon whenever the field is not empty
        """
        if self.get_text() != "":
            self.set_icon_from_stock(Gtk.EntryIconPosition.SECONDARY,
                Gtk.STOCK_CLEAR)
            # reverse the icon if we are in an rtl environment
            if self.get_direction() == Gtk.TextDirection.RTL:
                pb = self.get_icon_pixbuf(
                    Gtk.EntryIconPosition.SECONDARY).flip(True)
                self.set_icon_from_pixbuf(Gtk.EntryIconPosition.SECONDARY, pb)
        else:
            self.set_icon_from_stock(Gtk.EntryIconPosition.SECONDARY, None)


def on_entry_changed(self, terms):
    print(terms)


def get_test_searchentry_window():
    icons = Gtk.IconTheme.get_default()
    entry = SearchEntry(icons)
    entry.connect("terms-changed", on_entry_changed)

    win = Gtk.Window()
    win.connect("destroy", Gtk.main_quit)
    win.add(entry)
    win.set_size_request(400, 400)
    win.show_all()
    win.entry = entry
    return win

if __name__ == "__main__":
    win = get_test_searchentry_window()
    Gtk.main()
