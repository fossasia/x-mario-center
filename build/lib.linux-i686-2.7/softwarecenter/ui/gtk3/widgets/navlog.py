from gi.repository import Gtk, GObject


class NavLog(Gtk.TreeView):

    _COLUMN_NAMES = ("Pane name", "View name", "DisplayState repr")
    _COLUMN_TYPES = (str, str, str)

    def __init__(self, navhistory):
        Gtk.TreeView.__init__(self)
        self.navhistory = navhistory
        model = Gtk.ListStore()
        model.set_column_types(self._COLUMN_TYPES)
        self._build_tree_view(model)
        self.connect("button-press-event", self.on_press_event)
        return

    def on_press_event(self, *args):
        return True

    def _build_tree_view(self, model):
        for i, name in enumerate(self._COLUMN_NAMES):
            renderer = Gtk.CellRendererText()
            renderer.set_property("wrap-width", 200)
            column = Gtk.TreeViewColumn(name, renderer, markup=i)
            self.append_column(column)
        self.set_model(model)
        return

    def notify_append(self, nav_item):
        model = self.get_model()
        pane_name = GObject.markup_escape_text(
                                        str(nav_item.pane.pane_name))

        if nav_item.page >= 0:
            view_name = nav_item.pane.Pages.NAMES[nav_item.page]
        else:
            view_name = str(nav_item.page)

        it = model.append([pane_name,
                           view_name,
                           str(nav_item.view_state)])

        self.set_cursor(model.get_path(it), None, False)
        return

    def notify_step_back(self):
        path, _ = self.get_cursor()
        path.prev()
        self.set_cursor(path, None, False)
        return

    def notify_step_forward(self):
        path, _ = self.get_cursor()
        path.next()
        self.set_cursor(path, None, False)
        return

    def notify_clear_forward_items(self):
        model = self.get_model()
        cursor, _ = self.get_cursor()
        for row in model:
            if row.path > cursor:
                model.remove(row.iter)
        return


class NavLogUtilityWindow(Gtk.Window):

    def __init__(self, navhistory):
        Gtk.Window.__init__(self)
        self.set_default_size(600, 300)
        self.set_title("Software Center Navigation Log")

        scroll = Gtk.ScrolledWindow()
        self.add(scroll)

        self.log = NavLog(navhistory)
        scroll.add(self.log)

        self.show_all()
        return
