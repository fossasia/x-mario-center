#!/usr/bin/python

import unittest

import ooldtp
import os
import shutil
import subprocess
import time

class SoftwareCenterLdtp(unittest.TestCase):

    WINDOW       = "frmUbuntuSoftwareCenter"
    LAUNCHER     = "software-center"
    CLOSE_NAME   = "mnuClose"

    def setUp(self):
        env = os.environ.copy()
        env["PYTHONPATH="] = "."
        #self.atspi = subprocess.Popen(["/usr/lib/at-spi/at-spi-registryd"])
        #print "starting at-spi", self.atspi
        #time.sleep(5)
        self.p = subprocess.Popen(["./software-center"],
                                  cwd="..", env=env)
        # wait for app
        self._wait_for_sc()

    def _wait_for_sc(self):
        """ wait unil the software-center window becomes ready """
        while True:
            try:
                comp = ooldtp.component(self.WINDOW, self.CLOSE_NAME)
                close_menu_label = comp.gettextvalue()
            except Exception as e:
                print "waiting ...", e
                time.sleep(2)
                continue
            else:
                break
        print comp, close_menu_label

    def tearDown(self):
        self.p.kill()
	# remove the local db
	shutil.rmtree("../data/xapian")

    def test_search(self):
        application = ooldtp.context(self.WINDOW)
        # get search entry
        search = application.getchild("txtSearch")
        search.enterstring("ab")
        time.sleep(2)
        # check label
        label = application.getchild("status_text")
        label_str = label.gettextvalue()
        # make sure ab always hits the query limit (200 currently)
        self.assertEqual(label_str, "200 matching items")

if __name__ == "__main__":
    # kill locale stuff
    for k in ["LANGUAGE", "LANG"]:
        if k in os.environ:
            del os.environ[k]

    # FIXME: this does not work as at-spi-registryd is not started
    #        and starting it manually does not work for whatever reason
    # re-exec in xvfb if needed 
    #if os.environ.get("DISPLAY") != ":99":
    #    # the xvfb window can be viewed with "xwud < Xvfb_screen0"
    #    cmd = ["xvfb-run", "-e", "xvfb.log", "-s", "-fbdir .", 
    #           "python"]+sys.argv
    #    logging.warn("re-execing inside xvfb: %s" % cmd)
    #    subprocess.call(cmd)
    #else:
    #    unittest.main()

    unittest.main()
