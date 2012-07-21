#!/usr/bin/python
# Copyright (C) Canonical
#
# Author: 2011 Stephane Graber <stgraber@ubuntu.com>
#              Michael Vogt <mvo@ubuntu.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
# taken from lp:~weblive-dev/weblive/trunk/client/weblive.py
# and put into weblive_pristine.py

import re
import os
import random
import subprocess
import string
import imp

from gi.repository import GObject

from threading import Thread, Event
from weblive_pristine import WebLive
import softwarecenter.paths


class WebLiveBackend(object):
    """ Backend for interacting with the WebLive service """

    client = None
    URL = os.environ.get('SOFTWARE_CENTER_WEBLIVE_HOST',
        'https://weblive.stgraber.org/weblive/json')

    def __init__(self):
        self.weblive = WebLive(self.URL, True)
        self.available_servers = []

        for client in (WebLiveClientX2GO, WebLiveClientQTNX):
            if client.is_supported():
                self.client = client()
                break

        self._ready = Event()

    @property
    def ready(self):
        """ Return true if data from the remote server was loaded
        """

        return self.client and self._ready.is_set()

    def query_available(self):
        """ Get all the available data from WebLive """

        self._ready.clear()
        servers = self.weblive.list_everything()
        self._ready.set()
        return servers

    def query_available_async(self):
        """ Call query_available in a thread and set self.ready """

        def _query_available_helper():
            self.available_servers = self.query_available()

        p = Thread(target=_query_available_helper)
        p.start()

    def is_pkgname_available_on_server(self, pkgname, serverid=None):
        """Check if the package is available (on all servers or
           on 'serverid')
        """

        for server in self.available_servers:
            if not serverid or server.name == serverid:
                for pkg in server.packages:
                    if pkg.pkgname == pkgname:
                        return True
        return False

    def get_servers_for_pkgname(self, pkgname):
        """ Return a list of servers having a given package """

        servers = []
        for server in self.available_servers:
            # No point in returning a server that's full
            if server.current_users >= server.userlimit:
                continue

            for pkg in server.packages:
                if pkg.pkgname == pkgname:
                    servers.append(server)
        return servers

    def create_automatic_user_and_run_session(self, serverid,
                                              session="desktop", wait=False):
        """ Create a user on 'serverid' and start the session """

        # Use the boot_id to get a temporary unique identifier
        # (till next reboot)
        if os.path.exists('/proc/sys/kernel/random/boot_id'):
            uuid = open('/proc/sys/kernel/random/boot_id',
                'r').read().strip().replace('-', '')
            random.seed(uuid)

        # Generate a 20 characters string based on the boot_id
        identifier = ''.join(random.choice(string.ascii_lowercase)
            for x in range(20))

        # Use the current username as the GECOS on the server
        # if it's invalid (by weblive's standard), use "WebLive user" instead
        fullname = str(os.environ.get('USER', 'WebLive user'))
        if not re.match("^[A-Za-z0-9 ]*$", fullname) or len(fullname) == 0:
            fullname = 'WebLive user'

        # Send the user's locale so it's automatically selected when connecting
        locale = os.environ.get("LANG", "None").replace("UTF-8", "utf8")

        # Create the user and retrieve host and port of the target server
        connection = self.weblive.create_user(serverid, identifier, fullname,
            identifier, session, locale)

        # Connect using x2go or fallback to qtnx if not available
        if (self.client):
            self.client.start_session(connection[0], connection[1], session,
                identifier, identifier, wait)
        else:
            raise IOError("No remote desktop client available.")


