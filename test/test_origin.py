#!/usr/bin/python

import apt
import unittest

from testutils import setup_test_env
setup_test_env()

class TestOrigins(unittest.TestCase):
    """ tests the origin code """

    def test_origin(self):
        # get a cache
        cache = apt.Cache(rootdir="./data/aptroot")
        cache.update()
        cache.open()
        # PPA origin
        origins = cache["firefox-trunk"].candidate.origins
        print origins
        self.assertEqual(origins[0].site, "ppa.launchpad.net")
        self.assertEqual(origins[0].origin, "LP-PPA-ubuntu-mozilla-daily")
        # archive origin
        origins = cache["apt"].candidate.origins
        self.assertEqual(origins[0].site, "archive.ubuntu.com")
        self.assertEqual(origins[0].origin, "Ubuntu")
        self.assertEqual(origins[1].site, "de.archive.ubuntu.com")
        self.assertEqual(origins[1].origin, "Ubuntu")
        

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
