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

import cairo

from gi.repository import Gtk, Gdk, Pango, GObject, GdkPixbuf
from gettext import gettext as _

from softwarecenter.backend import get_install_backend
from softwarecenter.db.application import AppDetails
from softwarecenter.enums import Icons
from softwarecenter.ui.gtk3.em import StockEms, em
from softwarecenter.ui.gtk3.drawing import darken
from softwarecenter.ui.gtk3.widgets.stars import Star, StarSize

_HAND = Gdk.Cursor.new(Gdk.CursorType.HAND2)


def _update_icon(image, icon, icon_size):
    if isinstance(icon, GdkPixbuf.Pixbuf):
        image = image.set_from_pixbuf(icon)
    elif isinstance(icon, Gtk.Image):
        image = image.set_from_pixbuf(icon.get_pixbuf())
    elif isinstance(icon, str):
        image = image.set_from_icon_name(icon, icon_size)
    else:
        msg = "Acceptable icon values: None, GdkPixbuf, GtkImage or str"
        raise TypeError(msg)
    return image


class _Tile(object):

    MIN_WIDTH = em(7)

    def __init__(self):
        self.set_focus_on_click(False)
        self.set_relief(Gtk.ReliefStyle.NONE)
        self.box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        self.box.set_size_request(self.MIN_WIDTH, -1)
        self.add(self.box)

    def build_default(self, label, icon, icon_size):
        if icon is not None:
            if isinstance(icon, Gtk.Image):
                self.image = icon
            else:
                self.image = Gtk.Image()
                _update_icon(self.image, icon, icon_size)
            self.box.pack_start(self.image, True, True, 0)

        self.label = Gtk.Label.new(label)
        self.box.pack_start(self.label, True, True, 0)


class TileButton(Gtk.Button, _Tile):

    def __init__(self):
        Gtk.Button.__init__(self)
        _Tile.__init__(self)


class TileToggleButton(Gtk.RadioButton, _Tile):

    def __init__(self):
        Gtk.RadioButton.__init__(self)
        self.set_mode(False)
        _Tile.__init__(self)


class LabelTile(TileButton):

    MIN_WIDTH = -1

    def __init__(self, label, icon, icon_size=Gtk.IconSize.MENU):
        TileButton.__init__(self)
        self.build_default(label, icon, icon_size)
        self.label.set_line_wrap(True)

        context = self.label.get_style_context()
        context.add_class("label-tile")

        self.connect("enter-notify-event", self.on_enter)
        self.connect("leave-notify-event", self.on_leave)

    def do_draw(self, cr):
        cr.save()
        A = self.get_allocation()

        if self.has_focus():
            Gtk.render_focus(self.get_style_context(),
                             cr,
                             3, 3,
                             A.width - 6, A.height - 6)

        for child in self:
            self.propagate_draw(child, cr)

        cr.restore()

    def on_enter(self, widget, event):
        window = self.get_window()
        window.set_cursor(_HAND)

    def on_leave(self, widget, event):
        window = self.get_window()
        window.set_cursor(None)


class CategoryTile(TileButton):

    def __init__(self, label, icon, icon_size=Gtk.IconSize.DIALOG):
        TileButton.__init__(self)
        self.set_size_request(em(8), -1)
        self.build_default(label, icon, icon_size)
        self.label.set_justify(Gtk.Justification.CENTER)
        self.label.set_alignment(0.5, 0.0)
        self.label.set_line_wrap(True)
        self.box.set_border_width(StockEms.SMALL)

        context = self.label.get_style_context()
        context.add_class("category-tile")

        self.connect("enter-notify-event", self.on_enter)
        self.connect("leave-notify-event", self.on_leave)

    def do_draw(self, cr):
        cr.save()
        A = self.get_allocation()

        if self.has_focus():
            Gtk.render_focus(self.get_style_context(),
                             cr,
                             3, 3,
                             A.width - 6, A.height - 6)

        for child in self:
            self.propagate_draw(child, cr)

        cr.restore()

    def on_enter(self, widget, event):
        window = self.get_window()
        window.set_cursor(_HAND)

    def on_leave(self, widget, event):
        window = self.get_window()
        window.set_cursor(None)


