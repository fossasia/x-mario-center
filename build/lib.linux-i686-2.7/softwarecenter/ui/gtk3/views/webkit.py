# Copyright (C) 2010 Canonical
#
# Authors:
#  Michael Vogt
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

from gi.repository import WebKit as webkit
from gi.repository import Gtk
from gi.repository import Pango
import urlparse

from softwarecenter.i18n import get_language


class LocaleAwareWebView(webkit.WebView):

    def __init__(self):
        # actual webkit init
        webkit.WebView.__init__(self)
        self.connect("resource-request-starting",
                     self._on_resource_request_starting)

    def _on_resource_request_starting(self, view, frame, res, req, resp):
        lang = get_language()
        if lang:
            message = req.get_message()
            if message:
                headers = message.get_property("request-headers")
                headers.append("Accept-Language", lang)
        #def _show_header(name, value, data):
        #    print name, value
        #headers.foreach(_show_header, None)


class ScrolledWebkitWindow(Gtk.VBox):

    def __init__(self, include_progress_ui=False):
        super(ScrolledWebkitWindow, self).__init__()
        # get webkit
        self.webkit = LocaleAwareWebView()
        settings = self.webkit.get_settings()
        settings.set_property("enable-plugins", False)
        # add progress UI if needed
        if include_progress_ui:
            self._add_progress_ui()
        # create main webkitview
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.AUTOMATIC,
                               Gtk.PolicyType.AUTOMATIC)
        self.pack_start(self.scroll, True, True, 0)
        # embed the webkit view in a scrolled window
        self.scroll.add(self.webkit)
        self.show_all()

    def _add_progress_ui(self):
        # create toolbar box
        self.header = Gtk.HBox()
        # add spinner
        self.spinner = Gtk.Spinner()
        self.header.pack_start(self.spinner, False, False, 6)
        # add a url to the toolbar
        self.url = Gtk.Label()
        self.url.set_ellipsize(Pango.EllipsizeMode.END)
        self.url.set_alignment(0.0, 0.5)
        self.url.set_text("")
        self.header.pack_start(self.url, True, True, 0)
        # frame around the box
        self.frame = Gtk.Frame()
        self.frame.set_border_width(3)
        self.frame.add(self.header)
        self.pack_start(self.frame, False, False, 6)
        # connect the webkit stuff
        self.webkit.connect("notify::uri", self._on_uri_changed)
        self.webkit.connect("notify::load-status",
            self._on_load_status_changed)

    def _on_uri_changed(self, view, pspec):
        prop = pspec.name
        uri = view.get_property(prop)
        # the full uri is irellevant for the purchase view, but it is
        # interessting to know what protocol/netloc is in use so that the
        # user can verify its https on sites he is expecting
        scheme, netloc, path, params, query, frag = urlparse.urlparse(uri)
        if scheme == "file" and netloc == "":
            self.url.set_text("")
        else:
            self.url.set_text("%s://%s" % (scheme, netloc))
        # start spinner when the uri changes
        #self.spinner.start()

    def _on_load_status_changed(self, view, pspec):
        prop = pspec.name
        status = view.get_property(prop)
        #print status
        if status == webkit.LoadStatus.PROVISIONAL:
            self.spinner.start()
            self.spinner.show()
        if (status == webkit.LoadStatus.FINISHED or
            status == webkit.LoadStatus.FAILED):
            self.spinner.stop()
            self.spinner.hide()
