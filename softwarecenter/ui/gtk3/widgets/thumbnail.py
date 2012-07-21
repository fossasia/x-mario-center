# Copyright (C) 2011 Canonical
#
# Authors:
#  Matthew McGowan
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

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, Atk, Gio, GObject, GdkPixbuf

import logging
import os

from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.utils import SimpleFileDownloader

from imagedialog import SimpleShowImageDialog

from gettext import gettext as _

LOG = logging.getLogger(__name__)


class ScreenshotData(GObject.GObject):

    __gsignals__ = {"screenshots-available": (GObject.SIGNAL_RUN_FIRST,
                                              GObject.TYPE_NONE,
                                              (),),
                    }

    def __init__(self):
        GObject.GObject.__init__(self)
        self._sig = 0
        self._screenshots = []

    def set_app_details(self, app_details):
        if self._sig > 0:
            GObject.source_remove(self._sig)

        self.app_details = app_details
        self.appname = app_details.display_name
        self.pkgname = app_details.pkgname

        self._sig = self.app_details.connect(
            "screenshots-available", self._on_screenshots_available)

        self._screenshots = []
        self.app_details.query_multiple_screenshots()

    def _on_screenshots_available(self, screenshot_data, screenshots):
        self._screenshots = screenshots
        self.emit("screenshots-available")

    def get_n_screenshots(self):
        return len(self._screenshots)

    def get_nth_large_screenshot(self, index):
        return self._screenshots[index]['large_image_url']

    def get_nth_small_screenshot(self, index):
        return self._screenshots[index]['small_image_url']


class ScreenshotButton(Gtk.Button):

    def __init__(self):
        Gtk.Button.__init__(self)
        self.set_focus_on_click(False)
        self.set_valign(Gtk.Align.CENTER)
        self.image = Gtk.Image()
        self.add(self.image)

    def do_draw(self, cr):
        if self.has_focus():
            context = self.get_style_context()
            _a = self.get_allocation()
            a = self.image.get_allocation()
            pb = self.image.get_pixbuf()
            pbw, pbh = pb.get_width(), pb.get_height()
            Gtk.render_focus(
                context,
                cr,
                a.x - _a.x + (a.width - pbw) / 2 - 4,
                a.y - _a.y + (a.height - pbh) / 2 - 4,
                pbw + 8, pbh + 8)

        for child in self:
            self.propagate_draw(child, cr)