class WebLiveClient(GObject.GObject):
    """ Generic WebLive client """

    __gsignals__ = {
        "progress": (
            GObject.SIGNAL_RUN_FIRST,
            GObject.TYPE_NONE,
            (GObject.TYPE_INT,)
        ),
        "connected": (
            GObject.SIGNAL_RUN_FIRST,
            GObject.TYPE_NONE,
            (GObject.TYPE_BOOLEAN,)
        ),
        "disconnected": (
            GObject.SIGNAL_RUN_FIRST,
            GObject.TYPE_NONE,
            ()
        ),
        "exception": (
            GObject.SIGNAL_RUN_FIRST,
            GObject.TYPE_NONE,
            (GObject.TYPE_STRING,)
        ),
        "warning": (
            GObject.SIGNAL_RUN_FIRST,
            GObject.TYPE_NONE,
            (GObject.TYPE_STRING,)
        )
    }

    state = "disconnected"


class WebLiveClientQTNX(WebLiveClient):
    """ qtnx client """

    # NXML template
    NXML_TEMPLATE = """
<!DOCTYPE NXClientLibSettings>
<NXClientLibSettings>
<option key="Connection Name" value="WL_NAME"></option>
<option key="Server Hostname" value="WL_SERVER"></option>
<option key="Server Port" value="WL_PORT"></option>
<option key="Session Type" value="unix-application"></option>
<option key="Custom Session Command" value="WL_COMMAND"></option>
<option key="Disk Cache" value="64"></option>
<option key="Image Cache" value="16"></option>
<option key="Link Type" value="adsl"></option>
<option key="Use Render Extension" value="True"></option>
<option key="Image Compression Method" value="JPEG"></option>
<option key="JPEG Compression Level" value="9"></option>
<option key="Desktop Geometry" value=""></option>
<option key="Keyboard Layout" value="defkeymap"></option>
<option key="Keyboard Type" value="pc102/defkeymap"></option>
<option key="Media" value="False"></option>
<option key="Agent Server" value=""></option>
<option key="Agent User" value=""></option>
<option key="CUPS Port" value="0"></option>
<option key="Authentication Key" value=""></option>
<option key="Use SSL Tunnelling" value="True"></option>
<option key="Enable Fullscreen Desktop" value="False"></option>
</NXClientLibSettings>
"""

    BINARY_PATH = "/usr/bin/qtnx"

    @classmethod
    def is_supported(cls):
        """ Return if the current system will work
            (has the required dependencies)
        """

        if os.path.exists(cls.BINARY_PATH):
            return True
        return False

    def start_session(self, host, port, session, username, password, wait):
        """ Start a session using qtnx """

        self.state = "connecting"
        if not os.path.exists(os.path.expanduser('~/.qtnx')):
            os.mkdir(os.path.expanduser('~/.qtnx'))

        # Generate qtnx's configuration file
        filename = os.path.expanduser('~/.qtnx/%s-%s-%s.nxml') % (
            host, port, session.replace("/", "_"))
        nxml = open(filename, "w+")
        config = self.NXML_TEMPLATE
        config = config.replace("WL_NAME", "%s-%s-%s" % (host, port,
            session.replace("/", "_")))
        config = config.replace("WL_SERVER", host)
        config = config.replace("WL_PORT", str(port))
        config = config.replace("WL_COMMAND", "weblive-session %s" % session)
        nxml.write(config)
        nxml.close()

        # Prepare qtnx call
        cmd = [self.BINARY_PATH,
               '%s-%s-%s' % (str(host), str(port), session.replace("/", "_")),
               username,
               password]

        def qtnx_countdown():
            """ Send progress events every two seconds """

            if self.helper_progress == 10:
                self.state = "connected"
                self.emit("connected", False)
                return False
            else:
                self.emit("progress", self.helper_progress * 10)
                self.helper_progress += 1
                return True

        def qtnx_start_timer():
            """ As we don't have a way of knowing the connection
                status, we countdown from 20s
            """

            self.helper_progress = 0
            qtnx_countdown()
            GObject.timeout_add_seconds(2, qtnx_countdown)

        qtnx_start_timer()

        if wait == False:
            # Start in the background and attach a watch for when it exits
            (self.helper_pid, stdin, stdout, stderr) = GObject.spawn_async(
                cmd, standard_input=True, standard_output=True,
                standard_error=True, flags=GObject.SPAWN_DO_NOT_REAP_CHILD)
            GObject.child_watch_add(self.helper_pid, self._on_qtnx_exit,
                filename)
        else:
            # Start it and wait till it finishes
            p = subprocess.Popen(cmd)
            p.wait()

    def _on_qtnx_exit(self, pid, status, filename):
        """ Called when the qtnx process exits (when in the background) """

        # Remove configuration file
        self.state = "disconnected"
        self.emit("disconnected")
        if os.path.exists(filename):
            os.remove(filename)