_global_featured_tile_width = em(11)


class FeaturedTile(TileButton):

    INSTALLED_OVERLAY_SIZE = 22
    _MARKUP = '<b><small>%s</small></b>'

    def __init__(self, helper, doc, icon_size=48):
        TileButton.__init__(self)
        self._pressed = False

        label = helper.get_appname(doc)
        icon = helper.get_icon_at_size(doc, icon_size, icon_size)
        stats = helper.get_review_stats(doc)
        helper.update_availability(doc)
        helper.connect("needs-refresh", self._on_needs_refresh, doc, icon_size)
        self.is_installed = helper.is_installed(doc)
        self._overlay = helper.icons.load_icon(Icons.INSTALLED_OVERLAY,
                                               self.INSTALLED_OVERLAY_SIZE,
                                               0)  # flags

        self.box.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.box.set_spacing(StockEms.SMALL)

        self.content_left = Gtk.Box.new(Gtk.Orientation.VERTICAL,
            StockEms.MEDIUM)
        self.content_right = Gtk.Box.new(Gtk.Orientation.VERTICAL, 1)
        self.box.pack_start(self.content_left, False, False, 0)
        self.box.pack_start(self.content_right, False, False, 0)
        self.image = Gtk.Image()
        _update_icon(self.image, icon, icon_size)
        self.content_left.pack_start(self.image, False, False, 0)

        self.title = Gtk.Label.new(self._MARKUP %
            GObject.markup_escape_text(label))
        self.title.set_alignment(0.0, 0.5)
        self.title.set_use_markup(True)
        self.title.set_tooltip_text(label)
        self.title.set_ellipsize(Pango.EllipsizeMode.END)
        self.content_right.pack_start(self.title, False, False, 0)

        categories = helper.get_categories(doc)
        if categories is not None:
            self.category = Gtk.Label.new('<span font_desc="%i">%s</span>' %
                (em(0.6), GObject.markup_escape_text(categories)))
            self.category.set_use_markup(True)
            self.category.set_alignment(0.0, 0.5)
            self.category.set_ellipsize(Pango.EllipsizeMode.END)
            self.content_right.pack_start(self.category, False, False, 4)

        stats_a11y = None
        if stats is not None:
            self.stars = Star(size=StarSize.SMALL)
            self.stars.render_outline = True
            self.stars.set_rating(stats.ratings_average)
            self.rating_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL,
                StockEms.SMALL)
            self.rating_box.pack_start(self.stars, False, False, 0)
            self.n_ratings = Gtk.Label.new(
                '<span font_desc="%i"> (%i)</span>' % (
                    em(0.45), stats.ratings_total))
            self.n_ratings.set_use_markup(True)
            self.n_ratings.set_name("subtle-label")
            self.n_ratings.set_alignment(0.0, 0.5)
            self.rating_box.pack_start(self.n_ratings, False, False, 0)
            self.content_right.pack_start(self.rating_box, False, False, 0)
            # TRANSLATORS: this is an accessibility description for eg orca and
            # is not visible in the ui
            stats_a11y = _('%(stars)d stars - %(reviews)d reviews') % {
                'stars': stats.ratings_average, 'reviews': stats.ratings_total}

            # work out width tile needs to be to ensure ratings text is all
            # visible
            req_width = (self.stars.size_request().width +
                         self.image.size_request().width +
                         self.n_ratings.size_request().width +
                         StockEms.MEDIUM * 3
                         )
            global _global_featured_tile_width
            _global_featured_tile_width = max(_global_featured_tile_width,
                                              req_width)

        details = AppDetails(db=helper.db, doc=doc)
        # TRANSLATORS: Free here means Gratis
        price = details.price or _("Free")
        if price == '0.00':
            # TRANSLATORS: Free here means Gratis
            price = _("Free")
        # TRANSLATORS: Free here means Gratis
        if price != _("Free"):
            price = 'US$ ' + price
        self.price = Gtk.Label.new(
            '<span font_desc="%i">%s</span>' % (em(0.6), price))
        self.price.set_use_markup(True)
        self.price.set_name("subtle-label")
        self.price.set_alignment(0.0, 0.5)
        self.content_right.pack_start(self.price, False, False, 0)

        self.set_name("featured-tile")

        a11y_name = '. '.join([t
            for t in [label, categories, stats_a11y, price] if t])
        self.get_accessible().set_name(a11y_name)

        backend = get_install_backend()
        backend.connect("transaction-finished",
                        self.on_transaction_finished,
                        helper, doc)

        self.connect("enter-notify-event", self.on_enter)
        self.connect("leave-notify-event", self.on_leave)
        self.connect("button-press-event", self.on_press)
        self.connect("button-release-event", self.on_release)

    def _on_needs_refresh(self, helper, pkgname, doc, icon_size):
        icon = helper.get_icon_at_size(doc, icon_size, icon_size)
        _update_icon(self.image, icon, icon_size)

    def do_get_preferred_width(self):
        w = _global_featured_tile_width
        return w, w

    def do_draw(self, cr):
        cr.save()
        A = self.get_allocation()
        if self._pressed:
            cr.translate(1, 1)

        if self.has_focus():
            Gtk.render_focus(self.get_style_context(),
                             cr,
                             3, 3,
                             A.width - 6, A.height - 6)

        for child in self:
            self.propagate_draw(child, cr)

        if self.is_installed:
            # paint installed tick overlay
            if self.get_direction() != Gtk.TextDirection.RTL:
                x = y = 36
            else:
                x = A.width - 56
                y = 36

            Gdk.cairo_set_source_pixbuf(cr, self._overlay, x, y)
            cr.paint()

        cr.restore()

    def on_transaction_finished(self, backend, result, helper, doc):
        trans_pkgname = str(result.pkgname)
        pkgname = helper.get_pkgname(doc)
        if trans_pkgname != pkgname:
            return

        # update installed state
        helper.update_availability(doc)
        self.is_installed = helper.is_installed(doc)
        self.queue_draw()

    def on_enter(self, widget, event):
        window = self.get_window()
        window.set_cursor(_HAND)
        return True

    def on_leave(self, widget, event):
        window = self.get_window()
        window.set_cursor(None)
        self._pressed = False
        return True

    def on_press(self, widget, event):
        self._pressed = True

    def on_release(self, widget, event):
        if not self._pressed:
            return
        self.emit("clicked")
        self._pressed = False


