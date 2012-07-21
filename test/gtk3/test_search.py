#!/usr/bin/python

from gi.repository import Gtk, GObject
import time
import unittest

from testutils import setup_test_env
setup_test_env()

TIMEOUT=300

class TestSearch(unittest.TestCase):

    def test_installedpane(self):
        from softwarecenter.ui.gtk3.panes.installedpane import get_test_window
        win = get_test_window()
        installedpane = win.get_data("pane")
        self._p()
        installedpane.on_search_terms_changed(None, "the")
        self._p()
        model = installedpane.app_view.tree_view.get_model()
        len1 = len(model)
        installedpane.on_search_terms_changed(None, "nosuchsearchtermforsure")
        self._p()
        len2 = len(model)
        self.assertTrue(len2 < len1)
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_availablepane(self):
        from softwarecenter.ui.gtk3.panes.availablepane import get_test_window
        win = get_test_window()
        pane = win.get_data("pane")
        self._p()
        pane.on_search_terms_changed(None, "the")
        self._p()
        sortmode = pane.app_view.sort_methods_combobox.get_active_text()
        self.assertEqual(sortmode, "By Relevance")
        model = pane.app_view.tree_view.get_model()
        len1 = len(model)
        pane.on_search_terms_changed(None, "nosuchsearchtermforsure")
        self._p()
        len2 = len(model)
        self.assertTrue(len2 < len1)
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()
        


    def _p(self):
        for i in range(10):
            time.sleep(0.1)
            while Gtk.events_pending():
                Gtk.main_iteration()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    unittest.main()
