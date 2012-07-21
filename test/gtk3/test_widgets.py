#!/usr/bin/python

from gi.repository import Gtk, GdkPixbuf, GObject
import os
import unittest
from gettext import gettext as _

from mock import Mock, patch

from testutils import setup_test_env, do_events
setup_test_env()
from softwarecenter.utils import utf8
from softwarecenter.ui.gtk3.widgets.reviews import get_test_reviews_window
from softwarecenter.ui.gtk3.widgets.labels import (
    HardwareRequirementsLabel, HardwareRequirementsBox)

# window destory timeout
TIMEOUT=100

class TestWidgets(unittest.TestCase):
    """ basic tests for the various gtk3 widget """

    def test_stars(self):
        from softwarecenter.ui.gtk3.widgets.stars import get_test_stars_window
        win = get_test_stars_window()
        win.show_all()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_actionbar(self):
        from softwarecenter.ui.gtk3.widgets.actionbar import ActionBar
        mock = Mock()
        actionbar = ActionBar()
        actionbar.add_button("id1", "label", mock)
        actionbar.add_button("id2", "label", mock)
        actionbar.remove_button("id2")
        win = Gtk.Window()
        win.set_size_request(400, 400)
        win.add(actionbar)
        win.connect("destroy", Gtk.main_quit)
        win.show_all()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_backforward(self):
        from softwarecenter.ui.gtk3.widgets.backforward import get_test_backforward_window
        win = get_test_backforward_window()
        win.show_all()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_containers(self):
        from softwarecenter.ui.gtk3.widgets.containers import get_test_container_window
        win = get_test_container_window()
        win.show_all()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_description(self):
        from softwarecenter.ui.gtk3.widgets.description import get_test_description_window
        win = get_test_description_window()
        win.show_all()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_exhibits(self):
        from softwarecenter.ui.gtk3.widgets.exhibits import get_test_exhibits_window
        win = get_test_exhibits_window()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_show_image_dialog(self):
        from softwarecenter.ui.gtk3.widgets.imagedialog import SimpleShowImageDialog
        if os.path.exists("../../data/default_banner/fallback.png"):
            f = "../../data/default_banner/fallback.png"
        else:
            f = "../data/default_banner/fallback.png"
        pix = GdkPixbuf.Pixbuf.new_from_file(f)
        d = SimpleShowImageDialog("test caption", pix)
        GObject.timeout_add(TIMEOUT, lambda: d.destroy())
        d.run()

    def test_searchentry(self):
        from softwarecenter.ui.gtk3.widgets.searchentry import get_test_searchentry_window
        win = get_test_searchentry_window()
        s = "foo"
        win.entry.insert_text(s, len(s))
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_spinner(self):
        from softwarecenter.ui.gtk3.widgets.spinner import get_test_spinner_window
        win = get_test_spinner_window()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_symbolic_icons(self):
        from softwarecenter.ui.gtk3.widgets.symbolic_icons import get_test_symbolic_icons_window
        win = get_test_symbolic_icons_window()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_buttons(self):
        from softwarecenter.ui.gtk3.widgets.buttons import get_test_buttons_window
        win = get_test_buttons_window()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_screenshot_thumbnail(self):
        from softwarecenter.ui.gtk3.widgets.thumbnail import get_test_screenshot_thumbnail_window
        win = get_test_screenshot_thumbnail_window()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_videoplayer(self):
        from softwarecenter.ui.gtk3.widgets.videoplayer import get_test_videoplayer_window
        win = get_test_videoplayer_window()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()


    def test_apptreeview(self):
        from softwarecenter.ui.gtk3.widgets.apptreeview import get_test_window
        win = get_test_window()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

