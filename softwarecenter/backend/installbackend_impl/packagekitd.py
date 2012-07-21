# Copyright (C) 2009-2010 Canonical
#
# Authors:
#  Alex Eftimie
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
import dbus
import dbus.mainloop.glib

from gi.repository import GObject
from gi.repository import PackageKitGlib as packagekit

from softwarecenter.enums import TransactionTypes
from softwarecenter.backend.transactionswatcher import (
    BaseTransactionsWatcher,
    BaseTransaction,
    TransactionFinishedResult,
    TransactionProgress
)
from softwarecenter.backend.installbackend import InstallBackend

# temporary, must think of better solution
from softwarecenter.db.pkginfo import get_pkg_info

LOG = logging.getLogger("softwarecenter.backend.packagekit")


class PackagekitTransaction(BaseTransaction):
    _meta_data = {}

    def __init__(self, trans):
        """ trans -- a PkProgress object """
        GObject.GObject.__init__(self)
        self._trans = trans
        self._setup_signals()

    def _setup_signals(self):
        """ Connect signals to the PkProgress from libpackagekitlib,
        because PK DBus exposes only a generic Changed, without
        specifying the property changed
        """
        self._trans.connect('notify::role', self._emit,
            'role-changed', 'role')
        self._trans.connect('notify::status', self._emit,
            'status-changed', 'status')
        self._trans.connect('notify::percentage', self._emit,
            'progress-changed', 'percentage')
        # SC UI does not support subprogress:
        #self._trans.connect('notify::subpercentage', self._emit,
        #    'progress-changed', 'subpercentage')
        self._trans.connect('notify::percentage', self._emit,
            'progress-changed', 'percentage')
        self._trans.connect('notify::allow-cancel', self._emit,
            'cancellable-changed', 'allow-cancel')

        # connect the delete:
        proxy = dbus.SystemBus().get_object('org.freedesktop.PackageKit',
            self.tid)
        trans = dbus.Interface(proxy, 'org.freedesktop.PackageKit.Transaction')
        trans.connect_to_signal("Destroy", self._remove)

    def _emit(self, *args):
        prop, what = args[-1], args[-2]
        self.emit(what, self._trans.get_property(prop))

    @property
    def tid(self):
        return self._trans.get_property('transaction-id')

    @property
    def status_details(self):
        return self.get_status_description()  # FIXME

    @property
    def meta_data(self):
        return self._meta_data

    @property
    def cancellable(self):
        return self._trans.get_property('allow-cancel')

    @property
    def progress(self):
        return self._trans.get_property('percentage')

    def get_role_description(self, role=None):
        role = role if role is not None else self._trans.get_property('role')
        return self.meta_data.get('sc_appname',
            packagekit.role_enum_to_localised_present(role))

    def get_status_description(self, status=None):
        if status is None:
            status = self._trans.get_property('status')

        return packagekit.info_enum_to_localised_present(status)

    def is_waiting(self):
        """ return true if a time consuming task is taking place """
        #LOG.debug('is_waiting ' + str(self._trans.get_property('status')))
        status = self._trans.get_property('status')
        return status == packagekit.StatusEnum.WAIT or \
               status == packagekit.StatusEnum.LOADING_CACHE or \
               status == packagekit.StatusEnum.SETUP

    def is_downloading(self):
        #LOG.debug('is_downloading ' + str(self._trans.get_property('status')))
        status = self._trans.get_property('status')
        return status == packagekit.StatusEnum.DOWNLOAD or \
               (status >= packagekit.StatusEnum.DOWNLOAD_REPOSITORY and \
               status <= packagekit.StatusEnum.DOWNLOAD_UPDATEINFO)

    def cancel(self):
        proxy = dbus.SystemBus().get_object('org.freedesktop.PackageKit',
            self.tid)
        trans = dbus.Interface(proxy, 'org.freedesktop.PackageKit.Transaction')
        trans.Cancel()

    def _remove(self):
        """ delete transaction from _tlist """
        # also notify pk install backend, so that this transaction gets removed
        # from pending_transactions
        self.emit('deleted')
        if self.tid in PackagekitTransactionsWatcher._tlist.keys():
            del PackagekitTransactionsWatcher._tlist[self.tid]
            LOG.debug("Delete transaction %s" % self.tid)


