#!/usr/bin/python

from gi.repository import Gtk, GObject
import unittest

from testutils import setup_test_env
setup_test_env()

from softwarecenter.ui.gtk3.widgets.recommendations import get_test_window

# window destory timeout
TIMEOUT=100

# FIXME: the code from test_catview that tests the lobby widget should
#        move here as it should be fine to test it in isolation

class TestRecommendationsWidgets(unittest.TestCase):

    def test_recommendations_lobby(self):
        win = get_test_window(panel_type="lobby")
        win.show_all()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()
        
    def test_recommendations_category(self):
        win = get_test_window(panel_type="category")
        win.show_all()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()
        
    def test_recommendations_details(self):
        win = get_test_window(panel_type="details")
        win.show_all()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()



if __name__ == "__main__":
    #import logging
    #logging.basicConfig(level=logging.DEBUG)
    unittest.main()
