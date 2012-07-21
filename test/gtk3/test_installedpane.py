#!/usr/bin/python

from gi.repository import Gtk, GObject
import time
import unittest

from testutils import setup_test_env
setup_test_env()

TIMEOUT=300

class TestInstalledPane(unittest.TestCase):

    def test_installedpane(self):
        from softwarecenter.ui.gtk3.panes.installedpane import get_test_window
        win = get_test_window()
        installedpane = win.get_data("pane")
        self._p()
        # safe initial show/hide label for later
        initial_actionbar_label = installedpane.action_bar._label_text
        # do simple search
        installedpane.on_search_terms_changed(None, "foo")
        self._p()
        model = installedpane.app_view.tree_view.get_model()
        # FIXME: len(model) *only* counts the size of the top level
        #        (category) hits. thats still ok, as non-apps will 
        #        add the "system" category
        len_only_apps = len(model)
        # set to show nonapps
        installedpane._show_nonapp_pkgs()
        self._p()
        len_with_nonapps = len(model)
        self.assertTrue(len_with_nonapps > len_only_apps)
        # set to hide nonapps again and ensure the size matches the
        # previous one
        installedpane._hide_nonapp_pkgs()
        self._p()
        self.assertEqual(len(model), len_only_apps)
        # clear sarch and ensure we get a expanded size again
        installedpane.on_search_terms_changed(None, "")
        self._p()
        all_apps = len(model)
        self.assertTrue(all_apps > len_only_apps)
        # ensure we have the same show/hide info as initially
        self.assertEqual(initial_actionbar_label,
                         installedpane.action_bar._label_text)
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