class PackagekitTransactionsWatcher(BaseTransactionsWatcher):
    _tlist = {}

    def __init__(self):
        super(PackagekitTransactionsWatcher, self).__init__()
        self.client = packagekit.Client()

        bus = dbus.SystemBus()
        proxy = bus.get_object('org.freedesktop.PackageKit',
            '/org/freedesktop/PackageKit')
        daemon = dbus.Interface(proxy, 'org.freedesktop.PackageKit')
        daemon.connect_to_signal("TransactionListChanged",
                                     self._on_transactions_changed)
        queued = daemon.GetTransactionList()
        self._on_transactions_changed(queued)

    def _on_transactions_changed(self, queued):
        if len(queued) > 0:
            current = queued[0]
            queued = queued[1:] if len(queued) > 1 else []
        else:
            current = None
        self.emit("lowlevel-transactions-changed", current, queued)

    def add_transaction(self, tid, trans):
        """ return a tuple, (transaction, is_new) """
        if tid not in PackagekitTransactionsWatcher._tlist.keys():
            LOG.debug("Trying to setup %s" % tid)
            if not trans:
                trans = self.client.get_progress(tid, None)
            trans = PackagekitTransaction(trans)
            LOG.debug("Add return new transaction %s %s" % (tid, trans))
            PackagekitTransactionsWatcher._tlist[tid] = trans
            return (trans, True)
        return (PackagekitTransactionsWatcher._tlist[tid], False)

    def get_transaction(self, tid):
        if tid not in PackagekitTransactionsWatcher._tlist.keys():
            trans, new = self.add_transaction(tid, None)
            return trans
        return PackagekitTransactionsWatcher._tlist[tid]


