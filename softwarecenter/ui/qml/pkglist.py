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

from PyQt4 import QtCore
from PyQt4.QtCore import QAbstractListModel, QModelIndex, pyqtSlot

from softwarecenter.db.database import StoreDatabase, Application
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.db.categories import CategoriesParser
from softwarecenter.paths import XAPIAN_BASE_PATH
from softwarecenter.backend import get_install_backend
from softwarecenter.backend.reviews import get_review_loader


class PkgListModel(QAbstractListModel):

    COLUMNS = ('_appname',
               '_pkgname',
               '_icon',
               '_summary',
               '_installed',
               '_description',
               '_ratings_total',
               '_ratings_average',
               '_installremoveprogress')

    def __init__(self, parent=None):
        super(PkgListModel, self).__init__()
        self._docs = []
        roles = dict(enumerate(PkgListModel.COLUMNS))
        self.setRoleNames(roles)
        self._query = ""
        self._category = ""
        pathname = os.path.join(XAPIAN_BASE_PATH, "xapian")
        self.cache = get_pkg_info()
        self.db = StoreDatabase(pathname, self.cache)
        self.db.open(use_axi=False)
        self.backend = get_install_backend()
        self.backend.connect("transaction-progress-changed",
                             self._on_backend_transaction_progress_changed)
        self.reviews = get_review_loader(self.cache)
        # FIXME: get this from a parent
        self._catparser = CategoriesParser(self.db)
        self._categories = self._catparser.parse_applications_menu(
            '/usr/share/app-install')

    # QAbstractListModel code
    def rowCount(self, parent=QModelIndex()):
        return len(self._docs)

    def data(self, index, role):
        if not index.isValid():
            return None
        doc = self._docs[index.row()]
        role = self.COLUMNS[role]
        pkgname = unicode(self.db.get_pkgname(doc), "utf8", "ignore")
        appname = unicode(self.db.get_appname(doc), "utf8", "ignore")
        if role == "_pkgname":
            return pkgname
        elif role == "_appname":
            return appname
        elif role == "_summary":
            return unicode(self.db.get_summary(doc))
        elif role == "_installed":
            if not pkgname in self.cache:
                return False
            return self.cache[pkgname].is_installed
        elif role == "_description":
            if not pkgname in self.cache:
                return ""
            return self.cache[pkgname].description
        elif role == "_icon":
            iconname = self.db.get_iconname(doc)
            return self._findIcon(iconname)
        elif role == "_ratings_average":
            stats = self.reviews.get_review_stats(Application(appname,
                pkgname))
            if stats:
                return stats.ratings_average
            return 0
        elif role == "_ratings_total":
            stats = self.reviews.get_review_stats(Application(appname,
                pkgname))
            if stats:
                return stats.ratings_total
            return 0
        elif role == "_installremoveprogress":
            if pkgname in self.backend.pending_transactions:
                return self.backend.pending_transactions[pkgname].progress
            return -1
        return None

    # helper
    def _on_backend_transaction_progress_changed(self, backend, pkgname,
        progress):
        column = self.COLUMNS.index("_installremoveprogress")
        # FIXME: instead of the entire model, just find the row that changed
        top = self.createIndex(0, column)
        bottom = self.createIndex(self.rowCount() - 1, column)
        self.dataChanged.emit(top, bottom)

    def _findIcon(self, iconname):
        path = "/usr/share/icons/Humanity/categories/32/applications-other.svg"
        for ext in ["svg", "png", ".xpm"]:
            p = "/usr/share/app-install/icons/%s" % iconname
            if os.path.exists(p + ext):
                path = "file://%s" % p + ext
                break
        return path

    def clear(self):
        if self._docs == []:
            return
        self.beginRemoveRows(QModelIndex(), 0, self.rowCount() - 1)
        self._docs = []
        self.endRemoveRows()

    def _runQuery(self, querystr):
        self.clear()
        docs = self.db.get_docs_from_query(
            str(querystr), start=0, end=500, category=self._category)
        self.beginInsertRows(QModelIndex(), 0, len(docs) - 1)
        self._docs = docs
        self.endInsertRows()

    # install/remove interface (for qml)
    @pyqtSlot(str)
    def installPackage(self, pkgname):
        appname = ""
        iconname = ""
        app = Application(appname, pkgname)
        self.backend.install(app, iconname)

    @pyqtSlot(str)
    def removePackage(self, pkgname):
        appname = ""
        iconname = ""
        app = Application(appname, pkgname)
        self.backend.remove(app, iconname)

    # searchQuery property (for qml )
    def getSearchQuery(self):
        return self._query

    def setSearchQuery(self, query):
        self._query = query
        self._runQuery(query)
    searchQueryChanged = QtCore.pyqtSignal()
    searchQuery = QtCore.pyqtProperty(unicode, getSearchQuery, setSearchQuery,
        notify=searchQueryChanged)

    # allow to refine searches for specific categories
    @pyqtSlot(str)
    def setCategory(self, catname):
        # empty category resets it
        if not catname:
            self._category = None
        else:
            # search for the category
            for cat in self._categories:
                if cat.name == catname:
                    self._category = cat
                    break
            else:
                raise Exception("Can not find category '%s'" % catname)
        # and trigger a query
        self._runQuery(self._query)

if __name__ == "__main__":
    from PyQt4.QtGui import QApplication
    from PyQt4.QtDeclarative import QDeclarativeView
    import sys

    app = QApplication(sys.argv)
    app.cache = get_pkg_info()
    app.cache.open()
    view = QDeclarativeView()
    model = PkgListModel()
    rc = view.rootContext()
    rc.setContextProperty('pkglistmodel', model)

    # load the main QML file into the view
    qmlpath = os.path.join(os.path.dirname(__file__), "AppListView.qml")
    view.setSource(qmlpath)

    # show it
    view.show()
    sys.exit(app.exec_())
