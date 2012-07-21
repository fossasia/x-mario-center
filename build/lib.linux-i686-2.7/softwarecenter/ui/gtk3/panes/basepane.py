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


class BasePane(object):
    """ Base for all the View widgets that can be registered in a
        ViewManager
    """

    def __init__(self):
        # stuff that is queried by app.py
        self.apps_filter = None
        self.searchentry = None
        # flag to indicate that the pane's view has been fully initialized
        self.view_initialized = False

    def is_category_view_showing(self):
        return False

    def is_applist_view_showing(self):
        return False

    def is_app_details_view_showing(self):
        return False

    def get_current_app(self):
        pass

    def init_view(self):
        """
        A callback that is made at the time the pane is selected in the
        viewswitcher.  This method can be used to delay initialization
        and/or setup of a BasePane subclass' view until it is actually
        to be displayed (aka lazy-loading).  The primary purpose of this
        is to optimize startup time performance.
        """
        pass
