#!/usr/bin/python

from gi.repository import Gtk, GObject
import unittest

from testutils import setup_test_env
setup_test_env()

TIMEOUT=300

class TestPanes(unittest.TestCase):

    def test_availablepane(self):
        from softwarecenter.ui.gtk3.panes.availablepane import get_test_window
        win = get_test_window()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_globalpane(self):
        from softwarecenter.ui.gtk3.panes.globalpane import get_test_window
        win = get_test_window()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_pendingpane(self):
        from softwarecenter.ui.gtk3.panes.pendingpane import get_test_window
        win = get_test_window()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_historypane(self):
        from softwarecenter.ui.gtk3.panes.historypane import get_test_window
        win = get_test_window()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_installedpane(self):
        from softwarecenter.ui.gtk3.panes.installedpane import get_test_window
        win = get_test_window()
        pane = win.get_data("pane")
        # ensure it visible
        self.assertTrue(pane.get_property("visible"))
        # ensure the treeview is there and has data
        self._p()
        self.assertTrue(len(pane.treefilter.get_model()) > 5)
        # schedule close
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def _p(self):
        while Gtk.events_pending():
            Gtk.main_iteration()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
