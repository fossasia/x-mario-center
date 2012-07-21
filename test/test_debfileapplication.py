#!/usr/bin/python

import unittest
import logging

from testutils import setup_test_env
setup_test_env()

from softwarecenter.enums import PkgStates
from softwarecenter.db.debfile import DebFileApplication, DebFileOpenError
from softwarecenter.testutils import get_test_db

DEBFILE_PATH = './data/test_debs/gdebi-test9.deb'
DEBFILE_NAME = 'gdebi-test9'
DEBFILE_DESCRIPTION = ' provides/conflicts against "nvidia-glx"'
DEBFILE_SUMMARY = 'testpackage for gdebi - provides/conflicts against real pkg'
DEBFILE_VERSION = '1.0'
DEBFILE_WARNING = 'Only install this file if you trust the origin.'

DEBFILE_PATH_NOTFOUND = './data/test_debs/notfound.deb'
DEBFILE_PATH_NOTADEB = './data/notadeb.txt'
DEBFILE_PATH_CORRUPT = './data/test_debs/corrupt.deb'
DEBFILE_NOT_INSTALLABLE = './data/test_debs/gdebi-test1.deb'


class TestDebFileApplication(unittest.TestCase):
    """ Test the class DebFileApplication """

    def setUp(self):
        self.db = get_test_db()

    def test_get_name(self):
        debfileapplication = DebFileApplication(DEBFILE_PATH)
        debfiledetails = debfileapplication.get_details(self.db)

        self.assertEquals(debfiledetails.name, DEBFILE_NAME)

    def test_get_description(self):
        debfileapplication = DebFileApplication(DEBFILE_PATH)
        debfiledetails = debfileapplication.get_details(self.db)

        self.assertEquals(debfiledetails.description, DEBFILE_DESCRIPTION)

    def test_get_pkg_state_uninstalled(self):
        debfileapplication = DebFileApplication(DEBFILE_PATH)
        debfiledetails = debfileapplication.get_details(self.db)

        self.assertEquals(debfiledetails.pkg_state, PkgStates.UNINSTALLED)

    def test_get_pkg_state_not_installable(self):
        debfileapplication = DebFileApplication(DEBFILE_NOT_INSTALLABLE)
        debfiledetails = debfileapplication.get_details(self.db)

        self.assertEquals(debfiledetails.pkg_state, PkgStates.ERROR)

    def disabled_for_now_test_get_pkg_state_reinstallable(self):
        # FIMXE: add hand crafted dpkg status file into the testdir so
        #        that gdebi-test1 is marked install for the MockAptCache
        #debfileapplication = DebFileApplication(DEBFILE_REINSTALLABLE)
        #debfiledetails = debfileapplication.get_details(self.db)
        #self.assertEquals(debfiledetails.pkg_state, PkgStates.REINSTALLABLE)
        pass

    def test_get_pkg_state_not_found(self):
        debfileapplication = DebFileApplication(DEBFILE_PATH_NOTFOUND)
        debfiledetails = debfileapplication.get_details(self.db)
        self.assertEquals(debfiledetails.pkg_state, PkgStates.NOT_FOUND)

    def test_get_pkg_state_not_a_deb(self):
        self.assertRaises(DebFileOpenError,
                          DebFileApplication, DEBFILE_PATH_NOTADEB)

    def test_get_pkg_state_corrupt(self):
        debfileapplication = DebFileApplication(DEBFILE_PATH_CORRUPT)
        debfiledetails = debfileapplication.get_details(self.db)
        self.assertEquals(debfiledetails.pkg_state, PkgStates.NOT_FOUND)

    def test_get_summary(self):
        debfileapplication = DebFileApplication(DEBFILE_PATH)
        debfiledetails = debfileapplication.get_details(self.db)
        self.assertEquals(debfiledetails.summary, DEBFILE_SUMMARY)

    def test_get_version(self):
        debfileapplication = DebFileApplication(DEBFILE_PATH)
        debfiledetails = debfileapplication.get_details(self.db)
        self.assertEquals(debfiledetails.version, DEBFILE_VERSION)

    def test_get_installed_size_when_uninstalled(self):
        debfileapplication = DebFileApplication(DEBFILE_PATH)
        debfiledetails = debfileapplication.get_details(self.db)
        self.assertEquals(debfiledetails.installed_size, 0)

    def test_get_warning(self):
        debfileapplication = DebFileApplication(DEBFILE_PATH)
        debfiledetails = debfileapplication.get_details(self.db)
        self.assertEquals(debfiledetails.warning, DEBFILE_WARNING)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()

