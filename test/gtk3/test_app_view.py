#!/usr/bin/python

import unittest
import xapian

from testutils import setup_test_env
setup_test_env()

from softwarecenter.db.enquire import AppEnquire
from softwarecenter.enums import SortMethods

from softwarecenter.testutils import (get_test_db,
                                      get_test_pkg_info,
                                      get_test_gtk3_icon_cache,
                                      do_events,
                                      )

class TestAppView(unittest.TestCase):
    """ test the app view """

    def setUp(self):
        self.cache = get_test_pkg_info()
        self.icons = get_test_gtk3_icon_cache()
        self.db = get_test_db()

    def test_app_view(self):
        from softwarecenter.ui.gtk3.views.appview import get_test_window
        enquirer = AppEnquire(self.cache, self.db)
        enquirer.set_query(xapian.Query(""),
                           sortmode=SortMethods.BY_CATALOGED_TIME,
                           limit=10,
                           nonblocking_load=False)

        # get test window
        win = get_test_window()
        appview = win.get_data("appview")
        # set matches
        appview.clear_model()
        appview.display_matches(enquirer.matches)
        do_events()
        # verify that the order is actually the correct one
        model = appview.tree_view.get_model()
        docs_in_model = [item[0] for item in model]
        docs_from_enquirer = [m.document for m in enquirer.matches]
        self.assertEqual(len(docs_in_model), 
                         len(docs_from_enquirer))
        for i in range(len(docs_in_model)):
            self.assertEqual(self.db.get_pkgname(docs_in_model[i]),
                             self.db.get_pkgname(docs_from_enquirer[i]))
        win.destroy()

    def test_appview_search_combo(self):
        from softwarecenter.ui.gtk3.views.appview import get_test_window
        from softwarecenter.testutils import get_test_enquirer_matches

        # test if combox sort option "by relevance" vanishes for non-searches
        # LP: #861778
        expected_normal = ["By Name", "By Top Rated", "By Newest First"]
        expected_search = ["By Name", "By Top Rated", "By Newest First", 
                           "By Relevance"]

        # setup goo
        win = get_test_window()
        appview = win.get_data("appview")
        #entry = win.get_data("entry")
        do_events()

        # get the model
        model = appview.sort_methods_combobox.get_model()

        # test normal window (no search)
        matches = get_test_enquirer_matches(appview.helper.db)
        appview.display_matches(matches, is_search=False)
        appview.configure_sort_method(is_search=False)
        do_events()
        in_model = []
        for item in model:
            in_model.append(model.get_value(item.iter, 0))
        self.assertEqual(in_model, expected_normal)

        # now repeat and simulate a search
        matches = get_test_enquirer_matches(appview.helper.db)
        appview.display_matches(matches, is_search=True)
        appview.configure_sort_method(is_search=True)
        do_events()
        in_model = []
        for item in model:
            in_model.append(model.get_value(item.iter, 0))
        self.assertEqual(in_model, expected_search)

        # and back again to no search
        matches = get_test_enquirer_matches(appview.helper.db)
        appview.display_matches(matches, is_search=False)
        appview.configure_sort_method(is_search=False)
        do_events()
        # collect items in the model
        in_model = []
        for item in model:
            in_model.append(model.get_value(item.iter, 0))
        self.assertEqual(expected_normal, in_model)

        # destroy
        win.destroy()

        

if __name__ == "__main__":
    #import logging
    #logging.basicConfig(level=logging.DEBUG)
    unittest.main()