class ScreenshotGallery(Gtk.VBox):

    """ Widget that displays screenshot availability, download progress,
        and eventually the screenshot itself.
    """

    MAX_SIZE_CONSTRAINTS = 300, 250
    SPINNER_SIZE = 32, 32

    ZOOM_ICON = "stock_zoom-page"
    NOT_AVAILABLE_STRING = _('No screenshot available')

    USE_CACHING = True

    def __init__(self, distro, icons):
        Gtk.VBox.__init__(self)
        # data
        self.distro = distro
        self.icons = icons
        self.data = ScreenshotData()
        self.data.connect(
            "screenshots-available", self._on_screenshots_available)

        # state tracking
        self.ready = False
        self.screenshot_pixbuf = None
        self.screenshot_available = False
        self._thumbnail_sigs = []
        self._height = 0

        # zoom cursor
        try:
            zoom_pb = self.icons.load_icon(self.ZOOM_ICON, 22, 0)
            # FIXME
            self._zoom_cursor = Gdk.Cursor.new_from_pixbuf(
                                    Gdk.Display.get_default(),
                                    zoom_pb,
                                    0, 0)  # x, y
        except:
            self._zoom_cursor = None

        # convenience class for handling the downloading (or not) of
        # any screenshot
        self.loader = SimpleFileDownloader()
        self.loader.connect(
            'error',
            self._on_screenshot_load_error)
        self.loader.connect(
            'file-url-reachable',
            self._on_screenshot_query_complete)
        self.loader.connect(
            'file-download-complete',
            self._on_screenshot_download_complete)

        self._build_ui()
        # add cleanup handler to avoid signals after we are destroyed
        self.connect("destroy", self._on_destroy)

    def _on_destroy(self, widget):
        # we need to disconnect here otherwise gtk segfaults when it
        # tries to set a already destroyed gtk image
        self.loader.disconnect_by_func(
            self._on_screenshot_download_complete)
        self.loader.disconnect_by_func(
            self._on_screenshot_load_error)

    # overrides
    def do_get_preferred_width(self):
        if self.data.get_n_screenshots() <= 1:
            pb = self.button.image.get_pixbuf()
            if pb:
                width = pb.get_width() + 20
                return width, width
        return 320, 320

    def do_get_preferred_height(self):
        pb = self.button.image.get_pixbuf()
        if pb:
            height = pb.get_height()
            if self.data.get_n_screenshots() <= 1:
                height += 20
                height = max(self._height, height)
                self._height = height
                return height, height
            else:
                height += 110
                height = max(self._height, height)
                self._height = height
                return height, height
        self._height = max(self._height, 250)
        return self._height, self._height

    # private
    def _build_ui(self):
        self.set_border_width(3)
        # the frame around the screenshot (placeholder)
        self.screenshot = Gtk.VBox()
        self.pack_start(self.screenshot, True, True, 0)

        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(*self.SPINNER_SIZE)
        self.spinner.set_valign(Gtk.Align.CENTER)
        self.spinner.set_halign(Gtk.Align.CENTER)
        self.screenshot.add(self.spinner)

        # clickable screenshot button
        self.button = ScreenshotButton()
        self.screenshot.pack_start(self.button, True, False, 0)

        # unavailable layout
        self.unavailable = Gtk.Label(label=_(self.NOT_AVAILABLE_STRING))
        self.unavailable.set_alignment(0.5, 0.5)
        # force the label state to INSENSITIVE so we get the nice
        # subtle etched in look
        self.unavailable.set_state(Gtk.StateType.INSENSITIVE)
        self.screenshot.add(self.unavailable)

        self.thumbnails = ThumbnailGallery(self)
        self.thumbnails.set_margin_top(5)
        self.thumbnails.set_halign(Gtk.Align.CENTER)
        self.pack_end(self.thumbnails, False, False, 0)
        self.thumbnails.connect(
            "thumb-selected", self.on_thumbnail_selected)
        self.button.connect("clicked", self.on_clicked)
        self.button.connect('enter-notify-event', self._on_enter)
        self.button.connect('leave-notify-event', self._on_leave)
        self.show_all()

    def _on_enter(self, widget, event):
        if self.get_is_actionable():
            self.get_window().set_cursor(self._zoom_cursor)

    def _on_leave(self, widget, event):
        self.get_window().set_cursor(None)

    def _on_key_press(self, widget, event):
        # react to spacebar, enter, numpad-enter
        if (event.keyval in (Gdk.KEY_space, Gdk.KEY_Return,
            Gdk.KEY_KP_Enter) and self.get_is_actionable()):
            self.set_state(Gtk.StateType.ACTIVE)

    def _on_key_release(self, widget, event):
        # react to spacebar, enter, numpad-enter
        if (event.keyval in (Gdk.KEY_space, Gdk.KEY_Return,
            Gdk.KEY_KP_Enter) and self.get_is_actionable()):
            self.set_state(Gtk.StateType.NORMAL)
            self._show_image_dialog()

    def _show_image_dialog(self):
        """ Displays the large screenshot in a seperate dialog window """

        if self.data and self.screenshot_pixbuf:
            title = _("%s - Screenshot") % self.data.appname
            toplevel = self.get_toplevel()
            d = SimpleShowImageDialog(
                title, self.screenshot_pixbuf, toplevel)
            d.run()
            d.destroy()

    def _on_screenshots_available(self, screenshots):
        self.thumbnails.set_thumbnails_from_data(screenshots)

    def _on_screenshot_download_complete(self, loader, screenshot_path):
        try:
            self.screenshot_pixbuf = GdkPixbuf.Pixbuf.new_from_file(
                screenshot_path)
        except Exception, e:
            LOG.exception("Pixbuf.new_from_file() failed")
            self.loader.emit('error', GObject.GError, e)
            return False

        #context = self.button.get_style_context()
        tw, th = self.MAX_SIZE_CONSTRAINTS
        pb = self._downsize_pixbuf(self.screenshot_pixbuf, tw, th)
        self.button.image.set_from_pixbuf(pb)
        self.ready = True
        self.display_image()

    def _on_screenshot_load_error(self, loader, err_type, err_message):
        self.set_screenshot_available(False)
        self.ready = True

    def _on_screenshot_query_complete(self, loader, reachable):
        self.set_screenshot_available(reachable)
        if not reachable:
            self.ready = True

    def _downsize_pixbuf(self, pb, target_w, target_h):
        w = pb.get_width()
        h = pb.get_height()
        sf = min(float(target_w) / w, float(target_h) / h)
        sw = int(w * sf)
        sh = int(h * sf)
        return pb.scale_simple(sw, sh, GdkPixbuf.InterpType.BILINEAR)

    # public
    def download_and_display_from_url(self, url):
        self.loader.download_file(url, use_cache=self.USE_CACHING)

    def clear(self):
        """ All state trackers are set to their intitial states, and
            the old screenshot is cleared from the view.
        """
        self._height = 0
        self.clear_main_screenshot()
        self.thumbnails.clear()

    def clear_main_screenshot(self):
        self.screenshot_available = True
        self.ready = False
        self.display_spinner()

    def display_spinner(self):
        self.button.image.clear()
        self.button.hide()
        self.unavailable.hide()
        self.spinner.show()
        self.spinner.start()

    def display_unavailable(self):
        self.spinner.hide()
        self.spinner.stop()
        self.unavailable.show()
        self.button.hide()
        acc = self.get_accessible()
        acc.set_name(_(self.NOT_AVAILABLE_STRING))
        acc.set_role(Atk.Role.LABEL)

    def display_image(self):
        self.unavailable.hide()
        self.spinner.stop()
        self.spinner.hide()
        self.button.show_all()
        self.thumbnails.show()

    def get_is_actionable(self):
        """ Returns true if there is a screenshot available and
            the download has completed
        """
        return self.screenshot_available and self.ready

    def set_screenshot_available(self, available):
        """ Configures the ScreenshotView depending on whether there
            is a screenshot available.
        """
        if not available:
            self.display_unavailable()
        elif available and self.unavailable.get_property("visible"):
            self.display_spinner()
        self.screenshot_available = available

    def on_clicked(self, button):
        if self.get_is_actionable():
            self._show_image_dialog()

    def fetch_screenshots(self, app_details):
        """ Called to configure the screenshotview for a new application.
            The existing screenshot is cleared and the process of
            fetching a new screenshot is instigated.
        """
        self.clear()
        acc = self.get_accessible()
        acc.set_name(_('Fetching screenshot ...'))
        self.data.set_app_details(app_details)
        self.display_spinner()
        self.download_and_display_from_url(app_details.screenshot)

    def on_thumbnail_selected(self, gallery, id_):
        self.clear_main_screenshot()
        large_url = self.data.get_nth_large_screenshot(id_)
        self.download_and_display_from_url(large_url)

    def draw(self, widget, cr):
        """ Draws the thumbnail frame """
        pass


