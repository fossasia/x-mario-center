# Copyright (C) 2011 Canonical
#
# Authors:
#  Didier Roche
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

from gi.repository import Gtk


class MenuButton(Gtk.Button):

    def __init__(self, menu, icon=None, label=None):
        super(MenuButton, self).__init__()

        box = Gtk.Box()
        self.add(box)

        if icon:
            box.pack_start(icon, False, True, 1)
        if label:
            box.pack_start(Gtk.Label(label), True, True, 0)

        arrow = Gtk.Arrow.new(Gtk.ArrowType.DOWN, Gtk.ShadowType.OUT)
        box.pack_start(arrow, False, False, 1)

        self.menu = menu

        self.connect("button-press-event", self.on_button_pressed, menu)
        self.connect("clicked", self.on_keyboard_clicked, menu)

    def get_menu(self):
        '''Return menu attached to the button'''
        return self.menu

    def on_button_pressed(self, button, event, menu):
        menu.popup(None, None, self.menu_positionner, (button, event.x),
            event.button, event.time)

    def on_keyboard_clicked(self, button, menu):
        menu.popup(None, None, self.menu_positionner, (button, None), 1,
            Gtk.get_current_event_time())

    def menu_positionner(self, menu, (button, x_cursor_pos)):
        (button_id, x, y) = button.get_window().get_origin()

        # compute button position
        x_position = x + button.get_allocation().x
        y_position = (y + button.get_allocation().y +
            button.get_allocated_height())

        # if pressed by the mouse, center the X position to it
        if x_cursor_pos:
            x_position += x_cursor_pos
            x_position = x_position - menu.get_allocated_width() * 0.5

        # computer current monitor height
        current_screen = button.get_screen()
        num_monitor = current_screen.get_monitor_at_point(x_position,
            y_position)
        monitor_geo = current_screen.get_monitor_geometry(num_monitor)

        # if the menu width is of the current monitor, shift is a little
        if x_position < monitor_geo.x:
            x_position = monitor_geo.x
        if (x_position + menu.get_allocated_width() > monitor_geo.x +
            monitor_geo.width):
            x_position = (monitor_geo.x + monitor_geo.width -
                menu.get_allocated_width())

        # if the menu height is too long for the monitor, put it above the
        # widget
        if monitor_geo.height < y_position + menu.get_allocated_height():
            y_position = (y_position - button.get_allocated_height() -
                menu.get_allocated_height())

        return (x_position, y_position, True)


if __name__ == "__main__":

    win = Gtk.Window()
    win.set_size_request(200, 300)

    menu = Gtk.Menu()
    menuitem = Gtk.MenuItem(label="foo")
    menuitem2 = Gtk.MenuItem(label="long long long bar message")
    menu.append(menuitem)
    menu.append(menuitem2)
    menuitem.show()
    menuitem2.show()

    box1 = Gtk.Box()
    box1.pack_start(Gtk.Label("something before to show we don't cheat"),
        True, True, 0)
    win.add(box1)

    box2 = Gtk.Box()
    box2.set_orientation(Gtk.Orientation.VERTICAL)
    box1.pack_start(box2, True, True, 0)
    box2.pack_start(Gtk.Label("first label with multiple line"), True, True, 0)

    image = Gtk.Image.new_from_stock(Gtk.STOCK_PROPERTIES, Gtk.IconSize.BUTTON)
    label = "fooo"
    button_with_menu = MenuButton(menu, image, label)
    box2.pack_start(button_with_menu, False, False, 1)

    win.connect("destroy", lambda x: Gtk.main_quit())
    win.show_all()

    settings = Gtk.Settings.get_default()
    settings.set_property("gtk-button-images", True)

    Gtk.main()
