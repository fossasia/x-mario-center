#!/usr/bin/python

import os
import unittest

from collections import defaultdict
from functools import partial

from mock import Mock

from testutils import FakedCache, get_mock_options, setup_test_env
setup_test_env()

import softwarecenter.paths
from softwarecenter.db import DebFileApplication, DebFileOpenError
from softwarecenter.enums import PkgStates, SearchSeparators
from softwarecenter.ui.gtk3 import app


class ParsePackagesArgsTestCase(unittest.TestCase):
    """Test suite for the parse_packages_args helper."""

    pkg_name = 'foo'

    def transform_for_test(self, items):
        """Transform a sequence into a comma separated string."""
        return app.SEARCH_PREFIX + SearchSeparators.REGULAR.join(items)

    def do_check(self, apps, items=None):
        """Check that the available_pane was shown."""
        if items is None:
            items = self.transform_for_test(apps)

        search_text, result_app = app.parse_packages_args(items)

        self.assertEqual(SearchSeparators.REGULAR.join(apps), search_text)
        self.assertIsNone(result_app)

    def test_empty(self):
        """Pass an empty argument, show the 'available' view."""
        self.do_check(apps=())

    def test_single_empty_item(self):
        """Pass a single empty item, show the 'available' view."""
        self.do_check(apps=('',))

    def test_single_item(self):
        """Pass a single item, show the 'available' view."""
        self.do_check(apps=(self.pkg_name,))

    def test_two_items(self):
        """Pass two items, show the 'available' view."""
        self.do_check(apps=(self.pkg_name, 'bar'))

    def test_several_items(self):
        """Pass several items, show the 'available' view."""
        self.do_check(apps=(self.pkg_name, 'firefox', 'software-center'))


class ParsePackageArgsAsFileTestCase(unittest.TestCase):

    def test_item_is_a_file(self):
        """Pass an item that is an existing file."""
        # pass a real deb here
        fname = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "data", "test_debs", "gdebi-test1.deb")
        assert os.path.exists(fname)
        # test once as string and as list
        for items in ( fname, [fname] ):
            search_text, result_app = app.parse_packages_args(fname)
            self.assertIsInstance(result_app, DebFileApplication)

    def test_item_is_invalid_file(self):
        """ Pass an invalid file item """
        fname = __file__
        assert os.path.exists(fname)
        self.assertRaises(DebFileOpenError, app.parse_packages_args, fname)


class ParsePackagesWithAptPrefixTestCase(ParsePackagesArgsTestCase):

    installed = None

    def setUp(self):
        super(ParsePackagesWithAptPrefixTestCase, self).setUp()

        self.cache = FakedCache()
        self.db = app.StoreDatabase(cache=self.cache)

        assert self.pkg_name not in self.cache
        if self.installed is not None:
            mock_cache_entry = Mock()
            mock_cache_entry.website = None
            mock_cache_entry.license = None
            mock_cache_entry.installed_files = []
            mock_cache_entry.candidate = Mock()
            mock_cache_entry.candidate.version = '1.0'
            mock_cache_entry.candidate.description = 'A nonsense app.'
            mock_cache_entry.candidate.origins = ()
            mock_cache_entry.versions = (Mock(),)
            mock_cache_entry.versions[0].version = '0.99'
            mock_cache_entry.versions[0].origins = (Mock(),)
            mock_cache_entry.versions[0].origins[0].archive = 'test'
            mock_cache_entry.is_installed = self.installed
            if self.installed:
                mock_cache_entry.installed = Mock()
                mock_cache_entry.installed.version = '0.90'
                mock_cache_entry.installed.installed_size = 0
            else:
                mock_cache_entry.installed = None

            self.cache[self.pkg_name] = mock_cache_entry
            self.addCleanup(self.cache.pop, self.pkg_name)


    def transform_for_test(self, items):
        """Do nothing."""
        return items

    def check_package_availability(self, name):
        """Check whether the package 'name' is available."""
        if name not in self.cache:
            state = PkgStates.NOT_FOUND
        elif self.cache[name].installed:
            state = PkgStates.INSTALLED
        else:
            state = PkgStates.UNINSTALLED
        return state

    def do_check(self, apps, items=None):
        """Check that the available_pane was shown."""
        if items is None:
            items = self.transform_for_test(apps)

        search_text, result_app = app.parse_packages_args(items)

        if apps and len(apps) == 1 and apps[0] and not os.path.isfile(apps[0]):
            self.assertIsNotNone(result_app)
            app_details = result_app.get_details(self.db)

            self.assertEqual(apps[0], app_details.name)
            state = self.check_package_availability(app_details.name)
            self.assertEqual(state, app_details.pkg_state)
        else:
            self.assertIsNone(result_app)

        if apps and (len(apps) > 1 or os.path.isfile(apps[0])):
            self.assertEqual(SearchSeparators.PACKAGE.join(apps), search_text)
        else:
            self.assertEqual('', search_text)

    def test_item_with_prefix(self):
        """Pass a item with the item prefix."""
        for prefix in ('apt:', 'apt://', 'apt:///'):
            for case in (self.pkg_name, app.PACKAGE_PREFIX + self.pkg_name):
                self.do_check(apps=(case,), items=(prefix + case,))


class ParsePackagesNotInstalledTestCase(ParsePackagesWithAptPrefixTestCase):
    """Test suite for parsing/searching/loading package lists."""

    installed = False


class ParsePackagesInstalledTestCase(ParsePackagesWithAptPrefixTestCase):
    """Test suite for parsing/searching/loading package lists."""

    installed = True


