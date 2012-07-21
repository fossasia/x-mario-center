# Copyright (C) 2011 Canonical
#
# Authors:
#  Michael Vogt
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

import logging
import subprocess
import sys

from gettext import gettext as _
from gi.repository import Gdk

# FIXME: remove this try/except and add a dependency on gir1.2-gstreamer-0.10
#        if we (ever) start using VideoPlayerGtk3
try:
    from gi.repository import Gst
except ImportError:
    pass

from gi.repository import Gtk
from gi.repository import WebKit

LOG = logging.getLogger(__name__)


class VideoPlayer(Gtk.VBox):
    def __init__(self):
        super(VideoPlayer, self).__init__()
        self.set_size_request(400, 255)
        self.webkit = WebKit.WebView()
        settings = self.webkit.get_settings()
        # this disables the flash and other plugins so that we force html5
        # video on the system. This is works currently (11/2011) fine with
        # dailymotion and vimeo but youtube is opt-in only so we need
        # to monitor the situation
        settings.set_property("enable-plugins", False)
        # on navigation/new window etc, just use the proper browser
        self.webkit.connect(
            "new-window-policy-decision-requested", self._on_new_window)
        self.webkit.connect("create-web-view", self._on_create_web_view)
        self.pack_start(self.webkit, True, True, 0)
        self._uri = ""

    # helper required to follow ToS about the "back" link (flash version)
    def _on_new_window(self, view, frame, request, action, policy):
        subprocess.Popen(['xdg-open', request.get_uri()])
        return True

    # helper for the embedded html5 viewer
    def _on_create_web_view(self, view, frame):
        # mvo: this is not ideal, the trouble is that we do not get the
        #      url that the new view points to until after the view was
        #      created. But we don't want to be a full blow internal
        #      webbrowser so we simply go back to the youtube url here
        #      and the user needs to click "youtube" there again :/
        uri = frame.get_uri()
        subprocess.Popen(['xdg-open', uri])

    # uri property
    def _set_uri(self, v):
        self._uri = v or ""
        if self._uri:
            # only load the uri if it's defined, otherwise we may get:
            # Program received signal SIGSEGV, Segmentation fault.
            # webkit_web_frame_load_uri () from /usr/lib/libwebkitgtk-3.0.so.0
            self.webkit.load_uri(self._uri)

    def _get_uri(self):
        return self._uri
    uri = property(_get_uri, _set_uri, None, "uri property")

    def load_html_string(self, html):
        """ Instead of a video URI use a html embedded video like e.g.
            youtube or vimeo. Note that on a default install not all
            video codecs will play (no flash!), so be careful!
        """
        # FIXME: add something more useful here
        base_uri = "http://www.ubuntu.com"
        self.webkit.load_html_string(html, base_uri)


# AKA the-segfault-edition-with-no-documentation
class VideoPlayerGtk3(Gtk.VBox):

    def __init__(self):
        super(VideoPlayerGtk3, self).__init__()
        self.uri = ""
        # gtk ui
        self.movie_window = Gtk.DrawingArea()
        self.pack_start(self.movie_window, True, True, 0)
        self.button = Gtk.Button(_("Play"))
        self.pack_start(self.button, False, True, 0)
        self.button.connect("clicked", self.on_play_clicked)
        # player
        self.player = Gst.ElementFactory.make("playbin2", "player")
        # bus stuff
        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect("message", self.on_message)
        # FIXME: no sync messages currently so no playing in the widget :/
        # the former appears to be not working anymore with GIR, the
        # later is not exported (introspectable=0 in the GIR)
        bus.connect("sync-message", self.on_sync_message)
        #bus.set_sync_handler(self.on_sync_message)

    def on_play_clicked(self, button):
        if self.button.get_label() == _("Play"):
            self.button.set_label("Stop")
            print(self.uri)
            self.player.set_property("uri", self.uri)
            self.player.set_state(Gst.State.PLAYING)
        else:
            self.player.set_state(Gst.State.NULL)
            self.button.set_label(_("Play"))

    def on_message(self, bus, message):
        print("message: %s" % bus, message)
        if message is None:
            return
        t = message.type
        print(t)
        if t == Gst.MessageType.EOS:
            self.player.set_state(Gst.State.NULL)
            self.button.set_label(_("Play"))
        elif t == Gst.MessageType.ERROR:
            self.player.set_state(Gst.State.NULL)
            err, debug = message.parse_error()
            LOG.error("Error playing video: %s (%s)" % (err, debug))
            self.button.set_label(_("Play"))

    def on_sync_message(self, bus, message):
        print("sync: %s" % bus, message)
        if message is None or message.structure is None:
            return
        message_name = message.structure.get_name()
        if message_name == "prepare-xwindow-id":
            imagesink = message.src
            imagesink.set_property("force-aspect-ratio", True)
            Gdk.threads_enter()
            # FIXME: this is the way to do it, *but* get_xid() is not
            #        exported in the GIR
            xid = self.player.movie_window.get_window().get_xid()
            imagesink.set_xwindow_id(xid)
            Gdk.threads_leave()


def get_test_videoplayer_window():

    # youtube example fragment
    html_youtube = """<iframe width="640" height="390"
src="http://www.youtube.com/embed/h3oBU0NZJuA" frameborder="0"
allowfullscreen></iframe>"""
    # vimeo example video fragment
    html_vimeo = """<iframe
src="http://player.vimeo.com/video/2891554?title=0&amp;byline=0&amp;portrait=0"
width="400" height="308" frameborder="0" webkitAllowFullScreen
allowFullScreen></iframe><p><a href="http://vimeo.com/2891554">
Supertuxkart 0.6</a> from <a href="http://vimeo.com/user1183699">
constantin pelikan</a> on <a href="http://vimeo.com">Vimeo</a>.</p>"""
    # dailymotion example video fragment
    html_dailymotion = """<iframe frameborder="0" width="480" height="270"
src="http://www.dailymotion.com/embed/video/xm4ysu"></iframe>"""
    html_dailymotion2 = """<iframe frameborder="0" width="480" height="379"
src="http://www.dailymotion.com/embed/video/xdiktp"></iframe>"""

    html_youtube  # pyflakes
    html_dailymotion  # pyflakes
    html_dailymotion2  # pyflakes

    win = Gtk.Window.new(Gtk.WindowType.TOPLEVEL)
    win.set_default_size(500, 400)
    win.connect("destroy", Gtk.main_quit)
    player = VideoPlayer()
    win.add(player)
    if len(sys.argv) < 2:
        #player.uri = "http://upload.wikimedia.org/wikipedia/commons/9/9b/" \
        #    "Pentagon_News_Sample.ogg"
        #player.uri = "http://people.canonical.com/~mvo/totem.html"
        player.load_html_string(html_vimeo)
    else:
        player.uri = sys.argv[1]
    win.show_all()
    return win

if __name__ == "__main__":
    logging.basicConfig()
    Gdk.threads_init()
    # Gst.init(sys.argv)

    win = get_test_videoplayer_window()
    Gtk.main()
