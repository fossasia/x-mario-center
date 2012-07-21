#!/usr/bin/python

import unittest

from gi.repository import Gtk, GObject
from gettext import gettext as _

from testutils import setup_test_env
setup_test_env()

from mock import Mock, patch

from softwarecenter.db.application import Application
from softwarecenter.testutils import get_mock_app_from_real_app, do_events, make_recommend_app_data
from softwarecenter.ui.gtk3.widgets.labels import HardwareRequirementsBox
from softwarecenter.ui.gtk3.views.appdetailsview import get_test_window_appdetails
from softwarecenter.enums import PkgStates
from softwarecenter.region import REGION_WARNING_STRING

from test.test_database import make_purchased_app_details



# window destory timeout
TIMEOUT=100

class TestAppdetailsView(unittest.TestCase):

    def setUp(self):
        self.win = get_test_window_appdetails()
        self.view = self.win.get_data("view")

    def tearDown(self):
        GObject.timeout_add(TIMEOUT, lambda: self.win.destroy())
        Gtk.main()

    def test_videoplayer(self):
        # show app with no video
        app = Application("", "2vcard")
        self.view.show_app(app)
        do_events()
        self.assertFalse(self.view.videoplayer.get_property("visible"))

        # create app with video and ensure its visible
        app = Application("", "synaptic")
        mock = get_mock_app_from_real_app(app)
        details = mock.get_details(None)
        # this is a example html - any html5 video will do
        details.video_url = "http://people.canonical.com/~mvo/totem.html"
        self.view.show_app(mock)
        do_events()
        self.assertTrue(self.view.videoplayer.get_property("visible"))
    
    def test_page_pkgstates(self):
        # show app 
        app = Application("", "abiword")
        self.view.show_app(app)
        do_events()
        
        # check that the action bar is given initial focus in the view
        self.assertTrue(self.view.pkg_statusbar.button.is_focus())

        # create mock app
        mock_app = get_mock_app_from_real_app(app)
        self.view.app = mock_app
        mock_details = mock_app.get_details(None)
        mock_details.purchase_date = "2011-11-20 17:45:01"
        mock_details._error_not_found = "error not found"
        mock_details.price = "1.00"
        mock_details.pkgname = "abiword"
        mock_details.error = "error-text"
        self.view.app_details = mock_details

        # the states and what labels we expect in the pkgstatusbar
        # first string is status text, second is button text
        pkg_states_to_labels = {
            PkgStates.INSTALLED : ("Purchased on 2011-11-20", "Remove"),
            PkgStates.UNINSTALLED : ('Free', 'Install'),
            PkgStates.NEEDS_PURCHASE : ('US$ 1.00', u'Buy\u2026'),
            PkgStates.PURCHASED_BUT_REPO_MUST_BE_ENABLED : ('Purchased on 2011-11-20', 'Install'),
        }
        # this describes if a button is visible or invisible
        button_invisible = [ PkgStates.ERROR,
                             PkgStates.NOT_FOUND,
                             PkgStates.INSTALLING_PURCHASED,
                             PkgStates.PURCHASED_BUT_NOT_AVAILABLE_FOR_SERIES,
                             PkgStates.UNKNOWN,
                           ]

        # show a app through the various states and test if the right ui
        # elements are visible and have the right text
        for var in vars(PkgStates):
            state = getattr(PkgStates, var)
            mock_details.pkg_state = state
            # reset app to ensure its shown again
            self.view.app = None
            # show it
            self.view.show_app(mock_app)
            #do_events()
            # check button label
            if state in pkg_states_to_labels:
                label, button_label = pkg_states_to_labels[state]
                self.assertEqual(
                    self.view.pkg_statusbar.get_label(), 
                    label.decode("utf-8"))
                self.assertEqual(
                    self.view.pkg_statusbar.get_button_label().decode("utf-8"),
                    button_label)
            # check if button should be there or not
            if state in button_invisible:
                self.assertFalse(
                    self.view.pkg_statusbar.button.get_property("visible"),
                    "button visible error for state %s" % state)
            else:
                self.assertTrue(
                    self.view.pkg_statusbar.button.get_property("visible"),
                    "button visible error for state %s" % state)
            # regression test for #955005
            if state == PkgStates.NOT_FOUND:
                self.assertFalse(self.view.review_stats.get_property("visible"))
                self.assertFalse(self.view.reviews.get_property("visible"))

    def test_app_icon_loading(self):
        # get icon
        app = Application("", "software-center")
        mock_app = get_mock_app_from_real_app(app)
        self.view.app = mock_app
        mock_details = mock_app.get_details(None)
        mock_details.cached_icon_file_path = "download-icon-test"
        mock_details.icon = "favicon.ico"
        mock_details.icon_url = "http://de.wikipedia.org/favicon.ico"
        self.view.app_details = mock_details
        self.view.show_app(mock_app)
        do_events()
        # ensure the icon is there
        # FIXME: ensure that the icon is really downloaded
        #self.assertTrue(os.path.exists(mock_details.cached_icon_file_path))
        #os.unlink(mock_details.cached_icon_file_path)

    def test_add_where_is_it(self):
        app = Application("", "software-center")
        self.view.show_app(app)
        self.view._add_where_is_it_commandline("apt")
        do_events()
        self.view._add_where_is_it_launcher("/usr/share/applications/ubuntu-software-center.desktop")
        do_events()

    def test_reviews_page(self):
        win = get_test_window_appdetails()
        view = win.get_data("view")
        # show s-c and click on more review
        app = Application("", "software-center")
        view.show_app(app)
        self.assertEqual(view._reviews_server_page, 1)
        view._on_more_reviews_clicked(None)
        self.assertEqual(view._reviews_server_page, 2)
        # show different app, ensure page is reset
        app = Application("", "apt")
        view.show_app(app)
        self.assertEqual(view._reviews_server_page, 1)

    def test_human_readable_name_in_view(self):
        model = self.view.reviews.review_language.get_model()
        self.assertEqual(model[0][0], "English")

    def test_switch_language_resets_page(self):
        self.view._reviews_server_page = 4

        self.view.reviews.emit("different-review-language-clicked", 'my')

        self.assertEqual(1, self.view._reviews_server_page)

    def test_switch_reviews_sort_method_resets_page(self):
        self.view._reviews_server_page = 4

        self.view.reviews.emit("review-sort-changed", 1)

        self.assertEqual(1, self.view._reviews_server_page)

    @patch('softwarecenter.backend.reviews.rnr.ReviewLoaderSpawningRNRClient'
           '.get_reviews')
    def test_no_reviews_returned_attempts_relaxing(self, mock_get_reviews):
        """AppDetailsView._reviews_ready_callback will attempt to drop the
           origin and distroseries restriction if no reviews are returned
           with the restrictions in place.
        """
        self.view._do_load_reviews()

        self.assertEqual(1, mock_get_reviews.call_count)
        kwargs = mock_get_reviews.call_args[1]
        self.assertEqual(False, kwargs['relaxed'])
        self.assertEqual(1, kwargs['page'])

        # Now we come back with no data
        application, callback = mock_get_reviews.call_args[0]
        callback(application, [])

        self.assertEqual(2, mock_get_reviews.call_count)
        kwargs = mock_get_reviews.call_args[1]
        self.assertEqual(True, kwargs['relaxed'])
        self.assertEqual(1, kwargs['page'])

    @patch('softwarecenter.backend.reviews.rnr.ReviewLoaderSpawningRNRClient'
           '.get_reviews')
    def test_all_duplicate_reviews_keeps_going(self, mock_get_reviews):
        """AppDetailsView._reviews_ready_callback will fetch another page if
           all data returned was already displayed in the reviews list.
        """
        # Fixme: Do we have a test factory?
        review = Mock()
        review.rating = 3
        review.date_created = "2011-01-01 18:00:00"
        review.version = "1.0"
        review.summary = 'some summary'
        review.review_text = 'Some text'
        review.reviewer_username = "name"
        review.reviewer_displayname = "displayname"

        reviews = [review]
        self.view.reviews.reviews = reviews
        self.view._do_load_reviews()

        self.assertEqual(1, mock_get_reviews.call_count)
        kwargs = mock_get_reviews.call_args[1]
        self.assertEqual(False, kwargs['relaxed'])
        self.assertEqual(1, kwargs['page'])

        # Now we come back with no NEW data
        application, callback = mock_get_reviews.call_args[0]
        callback(application, reviews)

        self.assertEqual(2, mock_get_reviews.call_count)
        kwargs = mock_get_reviews.call_args[1]
        self.assertEqual(False, kwargs['relaxed'])
        self.assertEqual(2, kwargs['page'])

    @patch('softwarecenter.backend.spawn_helper.SpawnHelper.run')
    def test_submit_new_review_disables_button(self, mock_run):
        button = self.view.reviews.new_review
        self.assertTrue(button.is_sensitive())

        button.emit('clicked')

        self.assertFalse(button.is_sensitive())

    def test_new_review_dialog_closes_reenables_submit_button(self):
        button = self.view.reviews.new_review
        button.disable()

        self.view._submit_reviews_done_callback(None, 0)

        self.assertTrue(button.is_sensitive())
        

