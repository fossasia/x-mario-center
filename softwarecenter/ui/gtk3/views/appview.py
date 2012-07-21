# Copyright (C) 2009,2010 Canonical
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


import logging

from gi.repository import Gtk, GObject
from gettext import gettext as _

from softwarecenter.enums import SortMethods
from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.ui.gtk3.models.appstore2 import AppTreeStore
from softwarecenter.ui.gtk3.widgets.apptreeview import AppTreeView
from softwarecenter.ui.gtk3.models.appstore2 import AppPropertiesHelper
from softwarecenter.utils import ExecutionTime

LOG = logging.getLogger(__name__)


class AppView(Gtk.VBox):

    __gsignals__ = {
        "sort-method-changed": (GObject.SignalFlags.RUN_LAST,
                                None,
                                (GObject.TYPE_PYOBJECT, ),
                                ),
        "application-activated": (GObject.SignalFlags.RUN_LAST,
                                  None,
                                  (GObject.TYPE_PYOBJECT, ),
                                 ),
        "application-selected": (GObject.SignalFlags.RUN_LAST,
                                  None,
                                  (GObject.TYPE_PYOBJECT, ),
                                 ),
        }

    (INSTALLED_MODE, AVAILABLE_MODE, DIFF_MODE) = range(3)

    _SORT_METHOD_INDEX = (SortMethods.BY_ALPHABET,
                          SortMethods.BY_TOP_RATED,
                          SortMethods.BY_CATALOGED_TIME,
                          SortMethods.BY_SEARCH_RANKING,)

    # indices that relate to the above tuple
    _SORT_BY_ALPHABET = 0
    _SORT_BY_TOP_RATED = 1
    _SORT_BY_NEWEST_FIRST = 2
    _SORT_BY_SEARCH_RANKING = 3

    def __init__(self, db, cache, icons, show_ratings):
        Gtk.VBox.__init__(self)
        #~ self.set_name("app-view")
        # app properties helper
        self.helper = AppPropertiesHelper(db, cache, icons)
        # misc internal containers
        self.header_hbox = Gtk.HBox()
        self.header_hbox.set_border_width(StockEms.MEDIUM)
        self.pack_start(self.header_hbox, False, False, 0)
        self.tree_view_scroll = Gtk.ScrolledWindow()
        self.pack_start(self.tree_view_scroll, True, True, 0)

        # category label
        self.header_label = Gtk.Label()
        self.header_label.set_use_markup(True)
        self.header_hbox.pack_start(self.header_label, False, False, 0)

        # sort methods comboboxs
        # variant 1 includes sort by search relevance
        self.sort_methods_combobox = self._get_sort_methods_combobox()
        combo_alignment = Gtk.Alignment.new(0.5, 0.5, 1.0, 0.0)
        combo_alignment.add(self.sort_methods_combobox)
        self.header_hbox.pack_end(combo_alignment, False, False, 0)

        # content views
        self.tree_view = AppTreeView(self, db, icons,
                                     show_ratings, store=None)
        self.tree_view_scroll.add(self.tree_view)

        self.appcount = None
        self.vadj = 0.0

        # list view sorting stuff
        self._force_default_sort_method = True
        self._handler = self.sort_methods_combobox.connect(
                                    "changed",
                                    self.on_sort_method_changed)

    #~ def on_draw(self, w, cr):
        #~ cr.set_source_rgb(1,1,1)
        #~ cr.paint()

    def _append_appcount(self, appcount, mode=AVAILABLE_MODE):
#~
        #~ if mode == self.INSTALLED_MODE:
            #~ text = gettext.ngettext("%(amount)s item installed",
                                    #~ "%(amount)s items installed",
                                    #~ appcount) % { 'amount' : appcount, }
        #~ elif mode == self.DIFF_MODE:
            #~ text = gettext.ngettext("%(amount)s item",
                                    #~ "%(amount)s items",
                                    #~ appcount) % { 'amount' : appcount, }
        #~ else:
            #~ text = gettext.ngettext("%(amount)s item available",
                                    #~ "%(amount)s items available",
                                    #~ appcount) % { 'amount' : appcount, }
