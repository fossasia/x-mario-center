#!/usr/bin/python

import unittest

from testutils import setup_test_env
setup_test_env()

class TestNetstatus(unittest.TestCase):
    """ tests the netstaus utils """

    def test_netstaus(self):
        from softwarecenter.netstatus import get_network_watcher
        watcher = get_network_watcher()
        # FIXME: do something with the watcher
        watcher
        
    def test_testping(self):
        from softwarecenter.netstatus import test_ping
        res = test_ping()
        # FIXME: do something with the res
        res

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
