# -*- coding: utf-8 -*-
# Copyright (C) 2009-2011 Canonical
#
# Authors:
#  Michael Vogt
#  Didier Roche
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

from gi.repository import Gtk
import logging
import xapian
from gi.repository import GObject

from gettext import gettext as _
from gettext import ngettext

import platform

from softwarecenter.enums import (NonAppVisibility,
                                  SortMethods)
from softwarecenter.utils import (
    wait_for_apt_cache_ready, utf8, ExecutionTime)
from softwarecenter.db.categories import (CategoriesParser,
                                          categories_sorted_by_name)
from softwarecenter.ui.gtk3.models.appstore2 import (
    AppTreeStore, CategoryRowReference)
from softwarecenter.ui.gtk3.widgets.menubutton import MenuButton
from softwarecenter.ui.gtk3.widgets.oneconfviews import OneConfViews
from softwarecenter.ui.gtk3.widgets.spinner import SpinnerNotebook
from softwarecenter.ui.gtk3.views.appview import AppView
from softwarepane import SoftwarePane
from softwarecenter.backend.oneconfhandler import get_oneconf_handler
from softwarecenter.db.appfilter import AppFilter
from softwarecenter.paths import APP_INSTALL_PATH

LOG = logging.getLogger(__name__)


def interrupt_build_and_wait(f):
    """ decorator that ensures that a build of the categorised installed apps
        is interrupted before a new build commences.
        expects self._build_in_progress and self._halt_build as properties
    """
    def wrapper(*args, **kwargs):
        self = args[0]
        if self._build_in_progress:
            LOG.debug('Waiting for build to exit...')
            self._halt_build = True
            GObject.timeout_add(200, lambda: wrapper(*args, **kwargs))
            return False
        # ready now
        self._halt_build = False
        f(*args, **kwargs)
        return False
    return wrapper


