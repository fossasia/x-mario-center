# -*- coding: utf-8 -*-
# Copyright (C) 2011 Canonical
#
# Authors:
#  Didier Roche
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


# singleton
oneconf_handler = None


def get_oneconf_handler(oneconfviewpickler=None):
    global oneconf_handler
    try:
        from softwarecenter.backend.oneconfhandler.core import OneConfHandler
    except ImportError:
        return None
    if oneconf_handler is None and oneconfviewpickler:
        oneconf_handler = OneConfHandler(oneconfviewpickler)
    return oneconf_handler


def is_oneconf_available():
    try:
        from softwarecenter.backend.oneconfhandler.core import OneConfHandler
        OneConfHandler  # pyflakes
        return True
    except ImportError:
        pass
    return False
