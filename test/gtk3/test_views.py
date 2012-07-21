#!/usr/bin/python

from gi.repository import Gtk, GObject
import unittest

from testutils import setup_test_env
setup_test_env()

TIMEOUT=300

class TestViews(unittest.TestCase):

    def test_viewswitcher(self):
        from softwarecenter.ui.gtk3.panes.viewswitcher import get_test_window_viewswitcher
        win = get_test_window_viewswitcher()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_catview(self):
        from softwarecenter.ui.gtk3.views.catview_gtk import get_test_window_catview
        win = get_test_window_catview()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_appdetails(self):
        from softwarecenter.ui.gtk3.views.appdetailsview import get_test_window_appdetails
        win = get_test_window_appdetails()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()
    
    def test_pkgsnames(self):
        from softwarecenter.ui.gtk3.views.pkgnamesview import get_test_window_pkgnamesview
        win = get_test_window_pkgnamesview()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_purchaseview(self):
        from softwarecenter.ui.gtk3.views.purchaseview import get_test_window_purchaseview
        win = get_test_window_purchaseview()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_appview(self):
        from softwarecenter.ui.gtk3.views.appview import get_test_window
        win = get_test_window()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()
        

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
