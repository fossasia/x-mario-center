
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import GdkPixbuf
from gi.repository import GObject

import logging

from softwarecenter.utils import get_icon_from_theme, utf8
from softwarecenter.backend import get_install_backend
from softwarecenter.backend.transactionswatcher import get_transactions_watcher

from gettext import gettext as _


class PendingStore(Gtk.ListStore):

    # column names
    (COL_TID,
     COL_ICON,
     COL_NAME,
     COL_STATUS,
     COL_PROGRESS,
     COL_PULSE,
     COL_CANCEL) = range(7)

    # column types
    column_types = (str,               # COL_TID
                    GdkPixbuf.Pixbuf,  # COL_ICON
                    str,               # COL_NAME
                    str,               # COL_STATUS
                    float,             # COL_PROGRESS
                    int,               # COL_PULSE
                    str)               # COL_CANCEL

    # icons
    PENDING_STORE_ICON_CANCEL = Gtk.STOCK_CANCEL
    PENDING_STORE_ICON_NO_CANCEL = ""  # Gtk.STOCK_YES

    ICON_SIZE = 24

    # for the progress pulse if a transaction is in the waiting state
    DO_PROGRESS_PULSE = 1
    STOP_PROGRESS_PULSE = -1

    def __init__(self, icons):
        # icon, status, progress
        Gtk.ListStore.__init__(self)
        self.set_column_types(self.column_types)

        self._transactions_watcher = get_transactions_watcher()
        self._transactions_watcher.connect("lowlevel-transactions-changed",
            self._on_lowlevel_transactions_changed)
        # data
        self.icons = icons
        # the apt-daemon stuff
        self.backend = get_install_backend()
        self._signals = []
        # let the pulse helper run
        GObject.timeout_add(500, self._pulse_purchase_helper)

    def clear(self):
        super(PendingStore, self).clear()
        for sig in self._signals:
            GObject.source_remove(sig)
            del sig
        self._signals = []

    def _on_lowlevel_transactions_changed(self, watcher, current_tid,
        pending_tids):
        logging.debug("on_transaction_changed %s (%s)" % (current_tid,
            len(pending_tids)))
        self.clear()
        for tid in [current_tid] + pending_tids:
            if not tid:
                continue
            # we do this synchronous (it used to be a reply_handler)
            # otherwise we run into a race that
            # when we get two on_transaction_changed closely after each
            # other clear() is run before the "_append_transaction" handler
            # is run and we end up with two (or more) _append_transactions
            trans = self._transactions_watcher.get_transaction(tid)
            if trans:
                self._append_transaction(trans)
        # add pending purchases as pseudo transactions
        for pkgname in self.backend.pending_purchases:
            iconname = self.backend.pending_purchases[pkgname].iconname
            icon = get_icon_from_theme(self.icons, iconname=iconname,
                iconsize=self.ICON_SIZE)
            appname = self.backend.pending_purchases[pkgname].appname
            status_text = self._render_status_text(
                appname or pkgname, _(u'Installing purchase\u2026'))
            self.append([pkgname, icon, pkgname, status_text, float(0), 1,
                None])

    def _pulse_purchase_helper(self):
        for item in self:
            if item[self.COL_PULSE] > 0:
                self[-1][self.COL_PULSE] += 1
        return True

    def _append_transaction(self, trans):
        """Extract information about the transaction and append it to the
        store.
        """
        logging.debug("_append_transaction %s (%s)" % (trans.tid, trans))
        self._signals.append(
            trans.connect(
                "progress-details-changed", self._on_progress_details_changed))
        self._signals.append(
            trans.connect("progress-changed", self._on_progress_changed))
        self._signals.append(
            trans.connect("status-changed", self._on_status_changed))
        self._signals.append(
            trans.connect(
                "cancellable-changed", self._on_cancellable_changed))

        if "sc_appname" in trans.meta_data:
            appname = trans.meta_data["sc_appname"]
        elif "sc_pkgname" in trans.meta_data:
            appname = trans.meta_data["sc_pkgname"]
        else:
            #FIXME: Extract information from packages property
            appname = trans.get_role_description()
            self._signals.append(
                trans.connect("role-changed", self._on_role_changed))
        try:
            iconname = trans.meta_data["sc_iconname"]
        except KeyError:
            icon = get_icon_from_theme(self.icons, iconsize=self.ICON_SIZE)
        else:
            icon = get_icon_from_theme(self.icons, iconname=iconname,
                iconsize=self.ICON_SIZE)

        # if transaction is waiting, switch to indeterminate progress
        if trans.is_waiting():
            status = trans.status_details
            pulse = self.DO_PROGRESS_PULSE
        else:
            status = trans.get_status_description()
            pulse = self.STOP_PROGRESS_PULSE

        status_text = self._render_status_text(appname, status)
        cancel_icon = self._get_cancel_icon(trans.cancellable)
        self.append([trans.tid, icon, appname, status_text,
            float(trans.progress), pulse, cancel_icon])

    def _on_cancellable_changed(self, trans, cancellable):
        #print "_on_allow_cancel: ", trans, allow_cancel
        for row in self:
            if row[self.COL_TID] == trans.tid:
                row[self.COL_CANCEL] = self._get_cancel_icon(cancellable)

    def _get_cancel_icon(self, cancellable):
        if cancellable:
            return self.PENDING_STORE_ICON_CANCEL
        else:
            return self.PENDING_STORE_ICON_NO_CANCEL

    def _on_role_changed(self, trans, role):
        #print "_on_progress_changed: ", trans, role
        for row in self:
            if row[self.COL_TID] == trans.tid:
                row[self.COL_NAME] = trans.get_role_description(role) or ""

    def _on_progress_details_changed(self, trans, current_items, total_items,
                                     current_bytes, total_bytes, current_cps,
                                     eta):
        #print "_on_progress_details_changed: ", trans, progress
        for row in self:
            if row[self.COL_TID] == trans.tid:
                if trans.is_downloading():
                    name = row[self.COL_NAME]
                    current_bytes_str = GLib.format_size(current_bytes)
                    total_bytes_str = GLib.format_size(total_bytes)
                    status = _("Downloaded %s of %s") % \
                             (current_bytes_str, total_bytes_str)
                    row[self.COL_STATUS] = self._render_status_text(name,
                        status)

    def _on_progress_changed(self, trans, progress):
        # print "_on_progress_changed: ", trans, progress
        for row in self:
            if row[self.COL_TID] == trans.tid:
                if progress:
                    row[self.COL_PROGRESS] = float(progress)

    def _on_status_changed(self, trans, status):
        #print "_on_progress_changed: ", trans, status
        for row in self:
            if row[self.COL_TID] == trans.tid:
                # FIXME: the spaces around %s are poor mans padding because
                #        setting xpad on the cell-renderer seems to not work
                name = row[self.COL_NAME]
                if trans.is_waiting():
                    st = trans.status_details
                    row[self.COL_PULSE] = self.DO_PROGRESS_PULSE
                else:
                    st = trans.get_status_description(status)
                    row[self.COL_PULSE] = self.STOP_PROGRESS_PULSE
                row[self.COL_STATUS] = self._render_status_text(name, st)

    def _render_status_text(self, name, status):
        if not name:
            name = ""
        return "%s\n<small>%s</small>" % (utf8(name), utf8(status))
