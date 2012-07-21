#!/usr/bin/python
# Copyright (C) 2010-2011 Stephane Graber <stgraber@ubuntu.com>
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
# taken from
# lp:~weblive-dev/weblive/trunk/client/weblive.py
# and put into weblive_pristine.py until a ubuntu package is in main

import json
import urllib
import urllib2


class WebLiveJsonError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class WebLiveError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class WebLiveLocale(object):
    def __init__(self, locale, description):
        self.locale = locale
        self.description = description


class WebLivePackage(object):
    def __init__(self, pkgname, version, autoinstall):
        self.pkgname = pkgname
        self.version = version
        self.autoinstall = autoinstall


class WebLiveServer(object):
    def __init__(self, name, title, description, timelimit, userlimit,
            users, autoinstall):
        self.name = name
        self.title = title
        self.description = description
        self.timelimit = timelimit
        self.userlimit = userlimit
        self.current_users = users
        self.autoinstall = autoinstall

    def __repr__(self):
        return ("[WebLiveServer: %s (%s - %s), timelimit=%s, userlimit=%s, "
            "current_users=%s, autoinstall=%s") % (
            self.name, self.title, self.description, self.timelimit,
            self.userlimit, self.current_users, self.autoinstall)


class WebLiveEverythingServer(WebLiveServer):
    def __init__(self, name, title, description, timelimit, userlimit,
            users, autoinstall, locales, packages):
        self.locales = [WebLiveLocale(x[0], x[1]) for x in locales]
        self.packages = [WebLivePackage(x[0], x[1], x[2]) for x in packages]

        WebLiveServer.__init__(self, name, title, description, timelimit,
            userlimit, users, autoinstall)

    def __repr__(self):
        return ("[WebLiveServer: %s (%s - %s), timelimit=%s, userlimit=%s, "
            "current_users=%s, autoinstall=%s, nr_locales=%s, nr_pkgs=%s") % (
            self.name, self.title, self.description, self.timelimit,
            self.userlimit, self.current_users, self.autoinstall,
            len(self.locales), len(self.packages))


class WebLive:
    def __init__(self, url, as_object=False):
        self.url = url
        self.as_object = as_object

    def do_query(self, query):
        page = urllib2.Request(self.url, urllib.urlencode(
            {'query': json.dumps(query)}))

        try:
            response = urllib2.urlopen(page)
        except urllib2.HTTPError, e:
            raise WebLiveJsonError("HTTP return code: %s" % e.code)
        except urllib2.URLError, e:
            raise WebLiveJsonError("Failed to reach server: %s" % e.reason)

        try:
            reply = json.loads(response.read())
        except ValueError:
            raise WebLiveJsonError("Returned json object is invalid.")

        if reply['status'] != 'ok':
            if reply['message'] == -1:
                raise WebLiveJsonError("Missing 'action' field in query.")
            elif reply['message'] == -2:
                raise WebLiveJsonError("Missing parameter")
            elif reply['message'] == -3:
                raise WebLiveJsonError("Function '%s' isn't exported "
                    "over JSON." % query['action'])
            else:
                raise WebLiveJsonError("Unknown error code: %s" %
                    reply['message'])

        if 'message' not in reply:
            raise WebLiveJsonError("Invalid json reply")

        return reply

    def create_user(self, serverid, username, fullname, password,
            session, locale):
        query = {}
        query['action'] = 'create_user'
        query['serverid'] = serverid
        query['username'] = username
        query['fullname'] = fullname
        query['password'] = password
        query['session'] = session
        query['locale'] = locale
        reply = self.do_query(query)

        if type(reply['message']) != type([]):
            if reply['message'] == 1:
                raise WebLiveError("Reached user limit, return false.")
            elif reply['message'] == 2:
                raise WebLiveError("Different user with same username "
                    "already exists.")
            elif reply['message'] == 3:
                raise WebLiveError("Invalid fullname, must only contain "
                    "alphanumeric characters and spaces.")
            elif reply['message'] == 4:
                raise WebLiveError("Invalid login, must only contain "
                    "lowercase letters.")
            elif reply['message'] == 5:
                raise WebLiveError("Invalid password, must contain only "
                    "alphanumeric characters.")
            elif reply['message'] == 7:
                raise WebLiveError("Invalid server: %s" % serverid)
            else:
                raise WebLiveError("Unknown error code: %s" % reply['message'])

        return reply['message']

    def list_everything(self):
        query = {}
        query['action'] = 'list_everything'
        reply = self.do_query(query)

        if type(reply['message']) != type({}):
            raise WebLiveError("Invalid value, expected '%s' and got '%s'."
                % (type({}), type(reply['message'])))

        if not self.as_object:
            return reply['message']
        else:
            servers = []
            for server in reply['message']:
                attr = reply['message'][server]
                servers.append(WebLiveEverythingServer(
                    server,
                    attr['title'],
                    attr['description'],
                    attr['timelimit'],
                    attr['userlimit'],
                    attr['users'],
                    attr['autoinstall'],
                    attr['locales'],
                    attr['packages']))
            return servers

    def list_locales(self, serverid):
        query = {}
        query['action'] = 'list_locales'
        query['serverid'] = serverid
        reply = self.do_query(query)

        if type(reply['message']) != type([]):
            raise WebLiveError("Invalid value, expected '%s' and got '%s'."
                % (type({}), type(reply['message'])))

        if not self.as_object:
            return reply['message']
        else:
            return [WebLiveLocale(x[0], x[1]) for x in reply['message']]

    def list_package_blacklist(self):
        query = {}
        query['action'] = 'list_package_blacklist'
        reply = self.do_query(query)

        if type(reply['message']) != type([]):
            raise WebLiveError("Invalid value, expected '%s' and got '%s'."
                % (type({}), type(reply['message'])))

        if not self.as_object:
            return reply['message']
        else:
            return [WebLivePackage(x, None, None) for x in reply['message']]

    def list_packages(self, serverid):
        query = {}
        query['action'] = 'list_packages'
        query['serverid'] = serverid
        reply = self.do_query(query)

        if type(reply['message']) != type([]):
            raise WebLiveError("Invalid value, expected '%s' and got '%s'."
                % (type({}), type(reply['message'])))

        if not self.as_object:
            return reply['message']
        else:
            return [WebLivePackage(x[0], x[1], x[2]) for x in reply['message']]

    def list_servers(self):
        query = {}
        query['action'] = 'list_servers'
        reply = self.do_query(query)

        if type(reply['message']) != type({}):
            raise WebLiveError("Invalid value, expected '%s' and got '%s'."
                % (type({}), type(reply['message'])))

        if not self.as_object:
            return reply['message']
        else:
            servers = []
            for server in reply['message']:
                attr = reply['message'][server]
                servers.append(WebLiveServer(
                    server,
                    attr['title'],
                    attr['description'],
                    attr['timelimit'],
                    attr['userlimit'],
                    attr['users'],
                    attr['autoinstall']))
            return servers
