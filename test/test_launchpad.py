#!/usr/bin/python

from gi.repository import GObject
import unittest

from testutils import setup_test_env
setup_test_env()
from softwarecenter.backend.launchpad import GLaunchpad

class testUbuntuSSO(unittest.TestCase):

    def setUp(self):
        pass
    
    def _cb_login_successful(self, lp, token):
        self._login_successful = True

    def test_launchpad_login(self):
        lp = GLaunchpad()
        lp.connect("login-successful", self._cb_login_successful)
        # monkey patch
        lp.login = lambda u,p: True
        lp.login("user", "password")
        lp.emit("login-successful", None)
        main_loop = GObject.main_context_default()
        while main_loop.pending():
            main_loop.iteration()
        self.assertTrue(self._login_successful)
    
    def _monkey_get_subscribed_archives(self):
        return ["deb http://foo:pw@launchpad.net/ main"]

    def test_launchpad_get_subscribed_archives(self):
        lp = GLaunchpad()
        lp.get_subscribed_archives = self._monkey_get_subscribed_archives
        archives = lp.get_subscribed_archives()
        self.assertEqual(archives, ["deb http://foo:pw@launchpad.net/ main"])

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