class ParsePackagesArgsStringTestCase(ParsePackagesWithAptPrefixTestCase):
    """Test suite for parsing/loading package lists from strings."""

    def transform_for_test(self, items):
        """Transform a sequence into a comma separated string."""
        return SearchSeparators.PACKAGE.join(items)


class AppTestCase(unittest.TestCase):
    """Test suite for the app module."""

    def setUp(self):
        super(AppTestCase, self).setUp()
        self.called = defaultdict(list)
        self.addCleanup(self.called.clear)

        orig = app.SoftwareCenterAppGtk3.START_DBUS
        self.addCleanup(setattr, app.SoftwareCenterAppGtk3, 'START_DBUS', orig)
        app.SoftwareCenterAppGtk3.START_DBUS = False

        orig = app.get_pkg_info
        self.addCleanup(setattr, app, 'get_pkg_info', orig)
        app.get_pkg_info = lambda: FakedCache()

        datadir = softwarecenter.paths.datadir
        xapianpath = softwarecenter.paths.XAPIAN_BASE_PATH
        options = get_mock_options()
        self.app = app.SoftwareCenterAppGtk3(datadir, xapianpath, options)
        self.addCleanup(self.app.destroy)

        self.app.cache.open()

        # connect some signals of interest
        cid = self.app.installed_pane.connect('installed-pane-created',
                partial(self.track_calls, 'pane-created'))
        self.addCleanup(self.app.installed_pane.disconnect, cid)

        cid = self.app.available_pane.connect('available-pane-created',
                partial(self.track_calls, 'pane-created'))
        self.addCleanup(self.app.available_pane.disconnect, cid)

    def track_calls(self, name, *a, **kw):
        """Record the callback for 'name' using 'args' and 'kwargs'."""
        self.called[name].append((a, kw))


class ShowPackagesTestCase(AppTestCase):
    """Test suite for parsing/searching/loading package lists."""

    def do_check(self, packages, search_text):
        """Check that the available_pane was shown."""
        self.app.show_available_packages(packages=packages)

        self.assertEqual(self.called,
            {'pane-created': [((self.app.available_pane,), {})]})

        actual = self.app.available_pane.searchentry.get_text()
        self.assertEqual(search_text, actual,
            'Expected search text %r (got %r instead) for packages %r.' %
            (search_text, actual, packages))

        self.assertIsNone(self.app.available_pane.app_details_view.app_details)

    def test_show_available_packages_search_prefix(self):
        """Check that the available_pane was shown."""
        self.do_check(packages='search:foo,bar baz', search_text='foo bar baz')

    def test_show_available_packages_apt_prefix(self):
        """Check that the available_pane was shown."""
        for prefix in ('apt:', 'apt://', 'apt:///'):
            self.do_check(packages=prefix + 'foo,bar,baz',
                          search_text='foo,bar,baz')


class ShowPackagesOnePackageTestCase(AppTestCase):
    """Test suite for parsing/searching/loading package lists."""

    pkg_name = 'foo'
    installed = None

    def setUp(self):
        super(ShowPackagesOnePackageTestCase, self).setUp()
        assert self.pkg_name not in self.app.cache
        if self.installed is not None:
            mock_cache_entry = Mock()
            mock_cache_entry.website = None
            mock_cache_entry.license = None
            mock_cache_entry.installed_files = []
            mock_cache_entry.candidate = Mock()
            mock_cache_entry.candidate.version = '1.0'
            mock_cache_entry.candidate.description = 'A nonsense app.'
            mock_cache_entry.candidate.origins = ()
            mock_cache_entry.versions = (Mock(),)
            mock_cache_entry.versions[0].version = '0.99'
            mock_cache_entry.versions[0].origins = (Mock(),)
            mock_cache_entry.versions[0].origins[0].archive = 'test'
            mock_cache_entry.is_installed = self.installed
            if self.installed:
                mock_cache_entry.installed = Mock()
                mock_cache_entry.installed.version = '0.90'
                mock_cache_entry.installed.installed_size = 0
            else:
                mock_cache_entry.installed = None

            self.app.cache[self.pkg_name] = mock_cache_entry
            self.addCleanup(self.app.cache.pop, self.pkg_name)

    def check_package_availability(self, name):
        """Check whether the package 'name' is available."""
        pane = self.app.available_pane
        if name not in self.app.cache:
            state = PkgStates.NOT_FOUND
        elif self.app.cache[name].installed:
            state = PkgStates.INSTALLED
            pane = self.app.installed_pane
        else:
            state = PkgStates.UNINSTALLED

        self.assertEqual(state, pane.app_details_view.app_details.pkg_state)

        return pane

    def test_show_available_packages(self):
        """Check that the available_pane was shown."""
        self.app.show_available_packages(packages=self.pkg_name)

        expected_pane = self.check_package_availability(self.pkg_name)
        name = expected_pane.app_details_view.app_details.name
        self.assertEqual(self.pkg_name, name)

        self.assertEqual('', self.app.available_pane.searchentry.get_text())

        self.assertEqual(self.called,
            {'pane-created': [((expected_pane,), {})]})


class ShowPackagesNotInstalledTestCase(ShowPackagesOnePackageTestCase):
    """Test suite for parsing/searching/loading package lists."""

    installed = False


class ShowPackagesInstalledTestCase(ShowPackagesOnePackageTestCase):
    """Test suite for parsing/searching/loading package lists."""

    installed = True


if __name__ == "__main__":
    # avoid spawning recommender-agent, reviews, software-center-agent etc,
    # cuts ~5s or so
    os.environ["SOFTWARE_CENTER_DISABLE_SPAWN_HELPER"] = "1"
    unittest.main()
