# Copyright (C) 2010 Canonical Ltd
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

"""Template Test

This is a template to create tests for Mago

To run it with:
$ mago <path_to_this_file>

The only mandatory element is 'launcher'
If no 'window_name' property is set, then mago will try to guess it from the
XID of the window

set setupOnce to False to launch/close the app for each test

"""

import ldtp
import ooldtp
import unittest

from mago import TestCase

class TestSoftwareCenter(TestCase):
    """The minimal test that can be written with mago
    """
    # try local checkout first
    try:
        #import softwarecenter.enums
        launcher = "../software-center"
        print "using local checkout"
    except ImportError:
        launcher = 'software-center'
    window_name = 'frmUbuntuSoftwareCenter'
    setupOnce = True

    # widgets

    # navigation bar
    btnBackButton = "btnBackButton"
    btnForwardButton = "btnForwardButton"

    # available pane
    availablePaneAppView = "AvailablePane.app_view"
    availablePaneSearchEntry = "AvailablePane.searchentry"
    
    def test_search_simple(self):
        """ perform a basic search test """
        context = ooldtp.context(self.window_name)
        context.enterstring(self.availablePaneSearchEntry, "apt")
        ldtp.wait(1)
        row_count = context.getrowcount(self.availablePaneAppView)
        # ensure we get enough hits
        self.assertTrue(row_count > 10)
        # ensure apt is the first hit
        row = 0
        column = 0
        text = context.getcellvalue(self.availablePaneAppView, row, column)
        self.assertEqual(text, "\nInstalled\nAdvanced front-end for dpkg")

    # disabled for now as it takes a long time to run
    def _diabled_for_now_test_search_scroll_down_hang(self):
        context = ooldtp.context(self.window_name)
        ldtp.wait(2)
        context.enterstring(self.availablePaneSearchEntry, "a")
        ldtp.wait(1)
        row_count = context.getrowcount(self.availablePaneAppView)
        # ensure we get enough hits
        self.assertTrue(row_count > 10)
        ldtp.generatekeyevent("<tab>")
        # repeating this 100 times will eventually hang s-c, its
        # currently unclear why
        for i in range(100):
            self.generate_page_down()
            ldtp.wait(1)
            ldtp.generatekeyevent("<enter>")
            ldtp.wait(1)
            ldtp.generatekeyevent("<backspace>")
            ldtp.wait(1)
            
    def generate_page_down(self):
        # FIXME: currently broken
        #ldtp.generatekeyevent("<pagedown>")
        import pyatspi
        key_code=117 # pagedown
        pyatspi.Registry.generateKeyboardEvent(
            key_code, None, pyatspi.KEY_PRESS)
        pyatspi.Registry.generateKeyboardEvent(
            key_code, None, pyatspi.KEY_RELEASE)


    def xxx_test_TEMPLATE(self):
        """This a test template

        Add documentation for your test in the following format:
            caseid: XXXXX000 - Unique ID for the testcase
            name: Name of the test case usually the name of the method.
            requires: List of the packages required to run the test.
            command: Name of the binary to test
            _description:
             PURPOSE:
                 1. Describe the purpose of the test
             STEPS:
                 1. Describe the first step of the test case
                 2. Describe the second step of the test case
                 2. ...
             VERIFICATION:
                 1. Describe the expected result of the test.

        """
        self.assertTrue(True)

if __name__ == "__main__":
    unittest.main()
