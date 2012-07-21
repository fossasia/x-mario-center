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

import logging
from gettext import gettext as _
from gi.repository import Gtk

from basepane import BasePane
from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.ui.gtk3.panes.softwarepane import DisplayState
from softwarecenter.ui.gtk3.models.pendingstore import PendingStore
from softwarecenter.ui.gtk3.session.viewmanager import get_viewmanager

LOG = logging.getLogger(__name__)


class PendingPane(Gtk.ScrolledWindow, BasePane):

    CANCEL_XPAD = StockEms.MEDIUM
    CANCEL_YPAD = StockEms.MEDIUM

    def __init__(self, icons):
        Gtk.ScrolledWindow.__init__(self)
        BasePane.__init__(self)
        self.state = DisplayState()
        self.pane_name = _("Progress")

        self.tv = Gtk.TreeView()
        # customization
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.add(self.tv)
        self.tv.set_headers_visible(False)
        self.tv.connect("button-press-event", self._on_button_pressed)
        # icon
        self.icons = icons
        tp = Gtk.CellRendererPixbuf()
        tp.set_property("xpad", self.CANCEL_XPAD)
        tp.set_property("ypad", self.CANCEL_YPAD)
        column = Gtk.TreeViewColumn("Icon", tp, pixbuf=PendingStore.COL_ICON)
        self.tv.append_column(column)
        # name
        tr = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Name", tr, markup=PendingStore.COL_STATUS)
        column.set_min_width(200)
        column.set_expand(True)
        self.tv.append_column(column)
        # progress
        tp = Gtk.CellRendererProgress()
        tp.set_property("xpad", self.CANCEL_XPAD)
        tp.set_property("ypad", self.CANCEL_YPAD)
        tp.set_property("text", "")
        column = Gtk.TreeViewColumn("Progress", tp,
                                    value=PendingStore.COL_PROGRESS,
                                    pulse=PendingStore.COL_PULSE)
        column.set_min_width(200)
        self.tv.append_column(column)
        # cancel icon
        tpix = Gtk.CellRendererPixbuf()
        column = Gtk.TreeViewColumn("Cancel", tpix,
                                    stock_id=PendingStore.COL_CANCEL)
        self.tv.append_column(column)
        # fake columns that eats the extra space at the end
        tt = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Cancel", tt)
        self.tv.append_column(column)
        # add it
        store = PendingStore(icons)
        self.tv.set_model(store)

    def _on_button_pressed(self, widget, event):
        """button press handler to capture clicks on the cancel button"""
        #print "_on_clicked: ", event
        if event == None or event.button != 1:
            return
        res = self.tv.get_path_at_pos(int(event.x), int(event.y))
        if not res:
            return
        (path, column, wx, wy) = res
        # no path
        if not path:
            return
        # wrong column
        if column.get_title() != "Cancel":
            return
        # not cancelable (no icon)
        model = self.tv.get_model()
        if model[path][PendingStore.COL_CANCEL] == "":
            return
        # get tid
        tid = model[path][PendingStore.COL_TID]
        trans = model._transactions_watcher.get_transaction(tid)
        try:
            trans.cancel()
        except Exception as e:
            LOG.warning("transaction cancel failed: %s" % e)

    # subscribe to the back-forward navigation ...
    def on_nav_back_clicked(self, widget):
        vm = get_viewmanager()
        vm.nav_back()

    def on_nav_forward_clicked(self, widget):
        vm = get_viewmanager()
        vm.nav_forward()

    # boring stuff
    def get_current_page(self):
        return None

    def get_callback_for_page(self, page_id, view_state):
        return None


def get_test_window():

    from softwarecenter.testutils import get_test_gtk3_icon_cache
    icons = get_test_gtk3_icon_cache()

    view = PendingPane(icons)

    # gui
    scroll = Gtk.ScrolledWindow()
    scroll.add_with_viewport(view)

    win = Gtk.Window()
    win.add(scroll)
    view.grab_focus()
    win.set_size_request(500, 200)
    win.show_all()
    win.connect("destroy", Gtk.main_quit)

    return win

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    win = get_test_window()
    Gtk.main()
