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

import logging
import gettext
from gettext import gettext as _

from gi.repository import Gtk, Gdk, GObject

from softwarecenter.ui.gtk3.em import StockEms, em, small_em, big_em


_star_surface_cache = {}

LOG = logging.getLogger(__name__)


class StarSize:
    SMALL = 1
    NORMAL = 2
    BIG = 3
    PIXEL_VALUE = 4


class StarFillState:
    FULL = 10
    EMPTY = 20


class StarRenderHints:
    NORMAL = 1
    REACTIVE = -1


class ShapeStar():
    def __init__(self, points, indent=0.61):
        self.coords = self._calc_coords(points, 1 - indent)

    def _calc_coords(self, points, indent):
        coords = []

        from math import cos, pi, sin
        step = pi / points

        for i in range(2 * points):
            if i % 2:
                x = (sin(step * i) + 1) * 0.5
                y = (cos(step * i) + 1) * 0.5
            else:
                x = (sin(step * i) * indent + 1) * 0.5
                y = (cos(step * i) * indent + 1) * 0.5

            coords.append((x, y))
        return coords

    def layout(self, cr, x, y, w, h):
        points = [(sx_sy[0] * w + x, sx_sy[1] * h + y)
            for sx_sy in self.coords]
        cr.move_to(*points[0])

        for p in points[1:]:
            cr.line_to(*p)

        cr.close_path()