class PackagekitBackend(GObject.GObject, InstallBackend):

    __gsignals__ = {'transaction-started': (GObject.SIGNAL_RUN_FIRST,
                                            GObject.TYPE_NONE,
                                            (str, str, str, str)),
                    # emits a TransactionFinished object
                    'transaction-finished': (GObject.SIGNAL_RUN_FIRST,
                                             GObject.TYPE_NONE,
                                             (GObject.TYPE_PYOBJECT, )),
                    'transaction-stopped': (GObject.SIGNAL_RUN_FIRST,
                                            GObject.TYPE_NONE,
                                            (GObject.TYPE_PYOBJECT,)),
                    'transactions-changed': (GObject.SIGNAL_RUN_FIRST,
                                             GObject.TYPE_NONE,
                                             (GObject.TYPE_PYOBJECT, )),
                    'transaction-progress-changed': (GObject.SIGNAL_RUN_FIRST,
                                                     GObject.TYPE_NONE,
                                                     (str, int,)),
                    # the number/names of the available channels changed
                    # FIXME: not emitted.
                    'channels-changed': (GObject.SIGNAL_RUN_FIRST,
                                         GObject.TYPE_NONE,
                                         (bool,)),
                    }

    def __init__(self):
        GObject.GObject.__init__(self)
        InstallBackend.__init__(self)

        # transaction details for setting as meta
        self.new_pkgname, self.new_appname, self.new_iconname = '', '', ''

        # this is public exposed
        self.pending_transactions = {}

        self.client = packagekit.Client()
        self.pkginfo = get_pkg_info()
        self.pkginfo.open()

        self._transactions_watcher = PackagekitTransactionsWatcher()
        self._transactions_watcher.connect('lowlevel-transactions-changed',
                                self._on_lowlevel_transactions_changed)

    def upgrade(self, pkgname, appname, iconname, addons_install=[],
                addons_remove=[], metadata=None):
        pass  # FIXME implement it

    def remove(self, app, iconname, addons_install=[],
                addons_remove=[], metadata=None):
        self.remove_multiple((app,), (iconname,),
                addons_install, addons_remove, metadata
        )

    def remove_multiple(self, apps, iconnames,
                addons_install=[], addons_remove=[], metadatas=None):

        pkgnames = [app.pkgname for app in apps]
        appnames = [app.appname for app in apps]

        # keep track of pkg, app and icon for setting them as meta
        self.new_pkgname = pkgnames[0]
        self.new_appname = appnames[0]
        self.new_iconname = iconnames[0]

        # temporary hack
        pkgnames = self._fix_pkgnames(pkgnames)

        self.client.remove_packages_async(pkgnames,
                    False,  # allow deps
                    False,  # autoremove
                    None,  # cancellable
                    self._on_progress_changed,
                    None,  # progress data
                    self._on_remove_ready,  # callback ready
                    None  # callback data
        )
        self.emit("transaction-started", pkgnames[0], appnames[0], 0,
            TransactionTypes.REMOVE)

    def install(self, app, iconname, filename=None,
                addons_install=[], addons_remove=[], metadata=None):
        if filename is not None:
            LOG.error("Filename not implemented")  # FIXME
        else:
            self.install_multiple((app,), (iconname,),
                 addons_install, addons_remove, metadata
            )

    def install_multiple(self, apps, iconnames,
        addons_install=[], addons_remove=[], metadatas=None):

        pkgnames = [app.pkgname for app in apps]
        appnames = [app.appname for app in apps]

        # keep track of pkg, app and icon for setting them as meta
        self.new_pkgname = pkgnames[0]
        self.new_appname = appnames[0]
        self.new_iconname = iconnames[0]

        # temporary hack
        pkgnames = self._fix_pkgnames(pkgnames)

        LOG.debug("Installing multiple packages: " + str(pkgnames))

        # FIXME we set the only_trusted flag, which will prevent
        # PackageKit from installing untrusted packages
        # (in general, all enabled repos should have GPG signatures,
        # which is enough for being marked "trusted", but still)
        self.client.install_packages_async(True,  # only trusted
                    pkgnames,
                    None,  # cancellable
                    self._on_progress_changed,
                    None,  # progress data
                    self._on_install_ready,  # GAsyncReadyCallback
                    None  # ready data
        )
        self.emit("transaction-started", pkgnames[0], appnames[0], 0,
            TransactionTypes.INSTALL)

    def apply_changes(self, pkgname, appname, iconname,
        addons_install=[], addons_remove=[], metadata=None):
        pass

    def reload(self, sources_list=None, metadata=None):
        """ reload package list """
        pass

    def _on_transaction_deleted(self, trans):
        name = trans.meta_data.get('sc_pkgname', '')
        if name in self.pending_transactions:
            del self.pending_transactions[name]
            LOG.debug("Deleted transaction " + name)
        else:
            LOG.error("Could not delete: " + name + str(trans))
        # this is needed too
        self.emit('transactions-changed', self.pending_transactions)
        # also hack PackagekitInfo cache so that it emits a cache-ready signal
        if hasattr(self.pkginfo, '_reset_cache'):
            self.pkginfo._reset_cache(name)

    def _on_progress_changed(self, progress, ptype, data=None):
        """ de facto callback on transaction's progress change """
        tid = progress.get_property('transaction-id')
        status = progress.get_property('status')
        if not tid:
            LOG.debug("Progress without transaction")
            return

        trans, new = self._transactions_watcher.add_transaction(tid, progress)
        if new:
            trans.connect('deleted', self._on_transaction_deleted)
            LOG.debug("new transaction" + str(trans))
            # should add it to pending_transactions, but
            # i cannot get the pkgname here
            trans.meta_data['sc_appname'] = self.new_appname
            trans.meta_data['sc_pkgname'] = self.new_pkgname
            trans.meta_data['sc_iconname'] = self.new_iconname
            if self.new_pkgname not in self.pending_transactions:
                self.pending_transactions[self.new_pkgname] = trans

        # LOG.debug("Progress update %s %s %s %s" %
        #     (status, ptype, progress.get_property('transaction-id'),
        #     progress.get_property('status')))

        if status == packagekit.StatusEnum.FINISHED:
            LOG.debug("Transaction finished %s" % tid)
            self.emit("transaction-finished",
                TransactionFinishedResult(trans, True))

        if status == packagekit.StatusEnum.CANCEL:
            LOG.debug("Transaction canceled %s" % tid)
            self.emit("transaction-stopped",
                TransactionFinishedResult(trans, True))

        if ptype == packagekit.ProgressType.PACKAGE:
            # this should be done better
            # mvo: why getting package here at all?
            #package = progress.get_property('package')
            # fool sc ui about the name change
            trans.emit('role-changed', packagekit.RoleEnum.LAST)

        if ptype == packagekit.ProgressType.PERCENTAGE:
            pkgname = trans.meta_data.get('sc_pkgname', '')
            prog = progress.get_property('percentage')
            if prog >= 0:
                self.emit("transaction-progress-changed", pkgname, prog)
            else:
                self.emit("transaction-progress-changed", pkgname, 0)

    def _on_lowlevel_transactions_changed(self, watcher, current, pending):
        # update self.pending_transactions
        self.pending_transactions.clear()

        for tid in [current] + pending:
            if not tid:
                continue
            trans = self._transactions_watcher.get_transaction(tid)
            trans_progress = TransactionProgress(trans)
            try:
                self.pending_transactions[
                    trans_progress.pkgname] = trans_progress
            except:
                self.pending_transactions[trans.tid] = trans_progress

        self.emit('transactions-changed', self.pending_transactions)

    def _on_install_ready(self, source, result, data=None):
        LOG.debug("install done %s %s", source, result)

    def _on_remove_ready(self, source, result, data=None):
        LOG.debug("remove done %s %s", source, result)

    def _fix_pkgnames(self, pkgnames):
        is_pk_id = lambda a: ';' in a
        res = []
        for p in pkgnames:
            if not is_pk_id(p):
                candidate = self.pkginfo[p].candidate
                p = candidate.package.get_id()
            res.append(p)
        return res

if __name__ == "__main__":
    package = 'firefox'

    loop = dbus.mainloop.glib.DBusGMainLoop()
    dbus.set_default_main_loop(loop)

    backend = PackagekitBackend()
    pkginfo = get_pkg_info()
    if pkginfo[package].is_installed:
        backend.remove(package, package, '')
        backend.install(package, package, '')
    else:
        backend.install(package, package, '')
        backend.remove(package, package, '')
    from gi.repository import Gtk
    Gtk.main()
    #print backend._fix_pkgnames(('cheese',))
