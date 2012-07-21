#!/usr/bin/python

import logging
import os
import unittest

from testutils import setup_test_env
setup_test_env()
from softwarecenter.paths import XAPIAN_BASE_PATH
from softwarecenter.ui.gtk3.gmenusearch import GMenuSearcher
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.db.database import StoreDatabase
from softwarecenter.db.application import Application
from softwarecenter.enums import PkgStates

class TestWhereIsit(unittest.TestCase):
    """ tests the "where is it in the menu" code """

    def setUp(self):
        cache = get_pkg_info()
        cache.open()
        xapian_base_path = XAPIAN_BASE_PATH
        pathname = os.path.join(xapian_base_path, "xapian")
        self.db = StoreDatabase(pathname, cache)
        self.db.open()

    # mvo: disabled for now (2011-06-06) because the new gnome-panel
    #      does not have "System" anymore and its not clear to me yet
    #      where those items will appear. Once that is settled it
    #      should be re-enabled
    def disabled_for_now_test_where_is_it_in_system(self):
        app = Application("Hardware Drivers", "jockey-gtk")
        details = app.get_details(self.db)
        self.assertEqual(details.desktop_file, 
                         "/usr/share/app-install/desktop/jockey-gtk.desktop")
        # search the settings menu
        searcher = GMenuSearcher()
        found = searcher.get_main_menu_path(details.desktop_file)
        self.assertEqual(found[0].get_name(), "Desktop")
        self.assertEqual(found[0].get_icon(), "preferences-other")
        self.assertEqual(found[1].get_name(), "Administration")
        self.assertEqual(found[1].get_icon(), "preferences-system")

    def test_where_is_it_in_applications(self):
        app = Application("Calculator", "gcalctool")
        details = app.get_details(self.db)
        self.assertEqual(details.desktop_file, 
                         "/usr/share/app-install/desktop/gcalctool:gcalctool.desktop")
        # search the settings menu
        searcher = GMenuSearcher()
        found = searcher.get_main_menu_path(
            details.desktop_file,
            [os.path.abspath("./data/fake-applications.menu")])
        self.assertEqual(found[0].get_name(), "Applications")
        self.assertEqual(found[0].get_icon().get_names()[0], 
                         "applications-other")
        self.assertEqual(found[1].get_name(), "Accessories")
        self.assertEqual(found[1].get_icon().get_names()[0], 
                         "applications-utilities")
    
    def test_where_is_it_kde4(self):
        app = Application("", "ark")
        details = app.get_details(self.db)
        self.assertEqual(details.desktop_file, 
                         "/usr/share/app-install/desktop/ark:kde4__ark.desktop")
        # search the settings menu
        searcher = GMenuSearcher()
        found = searcher.get_main_menu_path(
            details.desktop_file,
            [os.path.abspath("./data/fake-applications.menu")])
        self.assertEqual(found[0].get_name(), "Applications")
        self.assertEqual(found[0].get_icon().get_names()[0], 
                         "applications-other")
        self.assertEqual(found[1].get_name(), "Accessories")
        self.assertEqual(found[1].get_icon().get_names()[0], 
                         "applications-utilities")
        
    def test_where_is_it_real_system(self):
        app = Application("", "gedit")
        details = app.get_details(self.db)
        if details.pkg_state != PkgStates.INSTALLED:
            logging.warn("gedit not installed, skipping real menu test")
            self.skipTest("gedit not installed")
            return
        self.assertEqual(details.desktop_file, 
                         "/usr/share/app-install/desktop/gedit:gedit.desktop")
        # search the *real* menu
        searcher = GMenuSearcher()
        found = searcher.get_main_menu_path(details.desktop_file)
        self.assertNotEqual(found, None)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