class TestHWRequirements(unittest.TestCase):

    HW_TEST_RESULT = { 'hardware::gps' : 'yes',
                       'hardware::xxx' : 'unknown',
                       'hardware::input:mouse' : 'no',
                       }

    def test_hardware_requirements_label(self):
        label = HardwareRequirementsLabel()
        label.set_hardware_requirement('hardware::gps', 'yes')
        self.assertEqual(
            label.get_label(),
            u"%sGPS" % HardwareRequirementsLabel.SUPPORTED_SYM["yes"])
        # test the gtk bits
        self.assertEqual(type(label.get_children()[0]), Gtk.Label)
        # test setting it again
        label.set_hardware_requirement('hardware::video:opengl', 'yes')
        self.assertEqual(len(label.get_children()), 1)

    # regression test for bug #967036
    @patch("softwarecenter.ui.gtk3.widgets.labels.get_hw_short_description")
    def test_hardware_requirements_label_utf8(self, mock_get_hw):
        magic_marker = u" \u1234 GPS"
        mock_get_hw.return_value = utf8(magic_marker)
        label = HardwareRequirementsLabel()
        label.set_hardware_requirement('hardware::gps', 'yes')
        self.assertEqual(
            label.get_label(),
            u"%s%s" % (HardwareRequirementsLabel.SUPPORTED_SYM["yes"],
                       magic_marker))

    def test_hardware_requirements_box(self):
        box = HardwareRequirementsBox()
        # test empty
        box.set_hardware_requirements({})
        # test sensible
        box.set_hardware_requirements(self.HW_TEST_RESULT)
        # its 2 because we do not display "unknown" currently
        self.assertEqual(len(box.hw_labels), 2)
        # test the gtk bits
        self.assertEqual(len(box.get_children()), 2)
        # no trailing ","
        self.assertEqual(
            box.get_children()[0].get_label(),
            u"%smouse," % HardwareRequirementsLabel.SUPPORTED_SYM["no"])
        self.assertEqual(
            box.get_children()[1].get_label(),
            u"%sGPS" % HardwareRequirementsLabel.SUPPORTED_SYM["yes"])

        # test seting it again
        box.set_hardware_requirements(self.HW_TEST_RESULT)
        self.assertEqual(len(box.get_children()), 2)
        

class TestUIReviewsList(unittest.TestCase):
    def setUp(self):
        self.win = get_test_reviews_window()
        self.rl = self.win.get_children()[0]

    def tearDown(self):
        GObject.timeout_add(TIMEOUT, lambda: self.win.destroy())
        Gtk.main()

    def assertComboBoxTextIncludes(self, combo, option):
        store = combo.get_model()
        self.assertTrue(option in [x[0] for x in store])

    def assertEmbeddedMessageLabel(self, title, message):
        markup = self.rl.vbox.get_children()[1].label.get_label()
        self.assertTrue(title in markup)
        self.assertTrue(message in markup)

    def test_reviews_includes_any_language(self):
        review_language = self.rl.review_language
        self.assertComboBoxTextIncludes(review_language, _('Any language'))

    def test_reviews_offers_to_relax_language(self):
        # No reviews found, but there are some in other languages:
        self.rl.clear()
        self.rl.global_review_stats = Mock()
        self.rl.global_review_stats.ratings_total = 4
        self.rl.configure_reviews_ui()
        do_events()

        self.assertEmbeddedMessageLabel(
            _("This app has not been reviewed yet in your language"),
            _('Try selecting a different language, or even "Any language"'
            ' in the language dropdown'))

    @patch('softwarecenter.ui.gtk3.widgets.reviews.network_state_is_connected')
    def test_reviews_no_reviews_but_app_not_installed(self, mock_connected):
        mock_connected.return_value = True
        # No reviews found, and the app isn't installed
        self.rl.clear()
        self.rl.configure_reviews_ui()
        do_events()

        self.assertEmbeddedMessageLabel(
            _("This app has not been reviewed yet"),
            _('You need to install this before you can review it'))

    @patch('softwarecenter.ui.gtk3.widgets.reviews.network_state_is_connected')
    def test_reviews_no_reviews_offer_to_write_one(self, mock_connected):
        from softwarecenter.enums import PkgStates
        mock_connected.return_value = True
        # No reviews found, and the app is installed
        self.rl.clear()
        self.rl._parent.app_details.pkg_state = PkgStates.INSTALLED
        self.rl.configure_reviews_ui()
        do_events()

        self.assertEmbeddedMessageLabel(
            _('Got an opinion?'),
            _('Be the first to contribute a review for this application'))




if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
