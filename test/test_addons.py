#!/usr/bin/python


import unittest

from testutils import setup_test_env
setup_test_env()

from softwarecenter.db.pkginfo import get_pkg_info

class TestSCAddons(unittest.TestCase):
    """ tests the addons """

    def setUp(self):
        self.cache = get_pkg_info()
        self.cache.open()

    @unittest.skip("disabled until fixture setup is done")
    def test_get_addons_simple(self):
        # 7zip
        res = self.cache.get_addons("p7zip-full", ignore_installed=False)
        self.assertEqual(res, ([], ["p7zip-rar"]))
        # apt 
        (recommends, suggests) = self.cache.get_addons(
            "apt", ignore_installed=False)
        self.assertEqual(set(suggests), set(
                ['lzma', 'bzip2', 'apt-doc', 'wajig', 'aptitude', 'dpkg-dev', 
                 'python-apt', 'synaptic']))
        # synaptic: FIXME: use something that changes less often
        #(recommends, suggests) = self.cache.get_addons(
        #    "synaptic", ignore_installed=False)
        #self.assertEqual(set(recommends), set(
        #        ['libgtk2-perl', 'rarian-compat', 'software-properties-gtk']))
        #self.assertEqual(set(suggests), set(
        #        ["apt-xapian-index", "dwww", "deborphan", "menu"]))


    def test_enhances(self):
        res = self.cache.get_addons("gwenview")
        self.assertEqual(res, ([], ["svgpart", "kipi-plugins"]))

    def test_enhances_with_virtual_pkgs(self):
        res = self.cache.get_addons("bibletime")
        self.assertTrue("sword-text-tr" in res[1])
        self.assertTrue(len(res[1]) > 5)
        

    def test_lonley_dependency(self):
        # gets additional recommends via lonely dependency
        # for arduino-core, there is a dependency on avrdude, nothing
        # else depends on avrdude other than arduino-core, so
        # we want to get the recommends/suggests/enhances for
        # this package too
        # FIXME: why only for "lonley" dependencies and not all?
        res = self.cache.get_addons("arduino-core")
        self.assertEqual(res, ([], ["avrdude-doc", "arduino-mk"]))

    def test_addons_removal_included_depends(self):
        res = self.cache.get_addons("amule-gnome-support")
        self.assertEqual(res, (['amule-daemon'], []))

        

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