class ChannelSelector(Gtk.Button):

    PADDING = 0

    def __init__(self, section_button):
        Gtk.Button.__init__(self)
        alignment = Gtk.Alignment.new(0.5, 0.5, 0.0, 1.0)
        alignment.set_padding(self.PADDING, self.PADDING,
                              self.PADDING, self.PADDING)
        self.add(alignment)
        self.arrow = Gtk.Arrow.new(Gtk.ArrowType.DOWN, Gtk.ShadowType.IN)
        alignment.add(self.arrow)

        # vars
        self.parent_style_type = Gtk.Toolbar
        self.section_button = section_button
        self.popup = None
        self.connect("button-press-event", self.on_button_press)

    def do_draw(self, cr):
        cr.save()

        parent_style = self.get_ancestor(self.parent_style_type)
        context = parent_style.get_style_context()

        color = darken(context.get_border_color(Gtk.StateFlags.ACTIVE), 0.2)

        cr.set_line_width(1)

        a = self.get_allocation()
        lin = cairo.LinearGradient(0, 0, 0, a.height)
        lin.add_color_stop_rgba(0.1,
                                color.red,
                                color.green,
                                color.blue,
                                0.0)    # alpha
        lin.add_color_stop_rgba(0.5,
                                color.red,
                                color.green,
                                color.blue,
                                1.0)    # alpha
        lin.add_color_stop_rgba(1.0,
                                color.red,
                                color.green,
                                color.blue,
                                0.1)    # alpha
        cr.set_source(lin)

        cr.move_to(0.5, 0.5)
        cr.rel_line_to(0, a.height)
        cr.stroke()

        cr.move_to(a.width - 0.5, 0.5)
        cr.rel_line_to(0, a.height)
        cr.stroke()

        cr.restore()

        for child in self:
            self.propagate_draw(child, cr)

    def on_button_press(self, button, event):
        if self.popup is None:
            self.build_channel_selector()
        self.show_channel_sel_popup(self, event)