class StarRenderer(ShapeStar):

    def __init__(self):
        ShapeStar.__init__(self, 5, 0.6)

        self.size = StarSize.NORMAL
        self.n_stars = 5
        self.spacing = 1
        self.rounded = True
        self.rating = 3
        self.hints = StarRenderHints.NORMAL

        self.pixel_value = None
        self._size_map = {StarSize.SMALL: small_em,
                          StarSize.NORMAL: em,
                          StarSize.BIG: big_em,
                          StarSize.PIXEL_VALUE: self.get_pixel_size}

    # private
    def _get_mangled_keys(self, size):
        keys = (size * self.hints + StarFillState.FULL,
                size * self.hints + StarFillState.EMPTY)
        return keys

    # public
    def create_normal_surfaces(self,
                    context, vis_width, vis_height, star_width):

        rgba1 = context.get_border_color(Gtk.StateFlags.NORMAL)
        rgba0 = context.get_color(Gtk.StateFlags.ACTIVE)

        lin = cairo.LinearGradient(0, 0, 0, vis_height)
        lin.add_color_stop_rgb(0, rgba0.red, rgba0.green, rgba0.blue)
        lin.add_color_stop_rgb(1, rgba1.red, rgba1.green, rgba1.blue)

        # paint full
        full_surf = cairo.ImageSurface(
                        cairo.FORMAT_ARGB32, vis_width, vis_height)

        cr = cairo.Context(full_surf)
        cr.set_source(lin)
        cr.set_line_width(1)
        if self.rounded:
            cr.set_line_join(cairo.LINE_CAP_ROUND)

        for i in range(self.n_stars):
            x = 1 + i * (star_width + self.spacing)
            self.layout(cr, x + 1, 1, star_width - 2, vis_height - 2)
            cr.stroke_preserve()
            cr.fill()

        del cr

        # paint empty
        empty_surf = cairo.ImageSurface(
                        cairo.FORMAT_ARGB32, vis_width, vis_height)

        cr = cairo.Context(empty_surf)
        cr.set_source(lin)
        cr.set_line_width(1)
        if self.rounded:
            cr.set_line_join(cairo.LINE_CAP_ROUND)

        for i in range(self.n_stars):
            x = 1 + i * (star_width + self.spacing)
            self.layout(cr, x + 1, 1, star_width - 2, vis_height - 2)
            cr.stroke()

        del cr

        return full_surf, empty_surf

    def create_reactive_surfaces(self,
                    context, vis_width, vis_height, star_width):

        # paint full
        full_surf = cairo.ImageSurface(
                        cairo.FORMAT_ARGB32, vis_width, vis_height)

        cr = cairo.Context(full_surf)
        if self.rounded:
            cr.set_line_join(cairo.LINE_CAP_ROUND)

        for i in range(self.n_stars):
            x = 1 + i * (star_width + self.spacing)
            self.layout(cr, x + 2, 2, star_width - 4, vis_height - 4)

        line_color = context.get_border_color(Gtk.StateFlags.NORMAL)
        cr.set_source_rgb(line_color.red, line_color.green,
                          line_color.blue)

        cr.set_line_width(3)
        cr.stroke_preserve()
        cr.clip()

        context.save()
        context.add_class("button")
        context.set_state(Gtk.StateFlags.NORMAL)

        Gtk.render_background(context, cr, 0, 0, vis_width, vis_height)

        context.restore()

        for i in range(self.n_stars):
            x = 1 + i * (star_width + self.spacing)
            self.layout(cr, x + 1.5, 1.5, star_width - 3, vis_height - 3)

        cr.set_source_rgba(1, 1, 1, 0.8)
        cr.set_line_width(1)
        cr.stroke()

        del cr

        # paint empty
        empty_surf = cairo.ImageSurface(
                        cairo.FORMAT_ARGB32, vis_width, vis_height)

        cr = cairo.Context(empty_surf)
        if self.rounded:
            cr.set_line_join(cairo.LINE_CAP_ROUND)

        line_color = context.get_border_color(Gtk.StateFlags.NORMAL)
        cr.set_source_rgb(line_color.red, line_color.green,
                          line_color.blue)

        for i in range(self.n_stars):
            x = 1 + i * (star_width + self.spacing)
            self.layout(cr, x + 2, 2, star_width - 4, vis_height - 4)

        cr.set_line_width(3)
        cr.stroke()

        del cr

        return full_surf, empty_surf

    def update_cache_surfaces(self, context, size):
        LOG.debug('update cache')
        global _star_surface_cache

        star_width = vis_height = self._size_map[size]()
        vis_width = (star_width + self.spacing) * self.n_stars

        if self.hints == StarRenderHints.NORMAL:
            surfs = self.create_normal_surfaces(context, vis_width,
                                                vis_height, star_width)

        elif self.hints == StarRenderHints.REACTIVE:
            surfs = self.create_reactive_surfaces(
                                    context, vis_width,
                                    vis_height, star_width)

        # dict keys
        full_key, empty_key = self._get_mangled_keys(size)
        # save surfs to dict
        _star_surface_cache[full_key] = surfs[0]
        _star_surface_cache[empty_key] = surfs[1]
        return surfs

    def lookup_surfaces_for_size(self, size):
        full_key, empty_key = self._get_mangled_keys(size)

        if full_key not in _star_surface_cache:
            return None, None

        full_surf = _star_surface_cache[full_key]
        empty_surf = _star_surface_cache[empty_key]
        return full_surf, empty_surf

    def render_star(self, context, cr, x, y):
        size = self.size

        full, empty = self.lookup_surfaces_for_size(size)
        if full is None:
            full, empty = self.update_cache_surfaces(context, size)

        fraction = self.rating / self.n_stars

        stars_width = star_height = full.get_width()

        full_width = round(fraction * stars_width, 0)
        cr.rectangle(x, y, full_width, star_height)
        cr.clip()
        cr.set_source_surface(full, x, y)
        cr.paint()
        cr.reset_clip()

        if fraction < 1.0:
            empty_width = stars_width - full_width
            cr.rectangle(x + full_width, y, empty_width, star_height)
            cr.clip()
            cr.set_source_surface(empty, x, y)
            cr.paint()
            cr.reset_clip()

    def get_pixel_size(self):
        return self.pixel_value

    def get_visible_size(self, context):
        surf, _ = self.lookup_surfaces_for_size(self.size)
        if surf is None:
            surf, _ = self.update_cache_surfaces(context, self.size)
        return surf.get_width(), surf.get_height()


