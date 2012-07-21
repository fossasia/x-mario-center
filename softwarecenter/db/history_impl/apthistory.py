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

from datetime import datetime

import apt_pkg
apt_pkg.init_config()

from gi.repository import GObject
from gi.repository import Gio

import glob
import gzip
import os.path
import logging
import string
import re

try:
    import cPickle as pickle
    pickle  # pyflakes
except ImportError:
    import pickle

LOG = logging.getLogger(__name__)

from softwarecenter.paths import SOFTWARE_CENTER_CACHE_DIR
from softwarecenter.utils import ExecutionTime
from softwarecenter.db.history import Transaction, PackageHistory


def ascii_lower(key):
    ascii_trans_table = string.maketrans(string.ascii_uppercase,
                                        string.ascii_lowercase)
    return key.translate(ascii_trans_table)


class AptTransaction(Transaction):
    PKGACTIONS = ["Install", "Upgrade", "Downgrade", "Remove", "Purge"]

    def __init__(self, sec):
        self.start_date = datetime.strptime(sec["Start-Date"],
                                            "%Y-%m-%d  %H:%M:%S")
        # set the object attributes "install", "upgrade", "downgrade",
        #                           "remove", "purge", error
        for k in self.PKGACTIONS + ["Error"]:
            # we use ascii_lower for issues described in LP: #581207
            attr = ascii_lower(k)
            if k in sec:
                value = map(self._fixup_history_item, sec[k].split("),"))
            else:
                value = []
            setattr(self, attr, value)

    @staticmethod
    def _fixup_history_item(s):
        """ strip history item string and add missing ")" if needed """
        s = s.strip()
        # remove the infomation about the architecture
        s = re.sub(":\w+", "", s)
        if "(" in s and not s.endswith(")"):
            s += ")"
        return s


class AptHistory(PackageHistory):

    def __init__(self, use_cache=True):
        LOG.debug("AptHistory.__init__()")
        self.main_context = GObject.main_context_default()
        self.history_file = apt_pkg.config.find_file("Dir::Log::History")
        #Copy monitoring of history file changes from historypane.py
        self.logfile = Gio.File.new_for_path(self.history_file)
        self.monitor = self.logfile.monitor_file(0, None)
        self.monitor.connect("changed", self._on_apt_history_changed)
        self.update_callback = None
        LOG.debug("init history")
        # this takes a long time, run it in the idle handler
        self._transactions = []
        self._history_ready = False
        GObject.idle_add(self._rescan, use_cache)

    @property
    def transactions(self):
        return self._transactions

    @property
    def history_ready(self):
        return self._history_ready

    def _mtime_cmp(self, a, b):
        return cmp(os.path.getmtime(a), os.path.getmtime(b))

    def _rescan(self, use_cache=True):
        self._history_ready = False
        self._transactions = []
        p = os.path.join(SOFTWARE_CENTER_CACHE_DIR, "apthistory.p")
        cachetime = 0
        if os.path.exists(p) and use_cache:
            with ExecutionTime("loading pickle cache"):
                try:
                    self._transactions = pickle.load(open(p))
                    cachetime = os.path.getmtime(p)
                except:
                    LOG.exception("failed to load cache")
        for history_gz_file in sorted(glob.glob(self.history_file + ".*.gz"),
                                      cmp=self._mtime_cmp):
            if os.path.getmtime(history_gz_file) < cachetime:
                LOG.debug("skipping already cached '%s'" % history_gz_file)
                continue
            self._scan(history_gz_file)
        self._scan(self.history_file)
        if use_cache:
            pickle.dump(self._transactions, open(p, "w"))
        self._history_ready = True

    def _scan(self, history_file, rescan=False):
        LOG.debug("_scan: '%s' (%s)" % (history_file, rescan))
        try:
            tagfile = apt_pkg.TagFile(open(history_file))
        except (IOError, SystemError) as ioe:
            LOG.debug(ioe)
            return
        for stanza in tagfile:
            # keep the UI alive
            while self.main_context.pending():
                self.main_context.iteration()
            # ignore records with
            try:
                trans = AptTransaction(stanza)
            except (KeyError, ValueError):
                continue
            # ignore the ones we have already
            if (rescan and
                len(self._transactions) > 0 and
                trans.start_date <= self._transactions[0].start_date):
                continue
            # add it
            # FIXME: this is a list, so potentially slow, but its sorted
            #        so we could (and should) do a binary search
            if not trans in self._transactions:
                self._transactions.insert(0, trans)

    def _on_apt_history_changed(self, monitor, afile, other_file, event):
        if event == Gio.FileMonitorEvent.CHANGES_DONE_HINT:
            self._scan(self.history_file, rescan=True)
            if self.update_callback:
                self.update_callback()

    def set_on_update(self, update_callback):
        self.update_callback = update_callback

    def get_installed_date(self, pkg_name):
        installed_date = None
        for trans in self._transactions:
            for pkg in trans.install:
                if pkg.split(" ")[0] == pkg_name:
                    installed_date = trans.start_date
                    return installed_date
        return installed_date

    def _find_in_terminal_log(self, date, term_file):
        found = False
        term_lines = []
        for line in term_file:
            if line.startswith("Log started: %s" % date):
                found = True
            elif line.endswith("Log ended") or line.startswith("Log started"):
                found = False
            if found:
                term_lines.append(line)
        return term_lines

    def find_terminal_log(self, date):
        """Find the terminal log part for the given transaction
           (this can be rather slow)
        """
        # FIXME: try to be more clever here with date/file timestamps
        term = apt_pkg.config.find_file("Dir::Log::Terminal")
        term_lines = self._find_in_terminal_log(date, open(term))
        # now search the older history
        if not term_lines:
            for f in glob.glob(term + ".*.gz"):
                term_lines = self._find_in_terminal_log(date, gzip.open(f))
                if term_lines:
                    return term_lines
        return term_lines
