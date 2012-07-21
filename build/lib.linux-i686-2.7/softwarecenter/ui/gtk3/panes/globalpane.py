from gi.repository import Gtk

from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.ui.gtk3.session.viewmanager import get_viewmanager
from softwarecenter.ui.gtk3.panes.viewswitcher import ViewSwitcher


def _widget_set_margins(widget, top=0, bottom=0, left=0, right=0):
    widget.set_margin_top(top)
    widget.set_margin_bottom(bottom)
    widget.set_margin_left(left)
    widget.set_margin_right(right)


class GlobalPane(Gtk.Toolbar):

    def __init__(self, view_manager, datadir, db, cache, icons):
        Gtk.Toolbar.__init__(self)
        context = self.get_style_context()
        context.add_class(Gtk.STYLE_CLASS_PRIMARY_TOOLBAR)

        # add nav history back/forward buttons...
        # note:  this is hacky, would be much nicer to make the custom
        # self/right buttons in BackForwardButton to be
        # Gtk.Activatable/Gtk.Widgets, then wire in the actions using e.g.
        # self.navhistory_back_action.connect_proxy(self.back_forward.left),
        # but couldn't seem to get this to work..so just wire things up
        # directly
        vm = get_viewmanager()
        self.back_forward = vm.get_global_backforward()
        self.back_forward.set_vexpand(False)
        self.back_forward.set_valign(Gtk.Align.CENTER)

        if self.get_direction() != Gtk.TextDirection.RTL:
            _widget_set_margins(self.back_forward,
                                left=StockEms.MEDIUM,
                                right=StockEms.MEDIUM + 2)
        else:
            _widget_set_margins(self.back_forward,
                                right=StockEms.MEDIUM,
                                left=StockEms.MEDIUM + 2)
        self._insert_as_tool_item(self.back_forward, 0)

        # this is what actually draws the All Software, Installed etc buttons
        self.view_switcher = ViewSwitcher(view_manager, datadir, db, cache,
            icons)
        self._insert_as_tool_item(self.view_switcher, 1)

        item = Gtk.ToolItem()
        item.set_expand(True)
        self.insert(item, -1)

        #~ self.init_atk_name(self.searchentry, "searchentry")
        self.searchentry = vm.get_global_searchentry()
        self._insert_as_tool_item(self.searchentry, -1)

        # spinner
        self.spinner = vm.get_global_spinner()
        self.spinner.set_size_request(StockEms.XLARGE, StockEms.XLARGE)
        self._insert_as_tool_item(self.spinner, -1)

        if self.get_direction() != Gtk.TextDirection.RTL:
            _widget_set_margins(self.searchentry, right=StockEms.MEDIUM)
        else:
            _widget_set_margins(self.searchentry, left=StockEms.MEDIUM)

    def _insert_as_tool_item(self, widget, pos):
        item = Gtk.ToolItem()
        item.add(widget)
        self.insert(item, pos)
        return item


def get_test_window():

    from softwarecenter.testutils import (get_test_db,
                                          get_test_datadir,
                                          get_test_gtk3_viewmanager,
                                          get_test_pkg_info,
                                          get_test_gtk3_icon_cache,
                                          )
    vm = get_test_gtk3_viewmanager()
    db = get_test_db()
    cache = get_test_pkg_info()
    datadir = get_test_datadir()
    icons = get_test_gtk3_icon_cache()

    p = GlobalPane(vm, datadir, db, cache, icons)

    win = Gtk.Window()
    win.set_size_request(400, 200)
    win.set_data("pane", p)
    win.connect("destroy", Gtk.main_quit)
    win.add(p)
    win.show_all()
    return win

if __name__ == "__main__":

    win = get_test_window()

    Gtk.main()
