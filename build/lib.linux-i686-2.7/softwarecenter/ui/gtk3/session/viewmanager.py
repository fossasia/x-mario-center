# Copyright (C) 2010 Canonical
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

from gi.repository import Gtk, GObject

from navhistory import NavigationHistory, NavigationItem
from softwarecenter.ui.gtk3.widgets.backforward import BackForwardButton
from softwarecenter.ui.gtk3.widgets.searchentry import SearchEntry


_viewmanager = None  # the global Viewmanager instance


def get_viewmanager():
    return _viewmanager


class ViewManager(GObject.GObject):

    __gsignals__ = {
        "view-changed": (GObject.SignalFlags.RUN_LAST,
                         None,
                         (GObject.TYPE_PYOBJECT, ),
                        ),
    }

    def __init__(self, notebook_view, options=None):
        GObject.GObject.__init__(self)
        self.notebook_view = notebook_view
        self.search_entry = SearchEntry()
        self.search_entry.connect(
            "terms-changed", self.on_search_terms_changed)
        self.search_entry.connect(
            "key-press-event", self.on_search_entry_key_press_event)

        self.back_forward = BackForwardButton()
        self.back_forward.connect(
            "left-clicked", self.on_nav_back_clicked)
        self.back_forward.connect(
            "right-clicked", self.on_nav_forward_clicked)

        self.navhistory = NavigationHistory(self.back_forward, options)
        self.spinner = Gtk.Spinner()

        self.all_views = {}
        self.view_to_pane = {}
        self._globalise_instance()

    def _globalise_instance(self):
        global _viewmanager
        if _viewmanager is not None:
            msg = "Only one instance of ViewManager is allowed!"
            raise ValueError(msg)
        else:
            _viewmanager = self

    def destroy(self):
        """Destroy the global instance."""
        global _viewmanager
        _viewmanager = None

    def on_search_terms_changed(self, widget, new_text):
        pane = self.get_current_view_widget()
        if hasattr(pane, "on_search_terms_changed"):
            pane.on_search_terms_changed(widget, new_text)

    def on_nav_back_clicked(self, widget):
        pane = self.get_current_view_widget()
        if hasattr(pane, "on_nav_back_clicked"):
            pane.on_nav_back_clicked(widget)

    def on_nav_forward_clicked(self, widget):
        pane = self.get_current_view_widget()
        if hasattr(pane, "on_nav_forward_clicked"):
            pane.on_nav_forward_clicked(widget)

    def on_search_entry_key_press_event(self, widget, event):

        pane = self.get_current_view_widget()
        if hasattr(pane, "on_search_entry_key_press_event"):
            pane.on_search_entry_key_press_event(event)

    def register(self, pane, view_id):
        page_id = self.notebook_view.append_page(
            pane,
            Gtk.Label.new("View %s" % view_id))  # label is for debugging only
        self.all_views[view_id] = page_id
        self.view_to_pane[view_id] = pane

    def get_current_view_widget(self):
        current_view = self.get_active_view()
        return self.get_view_widget(current_view)

    def get_view_id_from_page_id(self, page_id):
        for (k, v) in self.all_views.items():
            if page_id == v:
                return k

    def set_spinner_active(self, active):
        if active:
            self.spinner.show()
            self.spinner.start()
        else:
            self.spinner.stop()
            self.spinner.hide()

    def set_active_view(self, view_id):
        # no views yet
        if not self.all_views:
            return
        # if the view switches, ensure that the global spinner is hidden
        self.spinner.hide()

        # emit signal
        self.emit('view-changed', view_id)
        page_id = self.all_views[view_id]
        view_widget = self.get_view_widget(view_id)

        # it *seems* that this shouldn't be called here if we want the history
        # to work, but I'm not familiar with the code, so I'll leave it here
        # for the mean time
#        view_page = view_widget.get_current_page()
#        view_state = view_widget.state

        if (self.search_entry.get_text() !=
            view_widget.state.search_term):
            self.search_entry.set_text_with_no_signal(
                                        view_widget.state.search_term)

#        callback = view_widget.get_callback_for_page(view_page,
#                                                     view_state)

#        nav_item = NavigationItem(self, view_widget, view_page,
#                                  view_state.copy(), callback)
#        self.navhistory.append(nav_item)

        self.notebook_view.set_current_page(page_id)
        if view_widget:
            view_widget.init_view()
        return view_widget

    def get_active_view(self):
        page_id = self.notebook_view.get_current_page()
        return self.get_view_id_from_page_id(page_id)

    def is_active_view(self, view_id):
        return view_id == self.get_active_view()

    def get_notebook_page_from_view_id(self, view_id):
        return self.all_views[view_id]

    def get_view_widget(self, view_id):
        return self.view_to_pane.get(view_id, None)

    def get_latest_nav_item(self):
        return self.navhistory.stack[-1]

    def display_page(self, pane, page, view_state, callback=None):
        # if previous page is a list view, then store the scroll positions
        if self.navhistory.stack:
            ni = self.navhistory.stack[self.navhistory.stack.cursor]
            if ni.pane.is_applist_view_showing():
                v = ni.pane.app_view.tree_view_scroll.get_vadjustment()
                ni.view_state.vadjustment = v.get_value()

        if callback is None:
            callback = pane.get_callback_for_page(page, view_state)

        nav_item = NavigationItem(self, pane, page,
                                  view_state.copy(), callback)

        self.navhistory.append(nav_item)

        text = view_state.search_term
        if text != self.search_entry.get_text():
            self.search_entry.set_text_with_no_signal(text)

        pane.state = view_state
        if callback is not None:
            callback(page, view_state)

        if page is not None:
            pane.notebook.set_current_page(page)

        if self.get_current_view_widget() != pane:
            view_id = None
            for view_id, widget in self.view_to_pane.items():
                if widget == pane:
                    break

            self.set_active_view(view_id)

        if (not pane.searchentry or
            (hasattr(pane, 'Pages') and
             hasattr(pane.Pages, 'DETAILS') and
             page == pane.Pages.DETAILS) or
            (hasattr(pane, 'Pages') and
             hasattr(pane.Pages, 'PURCHASE') and
             page == pane.Pages.PURCHASE)):
            self.search_entry.hide()
        else:
            self.search_entry.show()
            self.spinner.hide()

    def nav_back(self):
        self.navhistory.nav_back()

    def nav_forward(self):
        self.navhistory.nav_forward()

    def clear_forward_history(self):
        self.navhistory.clear_forward_history()

    def get_global_searchentry(self):
        return self.search_entry

    def get_global_backforward(self):
        return self.back_forward

    def get_global_spinner(self):
        return self.spinner
