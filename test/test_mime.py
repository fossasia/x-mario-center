#!/usr/bin/python

import os
import unittest

from testutils import setup_test_env
setup_test_env()
from softwarecenter.db.database import StoreDatabase
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.db.update import rebuild_database

class TestMime(unittest.TestCase):
    """ tests the mime releated stuff """

    def setUp(self):
        self.cache = get_pkg_info()
        self.cache.open()

    def test_most_popular_applications_for_mimetype(self):
        pathname = "../data/xapian"
        if not os.listdir(pathname):
            rebuild_database(pathname)
        db = StoreDatabase(pathname, self.cache)
        db.open()
        # all
        result = db.get_most_popular_applications_for_mimetype("text/html", only_uninstalled=False, num=5)
        self.assertEqual(len(result), 5)
        # only_uninstaleld
        result = db.get_most_popular_applications_for_mimetype("text/html", only_uninstalled=True, num=2)
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
