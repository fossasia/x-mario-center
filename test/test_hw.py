#!/usr/bin/python

import unittest

from mock import patch

from testutils import setup_test_env
setup_test_env()
from softwarecenter.hw import (
    get_hardware_support_for_tags, 
    get_hw_missing_long_description,
    OPENGL_DRIVER_BLACKLIST_TAG)
from softwarecenter.utils import utf8

class TestHW(unittest.TestCase):
    """ tests the hardware support detection """

    def test_get_hardware_support_for_tags(self):
        tags = [OPENGL_DRIVER_BLACKLIST_TAG + "intel",
                "hardware::input:mouse",
               ]
        with patch("debtagshw.opengl.get_driver") as mock_get_driver:
            # test with the intel driver
            mock_get_driver.return_value = "intel"
            supported = get_hardware_support_for_tags(tags)
            self.assertEqual(supported[tags[0]], "no")
            self.assertEqual(len(supported), 2)
            # now with fake amd driver
            mock_get_driver.return_value = "amd"
            supported = get_hardware_support_for_tags(tags)
            self.assertEqual(supported[tags[0]], "yes")

    def test_get_hw_missing_long_description(self):
        s = get_hw_missing_long_description(
            { "hardware::input:keyboard": "yes",
              OPENGL_DRIVER_BLACKLIST_TAG + "intel": "no",
            })
        self.assertEqual(s, 
                         utf8(u'This software does not work with the '
                              u'\u201cintel\u201D graphics driver this '
                              u'computer is using.'))
                         

if __name__ == "__main__":
    #import logging
    #logging.basicConfig(level=logging.DEBUG)
    unittest.main()
