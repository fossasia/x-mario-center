from gi.repository import Gtk, Gdk, GObject
import logging

from gettext import gettext as _

from softwarecenter.ui.gtk3.session.appmanager import get_appmanager


from cellrenderers import (CellRendererAppView,
                           CellButtonRenderer,
                           CellButtonIDs)

from softwarecenter.ui.gtk3.em import em, StockEms
from softwarecenter.enums import (AppActions, Icons)
from softwarecenter.utils import ExecutionTime
from softwarecenter.backend import get_install_backend
from softwarecenter.netstatus import (get_network_watcher,
                                      network_state_is_connected)
from softwarecenter.ui.gtk3.models.appstore2 import (
    AppGenericStore, CategoryRowReference)


LOG = logging.getLogger(__name__)


class AppTreeView(Gtk.TreeView):

    """Treeview based view component that takes a AppStore and displays it"""

    VARIANT_INFO = 0
    VARIANT_REMOVE = 1
    VARIANT_INSTALL = 2
    VARIANT_PURCHASE = 3

    ACTION_BTNS = (VARIANT_REMOVE, VARIANT_INSTALL, VARIANT_PURCHASE)

    def __init__(self, app_view, db, icons, show_ratings, store=None):
        Gtk.TreeView.__init__(self)
        self._logger = logging.getLogger("softwarecenter.view.appview")

        self.app_view = app_view
        self.db = db

        self.pressed = False
        self.focal_btn = None
        self._action_block_list = []
        self._needs_collapse = []
        self.expanded_path = None
        self.selected_row_renderer = None

        # pixbuf for the icon that is displayed in the selected row
        self.selected_row_icon = None

        #~ # if this hacked mode is available everything will be fast
        #~ # and we can set fixed_height mode and still have growing rows
        #~ # (see upstream gnome #607447)
        try:
            self.set_property("ubuntu-almost-fixed-height-mode", True)
            self.set_fixed_height_mode(True)
        except:
            self._logger.warn(
                "ubuntu-almost-fixed-height-mode extension not available")

        self.set_headers_visible(False)

        # our custom renderer
        self._renderer = CellRendererAppView(icons,
                                 self.create_pango_layout(''),
                                 show_ratings,
                                 Icons.INSTALLED_OVERLAY)
        self._renderer.set_pixbuf_width(32)
        self._renderer.set_button_spacing(em(0.3))

        # create buttons and set initial strings
        info = CellButtonRenderer(self,
                                  name=CellButtonIDs.INFO)
        info.set_markup_variants(
                    {self.VARIANT_INFO: _('More Info')})

        action = CellButtonRenderer(self,
                                    name=CellButtonIDs.ACTION)

        action.set_markup_variants(
                {self.VARIANT_INSTALL: _('Install'),
                 self.VARIANT_REMOVE: _('Remove'),
                 self.VARIANT_PURCHASE: _(u'Buy\u2026')})

        self._renderer.button_pack_start(info)
        self._renderer.button_pack_end(action)

        self._column = Gtk.TreeViewColumn(
            "Applications", self._renderer,
            application=AppGenericStore.COL_ROW_DATA)
        self._column.set_cell_data_func(
            self._renderer, self._cell_data_func_cb)
        self._column.set_fixed_width(200)
        self._column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        self.append_column(self._column)

        # network status watcher
        watcher = get_network_watcher()
        watcher.connect("changed", self._on_net_state_changed, self._renderer)

        # custom cursor
        self._cursor_hand = Gdk.Cursor.new(Gdk.CursorType.HAND2)

        self.connect("style-updated", self._on_style_updated, self._renderer)
        # button and motion are "special"
        self.connect("button-press-event", self._on_button_press_event,
                     self._renderer)
        self.connect("button-release-event", self._on_button_release_event,
                     self._renderer)
        self.connect("key-press-event", self._on_key_press_event,
                     self._renderer)
        self.connect("key-release-event", self._on_key_release_event,
                     self._renderer)
        self.connect("motion-notify-event", self._on_motion, self._renderer)
        self.connect("cursor-changed", self._on_cursor_changed, self._renderer)
        # our own "activate" handler
        self.connect("row-activated", self._on_row_activated, self._renderer)

        self.backend = get_install_backend()
        self._transactions_connected = False
        self.connect('realize', self._on_realize, self._renderer)

    @property
    def appmodel(self):
        model = self.get_model()
        if isinstance(model, Gtk.TreeModelFilter):
            return model.get_model()
        return model

    def clear_model(self):
        vadjustment = self.get_scrolled_window_vadjustment()
        if vadjustment:
            vadjustment.set_value(0)
        self.expanded_path = None
        self._needs_collapse = []
        if self.appmodel:
            # before clearing the model, disconnect it from the view. this
            # avoids that the model gets a "cursor_changed" signal for each
            # removed row and consequently that _update_selected_row is called
            # for rows that are not really selected (LP: #969050)
            model = self.get_model()
            self.set_model(None)
            model.clear()
            self.set_model(model)

    def set_model(self, model):
        # the set_cell_data_func() calls here are a workaround for bug
        # LP: #986186 - once that is fixed upstream we can revert this
        # and remove the entire "set_model" again
        self._column.set_cell_data_func(self._renderer, None)
        Gtk.TreeView.set_model(self, model)
        self._column.set_cell_data_func(
            self._renderer, self._cell_data_func_cb)

    def expand_path(self, path):
        if path is not None and not isinstance(path, Gtk.TreePath):
            raise TypeError("Expects Gtk.TreePath or None, got %s" %
                              type(path))

        model = self.get_model()
        old = self.expanded_path
        self.expanded_path = path

        if old is not None:
            start, end = self.get_visible_range() or (None, None)
            if ((start and start.compare(old) != -1) or
                (end and end.compare(old) != 1)):
                self._needs_collapse.append(old)
            else:
                try:  # try... a lazy solution to Bug #846204
                    model.row_changed(old, model.get_iter(old))
                except:
                    LOG.exception(
                        "apptreeview.expand_path: Supplied 'old' "
                        "path is an invalid tree path: '%s'" % old)

        if path == None:
            return

        model.row_changed(path, model.get_iter(path))

    def get_scrolled_window_vadjustment(self):
        ancestor = self.get_ancestor(Gtk.ScrolledWindow)
        if ancestor:
            return ancestor.get_vadjustment()

    def get_rowref(self, model, path):
        if path is not None:
            return model[path][AppGenericStore.COL_ROW_DATA]

    def rowref_is_category(self, rowref):
        return isinstance(rowref, CategoryRowReference)

    def reset_action_button(self):
        """ Set the current row's action button sensitivity to the
            specified value
        """
        if self.selected_row_renderer:
            action_btn = self.selected_row_renderer.get_button_by_name(
                CellButtonIDs.ACTION)
            if action_btn:
                action_btn.set_sensitive(True)
                pkgname = self.db.get_pkgname(self.selected_doc)
                self._check_remove_pkg_from_blocklist(pkgname)

    def _on_realize(self, widget, tr):
        # connect to backend events once self is realized so handlers
        # have access to the TreeView's initialised Gdk.Window
        if self._transactions_connected:
            return
        self.backend.connect("transaction-started",
            self._on_transaction_started, tr)
        self.backend.connect("transaction-finished",
            self._on_transaction_finished, tr)
        self.backend.connect("transaction-stopped",
            self._on_transaction_stopped, tr)
        self._transactions_connected = True

    def _calc_row_heights(self, tr):
        ypad = StockEms.SMALL
        tr.set_property('xpad', StockEms.MEDIUM)
        tr.set_property('ypad', ypad)

        for btn in tr.get_buttons():
            # recalc button geometry and cache
            btn.configure_geometry(self.create_pango_layout(""))

        btn_h = btn.height

        tr.normal_height = max(32 + 2 * ypad, em(2.5) + ypad)
        tr.selected_height = tr.normal_height + btn_h + StockEms.MEDIUM

    def _on_style_updated(self, widget, tr):
        self._calc_row_heights(tr)

    def _on_motion(self, tree, event, tr):
        window = self.get_window()
        x, y = int(event.x), int(event.y)
        if not self._xy_is_over_focal_row(x, y):
            window.set_cursor(None)
            return

        path = tree.get_path_at_pos(x, y)
        if not path:
            window.set_cursor(None)
            return

        rowref = self.get_rowref(tree.get_model(), path[0])
        if not rowref:
            return

        if self.rowref_is_category(rowref):
            window.set_cursor(None)
            return

        model = tree.get_model()
        app = model[path[0]][AppGenericStore.COL_ROW_DATA]
        if (not network_state_is_connected() and
            not self.appmodel.is_installed(app)):
            for btn_id in self.ACTION_BTNS:
                btn_id = tr.get_button_by_name(CellButtonIDs.ACTION)
                btn_id.set_sensitive(False)

        use_hand = False
        for btn in tr.get_buttons():
            if btn.state == Gtk.StateFlags.INSENSITIVE:
                continue

            if btn.point_in(x, y):
                use_hand = True
                if self.focal_btn is btn:
                    btn.set_state(Gtk.StateFlags.ACTIVE)
                elif not self.pressed:
                    btn.set_state(Gtk.StateFlags.PRELIGHT)
            else:
                if btn.state != Gtk.StateFlags.NORMAL:
                    btn.set_state(Gtk.StateFlags.NORMAL)

        if use_hand:
            window.set_cursor(self._cursor_hand)
        else:
            window.set_cursor(None)

    def _on_cursor_changed(self, view, tr):
        model = view.get_model()
        sel = view.get_selection()
        path = view.get_cursor()[0]

        rowref = self.get_rowref(model, path)
        if not rowref:
            return

        if self.has_focus():
            self.grab_focus()

        if self.rowref_is_category(rowref):
            self.expand_path(None)
            return

        sel.select_path(path)
        self._update_selected_row(view, tr, path)

    def _update_selected_row(self, view, tr, path=None):
        # keep track of the currently selected row renderer and associated
        # doc for use when updating the widgets and for use with the Unity
        # integration feature
        self.selected_row_renderer = tr
        self.selected_doc = tr.application
        sel = view.get_selection()
        if not sel:
            return False
        model, rows = sel.get_selected_rows()
        if not rows:
            return False
        row = rows[0]
        if self.rowref_is_category(row):
            return False

        # update active app, use row-ref as argument
        self.expand_path(row)

        app = model[row][AppGenericStore.COL_ROW_DATA]

        # make sure this is not a category (LP: #848085)
        if self.rowref_is_category(app):
            return False

        action_btn = tr.get_button_by_name(
                            CellButtonIDs.ACTION)
        #if not action_btn: return False

        if self.appmodel.is_installed(app):
            action_btn.set_variant(self.VARIANT_REMOVE)
            action_btn.set_sensitive(True)
            action_btn.show()
        elif self.appmodel.is_available(app):
            if self.appmodel.is_purchasable(app):
                action_btn.set_variant(self.VARIANT_PURCHASE)
            else:
                action_btn.set_variant(self.VARIANT_INSTALL)

            action_btn.set_sensitive(True)
            action_btn.show()

            if not network_state_is_connected():
                action_btn.set_sensitive(False)
                self.app_view.emit("application-selected",
                                   self.appmodel.get_application(app))
                return
        else:
            action_btn.set_sensitive(False)
            action_btn.hide()
            self.app_view.emit("application-selected",
                               self.appmodel.get_application(app))
            return

        if self.appmodel.get_transaction_progress(app) > 0:
            action_btn.set_sensitive(False)
        elif self.pressed and self.focal_btn == action_btn:
            action_btn.set_state(Gtk.StateFlags.ACTIVE)
        else:
            action_btn.set_state(Gtk.StateFlags.NORMAL)

        self.app_view.emit(
            "application-selected", self.appmodel.get_application(app))
        return False

    def _on_row_activated(self, view, path, column, tr):
        rowref = self.get_rowref(view.get_model(), path)

        if not rowref:
            return
        elif self.rowref_is_category(rowref):
            return

        x, y = self.get_pointer()
        for btn in tr.get_buttons():
            if btn.point_in(x, y):
                return

        app = self.appmodel.get_application(rowref)
        if app:
            self.app_view.emit("application-activated", app)

    def _on_button_event_get_path(self, view, event, allow_categories=False):
        if event.button != 1:
            return False

        res = view.get_path_at_pos(int(event.x), int(event.y))
        if not res:
            return False

        # check the path is valid and is not a category row
        path = res[0]
        is_cat = self.rowref_is_category(
            self.get_rowref(view.get_model(), path))

        if path is None:
            return False

        if is_cat:
            if allow_categories:
                return path
            else:
                return False

        # only act when the selection is already there
        selection = view.get_selection()
        if not selection.path_is_selected(path):
            return False

        return path

    def _on_button_press_event(self, view, event, tr):
        path = self._on_button_event_get_path(view, event,
                                              allow_categories=False)
        if not path:
            path = self._on_button_event_get_path(view, event,
                                                  allow_categories=True)
            if path:
                if view.row_expanded(path):
                    view.collapse_row(path)
                else:
                    view.expand_row(path, True)
                return True  # swallow event to avoid double action when
                             # clicking on the expander arrow itself
            return

        self.pressed = True
        x, y = int(event.x), int(event.y)
        for btn in tr.get_buttons():
            if (btn.point_in(x, y) and
                (btn.state != Gtk.StateFlags.INSENSITIVE)):
                self.focal_btn = btn
                btn.set_state(Gtk.StateFlags.ACTIVE)
                view.queue_draw()
                return
        self.focal_btn = None

    def _on_button_release_event(self, view, event, tr):
        path = self._on_button_event_get_path(view, event)
        if not path:
            return

        self.pressed = False
        x, y = int(event.x), int(event.y)
        for btn in tr.get_buttons():
            if (btn.point_in(x, y) and
                (btn.state != Gtk.StateFlags.INSENSITIVE)):
                btn.set_state(Gtk.StateFlags.NORMAL)
                self.get_window().set_cursor(self._cursor_hand)
                if self.focal_btn is not btn:
                    break
                self._init_activated(btn, view.get_model(), path)
                view.queue_draw()
                break
        self.focal_btn = None

    def _on_key_press_event(self, widget, event, tr):
        kv = event.keyval
        #print kv
        r = False
        if kv == Gdk.KEY_Right:  # right-key
            btn = tr.get_button_by_name(CellButtonIDs.ACTION)
            if btn is None:
                return  # Bug #846779
            if btn.state != Gtk.StateFlags.INSENSITIVE:
                btn.has_focus = True
                btn = tr.get_button_by_name(CellButtonIDs.INFO)
                btn.has_focus = False
        elif kv == Gdk.KEY_Left:  # left-key
            btn = tr.get_button_by_name(CellButtonIDs.ACTION)
            if btn is None:
                return  # Bug #846779
            btn.has_focus = False
            btn = tr.get_button_by_name(CellButtonIDs.INFO)
            btn.has_focus = True
        elif kv == Gdk.KEY_space:  # spacebar
            for btn in tr.get_buttons():
                if (btn is not None and btn.has_focus and
                    btn.state != Gtk.StateFlags.INSENSITIVE):
                    btn.set_state(Gtk.StateFlags.ACTIVE)
                    sel = self.get_selection()
                    model, it = sel.get_selected()
                    path = model.get_path(it)
                    if path:
                        #self._init_activated(btn, self.get_model(), path)
                        r = True
                    break

        self.queue_draw()
        return r

    def _on_key_release_event(self, widget, event, tr):
        kv = event.keyval
        r = False
        if kv == 32:    # spacebar
            for btn in tr.get_buttons():
                if btn.has_focus and btn.state != Gtk.StateFlags.INSENSITIVE:
                    btn.set_state(Gtk.StateFlags.NORMAL)
                    sel = self.get_selection()
                    model, it = sel.get_selected()
                    path = model.get_path(it)
                    if path:
                        self._init_activated(btn, self.get_model(), path)
                        btn.has_focus = False
                        r = True
                    break

        self.queue_draw()
        return r

    def _init_activated(self, btn, model, path):
        app = model[path][AppGenericStore.COL_ROW_DATA]
        s = Gtk.Settings.get_default()
        GObject.timeout_add(s.get_property("gtk-timeout-initial"),
                            self._app_activated_cb,
                            btn,
                            btn.name,
                            app,
                            model,
                            path)

    def _cell_data_func_cb(self, col, cell, model, it, user_data):
        path = model.get_path(it)

        # this will pre-load data *only* on a AppListStore, it has
        # no effect with a AppTreeStore
        if model[path][0] is None:
            indices = path.get_indices()
            model.load_range(indices, 5)

        if path in self._needs_collapse:
            # collapse rows that were outside the visible range and
            # thus not immediately collapsed when expand_path was called
            cell.set_property('isactive', False)
            i = self._needs_collapse.index(path)
            del self._needs_collapse[i]
            model.row_changed(path, it)
            return

        # update active property
        cell.set_property('isactive', path == self.expanded_path)
        # update "text" property for a11y
        raw = model[path][AppGenericStore.COL_ROW_DATA]
        if self.rowref_is_category(raw):
            text = raw.display_name
        elif raw:
            text = self.db.get_pkgname(raw)
        else:
            # this can happen for empty/not-yet-loaded row, LP: #981992
            text = ""
        cell.set_property('text', text)

    def _app_activated_cb(self, btn, btn_id, app, store, path):
        if self.rowref_is_category(app):
            return

        # FIXME: would be nice if that would be more elegant
        # because we use a treefilter we need to get the "real"
        # model first
        if type(store) is Gtk.TreeModelFilter:
            store = store.get_model()

        pkgname = self.appmodel.get_pkgname(app)

        if btn_id == CellButtonIDs.INFO:
            self.app_view.emit("application-activated",
                               self.appmodel.get_application(app))
        elif btn_id == CellButtonIDs.ACTION:
            btn.set_sensitive(False)
            store.row_changed(path, store.get_iter(path))
            app_manager = get_appmanager()
            # be sure we dont request an action for a pkg with
            # pre-existing actions
            if pkgname in self._action_block_list:
                logging.debug("Action already in progress for package:"
                              " '%s'" % pkgname)
                return False
            self._action_block_list.append(pkgname)
            if self.appmodel.is_installed(app):
                action = AppActions.REMOVE
            elif self.appmodel.is_purchasable(app):
                app_manager.buy_app(self.appmodel.get_application(app))
                store.notify_action_request(app, path)
                return
            else:
                action = AppActions.INSTALL

            store.notify_action_request(app, path)

            app_manager.request_action(
                self.appmodel.get_application(app), [], [],
                action)
        return False

    def _set_cursor(self, btn, cursor):
        # make sure we have a window instance (LP: #617004)
        window = self.get_window()
        if isinstance(window, Gdk.Window):
            x, y = self.get_pointer()
            if btn.point_in(x, y):
                window.set_cursor(cursor)

    def _on_transaction_started(self, backend, pkgname, appname, trans_id,
        trans_type, tr):
        """callback when an application install/remove transaction has
        started
        """
        action_btn = tr.get_button_by_name(CellButtonIDs.ACTION)
        if action_btn:
            action_btn.set_sensitive(False)
            self._set_cursor(action_btn, None)

    def _on_transaction_finished(self, backend, result, tr):
        """callback when an application install/remove transaction has
        finished
        """
        # need to send a cursor-changed so the row button is properly updated
        self.emit("cursor-changed")
        # remove pkg from the block list
        self._check_remove_pkg_from_blocklist(result.pkgname)

        action_btn = tr.get_button_by_name(CellButtonIDs.ACTION)
        if action_btn:
            action_btn.set_sensitive(True)
            self._set_cursor(action_btn, self._cursor_hand)

    def _on_transaction_stopped(self, backend, result, tr):
        """callback when an application install/remove transaction has
        stopped
        """
        # remove pkg from the block list
        self._check_remove_pkg_from_blocklist(result.pkgname)

        action_btn = tr.get_button_by_name(CellButtonIDs.ACTION)
        if action_btn:
            # this should be a function that decides action button state label
            if action_btn.current_variant == self.VARIANT_INSTALL:
                action_btn.set_markup(self.VARIANT_REMOVE)
            action_btn.set_sensitive(True)
            self._set_cursor(action_btn, self._cursor_hand)

    def _on_net_state_changed(self, watcher, state, tr):
        self._update_selected_row(self, tr)
        # queue a draw just to be sure the view is looking right
        self.queue_draw()

    def _check_remove_pkg_from_blocklist(self, pkgname):
        if pkgname in self._action_block_list:
            i = self._action_block_list.index(pkgname)
            del self._action_block_list[i]

    def _xy_is_over_focal_row(self, x, y):
        res = self.get_path_at_pos(x, y)
        #cur = self.get_cursor()
        if not res:
            return False
        return self.get_path_at_pos(x, y)[0] == self.get_cursor()[0]


