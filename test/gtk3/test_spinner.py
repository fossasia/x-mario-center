import os
import unittest

from gi.repository import Gtk
from mock import patch

from testutils import setup_test_env
setup_test_env()

from softwarecenter.ui.gtk3.widgets import spinner


class SpinnerNotebookTestCase(unittest.TestCase):
    """The test case for the SpinnerNotebook."""

    _fake_timeout_id = object()

    def setUp(self):
        # helpers to check the timeout's callbacks
        self._interval = None
        self._callback = None

        self.content = Gtk.Label('My test')
        self.content.show()
        self.addCleanup(self.content.hide)
        self.addCleanup(self.content.destroy)

        self.obj = spinner.SpinnerNotebook(self.content)
        self.addCleanup(self.obj.hide)
        self.addCleanup(self.obj.destroy)
        assert spinner.SOFTWARE_CENTER_DEBUG_TABS not in os.environ

        self.obj.show()

    def _fake_timeout_add(self, interval, callback):
        self._interval = interval
        self._callback = callback
        return self._fake_timeout_id

    def _fake_source_remove(self, event_id):
        if event_id is self._fake_timeout_id:
            self._fake_timeout_id = None
            return True

    def test_no_borders(self):
        """The notebook has no borders."""
        self.assertFalse(self.obj.get_show_border())

    def test_no_tabs(self):
        """The notebook has no visible tabs."""
        self.assertFalse(self.obj.get_show_tabs())

    def test_tabs_if_debug_set(self):
        """The notebook has visible tabs if debug is set."""
        with patch.object(spinner, 'SOFTWARE_CENTER_DEBUG_TABS', True):
            self.obj = spinner.SpinnerNotebook(self.content)
            self.assertTrue(self.obj.get_show_tabs())

    def test_has_two_pages(self):
        """The notebook has two pages."""
        self.assertEqual(self.obj.get_n_pages(), 2)

    def test_has_content(self):
        """The notebook has the given content."""
        self.assertEqual(self.obj.get_nth_page(self.obj.CONTENT_PAGE),
                         self.content)

    def test_has_spinner(self):
        """The notebook has the spinner view."""
        self.assertEqual(self.obj.get_nth_page(self.obj.SPINNER_PAGE),
                         self.obj.spinner_view)
        self.assertTrue(self.obj.spinner_view.get_visible())

    def test_show_content_by_default(self):
        """The content tab is shown by default."""
        self.assertEqual(self.obj.get_current_page(), self.obj.CONTENT_PAGE)

    def test_show_spinner(self):
        """The spinner is shown only after the timeout occurs."""
        assert self._interval is None
        assert self._callback is None

        with patch.object(spinner.GObject, 'timeout_add',
                          self._fake_timeout_add):
            self.obj.show_spinner()

        # this must hold before the callback is fired
        self.assertEqual(self.obj.get_current_page(), self.obj.CONTENT_PAGE)
        self.assertFalse(self.obj.spinner_view.spinner.get_property('active'))
        self.assertFalse(self.obj.spinner_view.spinner.get_visible())
        self.assertEqual(self._interval, 250)
        self.assertEqual(self._callback, self.obj._unmask_view_spinner)

        result = self._callback()  # fire the timeout

        # this must hold after the callback is fired
        self.assertFalse(result, 'The timeout callback should return False.')
        self.assertTrue(self.obj.spinner_view.spinner.get_property('active'))
        self.assertTrue(self.obj.spinner_view.spinner.get_visible())
        self.assertEqual(self.obj.get_current_page(), self.obj.SPINNER_PAGE)

    def test_show_spinner_with_msg(self):
        """The spinner is shown with the given message."""
        message = 'Something I want to show'
        with patch.object(spinner.GObject, 'timeout_add', lambda *a: None):
            self.obj.show_spinner(msg=message)

        self.assertEqual(self.obj.spinner_view.get_text(), message)

    def test_hide_spinner_before_timeout(self):
        """The spinner is hidden cancelling the timeout."""
        with patch.object(spinner.GObject, 'timeout_add',
                          self._fake_timeout_add):
            self.obj.show_spinner()

        with patch.object(spinner.GObject, 'source_remove',
                          self._fake_source_remove):
            self.obj.hide_spinner()

        # hide_spinner should call source_remove with the proper event id,
        # which in turn will set the _fake_timeout_id to None
        self.assertTrue(self._fake_timeout_id is None,
            'The timeout should be removed by calling GObject.source_remove')
        # the content page is shown
        self.assertEqual(self.obj.get_current_page(), self.obj.CONTENT_PAGE)
        # the spinner is stoppped and hidden
        self.assertFalse(self.obj.spinner_view.spinner.get_property('active'))
        self.assertFalse(self.obj.spinner_view.spinner.get_visible())

    def test_hide_spinner_after_timeout(self):
        """The spinner is hidden without cancelling the timeout."""
        with patch.object(spinner.GObject, 'timeout_add',
                          self._fake_timeout_add):
            self.obj.show_spinner()

        self._callback()  # fake the timeout being fired

        with patch.object(spinner.GObject, 'source_remove',
                          self._fake_source_remove):
            self.obj.hide_spinner()

        self.assertTrue(self._fake_timeout_id is not None,
            'GObject.source_remove should not be called if already fired.')
        # the content page is shown
        self.assertEqual(self.obj.get_current_page(), self.obj.CONTENT_PAGE)
        # the spinner is stoppped and hidden
        self.assertFalse(self.obj.spinner_view.spinner.get_property('active'))
        self.assertFalse(self.obj.spinner_view.spinner.get_visible())


if __name__ == "__main__":
    unittest.main()
