from gi.repository import Gtk, Gdk


class HBar(Gtk.VBox):

    def __init__(self):
        Gtk.VBox.__init__(self)
        context = self.get_style_context()
        context.add_class("item-view-separator")
        self.connect("style-updated", self.on_style_updated)
        return

    def on_style_updated(self, widget):
        context = widget.get_style_context()
        border = context.get_border(Gtk.StateFlags.NORMAL)
        widget.set_size_request(-1,
                                max(1, max(border.top, border.bottom)))
        return

    def do_draw(self, cr):
        context = self.get_style_context()
        bc = context.get_border_color(self.get_state_flags())

        cr.save()
        Gdk.cairo_set_source_rgba(cr, bc)

        width = self.get_property("height-request")

        a = self.get_allocation()
        cr.move_to(0, 0)
        cr.rel_line_to(a.width, 0)
        cr.set_dash((width, 2 * width), 0)
        cr.set_line_width(2 * width)
        cr.stroke()
        cr.restore()
