#!/usr/bin/python

from gi.repository import Gtk
import time
import unittest

from testutils import setup_test_env
setup_test_env()

# overwrite early
import softwarecenter.utils

from softwarecenter.enums import TransactionTypes
from softwarecenter.utils import convert_desktop_file_to_installed_location
from softwarecenter.db.application import Application
from softwarecenter.ui.gtk3.panes.availablepane import get_test_window
from softwarecenter.backend.unitylauncher import UnityLauncherInfo

# Tests for Ubuntu Software Center's integration with the Unity launcher,
# see https://wiki.ubuntu.com/SoftwareCenter#Learning%20how%20to%20launch%20an%20application

# we can only have one instance of availablepane, so create it here
win = get_test_window()
available_pane = win.get_data("pane")

class TestUnityLauncherIntegration(unittest.TestCase):

    def setUp(self):
        # monkey patch is_unity_running
        softwarecenter.utils.is_unity_running = lambda: True
        
    def _zzz(self):
        for i in range(10):
            time.sleep(0.1)
            self._p()

    def _p(self):
        while Gtk.events_pending():
            Gtk.main_iteration()

    def _install_from_list_view(self, pkgname):
        from softwarecenter.ui.gtk3.panes.availablepane import AvailablePane
        available_pane.notebook.set_current_page(AvailablePane.Pages.LIST)
        
        self._p()
        available_pane.on_search_terms_changed(None, "ark,artha,software-center")
        self._p()
        
        # select the first item in the list
        available_pane.app_view.tree_view.set_cursor(Gtk.TreePath(0),
                                                            None, False)
        # ok to just use the test app here                                            
        app = Application("", pkgname)
        self._p()
        
        # pretend we started an install
        available_pane.backend.emit("transaction-started",
                                    app.pkgname, app.appname,
                                    "testid101",
                                    TransactionTypes.INSTALL)
        # wait a wee bit
        self._zzz()

    def _navigate_to_appdetails_and_install(self, pkgname):
        app = Application("", pkgname)
        available_pane.app_view.emit("application-activated",
                                     app)
        self._p()
        
        # pretend we started an install
        available_pane.backend.emit("transaction-started",
                                    app.pkgname, app.appname,
                                    "testid101",
                                    TransactionTypes.INSTALL)
        # wait a wee bit
        self._zzz()
        
    def _fake_send_application_to_launcher_and_check(self,
                                                     pkgname, launcher_info):
        self.assertEqual(pkgname, self.expected_pkgname)
        self.assertEqual(launcher_info.name, self.expected_launcher_info.name)
        self.assertEqual(launcher_info.icon_name,
                         self.expected_launcher_info.icon_name)
        self.assertTrue(launcher_info.icon_x > 5)
        self.assertTrue(launcher_info.icon_y > 5)
        # check that the icon size is one of either 32 pixels (for the
        # list view case) or 96 pixels (for the details view case)
        self.assertTrue(launcher_info.icon_size == 32 or
                        launcher_info.icon_size == 96)
        self.assertEqual(launcher_info.app_install_desktop_file_path,
                self.expected_launcher_info.app_install_desktop_file_path)
        self.assertEqual(launcher_info.trans_id,
                self.expected_launcher_info.trans_id)
        
    def test_unity_launcher_integration_list_view(self):
        # test the automatic add to launcher enabled functionality when
        # installing an app form the list view
        available_pane.add_to_launcher_enabled = True
        test_pkgname = "lincity-ng"
        # now pretend
        # for testing, we substitute a fake version of UnityLauncher's
        # send_application_to_launcher method that lets us check for the
        # correct values and also avoids firing the actual dbus signal
        # to the unity launcher service
        self.expected_pkgname = test_pkgname
        self.expected_launcher_info = UnityLauncherInfo("lincity-ng",
                 "lincity-ng",
                 0, 0, 0, 0, # these values are set in availablepane
                 "/usr/share/app-install/desktop/lincity-ng:lincity-ng.desktop",
                 "testid101")
        available_pane.unity_launcher.send_application_to_launcher = (
                self._fake_send_application_to_launcher_and_check)
        self._install_from_list_view(test_pkgname)

    def test_unity_launcher_integration_details_view(self):
        # test the automatic add to launcher enabled functionality when
        # installing an app from the details view
        available_pane.add_to_launcher_enabled = True
        test_pkgname = "lincity-ng"
        # now pretend
        # for testing, we substitute a fake version of UnityLauncher's
        # send_application_to_launcher method that lets us check for the
        # correct values and also avoids firing the actual dbus signal
        # to the unity launcher service
        self.expected_pkgname = test_pkgname
        self.expected_launcher_info = UnityLauncherInfo("lincity-ng",
                 "lincity-ng",
                 0, 0, 0, 0, # these values are set in availablepane
                 "/usr/share/app-install/desktop/lincity-ng:lincity-ng.desktop",
                 "testid101")
        available_pane.unity_launcher.send_application_to_launcher = (
                self._fake_send_application_to_launcher_and_check)
        self._navigate_to_appdetails_and_install(test_pkgname)
        
    def test_unity_launcher_integration_disabled(self):
        # test the case where automatic add to launcher is disabled
        available_pane.add_to_launcher_enabled = False
        test_pkgname = "lincity-ng"
        # now pretend
        # for testing, we substitute a fake version of UnityLauncher's
        # send_application_to_launcher method that lets us check for the
        # correct values and also avoids firing the actual dbus signal
        # to the unity launcher service
        # in the disabled add to launcher case, we just want to insure
        # that we never call send_application_to_launcher, so we can just
        # plug in bogus values and we will catch a call if it occurs
        self.expected_pkgname = ""
        self.expected_launcher_info = UnityLauncherInfo("", "",
                 0, 0, 0, 0, "", "")
        available_pane.unity_launcher.send_application_to_launcher = (
                self._fake_send_application_to_launcher_and_check)
        self._navigate_to_appdetails_and_install(test_pkgname)

    def test_desktop_file_path_conversion(self):
        # test 'normal' case
        app_install_desktop_path = ("./data/app-install/desktop/" +
                                    "deja-dup:deja-dup.desktop")
        installed_desktop_path = convert_desktop_file_to_installed_location(
                app_install_desktop_path, "deja-dup")
        self.assertEqual(installed_desktop_path,
                         "./data/applications/deja-dup.desktop")
        # test encoded subdirectory case, e.g. e.g. kde4_soundkonverter.desktop
        app_install_desktop_path = ("./data/app-install/desktop/" +
                                    "soundkonverter:" +
                                    "kde4__soundkonverter.desktop")
        installed_desktop_path = convert_desktop_file_to_installed_location(
                app_install_desktop_path, "soundkonverter")
        self.assertEqual(installed_desktop_path,
                         "./data/applications/kde4/soundkonverter.desktop")
        # test the for-purchase case (uses "software-center-agent" as its
        # appdetails.desktop_file value)
        # FIXME: this will only work if update-manager is installed
        app_install_desktop_path = "software-center-agent"
        installed_desktop_path = convert_desktop_file_to_installed_location(
                app_install_desktop_path, "update-manager")
        self.assertEqual(installed_desktop_path,
                         "/usr/share/applications/update-manager.desktop")
        # test case where we don't have a value for app_install_desktop_path
        # (e.g. for a local .deb install, see bug LP: #768158)
        installed_desktop_path = convert_desktop_file_to_installed_location(
                None, "update-manager")
        # FIXME: this will only work if update-manager is installed
        self.assertEqual(installed_desktop_path,
                         "/usr/share/applications/update-manager.desktop")
    

if __name__ == "__main__":
    unittest.main()