class Star(Gtk.EventBox, StarRenderer):
    def __init__(self, size=StarSize.NORMAL):
        Gtk.EventBox.__init__(self)
        StarRenderer.__init__(self)
        self.set_name("featured-star")

        self.label = None
        self.size = size

        self.xalign = 0.5
        self.yalign = 0.5

        self._render_allocation_bbox = False

        self.set_visible_window(False)
        self.connect("draw", self.on_draw)
        self.connect("style-updated", self.on_style_updated)

    def do_get_preferred_width(self):
        context = self.get_style_context()
        pref_w, _ = self.get_visible_size(context)
        return pref_w, pref_w

    def do_get_preferred_height(self):
        context = self.get_style_context()
        _, pref_h = self.get_visible_size(context)
        return pref_h, pref_h

    def set_alignment(self, xalign, yalign):
        self.xalign = xalign
        self.yalign = yalign
        self.queue_draw()

    #~ def set_padding(*args):
        #~ return

    def get_alignment(self):
        return self.xalign, self.yalign

    #~ def get_padding(*args):
        #~ return

    def on_style_updated(self, widget):
        global _star_surface_cache
        _star_surface_cache = {}
        self.queue_draw()

    def on_draw(self, widget, cr):
        self.render_star(widget.get_style_context(), cr, 0, 0)

        if self._render_allocation_bbox:
            a = widget.get_allocation()
            cr.rectangle(0, 0, a.width, a.height)
            cr.set_source_rgb(1, 0, 0)
            cr.set_line_width(2)
            cr.stroke()

    def set_n_stars(self, n_stars):
        if n_stars == self.n_stars:
            return

        self.n_stars = n_stars
        global _star_surface_cache
        _star_surface_cache = {}
        self.queue_draw()

    def set_rating(self, rating):
        self.rating = float(rating)
        self.queue_draw()

    def set_avg_rating(self, rating):
        # compat for ratings container
        return self.set_rating(rating)

    def set_size(self, size):
        self.size = size
        self.queue_draw()

    def set_size_big(self):
        return self.set_size(StarSize.BIG)

    def set_size_small(self):
        return self.set_size(StarSize.SMALL)

    def set_size_normal(self):
        return self.set_size(StarSize.NORMAL)

    def set_use_rounded_caps(self, use_rounded):
        self.rounded = use_rounded
        global _star_surface_cache
        _star_surface_cache = {}
        self.queue_draw()

    def set_size_as_pixel_value(self, pixel_value):
        if pixel_value == self.pixel_value:
            return

        global _star_surface_cache
        keys = (StarSize.PIXEL_VALUE + StarFillState.FULL,
                StarSize.PIXEL_VALUE + StarFillState.EMPTY)

        for key in keys:
            if key in _star_surface_cache:
                del _star_surface_cache[key]

        self.pixel_value = pixel_value
        self.set_size(StarSize.PIXEL_VALUE)


class StarRatingsWidget(Gtk.HBox):

    def __init__(self):
        Gtk.Box.__init__(self)
        self.set_spacing(StockEms.SMALL)
        self.stars = Star()
        self.stars.set_size_small()
        self.pack_start(self.stars, False, False, 0)
        self.label = Gtk.Label()
        self.label.set_alignment(0, 0.5)
        self.pack_start(self.label, False, False, 0)

    def set_avg_rating(self, rating):
        # compat for ratings container
        return self.stars.set_rating(rating)

    def set_nr_reviews(self, nr_reviews):
        s = gettext.ngettext(
            "%(nr_ratings)i rating",
            "%(nr_ratings)i ratings",
            nr_reviews) % {'nr_ratings': nr_reviews}

        # FIXME don't use fixed color
        m = '<span color="#8C8C8C"><small>(%s)</small></span>'
        self.label.set_markup(m % s)