#~
        #~ if not self.appcount:
            #~ self.appcount = Gtk.Label()
            #~ self.appcount.set_alignment(0.5, 0.5)
            #~ self.appcount.set_margin_top(4)
            #~ self.appcount.set_margin_bottom(3)
            #~ self.appcount.connect("draw", self.on_draw)
            #~ self.vbox.pack_start(self.appcount, False, False, 0)
        #~ self.appcount.set_text(text)
        #~ self.appcount.show()
        pass

    def on_sort_method_changed(self, *args):
        self.vadj = 0.0
        self.emit("sort-method-changed", self.sort_methods_combobox)

    def _get_sort_methods_combobox(self):
        combo = Gtk.ComboBoxText.new()
        combo.append_text(_("By Name"))
        combo.append_text(_("By Top Rated"))
        combo.append_text(_("By Newest First"))
        combo.append_text(_("By Relevance"))
        combo.set_active(self._SORT_BY_TOP_RATED)
        return combo

    def _get_combo_children(self):
        return len(self.sort_methods_combobox.get_model())

    def _use_combobox_with_sort_by_search_ranking(self):
        if self._get_combo_children() == 4:
            return
        self.sort_methods_combobox.append_text(_("By Relevance"))

    def _use_combobox_without_sort_by_search_ranking(self):
        if self._get_combo_children() == 3:
            return
        self.sort_methods_combobox.remove(self._SORT_BY_SEARCH_RANKING)
        self.set_sort_method_with_no_signal(self._SORT_BY_TOP_RATED)

    def set_sort_method_with_no_signal(self, sort_method):
        combo = self.sort_methods_combobox
        combo.handler_block(self._handler)
        combo.set_active(sort_method)
        combo.handler_unblock(self._handler)

    def set_allow_user_sorting(self, do_allow):
        self.sort_methods_combobox.set_visible(do_allow)

    def set_header_labels(self, first_line, second_line):
        if second_line:
            markup = '%s\n<big><b>%s</b></big>' % (first_line, second_line)
        else:
            markup = "<big><b>%s</b></big>" % first_line
        return self.header_label.set_markup(markup)

    def set_model(self, model):
        self.tree_view.set_model(model)

    def get_model(self):
        return self.tree_view.appmodel

    def display_matches(self, matches, is_search=False):
        # FIXME: installedpane handles display of the trees intimately,
        # so for the time being lets just return None in the case of our
        # TreeView displaying an AppTreeStore ...    ;(
        # ... also we dont currently support user sorting in the
        # installedview, so issue is somewhat moot for the time being...
        if isinstance(self.get_model(), AppTreeStore):
            LOG.debug("display_matches called on AppTreeStore, ignoring")
            return

        model = self.get_model()
        # disconnect the model from the view before running
        # set_from_matches to ensure that the _cell_data_func_cb is not
        # run when the placeholder items are set, otherwise the purpose
        # of the "load-on-demand" is gone and it leads to bugs like
        # LP: #964433
        self.set_model(None)
        if model:
            model.set_from_matches(matches)
        self.set_model(model)

        adj = self.tree_view_scroll.get_vadjustment()
        if adj:
            adj.set_lower(self.vadj)
            adj.set_value(self.vadj)

    def reset_default_sort_mode(self):
        """ force the appview to reset to the default sort method without
            doing a refresh or sending any signals
        """
        self._force_default_sort_method = True

    def configure_sort_method(self, is_search=False):
        """ configures the sort method UI appropriately based on current
            conditions, including whether a search is in progress.

            Note that this will not change the users current sort method,
            if that is the intention, call reset_default_sort_mode()
        """
        # figure out what combobox we need
        if is_search:
            self._use_combobox_with_sort_by_search_ranking()
        else:
            self._use_combobox_without_sort_by_search_ranking()

        # and what sorting
        if self._force_default_sort_method:
            # always reset this, its the job of the user of the appview
            # to call reset_default_sort_mode() to reset this
            self._force_default_sort_method = False
            # and now set the default sort depending on if its a view or not
            if is_search:
                self.set_sort_method_with_no_signal(
                    self._SORT_BY_SEARCH_RANKING)
            else:
                self.set_sort_method_with_no_signal(
                    self._SORT_BY_TOP_RATED)

    def clear_model(self):
        return self.tree_view.clear_model()

    def get_sort_mode(self):
        active_index = self.sort_methods_combobox.get_active()
        return self._SORT_METHOD_INDEX[active_index]

    def get_app_icon_details(self):
        """ helper for unity dbus support to provide details about the
            application icon as it is displayed on-screen
        """
        icon_size = self._get_app_icon_size_on_screen()
        (icon_x, icon_y) = self._get_app_icon_xy_position_on_screen()
        return (icon_size, icon_x, icon_y)

    def _get_app_icon_size_on_screen(self):
        """ helper for unity dbus support to get the size of the maximum side
            for the application icon as it is displayed on-screen
        """
        icon_size = 32
        if (self.tree_view.selected_row_renderer and
            self.tree_view.selected_row_renderer.icon):
            pb = self.tree_view.selected_row_renderer.icon
            if pb.get_width() > pb.get_height():
                icon_size = pb.get_width()
            else:
                icon_size = pb.get_height()
        return icon_size

    def _get_app_icon_xy_position_on_screen(self):
        """ helper for unity dbus support to get the x,y position of
            the application icon as it is displayed on-screen
        """
        # find toplevel parent
        parent = self
        while parent.get_parent():
            parent = parent.get_parent()
        # get toplevel window position
        (px, py) = parent.get_position()
        # and return the coordinate values
        if self.tree_view.selected_row_renderer:
            return (px + self.tree_view.selected_row_renderer.icon_x_offset,
                    py + self.tree_view.selected_row_renderer.icon_y_offset)
        else:
            return (px, py)


