#!/usr/bin/python

import unittest

from gi.repository import GObject

from testutils import setup_test_env
setup_test_env()
from gettext import gettext as _
from mock import Mock, patch

from softwarecenter.backend.piston.rnrclient_pristine import ReviewDetails
from softwarecenter.testutils import get_test_pkg_info, get_test_db
from softwarecenter.ui.gtk3.review_gui_helper import (
    TRANSMIT_STATE_DONE,
    GRatingsAndReviews,
    SubmitReviewsApp,
    )
from time import sleep

class TestReviewLoader(unittest.TestCase):
    cache = get_test_pkg_info()
    db = get_test_db()

    def _review_stats_ready_callback(self, review_stats):
        self._stats_ready = True
        self._review_stats = review_stats

#    def test_review_stats_caching(self):
#        self._stats_ready = False
#        self._review_stats = []
#        review_loader = ReviewLoader(self.cache, self.db)
#        review_loader.refresh_review_stats(self._review_stats_ready_callback)
#        while not self._stats_ready:
#            self._p()
#        self.assertTrue(len(self._review_stats) > 0)
#        self.assertTrue(os.path.exists(review_loader.REVIEW_STATS_CACHE_FILE))
#        self.assertTrue(os.path.exists(review_loader.REVIEW_STATS_BSDDB_FILE))
#        # once its there, get_top_rated
#        top_rated = review_loader.get_top_rated_apps(quantity=10)
#        self.assertEqual(len(top_rated), 10)
#        # and per-cat
#        top_cat = review_loader.get_top_rated_apps(
#            quantity=8, category="Internet")
#        self.assertEqual(len(top_cat), 8)

    def test_edit_review_screen_has_right_labels(self):
        """Check that LP #880255 stays fixed. """

        review_app = SubmitReviewsApp(datadir="../data", app=None,
            parent_xid='', iconname='accessories-calculator', origin=None,
            version=None, action='modify', review_id=10000)
        # monkey patch away login to avoid that we actually login
        # and the UI changes because of that

        review_app.login = lambda: True

        # run the main app
        review_app.run()

        self._p()
        review_app.login_successful('foobar')
        self._p()
        self.assertEqual(_('Rating:'), review_app.rating_label.get_label())
        self.assertEqual(_('Summary:'),
            review_app.review_summary_label.get_label())
        self.assertEqual(_('Review by: %s') % 'foobar',
            review_app.review_label.get_label())
        review_app.submit_window.hide()

    def test_get_fade_colour_markup(self):
        review_app = SubmitReviewsApp(datadir="../data", app=None,
            parent_xid='', iconname='accessories-calculator', origin=None,
            version=None, action='nothing')
        cases = (
            (('006000', '00A000', 40, 60, 50), ('008000', 10)),
            (('000000', 'FFFFFF', 40, 40, 40), ('000000', 0)),
            (('000000', '808080', 100, 400, 40), ('000000', 360)),
            (('000000', '808080', 100, 400, 1000), ('808080', -600)),
            (('123456', '5294D6', 10, 90, 70), ('427CB6', 20)),
            )
        for args, return_value in cases:
            result = review_app._get_fade_colour_markup(*args)
            expected = '<span fgcolor="#%s">%s</span>' % return_value
            self.assertEqual(expected, result)

    def test_modify_review_is_the_same_supports_unicode(self):
        review_app = SubmitReviewsApp(datadir="../data", app=None,
            parent_xid='', iconname='accessories-calculator', origin=None,
            version=None, action='modify', review_id=10000)
        self.assertTrue(review_app._modify_review_is_the_same())

        cases = ('', 'e', ')!')
        for case in cases:
            modified = review_app.orig_summary_text[:-1] + case
            review_app.review_summary_entry.set_text(modified)
            self.assertFalse(review_app._modify_review_is_the_same())

        review_app.review_summary_entry.set_text(review_app.orig_summary_text)
        for case in cases:
            modified = review_app.orig_review_text[:-1] + case
            review_app.review_buffer.set_text(modified)
            self.assertFalse(review_app._modify_review_is_the_same())

    def test_change_status(self):
        review_app = SubmitReviewsApp(datadir="../data", app=None,
            parent_xid='', iconname='accessories-calculator', origin=None,
            version=None, action='nothing')
        msg = 'Something completely different'
        cases = {'clear': (True, True, True, True, None, None),
                 'progress': (False, True, True, True, msg, None),
                 'fail': (True, False, True, True, None, msg),
                 'success': (True, True, False, True, msg, None),
                 'warning': (True, True, True, False, msg, None),
                }
        review_app.run()

        for status in cases:
            review_app._change_status(status, msg)
            spinner, error, success, warn, label, error_detail = cases[status]
            self.assertEqual(spinner,
                review_app.submit_spinner.get_parent() is None)
            self.assertEqual(error,
                review_app.submit_error_img.get_window() is None)
            self.assertEqual(success,
                review_app.submit_success_img.get_window() is None)
            self.assertEqual(warn,
                review_app.submit_warn_img.get_window() is None)
            if label:
                self.assertEqual(label,
                    review_app.label_transmit_status.get_text())
            if error_detail:
                buff = review_app.error_textview.get_buffer()
                self.assertEqual(error_detail,
                    buff.get_text(buff.get_start_iter(), buff.get_end_iter(),
                    include_hidden_chars=False))
                review_app.detail_expander.get_visible()

    def _p(self):
        main_loop = GObject.main_context_default()
        while main_loop.pending():
            main_loop.iteration()


