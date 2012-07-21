# Copyright (C) 2010 Matthew McGowan
#
# Authors:
#   Matthew McGowan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Atk
from gi.repository import Gtk
from gi.repository import GObject

from gettext import gettext as _

DEFAULT_PART_SIZE = (28, -1)


class BackForwardButton(Gtk.HBox):

    __gsignals__ = {'left-clicked': (GObject.SignalFlags.RUN_LAST,
                                     None,
                                     ()),

                    'right-clicked': (GObject.SignalFlags.RUN_LAST,
                                     None,
                                     ())}

    def __init__(self, part_size=None):
        Gtk.HBox.__init__(self)

        atk_obj = self.get_accessible()
        atk_obj.set_name(_('History Navigation'))
        atk_obj.set_description(_('Navigate forwards and backwards.'))
        atk_obj.set_role(Atk.Role.PANEL)

        self._build_left_right_buttons()

        self.pack_start(self.left, True, True, 0)
        self.pack_end(self.right, True, True, 0)

        self.left.connect("clicked", self.on_clicked)
        self.right.connect("clicked", self.on_clicked)

    def _build_left_right_buttons(self):
        if self.get_direction() != Gtk.TextDirection.RTL:
            # ltr
            self.left = ButtonPart('left-clicked',
                arrow_type=Gtk.ArrowType.LEFT)
            self.right = ButtonPart('right-clicked',
                arrow_type=Gtk.ArrowType.RIGHT)

            context = self.left.get_style_context()
            context.add_class("backforward-left-button")
            context = self.right.get_style_context()
            context.add_class("backforward-right-button")

            self.set_button_atk_info_ltr()
        else:
            # rtl
            self.left = ButtonPart('left-clicked',
                arrow_type=Gtk.ArrowType.RIGHT)
            self.right = ButtonPart('right-clicked',
                arrow_type=Gtk.ArrowType.LEFT)

            context = self.left.get_style_context()
            context.add_class("backforward-right-button")
            context = self.right.get_style_context()
            context.add_class("backforward-left-button")

            self.set_button_atk_info_rtl()

    def on_clicked(self, button):
        self.emit(button.signal_name)

    def set_button_atk_info_ltr(self):
        # left button
        atk_obj = self.left.get_accessible()
        atk_obj.set_name(_('Back Button'))
        atk_obj.set_description(_('Navigates back.'))

        # right button
        atk_obj = self.right.get_accessible()
        atk_obj.set_name(_('Forward Button'))
        atk_obj.set_description(_('Navigates forward.'))

    def set_button_atk_info_rtl(self):
        # right button
        atk_obj = self.right.get_accessible()
        atk_obj.set_name(_('Back Button'))
        atk_obj.set_description(_('Navigates back.'))
        atk_obj.set_role(Atk.Role.PUSH_BUTTON)

        # left button
        atk_obj = self.left.get_accessible()
        atk_obj.set_name(_('Forward Button'))
        atk_obj.set_description(_('Navigates forward.'))
        atk_obj.set_role(Atk.Role.PUSH_BUTTON)

    def set_use_hand_cursor(self, use_hand):
        self.use_hand = use_hand


class ButtonPart(Gtk.Button):

    def __init__(self, signal_name, arrow_type):
        Gtk.Button.__init__(self)
        #~ self.set_relief(Gtk.ReliefStyle.NORMAL)
        self.arrow_type = arrow_type

        if self.arrow_type == Gtk.ArrowType.LEFT:
            self.arrow = Gtk.Image.new_from_icon_name('stock_left',
                                                 Gtk.IconSize.BUTTON)
        elif self.arrow_type == Gtk.ArrowType.RIGHT:
            self.arrow = Gtk.Image.new_from_icon_name('stock_right',
                                                 Gtk.IconSize.BUTTON)

        self.arrow.set_margin_left(2)
        self.arrow.set_margin_right(2)
        self.add(self.arrow)
        self.signal_name = signal_name

    def do_draw(self, cr):
        context = self.get_style_context()
        context.save()

        state = self.get_state_flags()
        if (state & Gtk.StateFlags.NORMAL) == 0:
            state = Gtk.StateFlags.PRELIGHT
        context.set_state(state)

        a = self.get_allocation()
        x = 0
        y = 0
        width = a.width
        height = a.height

        border = context.get_border(Gtk.StateFlags.PRELIGHT)

        if self.arrow_type == Gtk.ArrowType.LEFT:
            width += 2 * border.right
        elif self.arrow_type == Gtk.ArrowType.RIGHT:
            x -= border.left
            width += border.left

        Gtk.render_background(context, cr,
                              x, y, width, height)
        Gtk.render_frame(context, cr,
                         x, y, width, height)

        context.restore()

        for child in self:
            self.propagate_draw(child, cr)


# this is used in the automatic tests as well
def get_test_backforward_window():
    win = Gtk.Window()
    win.set_border_width(20)
    win.connect("destroy", lambda x: Gtk.main_quit())
    win.set_default_size(300, 100)
    backforward = BackForwardButton()
    win.add(backforward)
    return win

if __name__ == "__main__":
    win = get_test_backforward_window()
    win.show_all()

    Gtk.main()
