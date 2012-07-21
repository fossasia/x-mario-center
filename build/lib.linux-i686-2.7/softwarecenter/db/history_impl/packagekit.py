# Copyright (C) 2011 Giovanni Campagna
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

from datetime import datetime
from gi.repository import PackageKitGlib

import logging

from softwarecenter.db.history import Transaction, PackageHistory

LOG = logging.getLogger(__name__)


class PackagekitTransaction(Transaction):
    def __init__(self, pktrans):
        self.start_date = datetime.strptime(pktrans.props.timespec,
                                            "%Y-%m-%dT%H:%M:%S.%fZ")

        self.install = []
        self.upgrade = []
        self.downgrade = []
        self.remove = []
        self.purge = []  # can't happen with a Packagekit backend (is mapped
                         # to remove)

        # parse transaction data
        lines = pktrans.props.data.split('\n')
        for line in lines:
            try:
                elements = line.split('\t')
                action = elements[0]
                package_id = elements[1]
                package_name = package_id.split(';')[0]
                # the rest of elements is the package description (garbage)

                # FIXME what action for downgrade
                if action == 'updating':
                    self.upgrade.append(package_name)
                elif action == 'installing':
                    self.install.append(package_name)
                elif action == 'removing':
                    self.remove.append(package_name)
                else:
                    # ignore other actions (include cleanup, downloading and
                    # untrusted)
                    continue
            except:
                LOG.warn("malformed line emitted by PackageKit, was %s" % line)


class PackagekitHistory(PackageHistory):
    """ Represents the history of the transactions """

    def __init__(self, use_cache=True):
        self._use_cache = use_cache
        self._cache = None
        self._update_callback = None

        self._client = PackageKitGlib.Client()
        self._client.get_old_transactions_async(0,
            None,  # cancellable
            lambda *args, **kwargs: None, None,  # progress callback
            self._transactions_received, None)

    @property
    def history_ready(self):
        """ The history is ready for consumption """
        return not self._cache is None

    @property
    def transactions(self):
        """ Return a ordered list of Transaction objects """
        return [] if self._cache is None else self._cache

    def set_on_update(self, update_callback):
        """ callback when a update is ready """
        self._update_callback = update_callback

    def get_installed_date(self, pkg_name):
        """Return the date that the given package name got instaled """
        pass

    def _transactions_received(self, client, async_result, user_data):
        try:
            pkresult = client.generic_finish(async_result)

            pktranslist = pkresult.get_transaction_array()
            self._cache = []
            for trans in pktranslist:
                self._cache.append(PackagekitTransaction(trans))

            if self._update_callback:
                self._update_callback()
        except:
            LOG.exception("error while reading Packagekit history")
