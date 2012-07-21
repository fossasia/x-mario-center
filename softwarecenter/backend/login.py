#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2010 Canonical
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


class LoginBackend(GObject.GObject):

    NEW_ACCOUNT_URL = None
    FORGOT_PASSWORD_URL = None

    __gsignals__ = {
        "login-successful": (GObject.SIGNAL_RUN_LAST,
                             GObject.TYPE_NONE,
                             (GObject.TYPE_PYOBJECT,),
                            ),
        "login-failed": (GObject.SIGNAL_RUN_LAST,
                         GObject.TYPE_NONE,
                         (),
                        ),
        "login-canceled": (GObject.SIGNAL_RUN_LAST,
                           GObject.TYPE_NONE,
                           (),
                          ),
        "need-username-password": (GObject.SIGNAL_RUN_LAST,
                                   GObject.TYPE_NONE,
                                   (),
                                  ),
        }

    def login(self, username=None, password=None):
        raise NotImplemented

    def cancel_login(self):
        self.emit("login-canceled")