#~
    #~ def on_style_updated(self, widget):
        #~ context = widget.get_style_context()
        #~ context.save()
        #~ context.add_class("menu")
        #~ bgcolor = context.get_background_color(Gtk.StateFlags.NORMAL)
        #~ context.restore()
#~
        #~ self._dark_color = darken(bgcolor, 0.5)

    def show_channel_sel_popup(self, widget, event):

        def position_func(menu, (window, a)):
            if self.get_direction() != Gtk.TextDirection.RTL:
                tmpx = a.x
            else:
                tmpx = a.x + a.width - self.popup.get_allocation().width
            x, y = window.get_root_coords(tmpx,
                                          a.y + a.height)
            return (x, y, False)

        a = self.section_button.get_allocation()
        window = self.section_button.get_window()
        self.popup.popup(None, None, position_func, (window, a),
                         event.button, event.time)

    def set_build_func(self, build_func):
        self.build_func = build_func

    def build_channel_selector(self):
        self.popup = Gtk.Menu()
        self.popup.set_name('toolbar-popup')  # to set 'padding: 0;'
        self.popup.get_style_context().add_class('primary-toolbar')
        self.build_func(self.popup)


class SectionSelector(TileToggleButton):

    MIN_WIDTH = em(5)
    _MARKUP = '<small>%s</small>'

    def __init__(self, label, icon, icon_size=Gtk.IconSize.DIALOG):
        TileToggleButton.__init__(self)
        markup = self._MARKUP % label
        self.build_default(markup, icon, icon_size)
        self.label.set_use_markup(True)
        self.label.set_justify(Gtk.Justification.CENTER)

        context = self.get_style_context()
        context.add_class("section-sel-bg")

        context = self.label.get_style_context()
        context.add_class("section-sel")

        self.draw_hint_has_channel_selector = False
        self._alloc = None
        self._bg_cache = {}

        self.connect('size-allocate', self.on_size_allocate)
        self.connect('style-updated', self.on_style_updated)

    def on_size_allocate(self, *args):
        alloc = self.get_allocation()

        if (self._alloc is None or
            self._alloc.width != alloc.width or
            self._alloc.height != alloc.height):
            self._alloc = alloc
            # reset the bg cache
            self._bg_cache = {}

    def on_style_updated(self, *args):
        # also reset the bg cache
        self._bg_cache = {}

    def _cache_bg_for_state(self, state):
        a = self.get_allocation()
        # tmp surface on which we render the button bg as per the gtk
        # theme engine
        _surf = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                   a.width, a.height)
        cr = cairo.Context(_surf)

        context = self.get_style_context()
        context.save()
        context.set_state(state)

        Gtk.render_background(context, cr,
                          -5, -5, a.width + 10, a.height + 10)
        Gtk.render_frame(context, cr,
                          -5, -5, a.width + 10, a.height + 10)
        del cr

        # new surface which will be cached which
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                  a.width, a.height)
        cr = cairo.Context(surf)

        # gradient for masking
        lin = cairo.LinearGradient(0, 0, 0, a.height)
        lin.add_color_stop_rgba(0.0, 1, 1, 1, 0.1)
        lin.add_color_stop_rgba(0.25, 1, 1, 1, 0.7)
        lin.add_color_stop_rgba(0.5, 1, 1, 1, 1.0)
        lin.add_color_stop_rgba(0.75, 1, 1, 1, 0.7)
        lin.add_color_stop_rgba(1.0, 1, 1, 1, 0.1)

        cr.set_source_surface(_surf, 0, 0)
        cr.mask(lin)
        del cr

        # cache the resulting surf...
        self._bg_cache[state] = surf

    def do_draw(self, cr):
        state = self.get_state_flags()
        if self.get_active():
            if state not in self._bg_cache:
                self._cache_bg_for_state(state)

            cr.set_source_surface(self._bg_cache[state], 0, 0)
            cr.paint()

        for child in self:
            self.propagate_draw(child, cr)


