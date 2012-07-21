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
import os

from math import pi as PI
from gi.repository import Gtk, Gdk, GObject, PangoCairo

import softwarecenter.paths
from softwarecenter.ui.gtk3.em import em
from softwarecenter.ui.gtk3.drawing import rounded_rect

# pi constants
_2PI = 2 * PI
PI_OVER_180 = PI / 180


def radian(deg):
    return PI_OVER_180 * deg


class SymbolicIcon(Gtk.Image):

    DROPSHADOW = "%s-dropshadow.png"
    ICON = "%s.png"

    def __init__(self, name):
        Gtk.Image.__init__(self)

        context = self.get_style_context()
        context.add_class("symbolic-icon")

        # get base dir
        SYMBOLIC_DIR = os.path.join(
            softwarecenter.paths.datadir, "ui/gtk3/art/icons/")

        drop_shadow_path = SYMBOLIC_DIR + self.DROPSHADOW % name
        self.drop_shadow = cairo.ImageSurface.create_from_png(drop_shadow_path)
        icon_path = SYMBOLIC_DIR + self.ICON % name
        self.icon = cairo.ImageSurface.create_from_png(icon_path)

        self.drop_shadow_x_offset = 0
        self.drop_shadow_y_offset = 1

        self.connect("draw", self.on_draw, self.drop_shadow, self.icon,
                     self.drop_shadow_x_offset, self.drop_shadow_y_offset)

    def do_get_preferred_width(self):
        ds = self.drop_shadow
        return ds.get_width(), ds.get_width()

    def do_get_preferred_height(self):
        ds = self.drop_shadow
        return ds.get_height(), ds.get_height()

    def on_draw(self, widget, cr, drop_shadow, icon, ds_xo, ds_yo, xo=0, yo=0):
        a = widget.get_allocation()

        # dropshadow
        x = (a.width - drop_shadow.get_width()) * 0.5 + ds_xo + xo
        y = (a.height - drop_shadow.get_height()) * 0.5 + ds_yo + yo
        cr.set_source_surface(drop_shadow, int(x), int(y))
        cr.paint_with_alpha(0.4)

        # colorised icon
        state = widget.get_state_flags()
        context = widget.get_style_context()
        color = context.get_color(state)
        Gdk.cairo_set_source_rgba(cr, color)
        x = (a.width - icon.get_width()) * 0.5 + xo
        y = (a.height - icon.get_height()) * 0.5 + yo
        cr.mask_surface(icon, int(x), int(y))


class RotationAboutCenterAnimation(object):

    NEW_FRAME_DELAY = 50  # msec
    ROTATION_INCREMENT = radian(5)  # 5 degrees -> radians

    def __init__(self):
        self.rotation = 0
        self.animator = None
        self._stop_requested = False

    def new_frame(self):
        _continue = True
        self.rotation += self.ROTATION_INCREMENT
        if self.rotation >= _2PI:
            self.rotation = 0
            if self._stop_requested:
                self.animator = None
                self._stop_requested = False
                _continue = False
        self.queue_draw()
        return _continue

    def start(self):
        if not self.is_animating():
            self.animator = GObject.timeout_add(self.NEW_FRAME_DELAY,
                                                self.new_frame)

    def stop(self):
        if self.is_animating():
            self._stop_requested = True

    def is_animating(self):
        return self.animator is not None


class PendingSymbolicIcon(SymbolicIcon, RotationAboutCenterAnimation):

    BUBBLE_MAX_BORDER_RADIUS = em()
    BUBBLE_XPADDING = 5
    BUBBLE_YPADDING = 2
    BUBBLE_FONT_DESC = "Bold 8.5"

    def __init__(self, name):
        SymbolicIcon.__init__(self, name)
        RotationAboutCenterAnimation.__init__(self)

        # for painting the trans count bubble
        self.layout = self.create_pango_layout("")
        self.transaction_count = 0

    def on_draw(self, widget, cr, *args, **kwargs):
        cr.save()
        if self.is_animating():
            # translate to the center, then set the rotation
            a = widget.get_allocation()
            cr.translate(a.width * 0.5, a.height * 0.5)
            cr.rotate(self.rotation)
            # pass on the translation details
            kwargs['xo'] = -(a.width * 0.5)
            kwargs['yo'] = -(a.height * 0.5)

        # do icon drawing
        SymbolicIcon.on_draw(self, widget, cr, *args, **kwargs)
        cr.restore()

        if not self.is_animating() or not self.transaction_count:
            return

        # paint transactions bubble

        # get the layout extents and calc the bubble size
        ex = self.layout.get_pixel_extents()[1]
        x = ((a.width - self.icon.get_width()) / 2 +
            self.icon.get_width() - ex.width + 2)
        y = ((a.height - self.icon.get_height()) / 2 +
            self.icon.get_height() - ex.height + 2)
        w = ex.width + 2 * self.BUBBLE_XPADDING
        h = ex.height + 2 * self.BUBBLE_YPADDING

        border_radius = w / 3
        if border_radius > self.BUBBLE_MAX_BORDER_RADIUS:
            border_radius = self.BUBBLE_MAX_BORDER_RADIUS

        # paint background
        context = widget.get_style_context()
        context.save()
        color = context.get_background_color(Gtk.StateFlags.SELECTED)
        rounded_rect(cr, x + 1, y + 1, w - 2, h - 2, border_radius)
        Gdk.cairo_set_source_rgba(cr, color)
        cr.fill()
        context.restore()

        # paint outline
        rounded_rect(cr, x + 1.5, y + 1.5, w - 3, h - 3, border_radius - 1)
        cr.set_source_rgb(1, 1, 1)
        cr.set_line_width(1)
        cr.stroke()

        # paint layout
        cr.save()
        cr.translate(x + (w - ex.width) * 0.5, y + (h - ex.height) * 0.5)
        cr.move_to(0, 1)
        PangoCairo.layout_path(cr, self.layout)
        cr.set_source_rgba(0, 0, 0, 0.6)
        cr.fill()
        Gtk.render_layout(context, cr, 0, 0, self.layout)
        cr.restore()

    def set_transaction_count(self, count):
        if count == self.transaction_count:
            return
        self.transaction_count = count
        m = ('<span font_desc="%s" color="%s">%i</span>' %
            (self.BUBBLE_FONT_DESC, "white", count))
        self.layout.set_markup(m, -1)
        self.queue_draw()


def get_test_symbolic_icons_window():
    win = Gtk.Window()
    win.set_border_width(20)
    hb = Gtk.HBox(spacing=12)
    win.add(hb)
    ico = SymbolicIcon("available")
    hb.add(ico)
    ico = PendingSymbolicIcon("pending")
    ico.start()
    ico.set_transaction_count(33)
    hb.add(ico)
    ico = PendingSymbolicIcon("pending")
    ico.start()
    ico.set_transaction_count(1)
    hb.add(ico)
    win.show_all()
    win.connect("destroy", Gtk.main_quit)
    return win

if __name__ == "__main__":
    softwarecenter.paths.datadir = os.path.join(os.getcwd(), 'data')
    win = get_test_symbolic_icons_window()
    Gtk.main()
