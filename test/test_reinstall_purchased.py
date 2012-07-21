#!/usr/bin/python

import apt_pkg
import apt
import logging
import json
import unittest
import xapian

from mock import patch
from piston_mini_client import PistonResponseObject
from testutils import setup_test_env
setup_test_env()

from softwarecenter.enums import (XapianValues,
                                  AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME,
                                  PURCHASED_NEEDS_REINSTALL_MAGIC_CHANNEL_NAME,
                                  )
from softwarecenter.db.database import StoreDatabase
from softwarecenter.db.update import (
    add_from_purchased_but_needs_reinstall_data,
    SCAPurchasedApplicationParser,
    SCAApplicationParser,
    )

# Example taken from running:
# PYTHONPATH=. utils/piston-helpers/piston_generic_helper.py --output=pickle \
#           --debug --needs-auth SoftwareCenterAgentAPI subscriptions_for_me
# then:
#    f = open('my_subscriptions.pickle')
#    subscriptions = pickle.load(f)
#    completed_subs = [subs for subs in subscriptions if subs.state=='Complete']
#    completed_subs[0].__dict__
SUBSCRIPTIONS_FOR_ME_JSON = """
[
    {
         "deb_line": "deb https://username:random3atoken@private-ppa.launchpad.net/commercial-ppa-uploaders/photobomb/ubuntu natty main",
         "purchase_price": "2.99",
         "purchase_date": "2011-09-16 06:37:52",
         "state": "Complete",
         "failures": [],
         "open_id": "https://login.ubuntu.com/+id/ABCDEF",
         "application": {
              "archive_id": "commercial-ppa-uploaders/photobomb",
              "signing_key_id": "1024R/75254D99",
              "name": "Photobomb",
              "package_name": "photobomb",
              "description": "Easy and Social Image Editor\\nPhotobomb give you easy access to images in your social networking feeds, pictures on your computer and peripherals, and pictures on the web, and let\'s you draw, write, crop, combine, and generally have a blast mashing \'em all up. Then you can save off your photobomb, or tweet your creation right back to your social network.",
              "version": "1.2.1"
         },
         "distro_series": {"code_name": "natty", "version": "11.04"}
    }
]
"""
# Taken directly from:
# https://software-center.ubuntu.com/api/2.0/applications/en/ubuntu/oneiric/i386/
AVAILABLE_APPS_JSON = """
[
    {
        "archive_id": "commercial-ppa-uploaders/fluendo-dvd",
        "signing_key_id": "1024R/75254D99",
        "license": "Proprietary",
        "name": "Fluendo DVD Player",
        "package_name": "fluendo-dvd",
        "support_url": "",
        "series": {
            "maverick": [
                "i386",
                "amd64"
            ],
            "natty": [
                "i386",
                "amd64"
            ],
            "oneiric": [
                "i386",
                "amd64"
            ]
        },
        "price": "24.95",
        "demo": null,
        "date_published": "2011-12-05 18:43:21.653868",
        "status": "Published",
        "channel": "For Purchase",
        "icon_data": "...",
        "department": [
            "Sound & Video"
        ],
        "archive_root": "https://private-ppa.launchpad.net/",
        "screenshot_url": "http://software-center.ubuntu.com/site_media/screenshots/2011/05/fluendo-dvd-maverick_.png",
        "tos_url": "https://software-center.ubuntu.com/licenses/3/",
        "icon_url": "http://software-center.ubuntu.com/site_media/icons/2011/05/fluendo-dvd.png",
        "categories": "AudioVideo",
        "description": "Play DVD-Videos\\r\\n\\r\\nFluendo DVD Player is a software application specially designed to\\r\\nreproduce DVD on Linux/Unix platforms, which provides end users with\\r\\nhigh quality standards.\\r\\n\\r\\nThe following features are provided:\\r\\n* Full DVD Playback\\r\\n* DVD Menu support\\r\\n* Fullscreen support\\r\\n* Dolby Digital pass-through\\r\\n* Dolby Digital 5.1 output and stereo downmixing support\\r\\n* Resume from last position support\\r\\n* Subtitle support\\r\\n* Audio selection support\\r\\n* Multiple Angles support\\r\\n* Support for encrypted discs\\r\\n* Multiregion, works in all regions\\r\\n* Multiple video deinterlacing algorithms",
        "version": "1.2.1"
    }
]
"""


