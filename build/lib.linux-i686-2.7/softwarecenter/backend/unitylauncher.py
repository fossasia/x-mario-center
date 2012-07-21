# Copyright (C) 2011 Canonical
#
# Authors:
#  Gary Lasker
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import dbus
import logging

LOG = logging.getLogger(__name__)


class UnityLauncherInfo(object):
    """ Simple class to keep track of application details needed for
        Unity launcher integration
    """
    def __init__(self,
                 name,
                 icon_name,
                 icon_file_path,
                 icon_x,
                 icon_y,
                 icon_size,
                 app_install_desktop_file_path,
                 trans_id):
        self.name = name
        self.icon_name = icon_name
        self.icon_file_path = icon_file_path
        self.icon_x = icon_x
        self.icon_y = icon_y
        self.icon_size = icon_size
        self.app_install_desktop_file_path = app_install_desktop_file_path
        self.trans_id = trans_id


class TransactionDetails(object):
    """ Simple class to keep track of aptdaemon transaction details for
        use with the Unity launcher integration
    """
    def __init__(self,
                 pkgname,
                 appname,
                 trans_id,
                 trans_type):
        self.pkgname = pkgname
        self.appname = appname
        self.trans_id = trans_id
        self.trans_type = trans_type


class UnityLauncher(object):
    """ Implements the integration between Software Center and the Unity
        launcher
    """

    def send_application_to_launcher(self, pkgname, launcher_info):
        """ send a dbus message to the Unity launcher service to initiate
            the add to launcher functionality for the specified application
        """
        LOG.debug("sending dbus signal to Unity launcher for application: ",
                  launcher_info.name)
        LOG.debug("  launcher_info.icon_file_path: ",
                     launcher_info.icon_file_path)
        LOG.debug("  launcher_info.app_install_desktop_file_path: ",
                     launcher_info.app_install_desktop_file_path)
        LOG.debug("  launcher_info.trans_id: ", launcher_info.trans_id)

        try:
            bus = dbus.SessionBus()
            launcher_obj = bus.get_object('com.canonical.Unity.Launcher',
                                          '/com/canonical/Unity/Launcher')
            launcher_iface = dbus.Interface(launcher_obj,
                                            'com.canonical.Unity.Launcher')
            launcher_iface.AddLauncherItemFromPosition(
                    launcher_info.name,
                    launcher_info.icon_file_path,
                    launcher_info.icon_x,
                    launcher_info.icon_y,
                    launcher_info.icon_size,
                    launcher_info.app_install_desktop_file_path,
                    launcher_info.trans_id)
        except Exception as e:
            LOG.warn("could not send dbus signal to the Unity launcher: (%s)",
                     e)
