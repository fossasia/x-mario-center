#!/usr/bin/python
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

from gi.repository import GObject
GObject.threads_init()

import os
import sys

from PyQt4 import QtDeclarative
from PyQt4.QtCore import QUrl
from PyQt4.QtGui import QApplication, QIcon
from PyQt4.QtDeclarative import QDeclarativeView

from softwarecenter.db.pkginfo import get_pkg_info

from pkglist import PkgListModel
from reviewslist import ReviewsListModel
from categoriesmodel import CategoriesModel

from softwarecenter.utils import mangle_paths_if_running_in_local_checkout

if __name__ == '__main__':
    app = QApplication(sys.argv)

    # TODO do this async
    app.cache = get_pkg_info()
    app.cache.open()

    view = QDeclarativeView()
    view.setWindowTitle(view.tr("X-Mario App Store"))
    view.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__),
        "../../../data/icons/scalable/apps/softwarecenter.svg")))
    view.setResizeMode(QtDeclarative.QDeclarativeView.SizeRootObjectToView)

    # if running locally, fixup softwarecenter.paths
    mangle_paths_if_running_in_local_checkout()

    # ideally this should be part of the qml by using a qmlRegisterType()
    # but that does not seem to be supported in pyqt yet(?) so we need
    # to cowboy it in here
    pkglistmodel = PkgListModel()
    reviewslistmodel = ReviewsListModel()
    categoriesmodel = CategoriesModel()
    rc = view.rootContext()
    rc.setContextProperty('pkglistmodel', pkglistmodel)
    rc.setContextProperty('reviewslistmodel', reviewslistmodel)
    rc.setContextProperty('categoriesmodel', categoriesmodel)

    # debug
    if len(sys.argv) > 1:
        # FIXME: we really should set the text entry here
        pkglistmodel.setSearchQuery(sys.argv[1])

    # load the main QML file into the view
    qmlpath = os.path.join(os.path.dirname(__file__), "sc.qml")
    view.setSource(QUrl.fromLocalFile(qmlpath))

    # show it
    view.show()
    sys.exit(app.exec_())
