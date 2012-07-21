from gi.repository import Gtk, Gdk

# key values we want to respond to
_uppers = (Gdk.KEY_KP_Up, Gdk.KEY_Up)
_downers = (Gdk.KEY_KP_Down, Gdk.KEY_Down)


class Viewport(Gtk.Viewport):

    def __init__(self):
        Gtk.Viewport.__init__(self)
        self.connect("key-press-event", self.on_key_press_event)
        return

    def on_key_press_event(self, widget, event):
        global _uppers, _downers
        kv = event.keyval

        if kv in _uppers or kv in _downers:
            # get the ScrolledWindow adjustments and tweak them appropriately
            if not self.get_parent():
                return False

            # the ScrolledWindow vertical-adjustment
            scroll = self.get_ancestor('GtkScrolledWindow')
            if not scroll:
                return False

            v_adj = scroll.get_vadjustment()

            # scroll up
            if kv in _uppers:
                v = max(v_adj.get_value() - v_adj.get_step_increment(),
                        v_adj.get_lower())

            # scroll down
            elif kv in _downers:
                v = min(v_adj.get_value() + v_adj.get_step_increment(),
                        v_adj.get_upper() - v_adj.get_page_size())

            # set our new value
            v_adj.set_value(v)

            # do not share the event with other widgets
            return True
        # share the event with other widgets
        return False
