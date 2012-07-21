#!/usr/bin/python

import datetime
import glob
import multiprocessing
import os
import stat
import subprocess
import shutil
import tempfile
import time
import unittest

from mock import patch

from testutils import setup_test_env
setup_test_env()
from softwarecenter.utils import (decode_xml_char_reference,
                                  release_filename_in_lists_from_deb_line,
                                  get_http_proxy_string_from_libproxy,
                                  )
from softwarecenter.testutils import do_events


class TestSCUtils(unittest.TestCase):
    """ tests the sc utils """

    def test_encode(self):
        xml = "What&#x2019;s New"
        python = u"What\u2019s New"
        self.assertEqual(decode_xml_char_reference(xml), python)
        # fails currently 
        #self.assertEqual(encode_for_xml(python), xml)

    def test_lists_filename(self):
        debline = "deb http://foo:pass@security.ubuntu.com/ubuntu maverick-security main restricted"
        self.assertEqual(release_filename_in_lists_from_deb_line(debline),
                         "security.ubuntu.com_ubuntu_dists_maverick-security_Release")

    def test_get_http_proxy_from_gsettings(self):
        from softwarecenter.utils import get_http_proxy_string_from_gsettings
        # FIXME: do something more meaningful here once I figured out
        #        how to create a private fake gsettings
        proxy = get_http_proxy_string_from_gsettings()
        self.assertTrue(type(proxy) in [type(None), type("")])

    # disabled, we don't use libproxy currently, its really rather
    # out of date
    def disabled_test_get_http_proxy_from_libproxy(self):
        # test url
        url = "http://archive.ubuntu.com"
        # ensure we look at environment first
        os.environ["PX_CONFIG_ORDER"] = "config_envvar"
        # normal proxy
        os.environ["http_proxy"] = "http://localhost:3128/"
        proxy = get_http_proxy_string_from_libproxy(url)
        self.assertEqual(proxy, "http://localhost:3128/")
        # direct
        os.environ["http_proxy"] = ""
        proxy = get_http_proxy_string_from_libproxy(url)
        self.assertEqual(proxy, "")
        # user/pass
        os.environ["http_proxy"] = "http://user:pass@localhost:3128/"
        proxy = get_http_proxy_string_from_libproxy(url)
        self.assertEqual(proxy, "http://user:pass@localhost:3128/")

    def test_get_title_from_html(self):
        from softwarecenter.utils import get_title_from_html
        html = """
<html>
<head>
<title>Title &amp; text</title>
</head>
<body>
 <h1>header1</h1>
</body>
</html>"""
        # get the title from the html
        self.assertEqual(get_title_from_html(html),
                         "Title & text")
        # fallback to the first h1 if there is no title
        html = "<body><h1>foo &gt;</h1><h1>bar</h1></body>"
        self.assertEqual(get_title_from_html(html), "foo >")
        # broken
        html = "<sadfsa>dsf"
        self.assertEqual(get_title_from_html(html),
                         "")
        # not supported to have sub-html tags in the extractor
        html = "<body><h1>foo <emph>bar</emph></h1></body>"
        self.assertEqual(get_title_from_html(html),
                         "")
        html = "<body><h1>foo <emph>bar</emph> x</h1><h2>some text</h2></body>"
        self.assertEqual(get_title_from_html(html),
                         "")

    def test_no_display_desktop_file(self):
        from softwarecenter.utils import is_no_display_desktop_file
        d = "/usr/share/app-install/desktop/wine1.4:wine.desktop"
        self.assertTrue(is_no_display_desktop_file(d))
        d = "/usr/share/app-install/desktop/software-center:ubuntu-software-center.desktop"
        self.assertFalse(is_no_display_desktop_file(d))

    def test_split_icon_ext(self):
        from softwarecenter.utils import split_icon_ext
        for unchanged in ["foo.bar.baz", "foo.bar", "foo", 
                          "foo.pngx", "foo.png.xxx"]:
            self.assertEqual(split_icon_ext(unchanged), unchanged)
        for changed in ["foo.png", "foo.tiff", "foo.jpg", "foo.jpeg"]:
            self.assertEqual(split_icon_ext(changed), 
                            os.path.splitext(changed)[0])

    def test_get_nice_date_string(self):
        from softwarecenter.utils import get_nice_date_string

        now = datetime.datetime.utcnow()

        ten_secs_ago = now + datetime.timedelta(seconds=-10)
        self.assertEqual(get_nice_date_string(ten_secs_ago), 'a few minutes ago')

        two_mins_ago = now + datetime.timedelta(minutes=-2)
        self.assertEqual(get_nice_date_string(two_mins_ago), '2 minutes ago')

        under_a_day = now + datetime.timedelta(hours=-23, minutes=-59, seconds=-59)
        self.assertEqual(get_nice_date_string(under_a_day), '23 hours ago')

        under_a_week = now + datetime.timedelta(days=-4, hours=-23, minutes=-59, seconds=-59)
        self.assertEqual(get_nice_date_string(under_a_week), '4 days ago')

        over_a_week = now + datetime.timedelta(days=-7)
        self.assertEqual(get_nice_date_string(over_a_week), over_a_week.isoformat().split('T')[0])
        
    def test_get_uuid(self):
        from softwarecenter.utils import get_uuid
        uuid = get_uuid()
        self.assertTrue(uuid and len(uuid) > 0)

    def test_clear_credentials(self):
        from softwarecenter.utils import clear_token_from_ubuntu_sso_sync
        clear_token_from_ubuntu_sso_sync("fo")
        do_events()

    def test_make_string_from_list(self):
        from softwarecenter.utils import make_string_from_list
        base = "There was a problem posting this review to %s (omg!)"
        # test the various forms
        l = ["twister"]
        self.assertEqual(
            make_string_from_list(base, l),
            "There was a problem posting this review to twister (omg!)")
        # two
        l = ["twister", "factbook"]
        self.assertEqual(
            make_string_from_list(base, l),
            "There was a problem posting this review to twister and factbook (omg!)")
        # three
        l = ["twister", "factbook", "identi.catz"]
        self.assertEqual(
            make_string_from_list(base, l),
            "There was a problem posting this review to twister, factbook and identi.catz (omg!)")
        # four
        l = ["twister", "factbook", "identi.catz", "baz"]
        self.assertEqual(
            make_string_from_list(base, l),
            "There was a problem posting this review to twister, factbook, identi.catz and baz (omg!)")

    def test_capitalize_first_word(self):
        from softwarecenter.utils import capitalize_first_word
        test_synopsis = "feature-rich console based todo list manager"
        capitalized = capitalize_first_word(test_synopsis)
        self.assertTrue(
            capitalized == "Feature-rich console based todo list manager")
        test_synopsis = "MPlayer's Movie Encoder"
        capitalized = capitalize_first_word(test_synopsis)
        self.assertTrue(
            capitalized == "MPlayer's Movie Encoder")
        # ensure it does not crash for empty strings, LP: #1002271
        self.assertEqual(capitalize_first_word(""), "")
            
    def test_ensure_file_writable_and_delete_if_not(self):
        from softwarecenter.utils import ensure_file_writable_and_delete_if_not
        from tempfile import NamedTemporaryFile
        # first test that a non-writable file (0400) is deleted
        test_file_not_writeable = NamedTemporaryFile()
        os.chmod(test_file_not_writeable.name, stat.S_IRUSR)
        self.assertFalse(os.access(test_file_not_writeable.name, os.W_OK))
        ensure_file_writable_and_delete_if_not(test_file_not_writeable.name)
        self.assertFalse(os.path.exists(test_file_not_writeable.name))
        # then test that a writable file (0600) is not deleted
        test_file_writeable = NamedTemporaryFile()
        os.chmod(test_file_writeable.name, stat.S_IRUSR|stat.S_IWUSR)
        self.assertTrue(os.access(test_file_writeable.name, os.W_OK))
        ensure_file_writable_and_delete_if_not(test_file_writeable.name)
        self.assertTrue(os.path.exists(test_file_writeable.name))

    def test_safe_makedirs(self):
        from softwarecenter.utils import safe_makedirs
        from tempfile import mkdtemp
        tmp = mkdtemp()
        # create base dir
        target = os.path.join(tmp, "foo", "bar")
        safe_makedirs(target)
        # we need the patch to ensure that the code is actually executed
        with patch("os.path.exists") as mock_:
            mock_.return_value = False
            self.assertTrue(os.path.isdir(target))
            # ensure that creating the base dir again does not crash
            safe_makedirs(target)
            self.assertTrue(os.path.isdir(target))
            # ensure we still get regular errors like permission denied
            # (stat.S_IRUSR)
            os.chmod(os.path.join(tmp, "foo"), 0400)
            self.assertRaises(OSError, safe_makedirs, target)
            # set back to stat.(S_IRUSR|S_IWUSR|S_IXUSR) to make rmtree work
            os.chmod(os.path.join(tmp, "foo"), 0700)
        # cleanup
        shutil.rmtree(tmp)

