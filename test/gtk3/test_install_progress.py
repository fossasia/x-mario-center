#!/usr/bin/python

from gi.repository import Gtk
import time
import unittest

from testutils import setup_test_env
setup_test_env()


from softwarecenter.db.application import Application
from softwarecenter.testutils import start_dummy_backend, stop_dummy_backend

TIMEOUT=300

class TestViews(unittest.TestCase):

    def setUp(self):
        start_dummy_backend()
        
    def tearDown(self):
        stop_dummy_backend()

    def test_install_appdetails(self):
        from softwarecenter.ui.gtk3.views.appdetailsview import get_test_window_appdetails
        win = get_test_window_appdetails()
        view = win.get_data("view")
        view.show_app(Application("", "2vcard"))
        self._p()
        app = view.app
        view.backend.install(app, "")
        self._p()
        self.assertTrue(view.pkg_statusbar.progress.get_property("visible"))

    def _p(self):
        for i in range(20):
            time.sleep(0.1)
            while Gtk.events_pending():
                Gtk.main_iteration()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    unittest.main()
