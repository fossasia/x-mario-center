#!/usr/bin/python

import apt
import unittest

from testutils import setup_test_env
setup_test_env()
from softwarecenter.cmdfinder import CmdFinder

class TestCmdFinder(unittest.TestCase):
    """ tests the CmdFinder class """

    def setUp(self):
        cache = apt.Cache()
        self.cmd = CmdFinder(cache)

    def test_cmdfinder_simple(self):
        cmds = self.cmd.find_cmds_from_pkgname("apt")
        self.assertTrue("apt-get" in cmds)
        self.assertTrue(len(cmds) > 2)

    def test_cmdfinder_find_alternatives(self):
        # this test ensures that alternatives are also considered
        cmds = self.cmd.find_cmds_from_pkgname("gawk")
        self.assertTrue("awk" in cmds)

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
