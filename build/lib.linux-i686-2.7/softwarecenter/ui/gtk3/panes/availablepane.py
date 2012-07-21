# Copyright (C) 2009 Canonical
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

import gettext
from gi.repository import GObject
from gi.repository import Gtk
import logging
import xapian
import os

import softwarecenter.utils
import softwarecenter.ui.gtk3.dialogs as dialogs
from softwarecenter.ui.gtk3.models.appstore2 import AppListStore

from gettext import gettext as _

from softwarecenter.enums import (ActionButtons,
                                  NavButtons,
                                  NonAppVisibility,
                                  DEFAULT_SEARCH_LIMIT,
                                  TransactionTypes)
from softwarecenter.paths import APP_INSTALL_PATH
from softwarecenter.utils import (wait_for_apt_cache_ready,
                                  get_exec_line_from_desktop,
                                  get_file_path_from_iconname)
from softwarecenter.db.appfilter import AppFilter
from softwarecenter.db.database import Application

from softwarecenter.ui.gtk3.views.purchaseview import PurchaseView

from softwarecenter.ui.gtk3.views.catview_gtk import (LobbyViewGtk,
                                                      SubCategoryViewGtk)
from softwarepane import SoftwarePane
from softwarecenter.ui.gtk3.session.viewmanager import get_viewmanager
from softwarecenter.ui.gtk3.session.appmanager import get_appmanager
from softwarecenter.backend.unitylauncher import (UnityLauncher,
                                                  UnityLauncherInfo,
                                                  TransactionDetails)

LOG = logging.getLogger(__name__)


