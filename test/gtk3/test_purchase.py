#!/usr/bin/python

import time
import unittest

from mock import Mock, patch

from testutils import setup_test_env
setup_test_env()

from softwarecenter.testutils import do_events, get_mock_options
from softwarecenter.ui.gtk3.app import SoftwareCenterAppGtk3
from softwarecenter.ui.gtk3.panes.availablepane import AvailablePane
import softwarecenter.paths

class TestPurchase(unittest.TestCase):

    def test_purchase_view_log_cleaner(self):
        import softwarecenter.ui.gtk3.views.purchaseview
        from softwarecenter.ui.gtk3.views.purchaseview import get_test_window_purchaseview
        win = get_test_window_purchaseview()
        self._p()
        # get the view
        view = win.get_data("view")
        # install the mock
        softwarecenter.ui.gtk3.views.purchaseview.LOG = mock = Mock()
        # run a "harmless" log message and ensure its logged normally
        view.wk.webkit.execute_script('console.log("foo")')
        self.assertTrue("foo" in mock.debug.call_args[0][0])
        mock.reset_mock()

        # run a message that contains token info
        s = 'http://sca.razorgirl.info/subscriptions/19077/checkout_complete/ @10: {"token_key": "hiddenXXXXXXXXXX", "consumer_secret": "hiddenXXXXXXXXXXXX", "api_version": 2.0, "subscription_id": 19077, "consumer_key": "rKhNPBw", "token_secret": "hiddenXXXXXXXXXXXXXXX"}'
        view.wk.webkit.execute_script("console.log('%s')" % s)
        self.assertTrue("skipping" in mock.debug.call_args[0][0])
        self.assertFalse("consumer_secret" in mock.debug.call_args[0][0])
        mock.reset_mock()

        # run another one
        win.destroy()

    def test_purchase_view_tos(self):
        from softwarecenter.ui.gtk3.views.purchaseview import get_test_window_purchaseview
        win = get_test_window_purchaseview()
        view = win.get_data("view")
        # install the mock
        mock_config = Mock()
        mock_config.has_option.return_value = False
        mock_config.getboolean.return_value = False
        view.config = mock_config
        func = "softwarecenter.ui.gtk3.views.purchaseview.show_accept_tos_dialog"
        with patch(func) as mock_func:
            mock_func.return_value = False
            res = view.initiate_purchase(None, None)
            self.assertFalse(res)
            self.assertTrue(mock_func.called)
        win.destroy()

    def test_spinner_emits_signals(self):
        from softwarecenter.ui.gtk3.views.purchaseview import get_test_window_purchaseview
        win = get_test_window_purchaseview()
        self._p()
        # get the view
        view = win.get_data("view")
        # ensure "purchase-needs-spinner" signals are send
        signal_mock = Mock()
        view.connect("purchase-needs-spinner", signal_mock)
        view.wk.webkit.load_uri("http://www.ubuntu.com/")
        self._p()
        self.assertTrue(signal_mock.called)
        # run another one
        win.destroy()

    def test_reinstall_previous_purchase_display(self):
        mock_options = get_mock_options()
        xapiandb = "/var/cache/software-center/"
        app = SoftwareCenterAppGtk3(
            softwarecenter.paths.datadir, xapiandb, mock_options)
        # real app opens cache async
        app.cache.open()
        # show it
        app.window_main.show_all()
        app.available_pane.init_view()
        self._p()
        app.on_menuitem_reinstall_purchases_activate(None)
        # it can take a bit until the sso client is ready
        for i in range(100):
            if (app.available_pane.get_current_page() ==
                AvailablePane.Pages.LIST):
                break
            self._p()
        self.assertEqual(
            app.available_pane.get_current_page(), AvailablePane.Pages.LIST)

    def _p(self):
        for i in range(5):
            time.sleep(0.1)
            do_events()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
