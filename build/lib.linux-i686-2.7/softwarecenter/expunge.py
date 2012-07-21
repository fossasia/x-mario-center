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
import os
import time

from softwarecenter.utils import get_lock, release_lock


class ExpungeCache(object):
    """ Expunge a httplib2 cache dir based on either age of the cache
        file or status of the http data
    """

    def __init__(self, dirs, by_days, by_unsuccessful_http_states,
                 dry_run=False):
        self.dirs = dirs
        # days to keep data in the cache (0 == disabled)
        self.keep_time = 60 * 60 * 24 * by_days
        self.keep_only_http200 = by_unsuccessful_http_states
        self.dry_run = dry_run

    def _rm(self, f):
        if self.dry_run:
            print "Would delete: %s" % f
        else:
            logging.debug("Deleting: %s" % f)
            try:
                os.unlink(f)
            except OSError as e:
                logging.warn("When expunging the cache, could not unlink "
                             "file '%s' (%s)'" % (f, e))

    def _cleanup_dir(self, path):
        """ cleanup the given directory (and subdirectories) using the
            age or http state of the cache
        """
        now = time.time()
        for root, dirs, files in os.walk(path):
            for f in files:
                fullpath = os.path.join(root, f)
                header = open(fullpath).readline().strip()
                if not header.startswith("status:"):
                    logging.debug(
                        "Skipping files with unknown header: '%s'" % f)
                    continue
                if self.keep_only_http200 and header != "status: 200":
                    self._rm(fullpath)
                if self.keep_time:
                    mtime = os.path.getmtime(fullpath)
                    logging.debug("mtime of '%s': '%s" % (f, mtime))
                    if (mtime + self.keep_time) < now:
                        self._rm(fullpath)

    def clean(self):
        # go over the directories
        for d in self.dirs:
            lock = get_lock(os.path.join(d, "expunge.lock"))
            if lock > 0:
                self._cleanup_dir(d)
                release_lock(lock)
            else:
                logging.info("dir '%s' locked by another process" % d)