class MultipleVersionsTestCase(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Set these as class attributes as we don't modify either
        # during the tests.
        from softwarecenter.testutils import get_test_db
        cls.db = get_test_db()
        cls.win = get_test_window_appdetails()
        cls.view = cls.win.get_data("view")

    @classmethod
    def tearDownClass(cls):
        GObject.timeout_add(TIMEOUT, lambda: cls.win.destroy())
        Gtk.main()

    def setUp(self):
        app = Application("", "software-center")
        self.app_mock = get_mock_app_from_real_app(app)
        self.app_mock.details.pkg_state = PkgStates.UNINSTALLED

    def test_multiple_versions_automatic_button(self):
        # normal app
        self.view.show_app(self.app_mock)
        self.assertFalse(self.view.pkg_statusbar.combo_multiple_versions.get_visible())
        # switch to not-automatic app with different description
        self.app_mock.details.get_not_automatic_archive_versions = lambda: [ 
            ("5.0", "precise"),
            ("12.0", "precise-backports"),
            ]
        self.view.show_app(self.app_mock)
        self.assertTrue(self.view.pkg_statusbar.combo_multiple_versions.get_visible())
        text = self.view.pkg_statusbar.combo_multiple_versions.get_active_text()
        self.assertEqual(text, "v5.0 (default)")

    def test_combo_multiple_versions(self):
        self.app_mock.details.get_not_automatic_archive_versions = lambda: [
            ("5.0",  "precise"),
            ("12.0", "precise-backports") 
            ]
        # ensure that the right method is called
        self.app_mock.details.force_not_automatic_archive_suite = Mock()
        self.view.show_app(self.app_mock)
        # test combo box switch
        self.view.pkg_statusbar.combo_multiple_versions.set_active(1)
        self.assertTrue(
            self.app_mock.details.force_not_automatic_archive_suite.called)
        call_args = self.app_mock.details.force_not_automatic_archive_suite.call_args
        self.assertEqual(call_args, (("precise-backports",), {}))

    def test_installed_multiple_version_default(self):
        self.app_mock.details.get_not_automatic_archive_versions = lambda: [
            ("5.0",  "precise"),
            ("12.0", "precise-backports") 
            ]
        self.app_mock.details.pkg_state = PkgStates.INSTALLED
        self.app_mock.details.version = "12.0"
        # FIXME: do we really need this or should the backend derive this
        #        automatically?
        self.app_mock.archive_suite = "precise-backports"

        self.app_mock.details.force_not_automatic_archive_suite = Mock()
        self.view.show_app(self.app_mock)
        active = self.view.pkg_statusbar.combo_multiple_versions.get_active_text()
        # ensure that the combo points to "precise-backports"
        self.assertEqual(active, "v12.0 (precise-backports)")
        # now change the installed version from 12.0 to 5.0
        self.app_mock.details.force_not_automatic_archive_suite.reset_mock()
        def _side_effect(*args):
            self.app_mock.archive_suite="precise"
            self.app_mock.details.pkg_state = PkgStates.FORCE_VERSION
        self.app_mock.details.force_not_automatic_archive_suite.side_effect = _side_effect
        self.view.pkg_statusbar.combo_multiple_versions.set_active(0)
        # ensure that now the default version is forced
        self.assertTrue(
            self.app_mock.details.force_not_automatic_archive_suite.called)
        #call_args = self.app_mock.details.force_not_automatic_archive_suite.call_args
        #self.assertEqual(call_args, (("precise",), {}))
        # ensure the button changes
        self.assertEqual(self.view.pkg_statusbar.button.get_label(), "Change")
        

class HardwareRequirementsTestCase(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Set these as class attributes as we don't modify either
        # during the tests.
        from softwarecenter.testutils import get_test_db
        cls.db = get_test_db()
        cls.win = get_test_window_appdetails()
        cls.view = cls.win.get_data("view")

    @classmethod
    def tearDownClass(cls):
        GObject.timeout_add(TIMEOUT, lambda: cls.win.destroy())
        Gtk.main()

    def setUp(self):
        app = Application("", "software-center")
        self.app_mock = get_mock_app_from_real_app(app)
        self.app_mock.details.pkg_state = PkgStates.UNINSTALLED

    def test_show_hardware_requirements(self):
        self.app_mock.details.hardware_requirements = { 
            'hardware::video:opengl' : 'yes',
            'hardware::gps' : 'no',
            }
        self.app_mock.details.hardware_requirements_satisfied = False
        self.view.show_app(self.app_mock)
        do_events()
        # ensure we have the data
        self.assertTrue(
            self.view.hardware_info.value_label.get_property("visible"))
        self.assertEqual(
            type(HardwareRequirementsBox()),
            type(self.view.hardware_info.value_label))
        self.assertEqual(
            self.view.hardware_info.key, _("Also requires"))
        # ensure that the button is correct
        self.assertEqual(
            self.view.pkg_statusbar.button.get_label(), "Install Anyway")
        # and again for purchase
        self.app_mock.details.pkg_state = PkgStates.NEEDS_PURCHASE
        self.view.show_app(self.app_mock)
        self.assertEqual(
            self.view.pkg_statusbar.button.get_label(), 
            _(u"Buy Anyway\u2026").encode("utf-8"))
        # check if the warning bar is displayed
        self.assertTrue(self.view.pkg_warningbar.get_property("visible"))
        self.assertEqual(self.view.pkg_warningbar.label.get_text(),
                         _('This software requires a GPS, '
                           'but the computer does not have one.'))

    def test_no_show_hardware_requirements(self):
        self.app_mock.details.hardware_requirements = {}
        self.app_mock.details.hardware_requirements_satisfied = True
        self.view.show_app(self.app_mock)
        do_events()
        # ensure we do not show anything if there are no HW requirements
        self.assertFalse(
            self.view.hardware_info.get_property("visible"))
        # ensure that the button is correct
        self.assertEqual(
            self.view.pkg_statusbar.button.get_label(), _("Install"))
        # and again for purchase
        self.app_mock.details.pkg_state = PkgStates.NEEDS_PURCHASE
        self.view.show_app(self.app_mock)
        self.assertEqual(
            self.view.pkg_statusbar.button.get_label(), 
            _(u'Buy\u2026').encode("utf-8"))
        # check if the warning bar is invisible
        self.assertFalse(self.view.pkg_warningbar.get_property("visible"))

class RegionRequirementsTestCase(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Set these as class attributes as we don't modify either
        # during the tests.
        from softwarecenter.testutils import get_test_db
        cls.db = get_test_db()
        cls.win = get_test_window_appdetails()
        cls.view = cls.win.get_data("view")

    @classmethod
    def tearDownClass(cls):
        GObject.timeout_add(TIMEOUT, lambda: cls.win.destroy())
        Gtk.main()

    def setUp(self):
        app = Application("", "software-center")
        self.app_mock = get_mock_app_from_real_app(app)
        self.app_mock.details.pkg_state = PkgStates.UNINSTALLED

    def test_show_region_requirements(self):
        self.app_mock.details.region_requirements_satisfied = False
        self.view.show_app(self.app_mock)
        do_events()
        # ensure that the button is correct
        self.assertEqual(
            self.view.pkg_statusbar.button.get_label(), "Install Anyway")
        # and again for purchase
        self.app_mock.details.pkg_state = PkgStates.NEEDS_PURCHASE
        self.view.show_app(self.app_mock)
        self.assertEqual(
            self.view.pkg_statusbar.button.get_label(), 
            _(u"Buy Anyway\u2026").encode("utf-8"))
        # check if the warning bar is displayed
        self.assertTrue(self.view.pkg_warningbar.get_property("visible"))
        self.assertEqual(self.view.pkg_warningbar.label.get_text(),
                         REGION_WARNING_STRING)


class PurchasedAppDetailsStatusBarTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Set these as class attributes as we don't modify either
        # during the tests.
        from softwarecenter.testutils import get_test_db
        cls.db = get_test_db()
        cls.win = get_test_window_appdetails()

    @classmethod
    def tearDownClass(cls):
        GObject.timeout_add(TIMEOUT, lambda: cls.win.destroy())
        Gtk.main()

    def _make_statusbar_view_for_state(self, state):
        app_details = make_purchased_app_details(db=self.db)
        # XXX 2011-01-23 It's unfortunate we need multiple mocks to test this
        # correctly, but I don't know the code well enough to refactor
        # dependencies yet so that it wouldn't be necessary. In this case, we
        # need a *real* app details object for displaying in the view, but want
        # to specify its state for the purpose of the test. As an Application
        # normally loads its details from the database, we patch
        # Application.get_details also.  Patch app_details.pkg_state for the
        # test.
        pkg_state_fn = 'softwarecenter.db.application.AppDetails.pkg_state'
        pkg_state_patcher = patch(pkg_state_fn)
        self.addCleanup(pkg_state_patcher.stop)
        mock_pkg_state = pkg_state_patcher.start()
        mock_pkg_state.__get__ = Mock(return_value=state)

        get_details_fn = 'softwarecenter.db.application.Application.get_details'
        get_details_patcher = patch(get_details_fn)
        self.addCleanup(get_details_patcher.stop)
        mock_get_details = get_details_patcher.start()
        mock_get_details.return_value = app_details

        app = app_details._app
        details_view = self.win.get_data("view")
        details_view.show_app(app)
        do_events()

        statusbar_view = details_view.pkg_statusbar
        statusbar_view.configure(app_details, state)

        return statusbar_view

    def test_NOT_AVAILABLE_FOR_SERIES_no_action_for_click_event(self):
        statusbar_view = self._make_statusbar_view_for_state(
            PkgStates.PURCHASED_BUT_NOT_AVAILABLE_FOR_SERIES)
        mock_app_manager = Mock()
        statusbar_view.app_manager = mock_app_manager

        statusbar_view._on_button_clicked(Mock())

        self.assertEqual([], mock_app_manager.method_calls)

    def test_NOT_AVAILABLE_FOR_SERIES_sets_label_and_button(self):
        statusbar_view = self._make_statusbar_view_for_state(
            PkgStates.PURCHASED_BUT_NOT_AVAILABLE_FOR_SERIES)

        self.assertEqual(
            "Purchased on 2011-09-16 but not available for your current "
            "Ubuntu version. Please contact the vendor for an update.",
            statusbar_view.label.get_text())
        self.assertFalse(statusbar_view.button.get_visible())

    def test_actions_for_purchased_apps(self):
        button_to_function_tests = (
            (PkgStates.INSTALLED, "remove"),
            (PkgStates.PURCHASED_BUT_REPO_MUST_BE_ENABLED, "reinstall_purchased"),
            (PkgStates.NEEDS_PURCHASE, "buy_app"),
            (PkgStates.UNINSTALLED, "install"),
            (PkgStates.REINSTALLABLE, "install"),
            (PkgStates.UPGRADABLE, "upgrade"),
            (PkgStates.NEEDS_SOURCE, "enable_software_source")
        )
        for state, func in button_to_function_tests:
            statusbar_view = self._make_statusbar_view_for_state(state)
            mock_app_manager = Mock()
            statusbar_view.app_manager = mock_app_manager

            statusbar_view._on_button_clicked(Mock())

            # If we want to also check the args/kwargs, we can update the above
            # button_to_function_tests.
            all_method_calls = [method_name for method_name, args, kwargs in (
                mock_app_manager.method_calls)]
            self.assertEqual(
                [method_name],
                all_method_calls)
                
class AppRecommendationsTestCase(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Set these as class attributes as we don't modify either
        # during the tests.
        cls.win = get_test_window_appdetails()
        cls.view = cls.win.get_data("view")
        from softwarecenter.testutils import get_test_db
        cls.db = get_test_db()

    @classmethod
    def tearDownClass(cls):
        GObject.timeout_add(TIMEOUT, lambda: cls.win.destroy())
        Gtk.main()

    def setUp(self):
        app = Application("", "pitivi")
        self.app_mock = get_mock_app_from_real_app(app)
        self.app_mock.details.pkg_state = PkgStates.UNINSTALLED
        
    def on_query_done(self, recagent, data):
        print "query done, data: '%s'" % data
        self.loop.quit()
        
    def on_query_error(self, recagent, error):
        print "query error received: ", error
        self.loop.quit()
        self.error = True

    # patch out the agent query method to avoid making the actual server call
    @patch('softwarecenter.backend.recagent.RecommenderAgent'
           '.query_recommend_app')
    def test_show_recommendations_for_app(self, mock_query):
        self.view.show_app(self.app_mock)
        do_events()
        self.view.recommended_for_app_panel._update_app_recommendations_content()
        do_events()
        # we fake the callback from the agent here
        self.view.recommended_for_app_panel.app_recommendations_cat._recommend_app_result(
                                None,
                                make_recommend_app_data())
        self.assertNotEqual(
                self.view.recommended_for_app_panel.app_recommendations_cat.get_documents(self.db), [])


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
