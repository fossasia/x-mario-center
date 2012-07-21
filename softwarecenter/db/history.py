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

import logging

LOG = logging.getLogger(__name__)


class Transaction(object):
    """ Represents an pkg transaction

o    Attributes:
    - 'start_date': the start date/time of the transaction as datetime
    - 'install', 'upgrade', 'downgrade', 'remove', 'purge':
        contain the list of packagenames affected by this action
    """

    PKGACTIONS = ["Install", "Upgrade", "Downgrade", "Remove", "Purge"]

    def __init__(self):
        pass

    def __len__(self):
        count = 0
        for k in self.PKGACTIONS:
            count += len(getattr(self, k.lower()))
        return count

    def __repr__(self):
        return ('<Transaction: start_date:%s install:%s upgrade:%s '
            'downgrade:%s remove:%s purge:%s' % (self.start_date,
            self.install, self.upgrade, self.downgrade, self.remove,
            self.purge))

    def __cmp__(self, other):
        return cmp(self.start_date, other.start_date)


class PackageHistory(object):
    """ Represents the history of the transactions """

    def __init__(self, use_cache=True):
        pass

    # FIXME: this should also emit a signal
    @property
    def history_ready(self):
        """ The history is ready for consumption """
        return False

    @property
    def transactions(self):
        """ Return a ordered list of Transaction objects """
        return []

    # FIXME: this should be a gobect signal
    def set_on_update(self, update_callback):
        """ callback when a update is ready """
        pass

    def get_installed_date(self, pkg_name):
        """Return the date that the given package name got instaled """
        pass


# make it a singleton
pkg_history = None


def get_pkg_history():
    """ get the global PackageHistory() singleton object """
    global pkg_history
    if pkg_history is None:
        from softwarecenter.enums import USE_PACKAGEKIT_BACKEND
        if USE_PACKAGEKIT_BACKEND:
            from history_impl.packagekit import PackagekitHistory
            pkg_history = PackagekitHistory()
        else:
            from history_impl.apthistory import AptHistory
            pkg_history = AptHistory()
    return pkg_history