class TestPurchased(unittest.TestCase):
    """ tests the store database """

    def _make_available_for_me_list(self):
        my_subscriptions = json.loads(SUBSCRIPTIONS_FOR_ME_JSON)
        return list(
            PistonResponseObject.from_dict(subs) for subs in my_subscriptions)

    def setUp(self):
        # use fixture apt data
        apt_pkg.config.set("APT::Architecture", "i386")
        apt_pkg.config.set("Dir::State::status",
                           "./data/appdetails/var/lib/dpkg/status")
        # create mocks
        self.available_to_me = self._make_available_for_me_list()
        self.cache = apt.Cache()

    def test_reinstall_purchased_mock(self):
        # test if the mocks are ok
        self.assertEqual(len(self.available_to_me), 1)
        self.assertEqual(
            self.available_to_me[0].application['package_name'], "photobomb")

    def test_reinstall_purchased_xapian(self):
        db = StoreDatabase("/var/cache/software-center/xapian", self.cache)
        db.open(use_axi=False)
        # now create purchased debs xapian index (in memory because
        # we store the repository passwords in here)
        old_db_len = len(db)
        query = add_from_purchased_but_needs_reinstall_data(
            self.available_to_me, db, self.cache)
        # ensure we have a new item (the available for reinstall one)
        self.assertEqual(len(db), old_db_len+1)
        # query
        enquire = xapian.Enquire(db.xapiandb)
        enquire.set_query(query)
        matches = enquire.get_mset(0, len(db))
        self.assertEqual(len(matches), 1)
        for m in matches:
            doc = db.xapiandb.get_document(m.docid)
            self.assertEqual(doc.get_value(XapianValues.PKGNAME), "photobomb")
            self.assertEqual(
                doc.get_value(XapianValues.ARCHIVE_SIGNING_KEY_ID),
                "1024R/75254D99")
            self.assertEqual(doc.get_value(XapianValues.ARCHIVE_DEB_LINE),
                "deb https://username:random3atoken@"
                 "private-ppa.launchpad.net/commercial-ppa-uploaders"
                 "/photobomb/ubuntu precise main")


class SCAApplicationParserTestCase(unittest.TestCase):

    def _make_application_parser(self, piston_application=None):
        if piston_application is None:
            piston_application = PistonResponseObject.from_dict(
                json.loads(AVAILABLE_APPS_JSON)[0])
        return SCAApplicationParser(piston_application)

    def test_parses_application_from_available_apps(self):
        parser = self._make_application_parser()
        inverse_map = dict(
            (val, key) for key, val in SCAApplicationParser.MAPPING.items())

        # Delete the keys which are not yet provided via the API:
        del(inverse_map['video_embedded_html_url'])

        for key in inverse_map:
            self.assertTrue(parser.has_option_desktop(inverse_map[key]),
                            "missing key from inverse_map '%s'" % key)
            self.assertEqual(
                getattr(parser.sca_application, key),
                parser.get_desktop(inverse_map[key]))

    def test_name_not_updated_for_non_purchased_apps(self):
        parser = self._make_application_parser()

        self.assertEqual('Fluendo DVD Player', parser.get_desktop('Name'))

    def test_keys_not_provided_by_api(self):
        parser = self._make_application_parser()

        self.assertFalse(parser.has_option_desktop('Video-Url'))
        self.assertTrue(parser.has_option_desktop('Type'))
        self.assertEqual('Application', parser.get_desktop('Type'))

    def test_thumbnail_is_screenshot(self):
        parser = self._make_application_parser()

        self.assertEqual(
            "http://software-center.ubuntu.com/site_media/screenshots/"
            "2011/05/fluendo-dvd-maverick_.png",
            parser.get_desktop('Thumbnail-Url'))

    def test_extracts_description(self):
        parser = self._make_application_parser()

        self.assertEqual("Play DVD-Videos", parser.get_desktop('Comment'))
        self.assertEqual(
            "Fluendo DVD Player is a software application specially designed "
            "to\r\nreproduce DVD on Linux/Unix platforms, which provides end "
            "users with\r\nhigh quality standards.\r\n\r\nThe following "
            "features are provided:\r\n* Full DVD Playback\r\n* DVD Menu "
            "support\r\n* Fullscreen support\r\n* Dolby Digital pass-through"
            "\r\n* Dolby Digital 5.1 output and stereo downmixing support\r\n"
            "* Resume from last position support\r\n* Subtitle support\r\n"
            "* Audio selection support\r\n* Multiple Angles support\r\n"
            "* Support for encrypted discs\r\n"
            "* Multiregion, works in all regions\r\n"
            "* Multiple video deinterlacing algorithms",
            parser.get_desktop('Description'))

    def test_desktop_categories_uses_department(self):
        parser = self._make_application_parser()

        self.assertEqual([u'DEPARTMENT:Sound & Video', "AudioVideo"],
            parser.get_desktop_categories())

    def test_desktop_categories_no_department(self):
        piston_app = PistonResponseObject.from_dict(
            json.loads(AVAILABLE_APPS_JSON)[0])
        del(piston_app.department)
        parser = self._make_application_parser(piston_app)

        self.assertEqual(["AudioVideo"], parser.get_desktop_categories())

    def test_magic_channel(self):
        parser = self._make_application_parser()

        self.assertEqual(
            AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME,
            parser.get_desktop('Channel'))


