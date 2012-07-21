#!/usr/bin/python

import os
import unittest

from testutils import setup_test_env
setup_test_env()

class TestGwibber(unittest.TestCase):
    """ tests the "where is it in the menu" code """

    def setUp(self):
        pass

    def test_gwibber_helper_mock(self):
        from softwarecenter.gwibber_helper import GwibberHelperMock
        os.environ["SOFTWARE_CENTER_GWIBBER_MOCK_USERS"] = "2"
        os.environ["SOFTWARE_CENTER_GWIBBER_MOCK_NO_FAIL"] = "1"
        gh = GwibberHelperMock()
        accounts = gh.accounts()
        self.assertEqual(len(accounts), 2)
        #print accounts
        # we can not test the real gwibber here, otherwise it will
        # post our test data to real services
        self.assertEqual(gh.send_message ("test"), True)

    def test_gwibber_helper(self):
        from softwarecenter.gwibber_helper import GwibberHelper
        # readonly test as there maybe be real accounts
        gh = GwibberHelper()
        have_accounts = gh.has_accounts_in_sqlite()
        self.assertTrue(isinstance(have_accounts, bool))
        accounts = gh.accounts()
        self.assertTrue(isinstance(accounts, list))

    def not_working_because_gi_does_not_provide_list_test_gwibber(self):
        from gi.repository import Gwibber
        #service = Gwibber.Service()
        #service.quit()
        # get account data
        accounts = Gwibber.Accounts()
        print dir(accounts)
        #print "list: ", accounts.list()
        # check single account for send enabled, only do if "True"
        #print accounts.send_enabled(accounts.list[0])
        # first check gwibber available
        service = Gwibber.Service()
        print dir(service)
        service.service_available(False)
        service.send_message ("test")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