class AvailablePane(SoftwarePane):
    """Widget that represents the available panel in software-center
       It contains a search entry and navigation buttons
    """

    class Pages():
        # page names, useful for debugging
        NAMES = ('lobby',
                 'subcategory',
                 'list',
                 'details',
                 'purchase',
                )
        # actual page id's
        (LOBBY,
         SUBCATEGORY,
         LIST,
         DETAILS,
         PURCHASE) = range(5)
        # the default page
        HOME = LOBBY

    __gsignals__ = {'available-pane-created': (GObject.SignalFlags.RUN_FIRST,
                                               None,
                                               ())}

    def __init__(self,
                 cache,
                 db,
                 distro,
                 icons,
                 datadir,
                 navhistory_back_action,
                 navhistory_forward_action):
        # parent
        SoftwarePane.__init__(self, cache, db, distro, icons, datadir)
        self.searchentry.set_sensitive(False)
        # navigation history actions
        self.navhistory_back_action = navhistory_back_action
        self.navhistory_forward_action = navhistory_forward_action
        # configure any initial state attrs
        self.state.filter = AppFilter(db, cache)
        # the spec says we mix installed/not installed
        #self.apps_filter.set_not_installed_only(True)
        self.current_app_by_category = {}
        self.current_app_by_subcategory = {}
        self.pane_name = _("Get Software")

        # views to be created in init_view
        self.cat_view = None
        self.subcategories_view = None

        # integrate with the Unity launcher
        self.unity_launcher = UnityLauncher()
        # keep track of applications that are queued to be added
        # to the Unity launcher
        self.unity_launcher_transaction_queue = {}
        # flag to indicate whether applications should be added to the
        # unity launcher when installed (this value is initialized by
        # the config load in app.py)
        self.add_to_launcher_enabled = True

    def init_view(self):
        if self.view_initialized:
            return

        self.show_appview_spinner()

        window = self.get_window()
        if window is not None:
            window.set_cursor(self.busy_cursor)

        while Gtk.events_pending():
            Gtk.main_iteration()

        SoftwarePane.init_view(self)
        # set the AppTreeView model, available pane uses list models
        liststore = AppListStore(self.db, self.cache, self.icons)
        #~ def on_appcount_changed(widget, appcount):
            #~ self.subcategories_view._append_appcount(appcount)
            #~ self.app_view._append_appcount(appcount)
        #~ liststore.connect('appcount-changed', on_appcount_changed)
        self.app_view.set_model(liststore)
        liststore.connect("needs-refresh",
            lambda helper, pkgname: self.app_view.queue_draw())

        # purchase view
        self.purchase_view = PurchaseView()
        app_manager = get_appmanager()
        app_manager.connect("purchase-requested",
            self.on_purchase_requested)
        self.purchase_view.connect("purchase-succeeded",
            self.on_purchase_succeeded)
        self.purchase_view.connect("purchase-failed",
            self.on_purchase_failed)
        self.purchase_view.connect("purchase-cancelled-by-user",
            self.on_purchase_cancelled_by_user)
        self.purchase_view.connect("terms-of-service-declined",
            self.on_terms_of_service_declined)
        self.purchase_view.connect("purchase-needs-spinner",
            self.on_purchase_needs_spinner)

        # categories, appview and details into the notebook in the bottom
        self.scroll_categories = Gtk.ScrolledWindow()
        self.scroll_categories.set_policy(Gtk.PolicyType.AUTOMATIC,
                                        Gtk.PolicyType.AUTOMATIC)
        self.cat_view = LobbyViewGtk(self.datadir, APP_INSTALL_PATH,
                                       self.cache,
                                       self.db,
                                       self.icons,
                                       self.apps_filter)
        self.scroll_categories.add(self.cat_view)
        self.notebook.append_page(self.scroll_categories,
            Gtk.Label(label="categories"))

        # sub-categories view
        self.subcategories_view = SubCategoryViewGtk(self.datadir,
            APP_INSTALL_PATH,
            self.cache,
            self.db,
            self.icons,
            self.apps_filter,
            root_category=self.cat_view.categories[0])
        self.subcategories_view.connect(
            "category-selected", self.on_subcategory_activated)
        self.subcategories_view.connect(
            "application-activated", self.on_application_activated)
        self.subcategories_view.connect(
            "show-category-applist", self.on_show_category_applist)
        # FIXME: why do we have two application-{selected,activated] ?!?
        self.subcategories_view.connect(
            "application-selected", self.on_application_selected)
        self.subcategories_view.connect(
            "application-activated", self.on_application_activated)
        self.scroll_subcategories = Gtk.ScrolledWindow()
        self.scroll_subcategories.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scroll_subcategories.add(self.subcategories_view)
        self.notebook.append_page(self.scroll_subcategories,
                                    Gtk.Label(label=NavButtons.SUBCAT))

        # app list
        self.notebook.append_page(self.box_app_list,
                                    Gtk.Label(label=NavButtons.LIST))

        self.cat_view.connect(
            "category-selected", self.on_category_activated)
        self.cat_view.connect(
            "application-selected", self.on_application_selected)
        self.cat_view.connect(
            "application-activated", self.on_application_activated)

        # details
        self.notebook.append_page(self.scroll_details,
            Gtk.Label(label=NavButtons.DETAILS))

        # purchase view
        self.notebook.append_page(self.purchase_view,
            Gtk.Label(label=NavButtons.PURCHASE))

        # install backend
        self.backend.connect("transaction-started",
            self.on_transaction_started)
        self.backend.connect("transactions-changed",
            self.on_transactions_changed)
        self.backend.connect("transaction-finished",
            self.on_transaction_complete)
        self.backend.connect("transaction-stopped",
            self.on_transaction_complete)

        # now we are initialized
        self.searchentry.set_sensitive(True)
        self.emit("available-pane-created")
        self.show_all()
        self.hide_appview_spinner()

        # consider the view initialized here already as display_page()
        # may run into a endless recurison otherwise (it will call init_view())
        # again (LP: #851671)
        self.view_initialized = True

        # important to "seed" the initial history stack (LP: #1005104)
        vm = get_viewmanager()
        vm.display_page(
            self, AvailablePane.Pages.LOBBY,
            self.state, self.display_lobby_page)

        if window is not None:
            window.set_cursor(None)

    def on_purchase_requested(self, appmanager, app, iconname, url):
        if self.purchase_view.initiate_purchase(app, iconname, url):
            vm = get_viewmanager()
            vm.display_page(
                self, AvailablePane.Pages.PURCHASE, self.state,
                self.display_purchase)

    def on_purchase_needs_spinner(self, appmanager, active):
        vm = get_viewmanager()
        vm.set_spinner_active(active)

    def on_purchase_succeeded(self, widget):
        # switch to the details page to display the transaction is in progress
        self._return_to_appdetails_view()

    def on_purchase_failed(self, widget):
        self._return_to_appdetails_view()
        dialogs.error(None,
                      _("Failure in the purchase process."),
                      _("Sorry, something went wrong. Your payment "
                        "has been cancelled."))

    def on_purchase_cancelled_by_user(self, widget):
        self._return_to_appdetails_view()

    def on_terms_of_service_declined(self, widget):
        """ The Terms of Service dialog was declined by the user, so we just
            reset the purchase button in case they want another chance
        """
        if self.is_app_details_view_showing():
            self.app_details_view.pkg_statusbar.button.set_sensitive(True)
        elif self.is_applist_view_showing():
            self.app_view.tree_view.reset_action_button()

    def _return_to_appdetails_view(self):
        vm = get_viewmanager()
        vm.nav_back()
        # don't keep the purchase view in navigation history
        # as its contents are no longer valid
        vm.clear_forward_history()
        window = self.get_window()
        if window is not None:
            window.set_cursor(None)

    def get_query(self):
        """helper that gets the query for the current category/search mode"""
        # NoDisplay is a specal case
        if self._in_no_display_category():
            return xapian.Query()
        # get current sub-category (or category, but sub-category wins)
        query = None

        if self.state.channel and self.state.channel.query:
            query = self.state.channel.query
        elif self.state.subcategory:
            query = self.state.subcategory.query
        elif self.state.category:
            query = self.state.category.query
        # mix channel/category with the search terms and return query
        return self.db.get_query_list_from_search_entry(
                            self.state.search_term, query)

    def _in_no_display_category(self):
        """return True if we are in a category with NoDisplay set in the XML"""
        return (self.state.category and
                self.state.category.dont_display and
                not self.state.subcategory and
                not self.state.search_term)

    def _get_header_for_view_state(self, view_state):
        channel = view_state.channel
        category = view_state.category
        subcategory = view_state.subcategory

        line1 = None
        line2 = None
        if channel is not None:
            name = channel.display_name or channel.name
            line1 = GObject.markup_escape_text(name)
        elif subcategory is not None:
            line1 = GObject.markup_escape_text(category.name)
            line2 = GObject.markup_escape_text(subcategory.name)
        elif category is not None:
            line1 = GObject.markup_escape_text(category.name)
        else:
            line1 = _("All Software")
        return line1, line2

    #~ def _show_hide_subcategories(self, show_category_applist=False):
        #~ # check if have subcategories and are not in a subcategory
        #~ # view - if so, show it
        #~ current_page = self.notebook.get_current_page()
        #~ if (current_page == AvailablePane.Pages.LOBBY or
            #~ current_page == AvailablePane.Pages.DETAILS):
            #~ return
        #~ if (not show_category_applist and
            #~ self.state.category and
            #~ self.state.category.subcategories and
            #~ not (self.state.search_term or self.state.subcategory)):
            #~ self.subcategories_view.set_subcategory(self.state.category,
                #~ num_items=len(self.app_view.get_model()))
            #~ self.notebook.set_current_page(AvailablePane.Pages.SUBCATEGORY)
        #~ else:
            #~ self.notebook.set_current_page(AvailablePane.Pages.LIST)

    def get_current_app(self):
        """return the current active application object"""
        if self.is_category_view_showing():
            return None
        else:
            if self.state.subcategory:
                return self.current_app_by_subcategory.get(
                    self.state.subcategory)
            else:
                return self.current_app_by_category.get(self.state.category)

    def get_current_category(self):
        """ return the current category that is in use or None """
        if self.state.subcategory:
            return self.state.subcategory
        elif self.state.category:
            return self.state.category

    def unset_current_category(self):
        """ unset the current showing category, but keep e.g. the current
            search
        """
        self.state.category = None
        self.state.subcategory = None
        # reset the non-global filters see (LP: #985389)
        if self.state.filter:
            self.state.filter.reset()

    def on_transaction_started(self, backend, pkgname, appname, trans_id,
                               trans_type):
        # we only care about installs for the launcher, queue here for
        # later, see #972710
        if trans_type == TransactionTypes.INSTALL:
            transaction_details = TransactionDetails(
                    pkgname, appname, trans_id, trans_type)
            self.unity_launcher_transaction_queue[pkgname] = (
                    transaction_details)

    def on_transactions_changed(self, backend, pending_transactions):
        """internal helper that keeps the action bar up-to-date by
           keeping track of the transaction-started signals
        """
        if self._is_custom_list_search(self.state.search_term):
            self._update_action_bar()
        # add app to unity launcher on the first sign of progress
        # and remove from the pending queue once that is done
        for pkgname in pending_transactions:
            if pkgname in self.unity_launcher_transaction_queue:
                transaction_details = (
                    self.unity_launcher_transaction_queue.pop(pkgname))
                self._add_application_to_unity_launcher(transaction_details)

    def on_transaction_complete(self, backend, result):
        if result.pkgname in self.unity_launcher_transaction_queue:
            self.unity_launcher_transaction_queue.pop(result.pkgname)

    def _add_application_to_unity_launcher(self, transaction_details):
        if not self.add_to_launcher_enabled:
            return
        # mvo: use use softwarecenter.utils explicitly so that we can monkey
        #      patch it in the test
        if not softwarecenter.utils.is_unity_running():
            return

        app = Application(pkgname=transaction_details.pkgname,
                          appname=transaction_details.appname)
        appdetails = app.get_details(self.db)
        # we only add items to the launcher that have a desktop file
        if not appdetails.desktop_file:
            return
        # do not add apps that have no Exec entry in their desktop file
        # (e.g. wine, see LP: #848437 or ubuntu-restricted-extras,
        # see LP: #913756)
        if (os.path.exists(appdetails.desktop_file) and
            not get_exec_line_from_desktop(appdetails.desktop_file)):
            return

        # now gather up the unity launcher info items and send the app to the
        # launcher service
        launcher_info = self._get_unity_launcher_info(app, appdetails,
                transaction_details.trans_id)
        self.unity_launcher.send_application_to_launcher(
                transaction_details.pkgname,
                launcher_info)

    def _get_unity_launcher_info(self, app, appdetails, trans_id):
        (icon_size, icon_x, icon_y) = (
                self._get_onscreen_icon_details_for_launcher_service(app))
        icon_path = get_file_path_from_iconname(
                                self.icons,
                                iconname=appdetails.icon_file_name)
        launcher_info = UnityLauncherInfo(app.name,
                                          appdetails.icon,
                                          icon_path,
                                          icon_x,
                                          icon_y,
                                          icon_size,
                                          appdetails.desktop_file,
                                          trans_id)
        return launcher_info

    def _get_onscreen_icon_details_for_launcher_service(self, app):
        if self.is_app_details_view_showing():
            return self.app_details_view.get_app_icon_details()
        elif self.is_applist_view_showing():
            return self.app_view.get_app_icon_details()
        else:
            # set a default, even though we cannot install from the other panes
            return (0, 0, 0)

    def on_app_list_changed(self, pane, length):
        """internal helper that keeps the status text and the action
           bar up-to-date by keeping track of the app-list-changed
           signals
        """
        LOG.debug("applist-changed %s %s" % (pane, length))
        super(AvailablePane, self).on_app_list_changed(pane, length)
        self._update_action_bar()

    def _update_action_bar(self):
        self._update_action_bar_buttons()

    def _update_action_bar_buttons(self):
        """Update buttons in the action bar to implement the custom package
           lists feature, see
           https://wiki.ubuntu.com/SoftwareCenter#Custom%20package%20lists
        """
        if self._is_custom_list_search(self.state.search_term):
            installable = []
            for doc in self.enquirer.get_documents():
                pkgname = self.db.get_pkgname(doc)
                if (pkgname in self.cache and
                    not self.cache[pkgname].is_installed and
                    not len(self.backend.pending_transactions) > 0):
                    app = Application(pkgname=pkgname)
                    installable.append(app)
            button_text = gettext.ngettext(
                "Install %(amount)s Item",
                "Install %(amount)s Items",
                len(installable)) % {'amount': len(installable)}
            button = self.action_bar.get_button(ActionButtons.INSTALL)
            if button and installable:
                # Install all already offered. Update offer.
                if button.get_label() != button_text:
                    button.set_label(button_text)
            elif installable:
                # Install all not yet offered. Offer.
                self.action_bar.add_button(ActionButtons.INSTALL, button_text,
                                           self._install_current_appstore)
            else:
                # Install offered, but nothing to install. Clear offer.
                self.action_bar.remove_button(ActionButtons.INSTALL)
        else:
            # Ensure button is removed.
            self.action_bar.remove_button(ActionButtons.INSTALL)

    def _install_current_appstore(self):
        '''
        Function that installs all applications displayed in the pane.
        '''
        apps = []
        iconnames = []
        self.action_bar.remove_button(ActionButtons.INSTALL)
        for doc in self.enquirer.get_documents():
            pkgname = self.db.get_pkgname(doc)
            if (pkgname in self.cache and
                not self.cache[pkgname].is_installed and
                pkgname not in self.backend.pending_transactions):
                apps.append(self.db.get_application(doc))
                # add iconnames
                iconnames.append(self.db.get_iconname(doc))
        self.backend.install_multiple(apps, iconnames)

    def _show_or_hide_search_combo_box(self, view_state):
        # show/hide the sort combobox headers if the category forces a
        # custom sort mode
        category = view_state.category
        allow_user_sort = category is None or not category.is_forced_sort_mode
        self.app_view.set_allow_user_sorting(allow_user_sort)

    def set_state(self, nav_item):
        pass

    def _clear_search(self):
        self.searchentry.clear_with_no_signal()
        self.apps_limit = 0
        self.apps_search_term = ""

    def _is_custom_list_search(self, search_term):
        return (search_term and
                ',' in search_term)

    # callbacks
    def on_cache_ready(self, cache):
        """ refresh the application list when the cache is re-opened """
        # just re-draw in the available pane, nothing but the
        # "is-installed" overlay icon will change when something
        # is installed or removed in the available pane
        self.app_view.queue_draw()

    def on_search_terms_changed(self, widget, new_text):
        """callback when the search entry widget changes"""
        LOG.debug("on_search_terms_changed: %s" % new_text)

        # reset the flag in the app_view because each new search should
        # reset the sort criteria
        self.app_view.reset_default_sort_mode()

        self.state.search_term = new_text

        # do not hide technical items for a custom list search
        if self._is_custom_list_search(self.state.search_term):
            self.nonapps_visible = NonAppVisibility.ALWAYS_VISIBLE

        vm = get_viewmanager()
        adj = self.app_view.tree_view_scroll.get_vadjustment()
        if adj:
            adj.set_value(0.0)

        # yeah for special cases - as discussed on irc, mpt
        # wants this to return to the category screen *if*
        # we are searching but we are not in any category or channel
        if not self.state.category and not self.state.channel and not new_text:
            # category activate will clear search etc
            self.state.reset()
            vm.display_page(self,
                           AvailablePane.Pages.LOBBY,
                           self.state,
                           self.display_lobby_page)
            return False

        elif (self.state.subcategory and not new_text):
            vm.display_page(self, AvailablePane.Pages.LIST, self.state,
                            self.display_app_view_page)
            return False

        elif (self.state.category and
                self.state.category.subcategories and not new_text):
            vm.display_page(self,
                           AvailablePane.Pages.SUBCATEGORY,
                           self.state,
                           self.display_subcategory_page)
            return False
        vm.display_page(self, AvailablePane.Pages.LIST, self.state,
                        self.display_search_page)

    def on_db_reopen(self, db):
        """Called when the database is reopened."""
        super(AvailablePane, self).on_db_reopen(db)
        self.refresh_apps()
        if self.app_details_view:
            self.app_details_view.refresh_app()

    def get_callback_for_page(self, page, state):
        if page == AvailablePane.Pages.LOBBY:
            return self.display_lobby_page

        elif page == AvailablePane.Pages.LIST:
            if state.search_term:
                return self.display_search_page
            else:
                return self.display_app_view_page

        elif page == AvailablePane.Pages.SUBCATEGORY:
            return self.display_subcategory_page

        elif page == AvailablePane.Pages.DETAILS:
            return self.display_details_page

        return self.display_lobby_page

    def display_lobby_page(self, page, view_state):
        self.state.reset()
        self.hide_appview_spinner()
        self.emit("app-list-changed", len(self.db))
        self._clear_search()
        self.action_bar.clear()
        return True

    def display_search_page(self, page, view_state):
        new_text = view_state.search_term
        # DTRT if the search is reseted
        if not new_text:
            self._clear_search()
        else:
            self.state.limit = DEFAULT_SEARCH_LIMIT

        header_strings = self._get_header_for_view_state(view_state)
        self.app_view.set_header_labels(*header_strings)
        self._show_or_hide_search_combo_box(view_state)

        self.app_view.vadj = view_state.vadjustment

        self.refresh_apps()
        self.cat_view.stop_carousels()
        return True

    def display_subcategory_page(self, page, view_state):
        category = view_state.category
        self.set_category(category)
        if self.state.search_term or self.searchentry.get_text():
            self._clear_search()
            self.refresh_apps()

        query = self.get_query()
        n_matches = self.quick_query_len(query)
        self.subcategories_view.set_subcategory(category, n_matches)

        self.action_bar.clear()
        self.cat_view.stop_carousels()
        return True

    def display_app_view_page(self, page, view_state):
        category = view_state.category
        self.set_category(category)

        header_strings = self._get_header_for_view_state(view_state)
        self.app_view.set_header_labels(*header_strings)
        self._show_or_hide_search_combo_box(view_state)

        if view_state.search_term:
            self._clear_search()

        self.app_view.vadj = view_state.vadjustment

        self.refresh_apps()
        self.cat_view.stop_carousels()
        return True

    def display_details_page(self, page, view_state):
        if self.searchentry.get_text() != self.state.search_term:
            self.searchentry.set_text_with_no_signal(
                                                self.state.search_term)

        self.action_bar.clear()

        SoftwarePane.display_details_page(self, page, view_state)
        self.cat_view.stop_carousels()
        return True

    def display_purchase(self, page, view_state):
        self.notebook.set_current_page(AvailablePane.Pages.PURCHASE)
        self.action_bar.clear()
        self.cat_view.stop_carousels()

    def display_previous_purchases(self, page, view_state):
        self.nonapps_visible = NonAppVisibility.ALWAYS_VISIBLE
        self.app_view.set_header_labels(_("Previous Purchases"), None)
        self.notebook.set_current_page(AvailablePane.Pages.LIST)
        # clear any search terms
        self._clear_search()
        # do not emit app-list-changed here, this is done async when
        # the new model is ready
        self.refresh_apps(query=self.previous_purchases_query)
        self.action_bar.clear()
        self.cat_view.stop_carousels()

    def on_subcategory_activated(self, subcat_view, category):
        LOG.debug("on_subcategory_activated: %s %s" % (
                category.name, category))
        self.state.subcategory = category
        self.state.application = None
        page = AvailablePane.Pages.LIST

        vm = get_viewmanager()
        vm.display_page(self, page, self.state, self.display_app_view_page)

    def on_category_activated(self, lobby_view, category):
        """ callback when a category is selected """
        LOG.debug("on_category_activated: %s %s" % (
                category.name, category))

        if category.subcategories:
            page = AvailablePane.Pages.SUBCATEGORY
            callback = self.display_subcategory_page
        else:
            page = AvailablePane.Pages.LIST
            callback = self.display_app_view_page

        self.state.category = category
        self.state.subcategory = None
        self.state.application = None

        vm = get_viewmanager()
        vm.display_page(self, page, self.state, callback)

    def on_application_selected(self, appview, app):
        """callback when an app is selected"""
        LOG.debug("on_application_selected: '%s'" % app)

        if self.state.subcategory:
            self.current_app_by_subcategory[self.state.subcategory] = app
        else:
            self.current_app_by_category[self.state.category] = app

    @wait_for_apt_cache_ready
    def on_application_activated(self, appview, app):
        """callback when an app is clicked"""
        LOG.debug("on_application_activated: '%s'" % app)
        self.state.application = app
        vm = get_viewmanager()
        vm.display_page(self, AvailablePane.Pages.DETAILS, self.state,
                        self.display_details_page)

    def on_show_category_applist(self, widget):
        self._show_hide_subcategories(show_category_applist=True)

    def on_previous_purchases_activated(self, query):
        """ called to activate the previous purchases view """
        #print cat_view, name, query
        LOG.debug("on_previous_purchases_activated with query: %s" % query)
        self.previous_purchases_query = query
        vm = get_viewmanager()
        vm.display_page(self, AvailablePane.Pages.LIST, self.state,
                        self.display_previous_purchases)

    def is_category_view_showing(self):
        """ Return True if we are in the category page or if we display a
            sub-category page
        """
        current_page = self.notebook.get_current_page()
        return (current_page == AvailablePane.Pages.LOBBY or
            current_page == AvailablePane.Pages.SUBCATEGORY)

    def is_applist_view_showing(self):
        """Return True if we are in the applist view """
        return self.notebook.get_current_page() == AvailablePane.Pages.LIST

    def is_app_details_view_showing(self):
        """Return True if we are in the app_details view """
        return self.notebook.get_current_page() == AvailablePane.Pages.DETAILS

    def set_category(self, category):
        LOG.debug('set_category: %s' % category)
        self.state.category = category

        # apply flags
        if category:
            if 'nonapps-visible' in category.flags:
                self.nonapps_visible = NonAppVisibility.ALWAYS_VISIBLE
            else:
                self.nonapps_visible = NonAppVisibility.MAYBE_VISIBLE

        # apply any category based filters
        if not self.state.filter:
            self.state.filter = AppFilter(self.db, self.cache)

        if (category and category.flags and
            'available-only' in category.flags):
            self.state.filter.set_available_only(True)
        else:
            self.state.filter.set_available_only(False)

        if (category and category.flags and
            'not-installed-only' in category.flags):
            self.state.filter.set_not_installed_only(True)
        else:
            self.state.filter.set_not_installed_only(False)

    def refresh_apps(self, query=None):
        SoftwarePane.refresh_apps(self, query)
        # tell the lobby to update its content
        if self.cat_view:
            self.cat_view.refresh_apps()
        # and the subcat view as well...
        if self.subcategories_view:
            self.subcategories_view.refresh_apps()


def get_test_window():
    from softwarecenter.testutils import (get_test_db,
                                          get_test_datadir,
                                          get_test_install_backend,
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
    backend = get_test_install_backend()

    # create global AppManager instance
    from softwarecenter.ui.gtk3.session.appmanager import ApplicationManager
    ApplicationManager(db, backend, icons)

    navhistory_back_action = Gtk.Action("navhistory_back_action", "Back",
        "Back", None)
    navhistory_forward_action = Gtk.Action("navhistory_forward_action",
        "Forward", "Forward", None)

    w = AvailablePane(cache, db, 'Ubuntu', icons, datadir,
        navhistory_back_action, navhistory_forward_action)
    w.init_view()
    w.show()

    win = Gtk.Window()
    win.connect("destroy", Gtk.main_quit)
    win.add(w)
    win.set_size_request(800, 600)
    win.show_all()

    # this is used later in tests
    win.set_data("pane", w)

    return win

if __name__ == "__main__":
    win = get_test_window()
    Gtk.main()
