#!/usr/bin/python

from gi.repository import Gtk, GObject
import unittest

from testutils import setup_test_env
setup_test_env()

import softwarecenter.ui.gtk3.dialogs

# window destory timeout
TIMEOUT=200

class TestDialogs(unittest.TestCase):
    """ basic tests for the various gtk3 dialogs """

    def test_dependency_dialogs(self):
        from softwarecenter.ui.gtk3.dialogs.dependency_dialogs import get_test_dialog
        dia = get_test_dialog()
        GObject.timeout_add(TIMEOUT, 
                            lambda: dia.response(Gtk.ResponseType.ACCEPT))
        dia.run()
        
    def test_confirm_repair_broken_cache(self):
        datadir = softwarecenter.paths.datadir
        GObject.timeout_add(TIMEOUT, self._close_dialog)
        res = softwarecenter.ui.gtk3.dialogs.confirm_repair_broken_cache(
            parent=None, datadir=datadir)
        self.assertEqual(res, False)
        
    def test_error_dialog(self):
        GObject.timeout_add(TIMEOUT, self._close_dialog)
        res = softwarecenter.ui.gtk3.dialogs.error(
            parent=None, primary="primary", secondary="secondary")
        self.assertEqual(res, False)

    def test_accept_tos_dialog(self):
        GObject.timeout_add(TIMEOUT, self._close_dialog)
        res = softwarecenter.ui.gtk3.dialogs.show_accept_tos_dialog(
            parent=None)
        self.assertEqual(res, False)
        
    # helper
    def _close_dialog(self):
        softwarecenter.ui.gtk3.dialogs._DIALOG.response(0)

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
