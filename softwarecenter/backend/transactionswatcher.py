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

from gi.repository import GObject


class BaseTransaction(GObject.GObject):
    """
    wrapper class for install backend dbus Transaction objects
    """
    __gsignals__ = {'progress-details-changed': (GObject.SIGNAL_RUN_FIRST,
                                            GObject.TYPE_NONE,
                                            (int, int, int, int, int, int)),
                    'progress-changed': (GObject.SIGNAL_RUN_FIRST,
                                         GObject.TYPE_NONE,
                                         (GObject.TYPE_PYOBJECT, )),
                    'status-changed': (GObject.SIGNAL_RUN_FIRST,
                                       GObject.TYPE_NONE,
                                       (GObject.TYPE_PYOBJECT, )),
                    'cancellable-changed': (GObject.SIGNAL_RUN_FIRST,
                                            GObject.TYPE_NONE,
                                            (GObject.TYPE_PYOBJECT, )),
                    'role-changed': (GObject.SIGNAL_RUN_FIRST,
                                     GObject.TYPE_NONE,
                                     (GObject.TYPE_PYOBJECT, )),
                    'deleted': (GObject.SIGNAL_RUN_FIRST,
                                GObject.TYPE_NONE,
                                []),
    }

    @property
    def tid(self):
        pass

    @property
    def status_details(self):
        pass

    @property
    def meta_data(self):
        return {}

    @property
    def cancellable(self):
        return False

    @property
    def progress(self):
        return False

    def get_role_description(self, role=None):
        pass

    def get_status_description(self, status=None):
        pass

    def is_waiting(self):
        return False

    def is_downloading(self):
        return False

    def cancel(self):
        pass


class BaseTransactionsWatcher(GObject.GObject):
    """
    base class for objects that need to watch the install backend
    for transaction changes.

    provides a "lowlevel-transactions-changed" signal
    """

    __gsignals__ = {'lowlevel-transactions-changed': (
                        GObject.SIGNAL_RUN_FIRST,
                        GObject.TYPE_NONE,
                        (str, GObject.TYPE_PYOBJECT)),
                    }

    def get_transaction(self, tid):
        """ should return a _Transaction object """
        pass


class TransactionFinishedResult(object):
    """ represents the result of a transaction """
    def __init__(self, trans, success):
        self.success = success
        if trans:
            self.pkgname = trans.meta_data.get("sc_pkgname")
            self.meta_data = trans.meta_data
        else:
            self.pkgname = None
            self.meta_data = None


class TransactionProgress(object):
    """ represents the progress of the transaction """
    def __init__(self, trans):
        self.pkgname = trans.meta_data.get("sc_pkgname")
        self.meta_data = trans.meta_data
        self.progress = trans.progress

# singleton
_tw = None


def get_transactions_watcher():
    global _tw
    if _tw is None:
        from softwarecenter.enums import USE_PACKAGEKIT_BACKEND
        if not USE_PACKAGEKIT_BACKEND:
            from softwarecenter.backend.installbackend_impl.aptd import (
                AptdaemonTransactionsWatcher)
            _tw = AptdaemonTransactionsWatcher()
        else:
            from softwarecenter.backend.installbackend_impl.packagekitd \
                import PackagekitTransactionsWatcher
            _tw = PackagekitTransactionsWatcher()
    return _tw
