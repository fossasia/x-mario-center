#!/usr/bin/python

import logging
import unittest

from testutils import setup_test_env
setup_test_env()
from softwarecenter.db.pkginfo import _Package, _Version
from softwarecenter.db.pkginfo_impl.aptcache import AptCache
# from softwarecenter.db.pkginfo_impl.packagekit import PackagekitInfo

class TestPkgInfoAptCache(unittest.TestCase):

    # the backend that we want to test
    klass = AptCache

    def setUp(self):
        self.pkginfo = self.klass()
        self.pkginfo.open()

    def test_pkg_version(self):
        pkginfo = self.pkginfo

        pkg = pkginfo['coreutils']
        self.assertTrue(isinstance(pkg, _Package))
        self.assertTrue(pkg.is_installed)
        self.assertTrue(isinstance(pkg.installed, _Version))
        self.assertTrue(isinstance(pkg.candidate, _Version))

        self.assertNotEqual(len(pkg.installed.origins), 0)
        self.assertNotEqual(len(pkg.installed.summary), '')
        self.assertNotEqual(len(pkg.installed.description), '')
        self.assertNotEqual(pkg.candidate.size, 0)
        self.assertNotEqual(pkg.candidate.installed_size, 0)

        for v in pkg.versions:
            self.assertTrue(isinstance(v, _Version))

    def test_pkg_info(self):
        pkginfo = self.pkginfo
        self.assertTrue(pkginfo.is_installed("coreutils"))
        self.assertTrue(pkginfo.is_available("bash"))
        self.assertTrue('GNU Bourne Again' in pkginfo.get_summary('bash'))
        self.assertTrue(pkginfo.get_description('bash') != '')
        self.assertTrue(pkginfo.get_installed("coreutils") is not None)
        self.assertTrue(pkginfo.get_candidate("coreutils") is not None)
        self.assertTrue(len(pkginfo.get_versions("coreutils")) != 0)

        self.assertTrue('coreutils' in pkginfo)

        # test getitem
        pkg = pkginfo['coreutils']
        self.assertTrue(pkg is not None)
        self.assertTrue(pkg.is_installed)
        self.assertTrue(len(pkg.versions) != 0)
        self.assertEqual(pkg.website, 'http://gnu.org/software/coreutils')

    def test_section(self):
        self.assertEqual(self.pkginfo.get_section('bash'), 'shells')

    def test_origins(self):
        self.assertTrue(len(self.pkginfo.get_origins("firefox")) > 0)

    def test_addons(self):
        pkginfo = self.pkginfo
        self.assertTrue(len(pkginfo.get_addons("firefox")) > 0)

    @unittest.skip("disabled due to invalid fixture data")
    def test_removal(self):
        pkginfo = self.pkginfo
        pkg = pkginfo['coreutils']
        self.assertTrue(len(pkginfo.get_packages_removed_on_install(pkg)) == 0)
        self.assertTrue(len(pkginfo.get_packages_removed_on_remove(pkg)) != 0)

    def test_installed_files(self):
        pkg = self.pkginfo['coreutils']
        files = pkg.installed_files
        self.assertTrue('/usr/bin/whoami' in files)

# FIXME: Enable packagekit tests when implemented
# class TestPkgInfoPackagekit(TestPkgInfoAptCache):
#     klass = PackagekitInfo
	
#     # FIXME: implement this in PK as well
#     def test_addons(self):
#         pass
#     def test_section(self):
#         pass
#     def test_removal(self):
#         pass

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