def get_test_window():
    import softwarecenter.log
    softwarecenter.log.root.setLevel(level=logging.DEBUG)
    softwarecenter.log.add_filters_from_string("performance")
    fmt = logging.Formatter("%(name)s - %(message)s", None)
    softwarecenter.log.handler.setFormatter(fmt)

    from softwarecenter.testutils import (
        get_test_db, get_test_pkg_info, get_test_gtk3_icon_cache,
        get_test_categories)

    cache = get_test_pkg_info()
    db = get_test_db()
    icons = get_test_gtk3_icon_cache()

    # create a filter
    from softwarecenter.db.appfilter import AppFilter
    filter = AppFilter(db, cache)
    filter.set_supported_only(False)
    filter.set_installed_only(True)

    # get the TREEstore
    from softwarecenter.ui.gtk3.models.appstore2 import AppTreeStore
    store = AppTreeStore(db, cache, icons)

    # populate from data
    cats = get_test_categories(db)
    for cat in cats[:3]:
        with ExecutionTime("query cat '%s'" % cat.name):
            docs = db.get_docs_from_query(cat.query)
            store.set_category_documents(cat, docs)

    # ok, this is confusing - the AppView contains the AppTreeView that
    #                         is a tree or list depending on the model
    from softwarecenter.ui.gtk3.views.appview import AppView
    app_view = AppView(db, cache, icons, show_ratings=True)
    app_view.set_model(store)

    box = Gtk.VBox()
    box.pack_start(app_view, True, True, 0)

    win = Gtk.Window()
    win.add(box)
    win.connect("destroy", lambda x: Gtk.main_quit())
    win.set_size_request(600, 400)
    win.show_all()

    return win


if __name__ == "__main__":
    win = get_test_window()
    Gtk.main()
