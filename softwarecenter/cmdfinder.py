# Copyright (C) 2011 Canonical
#
# Authors:
#   Matthew McGowan
#   Michael Vogt
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

from __future__ import absolute_import

import os
import logging

LOG = logging.getLogger(__name__)


class CmdFinder(object):
    """ helper class that can find binaries in packages """

    # standard ubuntu PATH
    PATH = ["/usr/local/sbin",
            "/usr/local/bin",
            "/usr/sbin",
            "/usr/bin",
            "/sbin",
            "/bin",
            "/usr/games",
           ]

    def __init__(self, cache):
        self._cache = cache
        return

    def _is_exec(self, f):
        return (os.path.dirname(f) in self.PATH and
                os.path.exists(f) and
                not os.path.isdir(f) and
                os.access(f, os.X_OK))

    def _get_exec_candidates(self, pkg):
        return filter(self._is_exec, pkg.installed_files)

    def _find_alternatives_for_cmds(self, cmds):
        alternatives = set()
        root = "/etc/alternatives"
        for p in os.listdir(root):
            if os.path.realpath(os.path.join(root, p)) in cmds:
                alternatives.add(p)
        return alternatives

    def find_cmds_from_pkgname(self, pkgname):
        """ find the executables binaries for a given package """
        try:
            pkg = self._cache[pkgname]
        except KeyError:
            LOG.debug("can't find %s" % pkgname)
            return []
        if not pkg.is_installed:
            return []
        cmds = self._get_exec_candidates(pkg)
        cmds += self._find_alternatives_for_cmds(cmds)
        return sorted([os.path.basename(p) for p in cmds])
