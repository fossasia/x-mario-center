#!/usr/bin/python

from gi.repository import GObject

import random
import os
import time
import unittest

# ensure we set the review backend to the fake one
os.environ["SOFTWARE_CENTER_IPSUM_REVIEWS"] = "1"

import sys
sys.path.insert(0,"../")
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.ui.qml.categoriesmodel import CategoriesModel
from softwarecenter.ui.qml.pkglist import PkgListModel
from softwarecenter.ui.qml.reviewslist import ReviewsListModel

class TestQMLHelpers(unittest.TestCase):
    """ tests the helper classes for the qml code """

    def setUp(self):
        # ensure the cache is ready
        cache = get_pkg_info()
        cache.open()

    def test_categories_model(self):
        """ test the qml categories model """
        CAT_NAME_COLUMN = 0
        # get the model
        model = CategoriesModel()
        # ensure we have something in it
        self.assertNotEqual(model.rowCount(), 0)
        # ensure we have "Games"
        names = set()
        for i in range(model.rowCount()):
            index = model.index(i, CAT_NAME_COLUMN)
            role = CAT_NAME_COLUMN
            names.add(model.data(index, role))
        self.assertTrue("Games" in names)
        
    def test_pkglist_model(self):
        APP_NAME_COLUMN = 0
        # get model
        model = PkgListModel()
        # ensure we start with a empty model by default
        self.assertEqual(model.rowCount(), 0)
        # test search
        model.setSearchQuery("software")
        # ensure we have something in it
        self.assertNotEqual(model.rowCount(), 0)
        # ensure we have "Software Center"
        names = set()
        for i in range(model.rowCount()):
            index = model.index(i, APP_NAME_COLUMN)
            role = APP_NAME_COLUMN
            names.add(model.data(index, role))
        # en_DK/en_US fun
        self.assertTrue("Ubuntu Software Center" in names or
                        "Ubuntu Software Centre" in names)
        # test setCategory by ensuring that setCategory() cuts the nr of 
        # search results
        old_search_hits =  model.rowCount()
        model.setCategory("Games")
        self.assertTrue(model.rowCount() < old_search_hits)
        # test clear
        model.clear()
        self.assertEqual(model.rowCount(), 0)

    def test_reviews_model_details(self):
        SUMMARY_COLUMN = 0
        # get the model
        model = ReviewsListModel()
        # ensure we start with a empty model by default
        self.assertEqual(model.rowCount(), 0)
        # fetch some reviews and ensure its not random
        random.seed(1)
        model.getReviews("software-center")
        time.sleep(0.1)
        self._p()
        # check the results
        self.assertEqual(model.rowCount(), 17)
        summaries = []
        for i in range(model.rowCount()):
            index = model.index(i, SUMMARY_COLUMN)
            role = SUMMARY_COLUMN
            summaries.append(model.data(index, role))
        # ensure the summaries are thre
        self.assertEqual(summaries[0], "Medium")
        self.assertEqual(summaries[4], "Cool")
        # test clear
        model.clear()
        self.assertEqual(model.rowCount(), 0)

    def test_reviews_model_stats(self):
        def _got_review_stats_changed_signal():
            self._i_am_refreshed = True
        # get the model
        model = ReviewsListModel()
        self._i_am_refreshed = False
        model.reviewStatsChanged.connect(_got_review_stats_changed_signal)
        model.refreshReviewStats()
        # ensure the signal got send
        self.assertTrue(self._i_am_refreshed)
        del self._i_am_refreshed
    
    def _p(self):
        context = GObject.main_context_default()
        while context.pending():
            context.iteration()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
