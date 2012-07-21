#!/usr/bin/python

import os
import unittest

from mock import Mock

from testutils import setup_test_env
setup_test_env()
from softwarecenter.region import RegionDiscover, get_region_name
from softwarecenter.i18n import init_locale

class TestRegion(unittest.TestCase):
    """ tests the region detection """

    def setUp(self):
        self.region = RegionDiscover()

    def test_get_region_dump(self):
        os.environ["LC_ALL"] = "en_ZM.utf8"
        init_locale()
        res = self.region._get_region_dumb()
        self.assertEqual(res["countrycode"], "ZM")
        self.assertEqual(res["country"], "Zambia")
        os.environ["LANG"] = ""

    def test_get_region_name(self):
        self.assertEqual(get_region_name("BO"), "Bolivia")
        self.assertEqual(get_region_name("DE"), "Germany")

    def test_get_region_geoclue(self):
        res = self.region._get_region_geoclue()
        self.assertNotEqual(len(res), 0)
        self.assertTrue("countrycode" in res)
        self.assertTrue("country" in res)

    # helper
    def _mock_internal_region_finders(self):
        self.region._get_region_dumb = Mock()
        self.region._get_region_geoclue = Mock()
        
    def test_get_region_no_mocks(self):
        res = self.region.get_region()
        self.assertNotEqual(len(res), 0)

    def test_get_region_normal(self):
        self._mock_internal_region_finders()
        self.region.get_region()
        self.assertTrue(self.region._get_region_geoclue.called)
        self.assertFalse(self.region._get_region_dumb.called)

    def test_get_region_fallback(self):
        # test fallback (no geoclue)
        self._mock_internal_region_finders()
        self.region._get_region_geoclue.side_effect = Exception("raise test exception")
        self.region.get_region()
        self.assertTrue(self.region._get_region_dumb.called)
        self.assertTrue(self.region._get_region_geoclue.called)

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