class TestExpungeCache(unittest.TestCase):

    def test_expunge_cache(self):
        dirname = tempfile.mkdtemp('s-c-testsuite')
        for name, content in [ ("foo-301", "status: 301"),
                               ("foo-200", "status: 200"),
                               ("foo-random", "random"),
                             ]:
            fullpath = os.path.join(dirname, name)
            open(fullpath, "w").write(content)
            # set to 1970+1s time to ensure the cleaner finds it
            os.utime(fullpath, (1,1))
        res = subprocess.call(["../utils/expunge-cache.py", dirname])
        # no arguments
        self.assertEqual(res, 1)
        # by status
        res = subprocess.call(["../utils/expunge-cache.py",
                               "--debug",
                               "--by-unsuccessful-http-states",
                               dirname])
        self.assertFalse(os.path.exists(os.path.join(dirname, "foo-301")))
        self.assertTrue(os.path.exists(os.path.join(dirname, "foo-200")))
        self.assertTrue(os.path.exists(os.path.join(dirname, "foo-random")))

        # by time 
        res = subprocess.call(["../utils/expunge-cache.py",
                               "--debug",
                               "--by-days", "1",
                               dirname])
        # now we expect the old file to be gone but the unknown one not to
        # be touched
        self.assertFalse(os.path.exists(os.path.join(dirname, "foo-200")))
        self.assertTrue(os.path.exists(os.path.join(dirname, "foo-random")))

    def test_expunge_cache_lock(self):
        def set_marker(d):
            time.sleep(0.5)
            target = os.path.join(d, "marker.%s." % os.getpid())
            open(target, "w")
        from softwarecenter.expunge import ExpungeCache
        tmpdir = tempfile.mkdtemp()
        # create two ExpungeCache processes 
        e1 = ExpungeCache([tmpdir], by_days=0, by_unsuccessful_http_states=True)
        e1._cleanup_dir = set_marker
        e2 = ExpungeCache([tmpdir], by_days=0, by_unsuccessful_http_states=True)
        e2._cleanup_dir = set_marker
        t1 = multiprocessing.Process(target=e1.clean)
        t1.start()
        t2 = multiprocessing.Process(target=e2.clean)
        t2.start()
        # wait for finish
        t1.join()
        t2.join()
        # ensure that the second one was not called
        self.assertEqual(len(glob.glob(os.path.join(tmpdir, "marker.*"))), 1)



if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
