# Copyright (C) 2009 Canonical
#
# Authors:
#   Matthew McGowan
#   Michael Vogt
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
from urlparse import urlparse
from dbus.mainloop.glib import DBusGMainLoop

from gi.repository import GObject

LOG = logging.getLogger(__name__)


# enums
class NetState(object):
    """ enums for network manager status """
    # Old enum values are for NM 0.7

    # The NetworkManager daemon is in an unknown state.
    NM_STATE_UNKNOWN = 0
    NM_STATE_UNKNOWN_LIST = [NM_STATE_UNKNOWN]
    # The NetworkManager daemon is asleep and all interfaces managed by
    # it are inactive.
    NM_STATE_ASLEEP_OLD = 1
    NM_STATE_ASLEEP = 10
    NM_STATE_ASLEEP_LIST = [NM_STATE_ASLEEP_OLD,
                            NM_STATE_ASLEEP]
    # The NetworkManager daemon is connecting a device.
    NM_STATE_CONNECTING_OLD = 2
    NM_STATE_CONNECTING = 40
    NM_STATE_CONNECTING_LIST = [NM_STATE_CONNECTING_OLD,
                                NM_STATE_CONNECTING]
    # The NetworkManager daemon is connected.
    NM_STATE_CONNECTED_OLD = 3
    NM_STATE_CONNECTED_LOCAL = 50
    NM_STATE_CONNECTED_SITE = 60
    NM_STATE_CONNECTED_GLOBAL = 70
    NM_STATE_CONNECTED_LIST = [NM_STATE_CONNECTED_OLD,
                               NM_STATE_CONNECTED_LOCAL,
                               NM_STATE_CONNECTED_SITE,
                               NM_STATE_CONNECTED_GLOBAL]
    # The NetworkManager daemon is disconnecting.
    NM_STATE_DISCONNECTING = 30
    NM_STATE_DISCONNECTING_LIST = [NM_STATE_DISCONNECTING]
    # The NetworkManager daemon is disconnected.
    NM_STATE_DISCONNECTED_OLD = 4
    NM_STATE_DISCONNECTED = 20
    NM_STATE_DISCONNECTED_LIST = [NM_STATE_DISCONNECTED_OLD,
                                   NM_STATE_DISCONNECTED]


class NetworkStatusWatcher(GObject.GObject):
    """ simple watcher which notifys subscribers to network events..."""
    __gsignals__ = {'changed': (GObject.SIGNAL_RUN_FIRST,
                                GObject.TYPE_NONE,
                                (int,)),
                   }

    def __init__(self):
        GObject.GObject.__init__(self)
        return


# internal helper
NETWORK_STATE = 0


def __connection_state_changed_handler(state):
    global NETWORK_STATE

    NETWORK_STATE = int(state)
    __WATCHER__.emit("changed", NETWORK_STATE)
    return


# init network state
def __init_network_state():
    global NETWORK_STATE

    # honor SOFTWARE_CENTER_NET_{DIS,}CONNECTED in the environment variables
    import os
    env_map = {
        'SOFTWARE_CENTER_NET_DISCONNECTED': NetState.NM_STATE_DISCONNECTED,
        'SOFTWARE_CENTER_NET_CONNECTED': NetState.NM_STATE_CONNECTED_GLOBAL,
    }
    for envkey, state in env_map.iteritems():
        if envkey in os.environ:
            NETWORK_STATE = state
            return

    dbus_loop = DBusGMainLoop()
    try:
        bus = dbus.SystemBus(mainloop=dbus_loop)
        nm = bus.get_object('org.freedesktop.NetworkManager',
                            '/org/freedesktop/NetworkManager')
        NETWORK_STATE = nm.state(
            dbus_interface='org.freedesktop.NetworkManager')
        bus.add_signal_receiver(
            __connection_state_changed_handler,
            dbus_interface="org.freedesktop.NetworkManager",
            signal_name="StateChanged")
        return

    except Exception as e:
        logging.warn("failed to init network state watcher '%s'" % e)

    NETWORK_STATE = NetState.NM_STATE_UNKNOWN
    # test ping to check if there is internet connectivity despite
    # NetworkManager not being available
    import threading
    thread = threading.Thread(target=test_ping, name='test_ping')
    thread.start()
    return


#helper
def test_ping():
    global NETWORK_STATE
    import subprocess

    # ping the main deb repository from the sources.list
    import aptsources
    source_list = aptsources.apt_pkg.SourceList()
    source_list.read_main_list()

    if not source_list.list:
        LOG.warn("apt sourcelist had no sources!!!")
        NETWORK_STATE = NetState.NM_STATE_DISCONNECTED
    else:
        # get a host to ping
        host = urlparse(source_list.list[0].uri)[1]
        msg = ("Attempting one time ping of %s to test if internet "
               "connectivity exists." % host)
        logging.info(msg)

        ping = subprocess.Popen(
            ["ping", "-c", "1", host],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
            )

    out, error = ping.communicate()
    if len(error.splitlines()):
        NETWORK_STATE = NetState.NM_STATE_DISCONNECTED
        msg = "Could not detect an internet connection\n%s" % error
    else:
        NETWORK_STATE = NetState.NM_STATE_CONNECTED_GLOBAL
        msg = "Internet connection available!\n%s" % out

    __WATCHER__.emit("changed", NETWORK_STATE)
    logging.info("ping output: '%s'" % msg)
    return

# global watcher
__WATCHER__ = NetworkStatusWatcher()


def get_network_watcher():
    return __WATCHER__


# simply query
def get_network_state():
    """ get the NetState state """
    global NETWORK_STATE
    return NETWORK_STATE


# simply query even more
def network_state_is_connected():
    """ get bool if we are connected """
    # unkown because in doubt, just assume we have network
    return get_network_state() in NetState.NM_STATE_UNKNOWN_LIST + \
                                  NetState.NM_STATE_CONNECTED_LIST

# init it once
__init_network_state()

if __name__ == '__main__':
    loop = GObject.MainLoop()
    loop.run()
