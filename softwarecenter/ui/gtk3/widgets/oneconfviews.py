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

from gi.repository import GdkPixbuf, GObject, Gtk
import logging

LOG = logging.getLogger(__name__)


class OneConfViews(Gtk.TreeView):

    __gsignals__ = {
        "computer-changed": (GObject.SIGNAL_RUN_LAST,
                             GObject.TYPE_NONE,
                             (GObject.TYPE_PYOBJECT, GObject.TYPE_PYOBJECT),
                            ),
        "current-inventory-refreshed": (GObject.SIGNAL_RUN_LAST,
                                        GObject.TYPE_NONE,
                                        (),
                                       ),
    }

    (COL_ICON, COL_HOSTID, COL_HOSTNAME) = range(3)

    def __init__(self, icons):
        super(OneConfViews, self).__init__()
        model = Gtk.ListStore(GdkPixbuf.Pixbuf, GObject.TYPE_STRING,
            GObject.TYPE_STRING)
        model.set_sort_column_id(self.COL_HOSTNAME, Gtk.SortType.ASCENDING)
        model.set_sort_func(self.COL_HOSTNAME, self._sort_hosts)
        self.set_model(model)
        self.set_headers_visible(False)
        self.col = Gtk.TreeViewColumn('hostname')

        hosticon_renderer = Gtk.CellRendererPixbuf()
        hostname_renderer = Gtk.CellRendererText()
        self.col.pack_start(hosticon_renderer, False)
        self.col.add_attribute(hosticon_renderer, 'pixbuf', self.COL_ICON)
        self.col.pack_start(hostname_renderer, True)
        self.col.add_attribute(hostname_renderer, 'text', self.COL_HOSTNAME)
        self.append_column(self.col)
        self.current_hostid = None
        self.hostids = []

        # TODO: load the dynamic one (if present), later
        self.default_computer_icon = icons.load_icon("computer", 22, 0)

        self.connect("cursor-changed", self.on_cursor_changed)

    def register_computer(self, hostid, hostname):
        '''Add a new computer to the model'''
        model = self.get_model()
        if not model:
            return
        if hostid in self.hostids:
            return
        hostid = hostid or ''  # bug 905605
        self.hostids.append(hostid)
        LOG.debug("register new computer: %s, %s" % (hostname, hostid))
        model.append([self.default_computer_icon, hostid, hostname])

    def store_packagelist_changed(self, hostid):
        '''Emit a signal for refreshing the installedpane if current view is
        concerned
        '''
        if hostid == self.current_hostid:
            self.emit("current-inventory-refreshed")

    def remove_computer(self, hostid):
        '''Remove a computer from the model'''
        model = self.get_model()
        if not model:
            return
        if hostid not in self.hostids:
            LOG.warning("ask to remove a computer that isn't registered: %s" %
                hostid)
            return
        iter_id = model.get_iter_first()
        while iter_id:
            if model.get_value(iter_id, self.COL_HOSTID) == hostid:
                model.remove(iter_id)
                self.hostids.remove(hostid)
                break
            iter_id = model.iter_next(iter_id)

    def on_cursor_changed(self, widget):

        (path, column) = self.get_cursor()
        if not path:
            return
        model = self.get_model()
        if not model:
            return
        hostid = model[path][self.COL_HOSTID]
        hostname = model[path][self.COL_HOSTNAME]
        if hostid != self.current_hostid:
            self.current_hostid = hostid
            self.emit("computer-changed", hostid, hostname)

    def select_first(self):
        '''Select first item'''
        self.set_cursor(Gtk.TreePath.new_first(), None, False)

    def _sort_hosts(self, model, iter1, iter2, user_data):
        '''Sort hosts, with "this computer" (NONE HOSTID) as first'''
        if not self.get_model().get_value(iter1, self.COL_HOSTID):
            return -1
        if not self.get_model().get_value(iter2, self.COL_HOSTID):
            return 1
        if (self.get_model().get_value(iter1, self.COL_HOSTNAME) >
            self.get_model().get_value(iter2, self.COL_HOSTNAME)):
            return 1
        else:
            return -1


def get_test_window():

    w = OneConfViews(Gtk.IconTheme.get_default())
    w.show()

    win = Gtk.Window()
    win.set_data("pane", w)
    win.add(w)
    win.set_size_request(400, 600)
    win.connect("destroy", lambda x: Gtk.main_quit())

    # init the view
    w.register_computer("AAAAA", "NameA")
    w.register_computer("ZZZZZ", "NameZ")
    w.register_computer("DDDDD", "NameD")
    w.register_computer("CCCCC", "NameC")
    w.register_computer("", "This computer should be first")
    w.select_first()

    GObject.timeout_add_seconds(5, w.register_computer, "EEEEE", "NameE")

    def print_selected_hostid(widget, hostid, hostname):
        print "%s selected for %s" % (hostid, hostname)

    w.connect("computer-changed", print_selected_hostid)

    w.remove_computer("DDDDD")
    win.show_all()
    return win


if __name__ == "__main__":
    win = get_test_window()
    Gtk.main()
