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
from datetime import datetime

from PyQt4.QtCore import QAbstractListModel, QModelIndex, pyqtSignal, pyqtSlot

from softwarecenter.db.database import Application
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.backend.reviews import get_review_loader


class ReviewsListModel(QAbstractListModel):

    # should match the softwarecenter.backend.reviews.Review attributes
    COLUMNS = ('_summary',
               '_review_text',
               '_rating',
               '_date_created',
               '_reviewer_displayname',
               )

    def __init__(self, parent=None):
        super(ReviewsListModel, self).__init__()
        self._reviews = []

        roles = dict(enumerate(ReviewsListModel.COLUMNS))
        self.setRoleNames(roles)
        # FIXME: make this async
        self.cache = get_pkg_info()
        self.reviews = get_review_loader(self.cache)

    # QAbstractListModel code
    def rowCount(self, parent=QModelIndex()):
        return len(self._reviews)

    def data(self, index, role):
        if not index.isValid():
            return None
        review = self._reviews[index.row()]
        role = self.COLUMNS[role]
        if role == '_date_created':
            when = datetime.strptime(getattr(review, role[1:]),
                '%Y-%m-%d %H:%M:%S')
            return when.strftime('%Y-%m-%d')
        return unicode(getattr(review, role[1:]))

    # helper
    def clear(self):
        self.beginRemoveRows(QModelIndex(), 0, self.rowCount() - 1)
        self._reviews = []
        self.endRemoveRows()

    def _on_reviews_ready_callback(self, loader, reviews):
        self.beginInsertRows(QModelIndex(),
                             self.rowCount(),  # first
                             self.rowCount() + len(reviews) - 1)  # last
        self._reviews += reviews
        self.endInsertRows()

    # getReviews interface (for qml)
    @pyqtSlot(str)
    def getReviews(self, pkgname, page=1):
        # pkgname is a QString, so we need to convert it to a old-fashioned str
        pkgname = unicode(pkgname).encode("utf-8")
        app = Application("", pkgname)
        # support pagination by not cleaning _reviews for subsequent pages
        if page == 1:
            self.clear()

        # load in the eventloop to ensure that animations are not delayed
        GObject.timeout_add(
            10, self.reviews.get_reviews, app,
            self._on_reviews_ready_callback, page)

    # refresh review-stats (for qml)
    @pyqtSlot()
    def refreshReviewStats(self):
        def _on_refresh_reviews_ready_callback(loader):
            self.reviewStatsChanged.emit()
        self.reviews.refresh_review_stats(
            _on_refresh_reviews_ready_callback)

    # FIXME: how is this signal actually used in the qml JS?
    # signals
    reviewStatsChanged = pyqtSignal()
