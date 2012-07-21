#!/usr/bin/python

import os
import time
import unittest

from testutils import setup_test_env
setup_test_env()

from softwarecenter.backend.installbackend_impl.aptd import AptdaemonBackend
from defer import inline_callbacks
from mock import Mock

import aptdaemon.loop 

class TestAptdaemon(unittest.TestCase):
    """ tests the AptdaemonBackend """

    def setUp(self):
        self.aptd = AptdaemonBackend()
        # monkey patch 
        self.aptd.aptd_client.install_packages = self._mock_aptd_client_install_packages
        self._pkgs_to_install = []
    
    def _mock_aptd_client_install_packages(self, pkgs, reply_handler, error_handler):
        self._pkgs_to_install.extend(pkgs)

    @inline_callbacks
    def test_add_license_key_home(self):
        data = "some-data"
        # test HOME
        target = "~/.fasfasdfsdafdfsdafdsfa"
        pkgname = "2vcard"
        json_auth = ""
        yield self.aptd.add_license_key(data, target, json_auth, pkgname)
        self.assertEqual(open(os.path.expanduser(target)).read(), data)
        # ensure its not written twice
        data2 = "other-data"
        yield self.aptd.add_license_key(data2, target, json_auth, pkgname)
        self.assertEqual(open(os.path.expanduser(target)).read(), data)
        # cleanup
        os.remove(os.path.expanduser(target))

    def test_add_license_key_opt(self):
        if os.getuid() != 0:
            logging.info("skipping add_license_key_opt test")
            return
        # test /opt
        data = "some-data"
        pkgname = "hellox"
        path = "/opt/hellox/conf/license-key.txt"
        json_auth = os.environ.get("SC_TEST_JSON") or "no-json-auth"
        def _error(*args):
            print "errror", args
        self.aptd.ui = Mock()
        self.aptd.ui.error = _error
        @inline_callbacks
        def run():
            yield self.aptd.add_license_key(data, path, json_auth, pkgname)
            aptdaemon.loop.mainloop.quit()
        # run the callback
        run()
        aptdaemon.loop.mainloop.run()
        # give the daemon time to write the file
        time.sleep(0.5)
        self.assertTrue(os.path.exists(path))
        #self.assertEqual(open(os.path.expanduser(target)).read(), data)
        #os.remove(os.path.expanduser(target))

    def test_install_multiple(self):
        # FIXME: this test is not great, it should really 
        #        test that there are multiple transactions, that the icons
        #        are correct etc - that needs some work in order to figure
        #        out how to best do that with aptdaemon/aptd.py
        pkgnames = ["7zip", "2vcard"]
        appnames = ["The 7 zip app", ""]
        iconnames = ["icon-7zip", ""]
        # need to yiel as install_multiple is a inline_callback (generator)
        yield self.aptd.install_multiple(pkgnames, appnames, iconnames)
        self.assertEqual(self._pkgs_to_install, ["7zip", "2vcard"])
        self._pkgs_to_install = []

    def _monkey_patched_add_vendor_key_from_keyserver(self, keyid, 
                                                      *args, **kwargs):
        self.assertTrue(keyid.startswith("0x"))
        return Mock()

    def test_download_key_from_keyserver(self):
        keyid = "0EB12F05"
        keyserver = "keyserver.ubuntu.com"
        self.aptd.aptd_client.add_vendor_key_from_keyserver = self._monkey_patched_add_vendor_key_from_keyserver
        self.aptd.add_vendor_key_from_keyserver(keyid, keyserver)
        
    def test_apply_changes(self):
        pkgname = "gimp"
        appname = "The GIMP app"
        iconname = "icon-gimp"
        addons_install = ["gimp-data-extras", "gimp-gutenprint"]
        addons_remove = ["gimp-plugin-registry"]
        yield self.aptd.apply_changes(pkgname, appname ,iconname, addons_install, addons_remove)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