class Thumbnail(Gtk.Button):

    def __init__(self, id_, url, cancellable, gallery):
        Gtk.Button.__init__(self)
        self.id_ = id_

        def download_complete_cb(loader, path):
            width, height = ThumbnailGallery.THUMBNAIL_SIZE_CONTRAINTS
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        path,
                        width, height,  # width, height constraints
                        True)  # respect image proportionality
            im = Gtk.Image.new_from_pixbuf(pixbuf)
            self.add(im)
            self.show_all()

        loader = SimpleFileDownloader()
        loader.connect("file-download-complete", download_complete_cb)
        loader.download_file(
            url, use_cache=ScreenshotGallery.USE_CACHING)

        self.connect("draw", self.on_draw)

    def on_draw(self, thumb, cr):
        state = self.get_state_flags()
        if self.has_focus() or (state & Gtk.StateFlags.ACTIVE) > 0:
            return

        for child in self:
            self.propagate_draw(child, cr)
        return True


class ThumbnailGallery(Gtk.HBox):

    __gsignals__ = {
        "thumb-selected": (GObject.SIGNAL_RUN_LAST,
                           GObject.TYPE_NONE,
                           (int,),), }

    THUMBNAIL_SIZE_CONTRAINTS = 90, 80
    THUMBNAIL_MAX_COUNT = 3

    def __init__(self, gallery):
        Gtk.HBox.__init__(self)
        self.gallery = gallery
        self.distro = gallery.distro
        self.icons = gallery.icons
        self.cancel = Gio.Cancellable()
        self._prev = None
        self._handlers = []

    def clear(self):
        self.cancel.cancel()
        self.cancel.reset()

        for sig in self._handlers:
            GObject.source_remove(sig)

        for child in self:
            child.destroy()

    def set_thumbnails_from_data(self, data):
        self.clear()

        # if there are multiple screenshots
        n = data.get_n_screenshots()
        if n <= 1:
            return

        # pick the first ones, the data is sorted by most appropriate
        # version first - if at some later point we have a lot of
        # screenshots we could consider randomizing again
        for i in range(min(n, ThumbnailGallery.THUMBNAIL_MAX_COUNT)):
            url = data.get_nth_small_screenshot(i)
            self._create_thumbnail_for_url(i, url)

        # set first child to selected
        self._prev = self.get_children()[0]
        self._prev.set_state_flags(Gtk.StateFlags.SELECTED, False)

        self.show_all()

    def _create_thumbnail_for_url(self, index, url):
        thumbnail = Thumbnail(index, url, self.cancel, self.gallery)
        self.pack_start(thumbnail, False, False, 0)
        sig = thumbnail.connect("clicked", self.on_clicked)
        self._handlers.append(sig)

    def on_clicked(self, thumb):
        if self._prev is not None:
            self._prev.set_state_flags(Gtk.StateFlags.NORMAL, True)
        thumb.set_state_flags(Gtk.StateFlags.SELECTED, False)
        self._prev = thumb
        self.emit("thumb-selected", thumb.id_)