class ReactiveStar(Star):

    __gsignals__ = {
        "changed": (GObject.SignalFlags.RUN_LAST,
                    None,
                    (),)
        }

    def __init__(self, size=StarSize.BIG):
        Star.__init__(self, size)
        self.hints = StarRenderHints.REACTIVE
        self.set_rating(0)

        self.set_can_focus(True)
        self.set_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                        Gdk.EventMask.BUTTON_RELEASE_MASK |
                        Gdk.EventMask.KEY_RELEASE_MASK |
                        Gdk.EventMask.KEY_PRESS_MASK |
                        Gdk.EventMask.ENTER_NOTIFY_MASK |
                        Gdk.EventMask.LEAVE_NOTIFY_MASK)

        self.connect("enter-notify-event", self.on_enter_notify)
        self.connect("leave-notify-event", self.on_leave_notify)
        self.connect("button-press-event", self.on_button_press)
        self.connect("button-release-event", self.on_button_release)
        self.connect("key-press-event", self.on_key_press)
        self.connect("key-release-event", self.on_key_release)
        self.connect("focus-in-event", self.on_focus_in)
        self.connect("focus-out-event", self.on_focus_out)

    # signal handlers
    def on_enter_notify(self, widget, event):
        pass

    def on_leave_notify(self, widget, event):
        pass

    def on_button_press(self, widget, event):
        pass

    def on_button_release(self, widget, event):
        star_index = self.get_star_at_xy(event.x, event.y)
        if star_index is None:
            return
        self.set_rating(star_index)
        self.emit('changed')

    def on_key_press(self, widget, event):
        pass

    def on_key_release(self, widget, event):
        pass

    def on_focus_in(self, widget, event):
        pass

    def on_focus_out(self, widget, event):
        pass

    # public
    def get_rating(self):
        return self.rating

    def render_star(self, widget, cr, x, y):
        # paint focus

        StarRenderer.render_star(self, widget, cr, x, y)
        # if a star is hovered paint prelit star

    def get_star_at_xy(self, x, y, half_star_precision=False):
        star_width = self._size_map[self.size]()

        star_index = x / star_width
        remainder = 1.0

        if half_star_precision:
            if round((x % star_width) / star_width, 1) <= 0.5:
                remainder = 0.5

        if star_index > self.n_stars:
            return None

        return int(star_index) + remainder


class StarRatingSelector(Gtk.Box):
    RATING_WORDS = [_('Hint: Click a star to rate this app'),  # unrated
                    _('Awful'),         # 1 star rating
                    _('Poor'),          # 2 star rating
                    _('Adequate'),      # 3 star rating
                    _('Good'),          # 4 star rating
                    _('Excellent')]     # 5 star rating

    INIT_RATING = 3
    N_STARS = 5

    def __init__(self):
        Gtk.Box.__init__(self)
        self.set_spacing(StockEms.SMALL)

        self.selector = ReactiveStar()
        self.selector.set_n_stars(self.N_STARS)
        self.selector.set_rating(self.INIT_RATING)
        self.selector.set_size_as_pixel_value(big_em(3))

        text = self.RATING_WORDS[self.INIT_RATING]
        self.caption = Gtk.Label.new(text)

        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.pack_start(self.selector, False, False, 0)
        self.pack_start(self.caption, False, False, 0)


# test helper also used in the unit tests
def get_test_stars_window():
    win = Gtk.Window()
    win.set_size_request(200, 200)

    vb = Gtk.VBox()
    vb.set_spacing(6)
    win.add(vb)

    vb.add(Gtk.Button())
    vb.add(Gtk.Label(label="BLAHHHHHH"))

    star = Star()
    star.set_n_stars(5)
    star.set_rating(2.5)
    star.set_size(StarSize.SMALL)
    vb.pack_start(star, False, False, 0)

    star = Star()
    star.set_n_stars(5)
    star.set_rating(2.5)
    star.set_size(StarSize.NORMAL)
    vb.pack_start(star, False, False, 0)

    star = Star()
    star.set_n_stars(5)
    star.set_rating(2.575)
    star.set_size(StarSize.BIG)
    vb.pack_start(star, False, False, 0)

    star = Star()
    star.set_n_stars(5)
    star.set_rating(3.333)
    star.set_size_as_pixel_value(36)
    vb.pack_start(star, False, False, 0)

    star = ReactiveStar()
    star.set_n_stars(5)
    star.set_rating(3)
    star.set_size_as_pixel_value(big_em(3))
    vb.pack_start(star, False, False, 0)

    selector = StarRatingSelector()
    vb.pack_start(selector, False, False, 0)

    win.connect("destroy", Gtk.main_quit)
    return win

if __name__ == "__main__":
    win = get_test_stars_window()
    win.show_all()
    Gtk.main()
