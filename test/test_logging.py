#!/usr/bin/python

import os
import stat
import unittest

from testutils import setup_test_env
setup_test_env()


class TestLogging(unittest.TestCase):
    """ tests the sc logging facilities """

    def test_no_write_access_for_cache_dir(self):
        """ test for bug LP: #688682 """
        # make the test cache dir non-writeable
        import softwarecenter.paths
        cache_dir = softwarecenter.paths.SOFTWARE_CENTER_CACHE_DIR
        # set not-writable (mode 0400)
        os.chmod(cache_dir, stat.S_IRUSR)
        self.assertFalse(os.access(cache_dir, os.W_OK))
        # and then start up the logger
        import softwarecenter.log
        softwarecenter.log # pyflakes
        # check that the old directory was moved aside (renamed with a ".0" appended)
        self.assertTrue(os.path.exists(cache_dir + ".0"))
        self.assertFalse(os.path.exists(cache_dir + ".1"))
        # and check that the new directory was created and is now writable
        self.assertTrue(os.path.exists(cache_dir))
        self.assertTrue(os.access(cache_dir, os.W_OK))


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