def get_test_screenshot_thumbnail_window():
    icons = Gtk.IconTheme.get_default()
    icons.append_search_path("/usr/share/app-install/icons/")

    import softwarecenter.distro
    distro = softwarecenter.distro.get_distro()

    win = Gtk.Window()
    win.set_border_width(10)

    from gi.repository import Gdk
    from softwarecenter.ui.gtk3.utils import init_sc_css_provider
    from softwarecenter.ui.gtk3.widgets.containers import FramedBox
    init_sc_css_provider(win, Gtk.Settings.get_default(),
                         Gdk.Screen.get_default(), "data")

    t = ScreenshotGallery(distro, icons)
    t.connect('draw', t.draw)
    frame = FramedBox()
    frame.add(t)
    win.set_data("screenshot_thumbnail_widget", t)

    vb = Gtk.VBox(spacing=6)
    win.add(vb)

    b = Gtk.Button('A button for focus testing')
    vb.pack_start(b, True, True, 0)
    win.set_data("screenshot_button_widget", b)
    vb.pack_start(frame, True, True, 0)

    win.show_all()
    win.connect('destroy', Gtk.main_quit)

    return win

if __name__ == '__main__':

    app_n = 0

    def testing_cycle_apps(_, thumb, apps, db):
        global app_n
        d = apps[app_n].get_details(db)

        if app_n + 1 < len(apps):
            app_n += 1
        else:
            app_n = 0

        thumb.fetch_screenshots(d)
        return True

    logging.basicConfig(level=logging.DEBUG)

    cache = get_pkg_info()
    cache.open()

    from softwarecenter.db.database import StoreDatabase
    xapian_base_path = "/var/cache/software-center"
    pathname = os.path.join(xapian_base_path, "xapian")
    db = StoreDatabase(pathname, cache)
    db.open()

    w = get_test_screenshot_thumbnail_window()
    t = w.get_data("screenshot_thumbnail_widget")
    b = w.get_data("screenshot_button_widget")

    from softwarecenter.db.application import Application
    apps = [Application("Movie Player", "totem"),
            Application("Comix", "comix"),
            Application("Gimp", "gimp"),
            Application("ACE", "uace")]

    b.connect("clicked", testing_cycle_apps, t, apps, db)

    Gtk.main()