class InstalledPane(SoftwarePane, CategoriesParser):
    """Widget that represents the installed panel in software-center
       It contains a search entry and navigation buttons
    """

    class Pages():
        # page names, useful for debugging
        NAMES = ('list', 'details')
        # the actual page id's
        (LIST,
         DETAILS) = range(2)
        # the default page
        HOME = LIST

    # pages for the installed view spinner notebook
    (PAGE_SPINNER,
     PAGE_INSTALLED) = range(2)

    __gsignals__ = {'installed-pane-created': (GObject.SignalFlags.RUN_FIRST,
                                               None,
                                               ())}

    def __init__(self, cache, db, distro, icons, datadir):

        # parent
        SoftwarePane.__init__(self, cache, db, distro, icons, datadir,
            show_ratings=False)
        CategoriesParser.__init__(self, db)

        self.current_appview_selection = None
        self.icons = icons
        self.loaded = False
        self.pane_name = _("Installed Software")

        self.installed_apps = 0
        # None is local
        self.current_hostid = None
        self.current_hostname = None
        self.oneconf_additional_pkg = set()
        self.oneconf_missing_pkg = set()

        # switches to terminate build in progress
        self._build_in_progress = False
        self._halt_build = False

        self.nonapps_visible = NonAppVisibility.NEVER_VISIBLE

        self.visible_docids = None
        self.visible_cats = {}

        self.installed_spinner_notebook = None

    def init_view(self):
        if self.view_initialized:
            return

        SoftwarePane.init_view(self)

        # show a busy cursor and display the main spinner while we build the
        # view
        window = self.get_window()
        if window:
            window.set_cursor(self.busy_cursor)
        self.show_appview_spinner()

        self.oneconf_viewpickler = OneConfViews(self.icons)
        self.oneconf_viewpickler.register_computer(None,
            _("This computer (%s)") % platform.node())
        self.oneconf_viewpickler.select_first()
        self.oneconf_viewpickler.connect('computer-changed',
            self._selected_computer_changed)
        self.oneconf_viewpickler.connect('current-inventory-refreshed',
            self._current_inventory_need_refresh)

        # Start OneConf
        self.oneconf_handler = get_oneconf_handler(self.oneconf_viewpickler)
        if self.oneconf_handler:
            self.oneconf_handler.connect('show-oneconf-changed',
                self._show_oneconf_changed)
            self.oneconf_handler.connect('last-time-sync-changed',
                self._last_time_sync_oneconf_changed)

        # OneConf pane
        self.computerpane = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        self.oneconfcontrol = Gtk.Box()
        self.oneconfcontrol.set_orientation(Gtk.Orientation.VERTICAL)
        self.computerpane.pack1(self.oneconfcontrol, False, False)
        # size negotiation takes everything for the first one
        self.oneconfcontrol.set_property('width-request', 200)
        self.box_app_list.pack_start(self.computerpane, True, True, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        scroll.add(self.oneconf_viewpickler)
        self.oneconfcontrol.pack_start(scroll, True, True, 0)

        oneconftoolbar = Gtk.Box()
        oneconftoolbar.set_orientation(Gtk.Orientation.HORIZONTAL)
        oneconfpropertymenu = Gtk.Menu()
        self.oneconfproperty = MenuButton(oneconfpropertymenu,
            Gtk.Image.new_from_stock(Gtk.STOCK_PROPERTIES,
            Gtk.IconSize.BUTTON))
        self.stopsync_label = _(u"Stop Syncing “%s”")
        stop_oneconf_share_menuitem = Gtk.MenuItem(
            label=self.stopsync_label % platform.node())
        stop_oneconf_share_menuitem.connect("activate",
            self._on_stop_oneconf_hostshare_clicked)
        stop_oneconf_share_menuitem.show()
        oneconfpropertymenu.append(stop_oneconf_share_menuitem)
        self.oneconfcontrol.pack_start(oneconftoolbar, False, False, 1)
        self.oneconf_last_sync = Gtk.Label()
        self.oneconf_last_sync.set_line_wrap(True)
        oneconftoolbar.pack_start(self.oneconfproperty, False, False, 0)
        oneconftoolbar.pack_start(self.oneconf_last_sync, True, True, 1)

        self.notebook.append_page(self.box_app_list, Gtk.Label(label="list"))

        # details
        self.notebook.append_page(self.scroll_details,
            Gtk.Label(label="details"))
        # initial refresh
        self.state.search_term = ""

        # build models and filters
        self.base_model = AppTreeStore(self.db, self.cache, self.icons)

        self.treefilter = self.base_model.filter_new(None)
        self.treefilter.set_visible_func(self._row_visibility_func,
                                         AppTreeStore.COL_ROW_DATA)
        self.app_view.set_model(self.treefilter)
        self.app_view.tree_view.connect("row-collapsed",
            self._on_row_collapsed)

        self._all_cats = self.parse_applications_menu(APP_INSTALL_PATH)
        self._all_cats = categories_sorted_by_name(self._all_cats)

        # we do not support the search aid feature in the installedview
        self.box_app_list.remove(self.search_aid)

        # remove here
        self.box_app_list.remove(self.app_view)

        # create a local spinner notebook for the installed view
        self.installed_spinner_notebook = SpinnerNotebook(self.app_view)

        self.computerpane.pack2(self.installed_spinner_notebook, True, True)
        self.show_installed_view_spinner()

        self.show_all()

        # initialize view to hide the oneconf computer selector
        self.oneconf_viewpickler.select_first()
        self.oneconfcontrol.hide()

        # hacky, hide the header
        self.app_view.header_hbox.hide()

        self.hide_appview_spinner()

        # keep track of the current view by tracking its origin
        self.current_displayed_origin = None

        # now we are initialized
        self.emit("installed-pane-created")

        self.view_initialized = True
        return False

    def show_installed_view_spinner(self):
        """ display the local spinner for the installed view panel """
        if self.installed_spinner_notebook:
            self.installed_spinner_notebook.show_spinner()

    def hide_installed_view_spinner(self):
        """ hide the local spinner for the installed view panel """
        if self.installed_spinner_notebook:
            self.installed_spinner_notebook.hide_spinner()

    def _selected_computer_changed(self, oneconf_pickler, hostid, hostname):
        if self.current_hostid == hostid:
            return
        LOG.debug("Selected computer changed to %s (%s)" % (hostid, hostname))
        self.current_hostid = hostid
        self.current_hostname = hostname
        menuitem = self.oneconfproperty.get_menu().get_children()[0]
        if self.current_hostid:
            diff = self.oneconf_handler.oneconf.diff(self.current_hostid, '')
            self.oneconf_additional_pkg, self.oneconf_missing_pkg = diff
            stopsync_hostname = self.current_hostname
            # FIXME for P: oneconf views don't support search
            if self.state.search_term:
                self._search()
        else:
            stopsync_hostname = platform.node()
            self.searchentry.show()
        menuitem.set_label(self.stopsync_label %
            stopsync_hostname.encode('utf-8'))
        self.refresh_apps()

    def _last_time_sync_oneconf_changed(self, oneconf_handler, msg):
        LOG.debug("refresh latest sync date")
        self.oneconf_last_sync.set_label(msg)

    def _show_oneconf_changed(self, oneconf_handler, oneconf_inventory_shown):
        LOG.debug('Share inventory status changed')
        if oneconf_inventory_shown:
            self.oneconfcontrol.show()
        else:
            self.oneconf_viewpickler.select_first()
            self.oneconfcontrol.hide()

    def _on_stop_oneconf_hostshare_clicked(self, widget):
        LOG.debug("Stop sharing inventory for %s" % self.current_hostname)
        self.oneconf_handler.sync_between_computers(False, self.current_hostid)
        # stop sharing another host than the local one.
        if self.current_hostid:
            self.oneconf_viewpickler.remove_computer(self.current_hostid)
            self.oneconf_viewpickler.select_first()

    def _current_inventory_need_refresh(self, oneconfviews):
        if self.current_hostid:
            diff = self.oneconf_handler.oneconf.diff(self.current_hostid, '')
            self.oneconf_additional_pkg, self.oneconf_missing_pkg = diff
        self.refresh_apps()

    def _on_row_collapsed(self, view, it, path):
        pass

    def _row_visibility_func(self, model, it, col):
        row = model.get_value(it, col)
        if self.visible_docids is None:
            if isinstance(row, CategoryRowReference):
                row.vis_count = row.pkg_count
            return True

        elif isinstance(row, CategoryRowReference):
            return row.untranslated_name in self.visible_cats.keys()

        elif row is None:
            return False

        return row.get_docid() in self.visible_docids

    def _use_category(self, cat):
        # System cat is large and slow to search, filter it in default mode

        if ('carousel-only' in cat.flags or
            ((self.nonapps_visible == NonAppVisibility.NEVER_VISIBLE)
            and cat.untranslated_name == 'System')):
                return False

        return True

    # override its SoftwarePane._hide_nonapp_pkgs...
    def _hide_nonapp_pkgs(self):
        self.nonapps_visible = NonAppVisibility.NEVER_VISIBLE
        self.refresh_apps()
        return True

    def _save_treeview_state(self):
        # store the state
        expanded_rows = []
        self.app_view.tree_view.map_expanded_rows(
            lambda view, path, data: expanded_rows.append(path.to_string()),
            None)
        va = self.app_view.tree_view_scroll.get_vadjustment()
        if va:
            vadj = va.get_value()
        else:
            vadj = 0
        return expanded_rows, vadj

    def _restore_treeview_state(self, state):
        expanded_rows, vadj = state
        for ind in expanded_rows:
            path = Gtk.TreePath.new_from_string(ind)
            self.app_view.tree_view.expand_row(path, False)
        va = self.app_view.tree_view_scroll.get_vadjustment()
        if va:
            va.set_lower(vadj)
            va.set_value(vadj)

    #~ @interrupt_build_and_wait
    def _build_categorised_installedview(self, keep_state=False):
        LOG.debug('Rebuilding categorised installedview...')

        # display the busy cursor and a local spinner while we build the view
        window = self.get_window()
        if window:
            window.set_cursor(self.busy_cursor)
        self.show_installed_view_spinner()

        if keep_state:
            treeview_state = self._save_treeview_state()

        # disconnect the model to avoid e.g. updates of "cursor-changed"
        #  AppTreeView.expand_path while the model is in rebuild-flux
        self.app_view.set_model(None)

        model = self.base_model  # base model not treefilter
        model.clear()

        def profiled_rebuild_categorised_view():
            with ExecutionTime("rebuild_categorized_view"):
                rebuild_categorised_view()

        def rebuild_categorised_view():
            self.cat_docid_map = {}
            enq = self.enquirer

            i = 0

            while Gtk.events_pending():
                Gtk.main_iteration()

            xfilter = AppFilter(self.db, self.cache)
            xfilter.set_installed_only(True)

            for cat in self._all_cats:
                # for each category do category query and append as a new
                # node to tree_view
                if not self._use_category(cat):
                    continue
                query = self.get_query_for_cat(cat)
                LOG.debug("xfilter.installed_only: %s" %
                    xfilter.installed_only)
                enq.set_query(query,
                              sortmode=SortMethods.BY_ALPHABET,
                              nonapps_visible=self.nonapps_visible,
                              filter=xfilter,
                              nonblocking_load=False,
                              persistent_duplicate_filter=(i > 0))

                L = len(enq.matches)
                if L:
                    i += L
                    docs = enq.get_documents()
                    self.cat_docid_map[cat.untranslated_name] = \
                                        set([doc.get_docid() for doc in docs])
                    model.set_category_documents(cat, docs)

            while Gtk.events_pending():
                Gtk.main_iteration()

            # check for uncategorised pkgs
            if self.state.channel:
                self._run_channel_enquirer(persistent_duplicate_filter=(i > 0))
                L = len(enq.matches)
                if L:
                    # some foo for channels
                    # if no categorised results but in channel, then use
                    # the channel name for the category
                    channel_name = None
                    if not i and self.state.channel:
                        channel_name = self.state.channel.display_name
                    docs = enq.get_documents()
                    tag = channel_name or 'Uncategorized'
                    self.cat_docid_map[tag] = set(
                        [doc.get_docid() for doc in docs])
                    model.set_nocategory_documents(docs, untranslated_name=tag,
                                                   display_name=channel_name)
                    i += L

            if i:
                self.app_view.tree_view.set_cursor(Gtk.TreePath(),
                                                   None, False)
                if i <= 10:
                    self.app_view.tree_view.expand_all()

            # cache the installed app count
            self.installed_count = i
            self.app_view._append_appcount(self.installed_count,
                mode=AppView.INSTALLED_MODE)

            self.app_view.set_model(self.treefilter)
            if keep_state:
                self._restore_treeview_state(treeview_state)

            # hide the local spinner
            self.hide_installed_view_spinner()

            if window:
                window.set_cursor(None)

            # reapply search if needed
            if self.state.search_term:
                self._do_search(self.state.search_term)

            self.emit("app-list-changed", i)
            return

        GObject.idle_add(profiled_rebuild_categorised_view)

    def _build_oneconfview(self, keep_state=False):
        LOG.debug('Rebuilding oneconfview for %s...' % self.current_hostid)

        # display the busy cursor and the local spinner while we build the view
        window = self.get_window()
        if window:
            window.set_cursor(self.busy_cursor)
        self.show_installed_view_spinner()

        if keep_state:
            treeview_state = self._save_treeview_state()

        # disconnect the model to avoid e.g. updates of "cursor-changed"
        #  AppTreeView.expand_path while the model is in rebuild-flux
        self.app_view.set_model(None)

        model = self.base_model  # base model not treefilter
        model.clear()

        def profiled_rebuild_oneconfview():
            with ExecutionTime("rebuild_oneconfview"):
                rebuild_oneconfview()

        def rebuild_oneconfview():

            # FIXME for P: hide the search entry
            self.searchentry.hide()

            self.cat_docid_map = {}
            enq = self.enquirer
            query = xapian.Query("")
            if self.state.channel and self.state.channel.query:
                query = xapian.Query(xapian.Query.OP_AND,
                                     query,
                                     self.state.channel.query)

            i = 0

            # First search: missing apps only
            xfilter = AppFilter(self.db, self.cache)
            xfilter.set_restricted_list(self.oneconf_additional_pkg)
            xfilter.set_not_installed_only(True)

            enq.set_query(query,
                          sortmode=SortMethods.BY_ALPHABET,
                          nonapps_visible=self.nonapps_visible,
                          filter=xfilter,
                          nonblocking_load=True,  # we don't block this one for
                                                # better oneconf responsiveness
                          persistent_duplicate_filter=(i > 0))

            L = len(enq.matches)

            if L:
                cat_title = utf8(ngettext(
                    u'%(amount)s item on “%(machine)s” not on this computer',
                    u'%(amount)s items on “%(machine)s” not on this computer',
                    L)) % {'amount': L, 'machine': utf8(self.current_hostname)}
                i += L
                docs = enq.get_documents()
                self.cat_docid_map["missingpkg"] = set(
                    [doc.get_docid() for doc in docs])
                model.set_nocategory_documents(docs,
                    untranslated_name="additionalpkg", display_name=cat_title)

            # Second search: additional apps
            xfilter.set_restricted_list(self.oneconf_missing_pkg)
            xfilter.set_not_installed_only(False)
            xfilter.set_installed_only(True)
            enq.set_query(query,
                          sortmode=SortMethods.BY_ALPHABET,
                          nonapps_visible=self.nonapps_visible,
                          filter=xfilter,
                          nonblocking_load=False,
                          persistent_duplicate_filter=(i > 0))

            L = len(enq.matches)
            if L:
                cat_title = utf8(ngettext(
                    u'%(amount)s item on this computer not on “%(machine)s”',
                    '%(amount)s items on this computer not on “%(machine)s”',
                    L)) % {'amount': L, 'machine': utf8(self.current_hostname)}
                i += L
                docs = enq.get_documents()
                self.cat_docid_map["additionalpkg"] = set(
                    [doc.get_docid() for doc in docs])
                model.set_nocategory_documents(docs,
                    untranslated_name="additionalpkg", display_name=cat_title)

            if i:
                self.app_view.tree_view.set_cursor(Gtk.TreePath(),
                                                   None, False)
                if i <= 10:
                    self.app_view.tree_view.expand_all()

            # cache the installed app count
            self.installed_count = i
            self.app_view._append_appcount(self.installed_count,
                mode=AppView.DIFF_MODE)

            self.app_view.set_model(self.treefilter)
            if keep_state:
                self._restore_treeview_state(treeview_state)

            # hide the local spinner
            self.hide_installed_view_spinner()

            if window:
                window.set_cursor(None)

            self.emit("app-list-changed", i)
            return

        GObject.idle_add(profiled_rebuild_oneconfview)

    def _check_expand(self):
        it = self.treefilter.get_iter_first()
        while it:
            path = self.treefilter.get_path(it)
            if self.state.search_term:  # or path in self._user_expanded_paths:
                self.app_view.tree_view.expand_row(path, False)
            else:
                self.app_view.tree_view.collapse_row(path)

            it = self.treefilter.iter_next(it)

    def _do_search(self, terms):
        self.state.search_term = terms
        xfilter = AppFilter(self.db, self.cache)
        xfilter.set_installed_only(True)
        self.enquirer.set_query(self.get_query(),
                                nonapps_visible=self.nonapps_visible,
                                filter=xfilter,
                                nonblocking_load=True)

        self.visible_docids = self.enquirer.get_docids()
        self.visible_cats = self._get_vis_cats(self.visible_docids)
        self.treefilter.refilter()
        self.app_view.tree_view.expand_all()

    def _run_channel_enquirer(self, persistent_duplicate_filter=True):
        xfilter = AppFilter(self.db, self.cache)
        xfilter.set_installed_only(True)
        if self.state.channel:
            self.enquirer.set_query(
                self.state.channel.query,
                sortmode=SortMethods.BY_ALPHABET,
                nonapps_visible=NonAppVisibility.MAYBE_VISIBLE,
                filter=xfilter,
                nonblocking_load=False,
                persistent_duplicate_filter=persistent_duplicate_filter)

    def _search(self, terms=None):
        if not terms:
            self.visible_docids = None
            self.state.search_term = ""
            self._clear_search()
            self.treefilter.refilter()
            self._check_expand()
            # run channel enquirer to ensure that the channel specific
            # info for show/hide nonapps is actually correct
            self._run_channel_enquirer()
            # trigger update of the show/hide
            self.emit("app-list-changed", 0)
        elif self.state.search_term != terms:
            self._do_search(terms)

    def get_query(self):
        # search terms
        return self.db.get_query_list_from_search_entry(
                                        self.state.search_term)

    def get_query_for_cat(self, cat):
        LOG.debug("self.state.channel: %s" % self.state.channel)
        if self.state.channel and self.state.channel.query:
            query = xapian.Query(xapian.Query.OP_AND,
                                 cat.query,
                                 self.state.channel.query)
            return query
        return cat.query

    @wait_for_apt_cache_ready
    def refresh_apps(self, *args, **kwargs):
        """refresh the applist and update the navigation bar """
        logging.debug("installedpane refresh_apps")
        keep_state = kwargs.get("keep_state", False)
        if self.current_hostid:
            self._build_oneconfview(keep_state)
        else:
            self._build_categorised_installedview(keep_state)

    def _clear_search(self):
        # remove the details and clear the search
        self.searchentry.clear_with_no_signal()

    def on_search_terms_changed(self, searchentry, terms):
        """callback when the search entry widget changes"""
        logging.debug("on_search_terms_changed: '%s'" % terms)

        self._search(terms.strip())
        self.state.search_term = terms
        self.notebook.set_current_page(InstalledPane.Pages.LIST)
        self.hide_installed_view_spinner()

    def _get_vis_cats(self, visids):
        vis_cats = {}
        appcount = 0
        visids = set(visids)
        for cat_uname, docids in self.cat_docid_map.iteritems():
            children = len(docids & visids)
            if children:
                appcount += children
                vis_cats[cat_uname] = children
        self.app_view._append_appcount(appcount, mode=AppView.DIFF_MODE)
        return vis_cats

    def _refresh_on_cache_or_db_change(self):
        self.refresh_apps(keep_state=True)
        self.app_details_view.refresh_app()

    def on_db_reopen(self, db):
        super(InstalledPane, self).on_db_reopen(db)
        self._refresh_on_cache_or_db_change()

    def on_cache_ready(self, cache):
        LOG.debug("on_cache_ready")
        self._refresh_on_cache_or_db_change()

    def on_application_selected(self, appview, app):
        """callback when an app is selected"""
        logging.debug("on_application_selected: '%s'" % app)
        self.current_appview_selection = app

    def get_callback_for_page(self, page, state):
        if page == InstalledPane.Pages.LIST:
            return self.display_overview_page
        return self.display_details_page

    def display_search(self):
        model = self.app_view.get_model()
        if model:
            self.emit("app-list-changed", len(model))
        self.searchentry.show()

    @wait_for_apt_cache_ready
    def display_overview_page(self, page, view_state):
        LOG.debug("view_state: %s" % view_state)
        if self.current_hostid:
            # FIXME for P: oneconf views don't support search
            # this one ensure that even when switching between pane, we
            # don't have the search item
            if self.state.search_term:
                self._search()
            self._build_oneconfview()
        elif (view_state and
              view_state.channel and
              view_state.channel.origin is not self.current_displayed_origin):
            # we don't need to refresh the full installed view every time it
            # is displayed, so we check to see if we are viewing the same
            # channel and if so we don't refresh the view, note that the view
            # *is* is refreshed whenever the contents change and this is
            # sufficient (see LP: #828887)
            self._build_categorised_installedview()
            self.current_displayed_origin = view_state.channel.origin

            if self.state.search_term:
                self._search(self.state.search_term)
        return True

    def get_current_app(self):
        """return the current active application object applicable
           to the context"""
        return self.current_appview_selection

    def is_category_view_showing(self):
        # there is no category view in the installed pane
        return False

    def is_applist_view_showing(self):
        """Return True if we are in the applist view """
        return (self.notebook.get_current_page() ==
                InstalledPane.Pages.LIST)

    def is_app_details_view_showing(self):
        """Return True if we are in the app_details view """
        return self.notebook.get_current_page() == InstalledPane.Pages.DETAILS


def get_test_window():
    from softwarecenter.testutils import (get_test_db,
                                          get_test_datadir,
                                          get_test_gtk3_viewmanager,
                                          get_test_pkg_info,
                                          get_test_gtk3_icon_cache,
                                          )
    # needed because available pane will try to get it
    vm = get_test_gtk3_viewmanager()
    vm  # make pyflakes happy
    db = get_test_db()
    cache = get_test_pkg_info()
    datadir = get_test_datadir()
    icons = get_test_gtk3_icon_cache()

    w = InstalledPane(cache, db, 'Ubuntu', icons, datadir)
    w.show()

    win = Gtk.Window()
    win.set_data("pane", w)
    win.add(w)
    win.set_size_request(400, 600)
    win.connect("destroy", lambda x: Gtk.main_quit())

    # init the view
    w.init_view()

    from softwarecenter.backend.channel import AllInstalledChannel
    from softwarecenter.ui.gtk3.panes.softwarepane import DisplayState
    w.state.channel = AllInstalledChannel()
    view_state = DisplayState()
    view_state.channel = AllInstalledChannel()
    w.display_overview_page(None, view_state)

    win.show()
    return win


if __name__ == "__main__":
    win = get_test_window()
    Gtk.main()
