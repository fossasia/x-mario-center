# -*- coding: utf-8 -*-
#
# Copyright (C) 2010 Canonical
#
# Authors:
#  Olivier Tilloy
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
# this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import GObject
from gi.repository import Gtk, Gdk

import logging
import datetime

from gettext import gettext as _

from softwarecenter.ui.gtk3.widgets.spinner import SpinnerNotebook
from basepane import BasePane
from softwarecenter.enums import Icons
from softwarecenter.ui.gtk3.session.viewmanager import get_viewmanager
from softwarepane import DisplayState


class HistoryPane(Gtk.VBox, BasePane):

    __gsignals__ = {
        "app-list-changed": (GObject.SignalFlags.RUN_LAST,
                             None,
                             (int, ),
                            ),
        "history-pane-created": (GObject.SignalFlags.RUN_FIRST,
                                 None,
                                 ()),
    }

    (COL_WHEN, COL_ACTION, COL_PKG) = range(3)
    COL_TYPES = (object, int, object)

    (ALL, INSTALLED, REMOVED, UPGRADED) = range(4)

    ICON_SIZE = 32
    PADDING = 6

    # pages for the spinner notebook
    (PAGE_HISTORY_VIEW,
     PAGE_SPINNER) = range(2)

    def __init__(self, cache, db, distro, icons, datadir):
        Gtk.VBox.__init__(self)
        self.cache = cache
        self.db = db
        self.distro = distro
        self.icons = icons
        self.datadir = datadir

        self.apps_filter = None
        self.state = DisplayState()

        self.pane_name = _("History")

        # Icon cache, invalidated upon icon theme changes
        self._app_icon_cache = {}
        self._reset_icon_cache()
        self.icons.connect('changed', self._reset_icon_cache)

        self._emblems = {}
        self._get_emblems(self.icons)

        vm = get_viewmanager()
        self.searchentry = vm.get_global_searchentry()

        self.toolbar = Gtk.Toolbar()
        self.toolbar.show()
        self.toolbar.set_style(Gtk.ToolbarStyle.TEXT)
        self.pack_start(self.toolbar, False, True, 0)

        all_action = Gtk.RadioAction('filter_all', _('All Changes'), None,
            None, self.ALL)
        all_action.connect('changed', self.change_filter)
        all_button = all_action.create_tool_item()
        self.toolbar.insert(all_button, 0)

        installs_action = Gtk.RadioAction('filter_installs',
            _('Installations'), None, None, self.INSTALLED)
        installs_action.join_group(all_action)
        installs_button = installs_action.create_tool_item()
        self.toolbar.insert(installs_button, 1)

        upgrades_action = Gtk.RadioAction(
            'filter_upgrads', _('Updates'), None, None, self.UPGRADED)
        upgrades_action.join_group(all_action)
        upgrades_button = upgrades_action.create_tool_item()
        self.toolbar.insert(upgrades_button, 2)

        removals_action = Gtk.RadioAction(
            'filter_removals', _('Removals'), None, None, self.REMOVED)
        removals_action.join_group(all_action)
        removals_button = removals_action.create_tool_item()
        self.toolbar.insert(removals_button, 3)
        self.toolbar.connect('draw', self.on_toolbar_draw)

        self._actions_list = all_action.get_group()
        self._set_actions_sensitive(False)

        self.view = Gtk.TreeView()
        self.view.set_headers_visible(False)
        self.view.show()
        self.history_view = Gtk.ScrolledWindow()
        self.history_view.set_policy(Gtk.PolicyType.AUTOMATIC,
                                      Gtk.PolicyType.AUTOMATIC)
        self.history_view.show()
        self.history_view.add(self.view)

        # make a spinner to display while history is loading
        self.spinner_notebook = SpinnerNotebook(
            self.history_view, _('Loading history'))

        self.pack_start(self.spinner_notebook, True, True, 0)

        self.store = Gtk.TreeStore(*self.COL_TYPES)
        self.visible_changes = 0
        self.store_filter = self.store.filter_new(None)
        self.store_filter.set_visible_func(self.filter_row, None)
        self.view.set_model(self.store_filter)
        all_action.set_active(True)
        self.last = None

        # to save (a lot of) time at startup we load history later, only when
        # it is selected to be viewed
        self.history = None

        self.column = Gtk.TreeViewColumn(_('Date'))
        self.view.append_column(self.column)
        self.cell_icon = Gtk.CellRendererPixbuf()
        self.column.pack_start(self.cell_icon, False)
        self.column.set_cell_data_func(self.cell_icon, self.render_cell_icon)
        self.cell_text = Gtk.CellRendererText()
        self.column.pack_start(self.cell_text, True)
        self.column.set_cell_data_func(self.cell_text, self.render_cell_text)

        # busy cursor
        self.busy_cursor = Gdk.Cursor.new(Gdk.CursorType.WATCH)

    def init_view(self):
        if self.history == None:
            # if the history is not yet initialized we have to load and parse
            # it show a spinner while we do that
            self.realize()
            window = self.get_window()
            window.set_cursor(self.busy_cursor)
            self.spinner_notebook.show_spinner()
            self.load_and_parse_history()
            self.spinner_notebook.hide_spinner()
            self._set_actions_sensitive(True)
            window.set_cursor(None)
            self.emit("history-pane-created")

    def on_toolbar_draw(self, widget, cr):
        a = widget.get_allocation()
        context = widget.get_style_context()

        color = context.get_border_color(widget.get_state_flags())
        cr.set_source_rgba(color.red, color.green, color.blue, 0.5)
        cr.set_line_width(1)
        cr.move_to(0.5, a.height - 0.5)
        cr.rel_line_to(a.width - 1, 0)
        cr.stroke()

    def _get_emblems(self, icons):
        from softwarecenter.enums import USE_PACKAGEKIT_BACKEND
        if USE_PACKAGEKIT_BACKEND:
            emblem_names = ("pk-package-add",
                            "pk-package-delete",
                            "pk-package-update")
        else:
            emblem_names = ("package-install",
                            "package-remove",
                            "package-upgrade")

        for i, emblem in enumerate(emblem_names):
            pb = icons.load_icon(emblem, self.ICON_SIZE, 0)
            self._emblems[i + 1] = pb

    def _set_actions_sensitive(self, sensitive):
        for action in self._actions_list:
            action.set_sensitive(sensitive)

    def _reset_icon_cache(self, theme=None):
        self._app_icon_cache.clear()
        try:
            missing = self.icons.load_icon(Icons.MISSING_APP, self.ICON_SIZE,
                0)
        except GObject.GError:
            missing = None
        self._app_icon_cache[Icons.MISSING_APP] = missing

    def load_and_parse_history(self):
        from softwarecenter.db.history import get_pkg_history
        self.history = get_pkg_history()
        # FIXME: a signal from AptHistory is nicer
        while not self.history.history_ready:
            while Gtk.events_pending():
                Gtk.main_iteration()
        self.parse_history()
        self.history.set_on_update(self.parse_history)

    def parse_history(self):
        date = None
        when = None
        last_row = None
        day = self.store.get_iter_first()
        if day is not None:
            date = self.store.get_value(day, self.COL_WHEN)
        if len(self.history.transactions) == 0:
            logging.debug("AptHistory is currently empty")
            return
        new_last = self.history.transactions[0].start_date
        for trans in self.history.transactions:
            while Gtk.events_pending():
                Gtk.main_iteration()
            when = trans.start_date
            if self.last is not None and when <= self.last:
                break
            if when.date() != date:
                date = when.date()
                day = self.store.append(None, (date, self.ALL, None))
                last_row = None
            actions = {self.INSTALLED: trans.install,
                       self.REMOVED: trans.remove,
                       self.UPGRADED: trans.upgrade,
                      }
            for action, pkgs in actions.items():
                for pkgname in pkgs:
                    row = (when, action, pkgname)
                    last_row = self.store.insert_after(day, last_row, row)
        self.last = new_last
        self.update_view()

    def get_current_page(self):
        # single page views can return None here
        pass

    def get_callback_for_page(self, page, state):
        # single page views can return None here
        pass

    def on_search_terms_changed(self, entry, terms):
        self.update_view()

    def on_nav_back_clicked(self, widget):
        vm = get_viewmanager()
        vm.nav_back()

    def on_nav_forward_clicked(self, widget):
        vm = get_viewmanager()
        vm.nav_forward()

    def change_filter(self, action, current):
        self.filter = action.get_current_value()
        self.update_view()

    def update_view(self):
        self.store_filter.refilter()
        self.view.collapse_all()
        # Expand all the matching rows
        if self.searchentry.get_text():
            self.view.expand_all()

        # Compute the number of visible changes
        # don't do this atm - the spec doesn't mention that the history pane
        # should have a status text and it gives us a noticable performance
        # gain if we don't calculate this
