# Copyright (C) 2010 Canonical
#
# Authors:
#  Gary Lasker
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

from gi.repository import Gtk, GObject

from softwarecenter.enums import SOFTWARE_CENTER_DEBUG_TABS


class SpinnerView(Gtk.Viewport):
    """A panel that contains a spinner with an optional legend.

    The spinner is preset to a standard size and centered. An optional
    label_text value can be specified for display with the spinner.

    """

    def __init__(self, label_text=""):
        Gtk.Viewport.__init__(self)
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(48, 48)

        # use a table for the spinner (otherwise the spinner is massive!)
        spinner_table = Gtk.Table(3, 3, False)
        self.spinner_label = Gtk.Label()
        self.spinner_label.set_markup('<big>%s</big>' % label_text)
        spinner_vbox = Gtk.VBox()
        spinner_vbox.pack_start(self.spinner, True, True, 0)
        spinner_vbox.pack_start(self.spinner_label, True, True, 10)
        spinner_table.attach(spinner_vbox, 1, 2, 1, 2,
            Gtk.AttachOptions.EXPAND, Gtk.AttachOptions.EXPAND)

        #~ self.modify_bg(Gtk.StateType.NORMAL, Gdk.Color(1.0, 1.0, 1.0))
        self.add(spinner_table)
        self.set_shadow_type(Gtk.ShadowType.NONE)

    def start_and_show(self):
        """Start the spinner and show it."""
        self.spinner.start()
        self.spinner.show()

    def stop_and_hide(self):
        """Stop the spinner and hide it."""
        self.spinner.stop()
        self.spinner.hide()

    def set_text(self, spinner_text=""):
        """Add/remove/change this spinner's label text."""
        self.spinner_label.set_markup('<big>%s</big>' % spinner_text)

    def get_text(self):
        """Return the spinner's currently set label text."""
        return self.spinner_label.get_text()


class SpinnerNotebook(Gtk.Notebook):
    """ this provides a Gtk.Notebook that contains a content page
        and a spinner page.
    """
    (CONTENT_PAGE,
     SPINNER_PAGE) = range(2)

    def __init__(self, content, msg=""):
        Gtk.Notebook.__init__(self)
        self._last_timeout_id = None
        self.spinner_view = SpinnerView(msg)
        # its critical to show() the spinner early as otherwise
        # gtk_notebook_set_active_page() will not switch to it
        self.spinner_view.show()
        if not SOFTWARE_CENTER_DEBUG_TABS:
            self.set_show_tabs(False)
        self.set_show_border(False)
        self.append_page(content, Gtk.Label("content"))
        self.append_page(self.spinner_view, Gtk.Label("spinner"))

    def _unmask_view_spinner(self):
        # start is actually start_and_show()
        self.spinner_view.start_and_show()
        self.set_current_page(self.SPINNER_PAGE)
        self._last_timeout_id = None
        return False

    def show_spinner(self, msg=""):
        """ show the spinner page with a alternative message """
        if msg:
            self.spinner_view.set_text(msg)
        # "mask" the spinner view momentarily to prevent it from flashing into
        # view in the case of short delays where it isn't actually needed
        self.spinner_view.stop_and_hide()
        self._last_timeout_id = GObject.timeout_add(250,
                                                    self._unmask_view_spinner)

    def hide_spinner(self):
        """ hide the spinner page again and show the content page """
        if self._last_timeout_id is not None:
            GObject.source_remove(self._last_timeout_id)
            self._last_timeout_id = None
        self.spinner_view.stop_and_hide()
        self.set_current_page(self.CONTENT_PAGE)


def get_test_spinner_window():
    label = Gtk.Label("foo")
    spinner_notebook = SpinnerNotebook(label, "random msg")

    window = Gtk.Window()
    window.add(spinner_notebook)
    window.set_size_request(600, 500)
    window.set_position(Gtk.WindowPosition.CENTER)
    window.show_all()
    window.connect('destroy', Gtk.main_quit)
    spinner_notebook.show_spinner("Loading for 1s ...")
    GObject.timeout_add_seconds(1, lambda: spinner_notebook.hide_spinner())
    return window

if __name__ == "__main__":
    win = get_test_spinner_window()
    Gtk.main()
