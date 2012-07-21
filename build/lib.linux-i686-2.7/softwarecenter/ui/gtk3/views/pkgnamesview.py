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

from gi.repository import Gtk, GdkPixbuf
from gi.repository import Pango

import logging
import os

from softwarecenter.db.application import Application
from softwarecenter.enums import Icons

LOG = logging.getLogger(__name__)


class PackageNamesView(Gtk.TreeView):
    """ A simple widget that presents a list of packages, with
        associated icons, in a treeview.  Note the for current
        uses we only show installed packages.  Useful in dialogs.
    """
    (COL_ICON,
     COL_TEXT) = range(2)

    def __init__(self, header, cache, pkgnames, icons, icon_size, db):
        super(PackageNamesView, self).__init__()
        model = Gtk.ListStore(GdkPixbuf.Pixbuf, str)
        self.set_model(model)
        tp = Gtk.CellRendererPixbuf()
        column = Gtk.TreeViewColumn("Icon", tp, pixbuf=self.COL_ICON)
        self.append_column(column)
        tr = Gtk.CellRendererText()
        tr.set_property("ellipsize", Pango.EllipsizeMode.END)
        column = Gtk.TreeViewColumn(header, tr, markup=self.COL_TEXT)
        self.append_column(column)
        for pkgname in sorted(pkgnames):
            if (not pkgname in cache or
                not cache[pkgname].installed):
                continue
            s = "%s \n<small>%s</small>" % (
                cache[pkgname].installed.summary.capitalize(), pkgname)

            app_details = Application("", pkgname).get_details(db)
            proposed_icon = app_details.icon
            if not proposed_icon or not icons.has_icon(proposed_icon):
                proposed_icon = Icons.MISSING_APP
            if icons.has_icon(proposed_icon):
                icon = icons.load_icon(proposed_icon, icon_size, 0)
                pb = icon.scale_simple(
                    icon_size, icon_size, GdkPixbuf.InterpType.BILINEAR)
            else:
                LOG.warn("cant set icon for '%s' " % pkgname)
                pb = icons.load_icon(Icons.MISSING_APP,
                                     icon_size,
                                     Gtk.IconLookupFlags.GENERIC_FALLBACK)
                pb = pb.scale_simple(icon_size,
                                     icon_size, GdkPixbuf.InterpType.BILINEAR)
            model.append([pb, s])

        # finally, we don't allow selection, it's just a simple display list
        tree_selection = self.get_selection()
        tree_selection.set_mode(Gtk.SelectionMode.NONE)


def get_test_window_pkgnamesview():

    from softwarecenter.db.pkginfo import get_pkg_info
    cache = get_pkg_info()
    cache.open()

    from softwarecenter.db.database import StoreDatabase
    xapian_base_path = "/var/cache/software-center"
    pathname = os.path.join(xapian_base_path, "xapian")
    db = StoreDatabase(pathname, cache)
    db.open()

    import softwarecenter.paths
    datadir = softwarecenter.paths.datadir

    from softwarecenter.ui.gtk3.utils import get_sc_icon_theme
    icons = get_sc_icon_theme(datadir)

    pkgs = ["apt", "software-center"]
    view = PackageNamesView("header", cache, pkgs, icons, 32, db)
    view.show()

    win = Gtk.Window()
    win.add(view)
    win.set_size_request(600, 400)
    win.show()
    win.connect('destroy', Gtk.main_quit)
    return win


if __name__ == "__main__":
    import logging
    logging.basicConfig()

    win = get_test_window_pkgnamesview()
    Gtk.main()