#        self.visible_changes = 0
 #       day = self.store_filter.get_iter_first()
  #      while day is not None:
   #         self.visible_changes += self.store_filter.iter_n_children(day)
    #        day = self.store_filter.iter_next(day)

        # Expand the most recent day
        day = self.store.get_iter_first()
        if day is not None:
            path = self.store.get_path(day)
            self.view.expand_row(path, False)
            self.view.scroll_to_cell(path)

#        self.emit('app-list-changed', self.visible_changes)

    def _row_matches(self, store, iter):
        # Whether a child row matches the current filter and the search entry
        pkg = store.get_value(iter, self.COL_PKG) or ''
        filter_values = (self.ALL, store.get_value(iter, self.COL_ACTION))
        filter_matches = self.filter in filter_values
        search_matches = self.searchentry.get_text().lower() in pkg.lower()
        return filter_matches and search_matches

    def filter_row(self, store, iter, user_data):
        pkg = store.get_value(iter, self.COL_PKG)
        if pkg is not None:
            return self._row_matches(store, iter)
        else:
            i = store.iter_children(iter)
            while i is not None:
                if self._row_matches(store, i):
                    return True
                i = store.iter_next(i)
            return False

    def render_cell_icon(self, column, cell, store, iter, user_data):
        pkg = store.get_value(iter, self.COL_PKG)
        if pkg is None:
            cell.set_visible(False)
            return

        cell.set_visible(True)

        when = store.get_value(iter, self.COL_WHEN)
        if isinstance(when, datetime.datetime):
            action = store.get_value(iter, self.COL_ACTION)
            cell.set_property('pixbuf', self._emblems[action])

            #~ icon_name = Icons.MISSING_APP
            #~ for m in self.db.xapiandb.postlist("AP" + pkg):
                #~ doc = self.db.xapiandb.get_document(m.docid)
                #~ icon_value = doc.get_value(XapianValues.ICON)
                #~ if icon_value:
                    #~ icon_name = os.path.splitext(icon_value)[0]
                #~ break
            #~ if icon_name in self._app_icon_cache:
                #~ icon = self._app_icon_cache[icon_name]
            #~ else:
                #~ try:
                    #~ icon = self.icons.load_icon(icon_name, self.ICON_SIZE,
                        #~ 0)
                #~ except GObject.GError:
                    #~ icon = self._app_icon_cache[Icons.MISSING_APP]
                #~ self._app_icon_cache[icon_name] = icon

    def render_cell_text(self, column, cell, store, iter, user_data):
        when = store.get_value(iter, self.COL_WHEN)
        if isinstance(when, datetime.datetime):
            action = store.get_value(iter, self.COL_ACTION)
            pkg = store.get_value(iter, self.COL_PKG)
            subs = {'pkgname': pkg,
                    'color': '#8A8A8A',
                    # Translators : time displayed in history, display hours
                    # (0-12), minutes and AM/PM. %H should be used instead
                    # of %I to display hours 0-24
                    'time': when.time().strftime(_('%I:%M %p')),
                   }
            if action == self.INSTALLED:
                text = _('%(pkgname)s <span color="%(color)s">'
                    'installed %(time)s</span>') % subs
            elif action == self.REMOVED:
                text = _('%(pkgname)s <span color="%(color)s">'
                    'removed %(time)s</span>') % subs
            elif action == self.UPGRADED:
                text = _('%(pkgname)s <span color="%(color)s">'
                    'updated %(time)s</span>') % subs
        elif isinstance(when, datetime.date):
            today = datetime.date.today()
            monday = today - datetime.timedelta(days=today.weekday())
            if when == today:
                text = _("Today")
            elif when >= monday:
                # Current week, display the name of the day
                text = when.strftime(_('%A'))
            else:
                if when.year == today.year:
                    # Current year, display the day and month
                    text = when.strftime(_('%d %B'))
                else:
                    # Display the full date: day, month, year
                    text = when.strftime(_('%d %B %Y'))
        cell.set_property('markup', text)


def get_test_window():

    from softwarecenter.testutils import (get_test_db,
                                          get_test_gtk3_viewmanager,
                                          get_test_pkg_info,
                                          get_test_gtk3_icon_cache,
                                          )
    # needed because available pane will try to get it
    vm = get_test_gtk3_viewmanager()
    vm  # make pyflakes happy
    db = get_test_db()
    cache = get_test_pkg_info()
    icons = get_test_gtk3_icon_cache()

    widget = HistoryPane(cache, db, None, icons, None)
    widget.show()

    win = Gtk.Window()
    win.add(widget)
    win.set_size_request(600, 500)
    win.set_position(Gtk.WindowPosition.CENTER)
    win.show_all()
    win.connect('destroy', Gtk.main_quit)

    widget.init_view()
    return win

if __name__ == '__main__':
    win = get_test_window()
    Gtk.main()
