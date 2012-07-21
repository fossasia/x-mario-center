#!/usr/bin/python

import logging
import unittest

from testutils import setup_test_env
setup_test_env()
from softwarecenter.plugin import PluginManager

class MockApp(object):
    """ mock app """

class TestPlugin(unittest.TestCase):

    def setUp(self):
        pass

    def test_plugin_manager(self):
        app = MockApp()
        pm = PluginManager(app, "./data/plugins")
        pm.load_plugins()
        self.assertEqual(len(pm.plugins), 1)
        self.assertTrue(pm.plugins[0].i_am_happy)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
