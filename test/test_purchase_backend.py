#!/usr/bin/python

import os
import time
import unittest

from gi.repository import GObject, Gtk
from mock import Mock

from testutils import setup_test_env
setup_test_env()
from softwarecenter.db.application import Application
from softwarecenter.backend import get_install_backend

#import softwarecenter.log
#softwarecenter.log.root.setLevel(logging.DEBUG)

class TestPurchaseBackend(unittest.TestCase):
    
    PKGNAME = "hello-license-key-x"
    LICENSE_KEY = "license-key-data"
    # this must match the binary deb (XB-LicenseKeyPath)
    LICENSE_KEY_PATH = "/opt/hello-license-key-x/mykey.txt"

    def test_add_license_key_backend(self):
        self._finished = False
        # add repo
        deb_line = "deb https://mvo:nopassyet@private-ppa.launchpad.net/canonical-isd-hackers/internal-qa/ubuntu oneiric main"
        signing_key_id = "F5410BE0"
        app = Application("Test app1", self.PKGNAME)
        # install only when runnig as root, as we require polkit promtps
        # otherwise
        # FIXME: provide InstallBackendSimulate()
        if os.getuid() == 0:
            backend = get_install_backend()
            backend.ui = Mock()
            backend.connect("transaction-finished", 
                            self._on_transaction_finished)
            # simulate repos becomes available for the public 20 s later
            GObject.timeout_add_seconds(20, self._add_pw_to_commercial_repo)
            # run it
            backend.add_repo_add_key_and_install_app(deb_line,
                                                     signing_key_id,
                                                     app,
                                                     "icon",
                                                     self.LICENSE_KEY)
            # wait until the pkg is installed
            while not self._finished:
		while Gtk.events_pending():
			Gtk.main_iteration()
		time.sleep(0.1)
        if os.getuid() == 0:
            self.assertTrue(os.path.exists(self.LICENSE_KEY_PATH))
            self.assertEqual(open(self.LICENSE_KEY_PATH).read(), self.LICENSE_KEY)
        #time.sleep(10)
        
    def _add_pw_to_commercial_repo(self):
        print "making pw available now"
        path="/etc/apt/sources.list.d/private-ppa.launchpad.net_canonical-isd-hackers_internal-qa_ubuntu.list"
        content= open(path).read()
        passw = os.environ.get("SC_PASS") or "pass"
        content = content.replace("nopassyet", passw)
        open(path, "w").write(content)

    def _on_transaction_finished(self, backend, result):
        print "_on_transaction_finished", result.pkgname, result.success
        if not result.pkgname:
            return
        print "done", result.pkgname
        self._finished = True
        self.assertTrue(result.success)

if __name__ == "__main__":
    unittest.main()
