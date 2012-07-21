# Copyright (C) 2010 Canonical
#
# Authors:
#  Jacob Johan Edwards
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

from gi.repository import Gtk, Gdk, GObject

LOG = logging.getLogger(__name__)


class ActionBar(Gtk.HBox):
    """
    This is a gtk box wrapped so that all child widgets, save one, align
    to the right. The widget does not show by default when its parent
    calls show_all(), but rather autoshows and autohides when buttons
    (or a left-aligned label) are added and removed.

    The widget is only intended to hold buttons and a label, for which
    it has specific methods; general add and pack are not implemented.

    See:
https://wiki.ubuntu.com/SoftwareCenter#Main%20window
https://wiki.ubuntu.com/SoftwareCenter#Custom%20package%20lists
https://wiki.ubuntu.com/SoftwareCenter#software-list-view-disclosure
https://wiki.ubuntu.com/SoftwareCenter#Learning_how_to_launch_an_application
    """

    PADDING = 4

    ANIMATE_START_DELAY = 50
    ANIMATE_STEP_INTERVAL = 10
    ANIMATE_STEP = 8

    def __init__(self):
        super(ActionBar, self).__init__(spacing=self.PADDING)
        self._btns = Gtk.HBox(spacing=self.PADDING)
        self._btns.set_border_width(self.PADDING)
        self._label_hbox = Gtk.HBox()
        self._label_hbox.set_border_width(self.PADDING)
        # So that all buttons children right align
        self._btn_bin = Gtk.Alignment.new(1.0, 0.0, 1.0, 1.0)
        self._btn_bin.set_padding(0, 0, 0, 10)
        self._btn_bin.add(self._btns)
        # Buttons go on the right, labels on the left (in LTR mode)
        super(ActionBar, self).pack_start(self._label_hbox, False, False, 10)
        super(ActionBar, self).pack_end(self._btn_bin, False, True, 0)

        # Don't show_all() by default.
        self.set_no_show_all(True)
        self._label_hbox.show_all()
        self._btn_bin.show_all()
        self._visible = False

        # listen for size allocation events, used for implementing the
        # action bar slide in/out animation effect
        self.connect('size-allocate', self._on_size_allocate)
        self._is_sliding_in = False
        self._is_sliding_out = False
        self._target_height = None

        self.connect("draw", self._on_draw)

    def add_button(self, id, label, result, *result_args):
        """Adds a button and shows the bar.

        Keyword arguments:
        id -- A unique identifier for the button
        label -- A string for the button label
        result -- A function to be called on button click
        result_args -- Any arguments for the result function
        """
        overwrite = self.get_button(id)
        if overwrite:
            self._btns.remove(overwrite)
        btn = Gtk.Button(label)
        btn.connect("clicked", self._callback(result, result_args))
        btn.id = id
        btn.show()
        self._btns.pack_start(btn, False, True, 0)

        if not self._visible:
            # always animate with buttons
            self._show(animate=True)

    def remove_button(self, id):
        """Removes a button. Hides bar if no buttons left."""
        children = self._btns.get_children()
        for child in children:
            if child.id == id:
                # lock the height of the action bar when removing buttons to
                # prevent an unsightly resize if a label remains but all
                # buttons are removed
                self.set_size_request(-1, self.get_allocation().height)
                self._btns.remove(child)
                if len(children) == 1 and not len(self._label_hbox):
                    # always animate with buttons
                    self._hide(animate=True)
                return

    def set_label(self, text, link_result=None, *link_result_args):
        """
        Places a string on the left and shows the actionbar.
        Note the "_" symbol acts to delimit sections treated as a link.
        For example, in text="Lorem _ ipsum_ dolor _sit amat", clicking
        the section " ipsum" or "sit amat" will trigger the link_result.

        Keyword arguments:
        text -- a string optionally with "_" to indicate a link button.
        link_result -- A function to be called on link click
        link_result_args -- Any arguments for the result function
        """
        sections = text.split("_")
        LOG.debug("got sections '%s'" % sections)
        self._label_text = text

        for i, text_for_label in enumerate(sections):
            action_bar_item = Gtk.Label(text_for_label)
            # every second item in the bar is a clickable link,
            # this is because the text.split("_") earlier (all links
            # are put into "_foo_"
            # FIXME: actually remove the "_" and use proper <a href>"
            #        in the label, but this requires a string change
            #        so we need to do it after 12.04
            if not i % 2:
                markup = text_for_label
                action_bar_item.set_markup(markup)
            else:
                markup = '<a href="">%s</a>' % text_for_label
                action_bar_item.set_markup(markup)
                action_bar_item.connect("activate-link",
                    self._callback(link_result, link_result_args))
            self._label_hbox.pack_start(action_bar_item, True, True, 0)

        self._label_hbox.show_all()
        self._show(animate=False)

    def unset_label(self):
        """
        Removes the currently set label, hiding the actionbar if no
        buttons are displayed.
        """
        self._label_text = ""

        # Destroy all event boxes holding text segments.
        while len(self._label_hbox):
            last = self._label_hbox.get_children()[-1]
            self._label_hbox.remove(last)

        window = self.get_window()
        if window:
            window.set_cursor(None)
        # Then hide if there's nothing else visible.
        if not len(self._btns):
            self._hide(animate=False)

    def get_button(self, id):
        """Returns a button, or None if `id` links to no button."""
        for child in self._btns.get_children():
            if child.id == id:
                return child

    def clear(self):
        """Removes all contents and hides the bar."""
        animate = len(self._btns.get_children()) > 0
        self._hide(animate)
        for child in self._btns.get_children():
                self._btns.remove(child)
        self.unset_label()

    # The following Gtk.Container methods are deimplemented to prevent
    # overwriting of the _elems children box, and because the only
    # intended contents of an ActionBar are buttons and perhaps a text
    # label.

    def add(self, widget):
        """Not Implemented: Do not call."""
        raise NotImplementedError

    def add_with_properties(self, widget):
        """Not Implemented: Do not call."""
        raise NotImplementedError

    def remove(self, widget):
        """Not Implemented: Do not call."""
        raise NotImplementedError

    def pack_start(self, *args):
        """Not Implemented: Do not call."""
        raise NotImplementedError

    def pack_default_start(self, *args):
        """Not Implemented: Do not call."""
        raise NotImplementedError

    def pack_end(self, *args):
        """Not Implemented: Do not call."""
        raise NotImplementedError

    def pack_default_end(self, *args):
        """Not Implemented: Do not call."""
        raise NotImplementedError

    # Internal methods

    def _show(self, animate):
        if self._visible or self._is_sliding_in:
            return
        self._visible = True
        if animate:
            self._slide_in()
        else:
            super(ActionBar, self).show()

    def _hide(self, animate):
        if not self._visible or self._is_sliding_out:
            return
        if animate:
            self._slide_out()
        else:
            self.set_size_request(-1, -1)
            self._visible = False
            super(ActionBar, self).hide()

    def _slide_in(self):
        self._is_sliding_in = True
        self._target_height = self.get_size_request()[1]
        self._current_height = 0
        self.set_size_request(-1, self._current_height)
        super(ActionBar, self).show()
        GObject.timeout_add(self.ANIMATE_START_DELAY,
                            self._slide_in_cb)

    def _slide_out(self):
        self._is_sliding_out = True
        self._target_height = 0
        self._current_height = self.get_size_request()[1]
        GObject.timeout_add(self.ANIMATE_START_DELAY,
                            self._slide_out_cb)

    def _slide_in_cb(self):
        if (self._is_sliding_in and
            self._current_height < self._target_height):
            new_height = self._current_height + self.ANIMATE_STEP
            if new_height > self._target_height:
                new_height = self._target_height
            self.set_size_request(-1, new_height)
        else:
            self._is_sliding_in = False

    def _slide_out_cb(self):
        if (self._is_sliding_out and
            self._current_height > self._target_height):
            new_height = self._current_height - self.ANIMATE_STEP
            if new_height <= self._target_height:
                new_height = self._target_height
                self._is_sliding_out = False
                self.set_size_request(-1, -1)
                self._visible = False
                super(ActionBar, self).hide()
            else:
                self.set_size_request(-1, new_height)

    def _on_size_allocate(self, widget, allocation):
        # FIXME: mvo: allocation.height is no longer accessable with gtk3
        #        THIS SEEMS TO BREAK THE ANIMATION
        #height = allocation.height
        height = widget.get_allocation().height
        if self._is_sliding_in:
            self._current_height = height
            GObject.timeout_add(self.ANIMATE_STEP_INTERVAL,
                                self._slide_in_cb,
                                priority=100)
        elif self._is_sliding_out:
            self._current_height = height
            GObject.timeout_add(self.ANIMATE_STEP_INTERVAL,
                                self._slide_out_cb,
                                priority=100)
        else:
            self.queue_draw()

    def _on_draw(self, widget, cr):
        a = widget.get_allocation()
        context = widget.get_style_context()

        color = context.get_background_color(widget.get_state_flags())
        cr.set_source_rgb(color.red, color.green, color.blue)
        cr.paint()

        color = context.get_border_color(widget.get_state_flags())
        cr.set_source_rgba(color.red, color.green, color.blue, 0.5)
        cr.set_line_width(1)
        cr.move_to(0.5, 0.5)
        cr.rel_line_to(a.width - 1, 0)
        cr.stroke()

    def _callback(self, function, args):
        # Disposes of the 'widget' argument that
        # Gtk.Widget.connect() prepends to calls.
        callback = lambda *trash_args: function(*args)
        return callback

    def _hover_link(self, linkbox, *args):
        # Makes the link in given eventbox bold
