"""
 SimpleGladeApp.py
 Module that provides an object oriented abstraction to pygtk and gtkbuilder
 Copyright (C) 2009 Michael Vogt
 based on ideas from SimpleGladeBuilder by Sandino Flores Moreno
"""

# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; version 3.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
# USA

from gi.repository import Gtk


# based on SimpleGladeApp
class SimpleGtkbuilderApp(object):

    def __init__(self, path, domain):
        super(SimpleGtkbuilderApp, self).__init__()
        self.builder = Gtk.Builder()
        self.builder.set_translation_domain(domain)
        self.builder.add_from_file(path)
        self.builder.connect_signals(self)
        for o in self.builder.get_objects():
            if issubclass(type(o), Gtk.Buildable):
                name = Gtk.Buildable.get_name(o)
                setattr(self, name, o)

    def run(self):
        """
        Starts the main loop of processing events checking for Control-C.

        The default implementation checks wheter a Control-C is pressed,
        then calls on_keyboard_interrupt().

        Use this method for starting programs.
        """
        try:
            Gtk.main()
        except KeyboardInterrupt:
            self.on_keyboard_interrupt()

    def on_keyboard_interrupt(self):
        """
        This method is called by the default implementation of run()
        after a program is finished by pressing Control-C.
        """
        pass
