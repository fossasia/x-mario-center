#
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

import os

# this is a bit silly, but *something* imports gtk2 symbols, so if we
# force gtk3 here it crashes - the only reason we need this at all is to
# get the icon path
import gi
gi.require_version("Gtk", "2.0")
from gi.repository import Gtk

from PyQt4.QtCore import QAbstractListModel, QModelIndex
#from PyQt4.QtGui import QIcon

from softwarecenter.db.categories import CategoriesParser
from softwarecenter.db.database import StoreDatabase
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.paths import XAPIAN_BASE_PATH
import softwarecenter.paths


class CategoriesModel(QAbstractListModel):

    # should match the softwarecenter.backend.reviews.Review attributes
    COLUMNS = ('_name',
               '_iconname',
               )

    def __init__(self, parent=None):
        super(CategoriesModel, self).__init__()
        self._categories = []
        roles = dict(enumerate(CategoriesModel.COLUMNS))
        self.setRoleNames(roles)
        pathname = os.path.join(XAPIAN_BASE_PATH, "xapian")
        # FIXME: move this into app
        cache = get_pkg_info()
        db = StoreDatabase(pathname, cache)
        db.open()
        # /FIXME
        self.catparser = CategoriesParser(db)
        self._categories = self.catparser.parse_applications_menu(
            softwarecenter.paths.APP_INSTALL_PATH)

    # QAbstractListModel code
    def rowCount(self, parent=QModelIndex()):
        return len(self._categories)

    def data(self, index, role):
        if not index.isValid():
            return None
        cat = self._categories[index.row()]
        role = self.COLUMNS[role]
        if role == "_name":
            return unicode(cat.name, "utf8", "ignore")
        elif role == "_iconname":
            # funny, but it appears like Qt does not have something
            # to lookup the icon path in QIcon
            icons = Gtk.IconTheme.get_default()
            info = icons.lookup_icon(cat.iconname, 48, 0)
            if info:
                return info.get_filename()
            return ""

if __name__ == "__main__":
    from PyQt4.QtGui import QApplication
    from PyQt4.QtDeclarative import QDeclarativeView
    import sys

    app = QApplication(sys.argv)
    app.cache = get_pkg_info()
    app.cache.open()
    view = QDeclarativeView()
    categoriesmodel = CategoriesModel()
    rc = view.rootContext()
    rc.setContextProperty('categoriesmodel', categoriesmodel)

    # load the main QML file into the view
    qmlpath = os.path.join(os.path.dirname(__file__), "CategoriesView.qml")
    view.setSource(qmlpath)

    # show it
    view.show()
    sys.exit(app.exec_())