class TestGRatingsAndReviews(unittest.TestCase):
    def setUp(self):
        mock_token = {'token': 'foobar', 
                      'token_secret': 'foobar',
                      'consumer_key': 'foobar',
                      'consumer_secret': 'foobar',
                     }
        self.api = GRatingsAndReviews(mock_token)

    def tearDown(self):
        self.api.shutdown()

    def make_review(self):
        review = Mock()
        review.rating = 4
        review.origin = 'ubuntu'
        review.app.appname = ''
        review.app.pkgname = 'foobar'
        review.text = 'Super awesome app!'
        review.summary = 'Cool'
        review.package_version = '1.0'
        review.date = '2012-01-22'
        review.language = 'en'
        return review        

    def wait_for_worker(self):
        while self.api.worker_thread._transmit_state != TRANSMIT_STATE_DONE:
            sleep(0.1)

    @patch('softwarecenter.ui.gtk3.review_gui_helper.RatingsAndReviewsAPI'
        '.submit_review')
    def test_submit_review(self, mock_submit_review):
        mock_submit_review.return_value = ReviewDetails.from_dict(
            {'foo': 'bar'})
        review = self.make_review()

        self.api.submit_review(review)

        self.wait_for_worker()
        self.assertTrue(mock_submit_review.called)
        review_arg = mock_submit_review.call_args[1]['review']
        self.assertEqual(review.text, review_arg.review_text)

    @patch('softwarecenter.ui.gtk3.review_gui_helper.RatingsAndReviewsAPI'
        '.flag_review')
    def test_flag_review(self, mock_flag_review):
        mock_flag_review.return_value = 'Something'

        self.api.report_abuse(1234, 'Far too silly', 'Stop right now.')

        self.wait_for_worker()
        self.assertTrue(mock_flag_review.called)
        self.assertEqual(1234, mock_flag_review.call_args[1]['review_id'])

    @patch('softwarecenter.ui.gtk3.review_gui_helper.RatingsAndReviewsAPI'
        '.submit_usefulness')
    def test_submit_usefulness(self, mock_submit_usefulness):
        mock_submit_usefulness.return_value = 'Something'

        self.api.submit_usefulness(1234, True)

        self.wait_for_worker()
        self.assertTrue(mock_submit_usefulness.called)
        self.assertEqual(1234, mock_submit_usefulness.call_args[1]['review_id'])

    @patch('softwarecenter.ui.gtk3.review_gui_helper.RatingsAndReviewsAPI'
        '.modify_review')
    def test_modify_review(self, mock_modify_review):
        mock_modify_review.return_value = ReviewDetails.from_dict(
            {'foo': 'bar'})
        review = {
            'summary': 'Cool',
            'review_text': 'Super awesome app!',
            'rating': 4,
        }

        self.api.modify_review(1234, review)

        self.wait_for_worker()
        self.assertTrue(mock_modify_review.called)
        self.assertEqual(1234, mock_modify_review.call_args[1]['review_id'])
        self.assertEqual(4, mock_modify_review.call_args[1]['rating'])
        self.assertEqual('Cool', mock_modify_review.call_args[1]['summary'])

    @patch('softwarecenter.ui.gtk3.review_gui_helper.RatingsAndReviewsAPI'
        '.delete_review')
    def test_delete_review(self, mock_delete_review):
        mock_delete_review.return_value = 'Something'

        self.api.delete_review(1234)

        self.wait_for_worker()
        self.assertTrue(mock_delete_review.called)
        self.assertEqual(1234, mock_delete_review.call_args[1]['review_id'])


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
