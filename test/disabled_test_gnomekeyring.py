#!/usr/bin/python

from gi.repository import GObject
import gnomekeyring as gk
import unittest

class testGnomeKeyringUsage(unittest.TestCase):

    APP = "gk-test"
    KEYRING_NAME = "gk-test-keyring"

    def setUp(self):
        GObject.set_application_name(self.APP)

    def test_keyring_available(self):
        available = gk.is_available()
        self.assertTrue(available)
    
    def test_keyring_populate(self):
        attr = { 'token' : 'the-token',
                 'consumer-key' : 'the-consumer-key',
                 'usage' : 'software-center-agent-token',
                 }
        secret = 'consumer_secret=xxx&token=xxx&consumer_key=xxx&token_secret=xxx&name=s-c'

        keyring_names = gk.list_keyring_names_sync()
        print keyring_names
        self.assertFalse(self.KEYRING_NAME in keyring_names)
        gk.create_sync(self.KEYRING_NAME, "")
        keyring_names = gk.list_keyring_names_sync()
        self.assertTrue(self.KEYRING_NAME in keyring_names)
        res = gk.item_create_sync(self.KEYRING_NAME,
                                  gk.ITEM_GENERIC_SECRET, 
                                  "Software Center Agent token",
                                  attr,
                                  secret,
                                  True) # update if exists
        self.assertTrue(res)

        # get the token from the keyring using the 'usage' field
        # in the attr
        search_attr = { 'usage' :  'software-center-agent-token',
                        }
        found = gk.find_items_sync(gk.ITEM_GENERIC_SECRET,
                                   search_attr)
        self.assertEqual(len(found), 1)
        for item in found:
            self.assertEqual(item.keyring, self.KEYRING_NAME)
            #print item.item_id, item.attributes
            self.assertEqual(item.secret, secret)

    def tearDown(self):
        try:
            gk.delete_sync(self.KEYRING_NAME)
        except gk.NoSuchKeyringError:
            pass


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()