#        label = linkbox.get_child()
#        label.set_markup("<b><u>%s</u></b>" % label.get_text())
        window = self.get_window()
        window.set_cursor(Gdk.Cursor.new(Gdk.CursorType.HAND2))

    def _unhover_link(self, linkbox, *args):
        # Sets the link in given eventbox to its base state
#        label = linkbox.get_child()
#        label.set_markup("<u>%s</u>" % label.get_text())
        window = self.get_window()
        window.set_cursor(None)


if __name__ == "__main__":
    win = Gtk.Window()
    win.set_size_request(600, 400)
    box = Gtk.VBox()
    control_box = Gtk.HBox()
    tree = Gtk.TreeView()
    bar = ActionBar()
    btns = 0

    def perform(btn):
        print("Clicked 'Perform %i'" % btn)

    def perform_lbl():
        print("Clicked label link")
        return True

    def add_func(*args):
        global btns
        btns += 1
        bar.add_button(btns, "Perform %i action" % btns, perform, btns)

    def rmv_func(*args):
        global btns
        if btns > 0:
            bar.remove_button(btns)
            btns -= 1

    def set_func(*args):
        # example with multiple links
        bar.set_label("This label _has a link_ and _another one_", perform_lbl)

    def unset_func(*args):
        bar.unset_label()

    addbtn = Gtk.Button("Add Button")
    rmvbtn = Gtk.Button("Remove Button")
    setbtn = Gtk.Button("Set Label")
    unsetbtn = Gtk.Button("Unset Label")
    addbtn.connect("clicked", add_func)
    rmvbtn.connect("clicked", rmv_func)
    setbtn.connect("clicked", set_func)
    unsetbtn.connect("clicked", unset_func)
    control_box.pack_start(addbtn, True, True, 0)
    control_box.pack_start(rmvbtn, True, True, 0)
    control_box.pack_start(setbtn, True, True, 0)
    control_box.pack_start(unsetbtn, True, True, 0)

    win.add(box)
    box.pack_start(control_box, False, True, 0)
    box.pack_start(tree, True, True, 0)
    box.pack_start(bar, False, True, 5)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()

    Gtk.main()
