#!/usr/bin/python

from gi.repository import GObject

import os
import time
import unittest

from testutils import setup_test_env
setup_test_env()
from softwarecenter.utils import SimpleFileDownloader

class TestImageDownloader(unittest.TestCase):

    DOWNLOAD_FILENAME = "test_image_download"

    def setUp(self):
        self.downloader = SimpleFileDownloader()
        self.downloader.connect("file-url-reachable",
                                self._cb_image_url_reachable)
        self.downloader.connect("file-download-complete",
                                self._cb_image_download_complete)
        self.downloader.connect("error",
                                self._cb_image_download_error)
        self._image_is_reachable = None
        self._image_downloaded_filename = None
        self._error = False
        if os.path.exists(self.DOWNLOAD_FILENAME):
            os.unlink(self.DOWNLOAD_FILENAME)

    def _cb_image_url_reachable(self, downloader, is_reachable):
        self._image_is_reachable = is_reachable

    def _cb_image_download_complete(self, downloader, filename):
        self._image_downloaded_filename = filename

    def _cb_image_download_error(self, downloader, gerror, exc):
        self._error = True

    def test_download_unreachable(self):
        self.downloader.download_file("http://www.ubuntu.com/really-not-there",
                                      self.DOWNLOAD_FILENAME)
        main_loop = GObject.main_context_default()
        while self._image_is_reachable is None:
            while main_loop.pending():
                main_loop.iteration()
            time.sleep(0.1)
        self.assertNotEqual(self._image_is_reachable, None)
        self.assertFalse(self._image_is_reachable)
        self.assertTrue(not os.path.exists(self.DOWNLOAD_FILENAME))
 
    def test_download_reachable(self):
        self.downloader.download_file("http://www.ubuntu.com",
                                      self.DOWNLOAD_FILENAME)
        main_loop = GObject.main_context_default()
        while (self._image_downloaded_filename is None and
               not self._error):
            while main_loop.pending():
                main_loop.iteration()
            time.sleep(0.1)
        self.assertNotEqual(self._image_is_reachable, None)
        self.assertTrue(self._image_is_reachable)
        self.assertTrue(os.path.exists(self.DOWNLOAD_FILENAME))

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