class WebLiveClientX2GO(WebLiveClient):
    """ x2go client """

    @classmethod
    def is_supported(cls):
        """ Return if the current system will work
            (has the required dependencies)
        """

        try:
            imp.find_module("x2go")
            return True
        except:
            return False

    def start_session(self, host, port, session, username, password, wait):
        """ Start a session using x2go """

        # Start in the background and attach a watch for when it exits
        cmd = [os.path.join(softwarecenter.paths.datadir,
            softwarecenter.paths.X2GO_HELPER)]
        (self.helper_pid, stdin, stdout, stderr) = GObject.spawn_async(
            cmd, standard_input=True, standard_output=True,
            standard_error=True, flags=GObject.SPAWN_DO_NOT_REAP_CHILD)
        self.helper_stdin = os.fdopen(stdin, "w")
        self.helper_stdout = os.fdopen(stdout)
        self.helper_stderr = os.fdopen(stderr)

        # Add a watch for when the process exits
        GObject.child_watch_add(self.helper_pid, self._on_x2go_exit)

        # Add a watch on stdout
        GObject.io_add_watch(self.helper_stdout, GObject.IO_IN,
            self._on_x2go_activity)

        # Start the connection
        self.state = "connecting"
        self.helper_stdin.write(
            "CONNECT: \"%s\" \"%s\" \"%s\" \"%s\" \"%s\"\n" %
            (host, port, username, password, session))
        self.helper_stdin.flush()

    def disconnect_session(self):
        """ Disconnect the current session """

        if self.state == "connected":
            self.state = "disconnecting"
            self.helper_stdin.write("DISCONNECT\n")
            self.helper_stdin.flush()

    def _on_x2go_exit(self, pid, status):
        # We get everything by just watching stdout
        pass

    def _on_x2go_activity(self, stdout, condition):
        """ Called when something appears on stdout """

        line = stdout.readline().strip()
        if line.startswith("PROGRESS: "):
            if line.endswith("creating"):
                self.emit("progress", 10)
            elif line.endswith("connecting"):
                self.emit("progress", 30)
            elif line.endswith("starting"):
                self.emit("progress", 60)

        elif line == "CONNECTED":
            self.emit("connected", True)
            self.state = "connected"
        elif line == "DISCONNECTED":
            self.emit("disconnected")
            self.state = "disconnected"
        elif line.startswith("EXCEPTION: "):
            self.emit("exception", line.split(": ")[1])
            self.state = "disconnected"
        elif line.startswith("WARNING: "):
            self.emit("warning", line.split(": ")[1])
        else:
            pass
        return True

# singleton
_weblive_backend = None


def get_weblive_backend():
    global _weblive_backend
    if _weblive_backend is None:
        _weblive_backend = WebLiveBackend()
        # initial query
        if _weblive_backend.client:
            _weblive_backend.query_available_async()
    return _weblive_backend

if __name__ == "__main__":
    # Contact the weblive daemon to get all servers
    weblive = get_weblive_backend()
    weblive.query_available_async()
    weblive._ready.wait()

    # Show the currently available servers
    print(weblive.available_servers)

    # Start firefox on the first available server and wait for it to finish
    weblive.create_automatic_user_and_run_session(
        serverid=weblive.available_servers[0].name, session="firefox",
        wait=True)