# ----------------------------------------------- testcode
from softwarecenter.enums import NonAppVisibility


def get_query_from_search_entry(search_term):
    import xapian
    if not search_term:
        return xapian.Query("")
    parser = xapian.QueryParser()
    user_query = parser.parse_query(search_term)
    return user_query


def on_entry_changed(widget, data):

    def _work():
        new_text = widget.get_text()
        (view, enquirer) = data

        with ExecutionTime("total time"):
            with ExecutionTime("enquire.set_query()"):
                enquirer.set_query(get_query_from_search_entry(new_text),
                    limit=100 * 1000,
                    nonapps_visible=NonAppVisibility.ALWAYS_VISIBLE)

            store = view.tree_view.get_model()
            with ExecutionTime("store.clear()"):
                store.clear()

            with ExecutionTime("store.set_from_matches()"):
                store.set_from_matches(enquirer.matches)

            with ExecutionTime("model settle (size=%s)" % len(store)):
                while Gtk.events_pending():
                    Gtk.main_iteration()
        return

    if widget.stamp:
        GObject.source_remove(widget.stamp)
    widget.stamp = GObject.timeout_add(250, _work)


def get_test_window():
    import softwarecenter.log
    softwarecenter.log.root.setLevel(level=logging.DEBUG)
    softwarecenter.log.add_filters_from_string("performance")
    fmt = logging.Formatter("%(name)s - %(message)s", None)
    softwarecenter.log.handler.setFormatter(fmt)

    from softwarecenter.testutils import (
        get_test_db, get_test_pkg_info, get_test_gtk3_icon_cache)
    from softwarecenter.ui.gtk3.models.appstore2 import AppListStore

    db = get_test_db()
    cache = get_test_pkg_info()
    icons = get_test_gtk3_icon_cache()

    # create a filter
    from softwarecenter.db.appfilter import AppFilter
    filter = AppFilter(db, cache)
    filter.set_supported_only(False)
    filter.set_installed_only(True)

    # appview
    from softwarecenter.db.enquire import AppEnquire
    enquirer = AppEnquire(cache, db)
    store = AppListStore(db, cache, icons)

    from softwarecenter.ui.gtk3.views.appview import AppView
    view = AppView(db, cache, icons, show_ratings=True)
    view.set_model(store)

    entry = Gtk.Entry()
    entry.stamp = 0
    entry.connect("changed", on_entry_changed, (view, enquirer))

    box = Gtk.VBox()
    box.pack_start(entry, False, True, 0)
    box.pack_start(view, True, True, 0)

    win = Gtk.Window()
    win.set_data("appview", view)
    win.set_data("entry", entry)
    win.connect("destroy", lambda x: Gtk.main_quit())
    win.add(box)
    win.set_size_request(600, 400)
    win.show_all()

    return win

if __name__ == "__main__":
    win = get_test_window()
    win.get_data("entry").set_text("gtk3")
    Gtk.main()