class Link(Gtk.Label):

    __gsignals__ = {
        "clicked": (GObject.SignalFlags.RUN_LAST,
                    None,
                    (),)
        }

    def __init__(self, markup="", uri="none"):
        Gtk.Label.__init__(self)
        self._handler = 0
        self.set_markup(markup, uri)

    def set_markup(self, markup="", uri="none"):
        markup = '<a href="%s">%s</a>' % (uri, markup)
        Gtk.Label.set_markup(self, markup)
        if self._handler == 0:
            self._handler = self.connect("activate-link",
                self.on_activate_link)

    # synonyms for set_markup
    def set_label(self, label):
        return self.set_markup(label)

    def set_text(self, text):
        return self.set_markup(text)

    def on_activate_link(self, uri, data):
        self.emit("clicked")

    def disable(self):
        self.set_sensitive(False)
        self.set_name("subtle-label")

    def enable(self):
        self.set_sensitive(True)
        self.set_name("label")


class MoreLink(Gtk.Button):

    _MARKUP = '<b>%s</b>'
    _MORE = _("More")

    def __init__(self):
        Gtk.Button.__init__(self)
        self.label = Gtk.Label()
        self.label.set_padding(StockEms.SMALL, 0)
        self.label.set_markup(self._MARKUP % _(self._MORE))
        self.add(self.label)
        self._init_event_handling()
        context = self.get_style_context()
        context.add_class("more-link")

    def _init_event_handling(self):
        self.connect("enter-notify-event", self.on_enter)
        self.connect("leave-notify-event", self.on_leave)

    def do_draw(self, cr):

        if self.has_focus():
            layout = self.label.get_layout()
            a = self.get_allocation()
            e = layout.get_pixel_extents()[1]
            xo, yo = self.label.get_layout_offsets()
            Gtk.render_focus(self.get_style_context(), cr,
                             xo - a.x - 3, yo - a.y - 1,
                             e.width + 6, e.height + 2)

        for child in self:
            self.propagate_draw(child, cr)

    def on_enter(self, widget, event):
        window = self.get_window()
        window.set_cursor(_HAND)

    def on_leave(self, widget, event):
        window = self.get_window()
        window.set_cursor(None)


def _build_channels_list(popup):
    for i in range(3):
        item = Gtk.MenuItem.new()
        label = Gtk.Label.new("channel_name %s" % i)
        box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, StockEms.MEDIUM)
        box.pack_start(label, False, False, 0)
        item.add(box)
        item.show_all()
        popup.attach(item, 0, 1, i, i + 1)


def get_test_buttons_window():
    win = Gtk.Window()
    win.set_size_request(200, 200)

    vb = Gtk.VBox(spacing=12)
    win.add(vb)

    link = Link("<small>test link</small>", uri="www.google.co.nz")
    vb.pack_start(link, False, False, 0)

    button = Gtk.Button()
    button.set_label("channels")
    channels_button = ChannelSelector(button)
    channels_button.parent_style_type = Gtk.Window
    channels_button.set_build_func(_build_channels_list)
    hb = Gtk.HBox()
    hb.pack_start(button, False, False, 0)
    hb.pack_start(channels_button, False, False, 0)
    vb.pack_start(hb, False, False, 0)

    win.show_all()
    win.connect("destroy", Gtk.main_quit)
    return win

if __name__ == "__main__":
    win = get_test_buttons_window()
    Gtk.main()
