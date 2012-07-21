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


from gi.repository import Gtk, GObject
import logging

from gettext import gettext as _

from softwarecenter.backend import get_install_backend
from softwarecenter.enums import ViewPages
from softwarecenter.backend.channel import (get_channels_manager,
                                            AllInstalledChannel,
                                            AllAvailableChannel)
from softwarecenter.ui.gtk3.widgets.buttons import (SectionSelector,
                                                    ChannelSelector)
from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.ui.gtk3.widgets.symbolic_icons import (
                                    SymbolicIcon, PendingSymbolicIcon)


LOG = logging.getLogger(__name__)


_last_button = None


class ViewSwitcher(Gtk.Box):

    ICON_SIZE = Gtk.IconSize.LARGE_TOOLBAR

    def __init__(self, view_manager, datadir, db, cache, icons):
        # boring stuff
        self.view_manager = view_manager

        def on_view_changed(widget, view_id):
            self.view_buttons[view_id].set_active(True)
        self.view_manager.connect('view-changed', on_view_changed)
        self.channel_manager = get_channels_manager(db)

        # backend sig handlers ...
        self.backend = get_install_backend()
        self.backend.connect("transactions-changed",
                             self.on_transaction_changed)
        self.backend.connect("transaction-finished",
                             self.on_transaction_finished)
        self.backend.connect("channels-changed",
                             self.on_channels_changed)

        # widgetry
        Gtk.Box.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)

        # Gui stuff
        self.view_buttons = {}
        self.selectors = {}
        self._prev_view = None  # track the previous active section
        self._prev_item = None  # track the previous active menu-item
        self._handlers = []

        # order is important here!
        # first, the availablepane items
        icon = SymbolicIcon("available")
        self.append_section_with_channel_sel(
                                ViewPages.AVAILABLE,
                                _("All Software"),
                                icon,
                                self.on_get_available_channels)

        # the installedpane items
        icon = SymbolicIcon("installed")
        self.append_section_with_channel_sel(
                                ViewPages.INSTALLED,
                                _("Installed"),
                                icon,
                                self.on_get_installed_channels)

        # the historypane item
        icon = SymbolicIcon("history")
        self.append_section(ViewPages.HISTORY, _("History"), icon)

        # the pendingpane
        icon = PendingSymbolicIcon("pending")
        self.append_section(ViewPages.PENDING, _("Progress"), icon)

        # set sensible atk name
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Software sources"))

    def on_transaction_changed(self, backend, total_transactions):
        LOG.debug("on_transactions_changed '%s'" % total_transactions)
        pending = len(total_transactions)
        self.notify_icon_of_pending_count(pending)
        if pending > 0:
            self.start_icon_animation()
            pending_btn = self.view_buttons[ViewPages.PENDING]
            if not pending_btn.get_visible():
                pending_btn.set_visible(True)
        else:
            self.stop_icon_animation()
            pending_btn = self.view_buttons[ViewPages.PENDING]
            from softwarecenter.ui.gtk3.session.viewmanager import (
                get_viewmanager,
            )
            vm = get_viewmanager()
            if vm.get_active_view() == 'view-page-pending':
                vm.nav_back()
                vm.clear_forward_history()
            pending_btn.set_visible(False)

    def start_icon_animation(self):
        self.view_buttons[ViewPages.PENDING].image.start()

    def stop_icon_animation(self):
        self.view_buttons[ViewPages.PENDING].image.stop()

    def notify_icon_of_pending_count(self, count):
        image = self.view_buttons[ViewPages.PENDING].image
        image.set_transaction_count(count)

    def on_transaction_finished(self, backend, result):
        if result.success:
            self.on_channels_changed()

    def on_section_sel_clicked(self, button, event, view_id):
        # mvo: this check causes bug LP: #828675
        #if self._prev_view is view_id:
        #    return True

        vm = self.view_manager

        def config_view():
            # set active pane
            pane = vm.set_active_view(view_id)
            # configure DisplayState
            state = pane.state.copy()
            if view_id == ViewPages.INSTALLED:
                state.channel = AllInstalledChannel()
            else:
                state.channel = AllAvailableChannel()
            # decide which page we want to display
            if hasattr(pane, "Pages"):
                page = pane.Pages.HOME
            else:
                page = None
            # request page change
            vm.display_page(pane, page, state)
            return False

        self._prev_view = view_id
        GObject.idle_add(config_view)

    def on_get_available_channels(self, popup):
        return self.build_channel_list(popup, ViewPages.AVAILABLE)

    def on_get_installed_channels(self, popup):
        return self.build_channel_list(popup, ViewPages.INSTALLED)

    def on_channels_changed(self, backend=None, res=None):
        for view_id, sel in self.selectors.items():
            # setting popup to None will cause a rebuild of the popup
            # menu the next time the selector is clicked
            sel.popup = None

    def append_section(self, view_id, label, icon):
        btn = SectionSelector(label, icon, self.ICON_SIZE)
        self.view_buttons[view_id] = btn
        self.pack_start(btn, False, False, 0)

        global _last_button
        if _last_button is not None:
            btn.join_group(_last_button)

        _last_button = btn

        # this must go last otherwise as the buttons are added
        # to the group, toggled & clicked gets emitted... causing
        # all panes to fully initialise on USC startup, which is
        # undesirable!
        btn.connect("button-release-event", self.on_section_sel_clicked,
            view_id)
        return btn

    def append_channel_selector(self, section_btn, view_id, build_func):
        sel = ChannelSelector(section_btn)
        self.selectors[view_id] = sel
        sel.set_build_func(build_func)
        self.pack_start(sel, False, False, 0)
        return sel

    def append_section_with_channel_sel(self, view_id, label, icon,
        build_func):
        btn = self.append_section(view_id, label, icon)
        btn.draw_hint_has_channel_selector = True
        sel = self.append_channel_selector(btn, view_id, build_func)
        return btn, sel

    def build_channel_list(self, popup, view_id):
        # clean up old signal handlers
        for sig in self._handlers:
            GObject.source_remove(sig)

        if view_id == ViewPages.AVAILABLE:
            channels = self.channel_manager.channels
        elif view_id == ViewPages.INSTALLED:
            channels = self.channel_manager.channels_installed_only
        else:
            channels = self.channel_manager.channels

        for i, channel in enumerate(channels):
            # only calling it with a explicit new() makes it a really
            # empty one, otherwise the following error is raised:
            # """Attempting to add a widget with type GtkBox to a
            #    GtkCheckMenuItem, but as a GtkBin subclass a
            #    GtkCheckMenuItem can only contain one widget at a time;
            #    it already contains a widget of type GtkAccelLabel """

            item = Gtk.MenuItem.new()

            label = Gtk.Label.new(channel.display_name)
            image = Gtk.Image.new_from_icon_name(channel.icon,
                Gtk.IconSize.MENU)

            box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, StockEms.SMALL)
            box.pack_start(image, False, False, 0)
            box.pack_start(label, False, False, 0)

            item.add(box)
            item.show_all()

            self._handlers.append(
                item.connect(
                    "button-release-event",
                    self.on_channel_selected,
                    channel,
                    view_id
                )
            )
            popup.attach(item, 0, 1, i, i + 1)

    def on_channel_selected(self, item, event, channel, view_id):
        vm = self.view_manager

        def config_view():
            # set active pane
            pane = vm.set_active_view(view_id)
            # configure DisplayState
            state = pane.state.copy()
            state.category = None
            state.subcategory = None
            state.channel = channel
            # decide which page we want to display
            if hasattr(pane, "Pages"):
                if channel.origin == "all":
                    page = pane.Pages.HOME
                else:
                    page = pane.Pages.LIST
            else:
                page = None
            # request page change
            vm.display_page(pane, page, state)
            return False

        GObject.idle_add(config_view)


def get_test_window_viewswitcher():
    from softwarecenter.testutils import (get_test_db,
                                          get_test_datadir,
                                          get_test_gtk3_viewmanager,
                                          get_test_pkg_info,
                                          get_test_gtk3_icon_cache,
                                          )
    cache = get_test_pkg_info()
    db = get_test_db()
    icons = get_test_gtk3_icon_cache()
    datadir = get_test_datadir()
    manager = get_test_gtk3_viewmanager()

    view = ViewSwitcher(manager, datadir, db, cache, icons)

    scroll = Gtk.ScrolledWindow()
    box = Gtk.VBox()
    box.pack_start(scroll, True, True, 0)

    win = Gtk.Window()
    scroll.add_with_viewport(view)

    win.add(box)
    win.set_size_request(400, 200)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    return win

if __name__ == "__main__":
    import softwarecenter.paths
    logging.basicConfig(level=logging.DEBUG)

    softwarecenter.paths.datadir = "./data"
    win = get_test_window_viewswitcher()

    Gtk.main()