class SCAPurchasedApplicationParserTestCase(unittest.TestCase):

    def _make_application_parser(self, piston_subscription=None):
        if piston_subscription is None:
            piston_subscription = PistonResponseObject.from_dict(
                json.loads(SUBSCRIPTIONS_FOR_ME_JSON)[0])

        return SCAPurchasedApplicationParser(piston_subscription)

    def setUp(self):
        get_distro_patcher = patch('softwarecenter.db.update.get_distro')
        self.addCleanup(get_distro_patcher.stop)
        mock_get_distro = get_distro_patcher.start()
        mock_get_distro.return_value.get_codename.return_value = 'quintessential'

    def test_get_desktop_subscription(self):
        parser = self._make_application_parser()

        expected_results = {
             "X-AppInstall-Deb-Line": "deb https://username:random3atoken@"
                         "private-ppa.launchpad.net/commercial-ppa-uploaders"
                         "/photobomb/ubuntu quintessential main",
             "X-AppInstall-Deb-Line-Orig": 
                         "deb https://username:random3atoken@"
                         "private-ppa.launchpad.net/commercial-ppa-uploaders"
                         "/photobomb/ubuntu natty main",
             "X-AppInstall-Purchased-Date": "2011-09-16 06:37:52",
            }
        for key in expected_results:
            result = parser.get_desktop(key)
            self.assertEqual(expected_results[key], result)

    def test_get_desktop_application(self):
        # The parser passes application attributes through to
        # an application parser for handling.
        parser = self._make_application_parser()

        # We're testing here also that the name is updated automatically.
        expected_results = {
            "Name": "Photobomb (already purchased)",
            "Package": "photobomb",
            "Signing-Key-Id": "1024R/75254D99",
            "PPA": "commercial-ppa-uploaders/photobomb",
            }
        for key in expected_results.keys():
            result = parser.get_desktop(key)
            self.assertEqual(expected_results[key], result)

    def test_has_option_desktop_includes_app_keys(self):
        # The SCAPurchasedApplicationParser handles application keys also
        # (passing them through to the composited application parser).
        parser = self._make_application_parser()

        for key in ('Name', 'Package', 'Signing-Key-Id', 'PPA'):
            self.assertTrue(parser.has_option_desktop(key))
        for key in ('Deb-Line', 'Purchased-Date'):
            self.assertTrue(parser.has_option_desktop(key),
                    'Key: {0} was not an option.'.format(key))

    def test_license_key_present(self):
        piston_subscription = PistonResponseObject.from_dict(
            json.loads(SUBSCRIPTIONS_FOR_ME_JSON)[0])
        piston_subscription.license_key = 'abcd'
        piston_subscription.license_key_path = '/foo'
        parser = self._make_application_parser(piston_subscription)

        self.assertTrue(parser.has_option_desktop('License-Key'))
        self.assertTrue(parser.has_option_desktop('License-Key-Path'))
        self.assertEqual('abcd', parser.get_desktop('License-Key'))
        self.assertEqual('/foo', parser.get_desktop('License-Key-Path'))

    def test_license_key_not_present(self):
        parser = self._make_application_parser()

        self.assertFalse(parser.has_option_desktop('License-Key'))
        self.assertFalse(parser.has_option_desktop('License-Key-Path'))

    def test_magic_channel(self):
        parser = self._make_application_parser()

        self.assertEqual(
            PURCHASED_NEEDS_REINSTALL_MAGIC_CHANNEL_NAME,
            parser.get_desktop('Channel'))

    def test_will_handle_supported_distros_when_available(self):
        # When the fix for bug 917109 reaches production, we will be
        # able to use the supported series.
        parser = self._make_application_parser()
        supported_distros = {
            "maverick": [
                "i386",
                "amd64"
                ],
            "natty": [
                "i386",
                "amd64"
                ],
            }
        parser.sca_application.series = supported_distros

        self.assertEqual(
            supported_distros,
            parser.get_desktop('Supported-Distros'))

    def test_update_debline_other_series(self):
        orig_debline = (
            "deb https://username:random3atoken@"
            "private-ppa.launchpad.net/commercial-ppa-uploaders"
            "/photobomb/ubuntu karmic main")
        expected_debline = (
            "deb https://username:random3atoken@"
            "private-ppa.launchpad.net/commercial-ppa-uploaders"
            "/photobomb/ubuntu quintessential main")

        self.assertEqual(expected_debline,
            SCAPurchasedApplicationParser.update_debline(orig_debline))

    def test_update_debline_with_pocket(self):
        orig_debline = (
            "deb https://username:random3atoken@"
            "private-ppa.launchpad.net/commercial-ppa-uploaders"
            "/photobomb/ubuntu karmic-security main")
        expected_debline = (
            "deb https://username:random3atoken@"
            "private-ppa.launchpad.net/commercial-ppa-uploaders"
            "/photobomb/ubuntu quintessential-security main")

        self.assertEqual(expected_debline,
            SCAPurchasedApplicationParser.update_debline(orig_debline))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
