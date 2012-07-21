# Copyright (C) 2009 Canonical
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

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf

ICON_EXCEPTIONS = ["gnome"]


class Url404Error(IOError):
    pass


class Url403Error(IOError):
    pass


class SimpleShowImageDialog(Gtk.Dialog):
    """A dialog that shows a image """

    DEFAULT_WIDTH = 850
    DEFAULT_HEIGHT = 650

    def __init__(self, title, pixbuf, parent=None):
        Gtk.Dialog.__init__(self)
        # find parent window for the dialog
        if not parent:
            parent = self.get_parent()
            while parent:
                parent = parent.get_parent()

        # screenshot
        img = Gtk.Image.new_from_pixbuf(pixbuf)

        # scolled window for screenshot
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC,
                               Gtk.PolicyType.AUTOMATIC)
        scroll.add_with_viewport(img)
        content_area = self.get_content_area()
        content_area.pack_start(scroll, True, True, 0)

        # dialog
        self.set_title(title)
        self.set_transient_for(parent)
        self.set_destroy_with_parent(True)
        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.add_button(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
        self.set_default_size(SimpleShowImageDialog.DEFAULT_WIDTH,
                              SimpleShowImageDialog.DEFAULT_HEIGHT)

    def run(self):
        # show all and run the real thing
        self.show_all()
        Gtk.Dialog.run(self)


if __name__ == "__main__":

    # pixbuf
    d = SimpleShowImageDialog("Synaptic Screenshot",
        GdkPixbuf.Pixbuf.new_from_file(
        "/usr/share/software-center/default_banner/fallback.png"))
    d.run()
