#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2011 Canonical
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

# py3 compat
try:
    import cPickle as pickle
    pickle  # pyflakes
except ImportError:
    import pickle

import logging
import os
import json

import softwarecenter.paths
from softwarecenter.paths import PistonHelpers

from gi.repository import GObject

LOG = logging.getLogger(__name__)


class SpawnHelper(GObject.GObject):

    __gsignals__ = {
        "data-available": (GObject.SIGNAL_RUN_LAST,
                           GObject.TYPE_NONE,
                           (GObject.TYPE_PYOBJECT,),
                           ),
        "exited": (GObject.SIGNAL_RUN_LAST,
                   GObject.TYPE_NONE,
                   (int,),
                   ),
        "error": (GObject.SIGNAL_RUN_LAST,
                  GObject.TYPE_NONE,
                  (str,),
                 ),
        }

    def __init__(self, format="pickle"):
        super(SpawnHelper, self).__init__()
        self._expect_format = format
        self._stdout = None
        self._stderr = None
        self._io_watch = None
        self._child_watch = None
        self._cmd = None
        self.needs_auth = False
        self.ignore_cache = False
        self.parent_xid = None

    def run_generic_piston_helper(self, klass, func, **kwargs):
        binary = os.path.join(
            softwarecenter.paths.datadir, PistonHelpers.GENERIC_HELPER)
        cmd = [binary]
        cmd += ["--datadir", softwarecenter.paths.datadir]
        if self.needs_auth:
            cmd.append("--needs-auth")
        if self.ignore_cache:
            cmd.append("--ignore-cache")
        if self.parent_xid:
            cmd.append("--parent-xid")
            cmd.append(str(self.parent_xid))
        cmd += [klass, func]
        if kwargs:
            cmd.append(json.dumps(kwargs))
        LOG.debug("run_generic_piston_helper()")
        self.run(cmd)

    def run(self, cmd):
        # only useful for debugging
        if "SOFTWARE_CENTER_DISABLE_SPAWN_HELPER" in os.environ:
            return
        self._cmd = cmd
        (pid, stdin, stdout, stderr) = GObject.spawn_async(
            cmd, flags=GObject.SPAWN_DO_NOT_REAP_CHILD,
            standard_output=True, standard_error=True)
        LOG.debug("running: '%s' as pid: '%s'" % (cmd, pid))
        self._child_watch = GObject.child_watch_add(
            pid, self._helper_finished, data=(stdout, stderr))
        self._io_watch = GObject.io_add_watch(
            stdout, GObject.IO_IN, self._helper_io_ready, (stdout, ))

    def _helper_finished(self, pid, status, (stdout, stderr)):
        LOG.debug("helper_finished: '%s' '%s'" % (pid, status))
        # get status code
        res = os.WEXITSTATUS(status)
        if res == 0:
            self.emit("exited", res)
        else:
            LOG.warn("exit code %s from helper for '%s'" % (res, self._cmd))
            # check stderr
            err = os.read(stderr, 4 * 1024)
            self._stderr = err
            if err:
                LOG.warn("got error from helper: '%s'" % err)
            self.emit("error", err)
            os.close(stderr)
        if self._io_watch:
            # remove with a delay timeout delay to ensure that any
            # pending data is still flused
            GObject.timeout_add(100, GObject.source_remove, self._io_watch)
        if self._child_watch:
            GObject.source_remove(self._child_watch)

    def _helper_io_ready(self, source, condition, (stdout,)):
        # read the raw data
        data = ""
        while True:
            s = os.read(stdout, 1024)
            if not s:
                break
            data += s
        os.close(stdout)
        self._stdout = data
        if self._expect_format == "pickle":
            # unpickle it, we should *always* get valid data here, so if
            # we don't this should raise a error
            try:
                data = pickle.loads(data)
            except:
                LOG.exception("can not load pickle data: '%s'" % data)
        elif self._expect_format == "json":
            try:
                data = json.loads(data)
            except:
                LOG.exception("can not load json: '%s'" % data)
        elif self._expect_format == "none":
            pass
        else:
            LOG.error("unknown format: '%s'", self._expect_format)
        LOG.debug("got data for cmd: '%s'='%s'" % (self._cmd, data))
        self.emit("data-available", data)
        return False
