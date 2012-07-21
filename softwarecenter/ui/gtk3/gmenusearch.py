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

import os
import logging
from softwarecenter.enums import APP_INSTALL_PATH_DELIMITER

LOG = logging.getLogger(__name__)


class GMenuSearcher(object):

    def __init__(self):
        self._found = None

    def _search_gmenu_dir(self, dirlist, needle):
        if not dirlist[-1]:
            return
        from gi.repository import GMenu
        dir_iter = dirlist[-1].iter()
        current_type = dir_iter.next()
        while current_type is not GMenu.TreeItemType.INVALID:
            if current_type == GMenu.TreeItemType.DIRECTORY:
                self._search_gmenu_dir(
                    dirlist + [dir_iter.get_directory()], needle)
            elif current_type == GMenu.TreeItemType.ENTRY:
                item = dir_iter.get_entry()
                desktop_file_path = item.get_desktop_file_path()
                # direct match of the desktop file name and the installed
                # desktop file name
                if os.path.basename(desktop_file_path) == needle:
                    self._found = dirlist + [item]
                    return
                # if there is no direct match, take the part of the path after
                # "applications" (e.g. kde4/amarok.desktop) and
                # change "/" to "__" and do the match again - this is what
                # the data extractor is doing
                if "applications/" in desktop_file_path:
                    path_after_applications = desktop_file_path.split(
                        "applications/")[1]
                    if needle == path_after_applications.replace("/",
                        APP_INSTALL_PATH_DELIMITER):
                        self._found = dirlist + [item]
                        return
            current_type = dir_iter.next()

    def get_main_menu_path(self, desktop_file, menu_files_list=None):
        if not desktop_file:
            return
        from gi.repository import GMenu
        from gi.repository import GObject
        # use the system ones by default, but allow override for
        # easier testing
        if menu_files_list is None:
            menu_files_list = ["applications.menu", "settings.menu"]
        for n in menu_files_list:
            if n.startswith("/"):
                tree = GMenu.Tree.new_for_path(n, 0)
            else:
                tree = GMenu.Tree.new(n, 0)
            try:
                tree.load_sync()
            except GObject.GError as e:
                LOG.warning("could not load GMenu path: %s" % e)
                return

            root = tree.get_root_directory()
            self._search_gmenu_dir([root],
                                   os.path.basename(desktop_file))
            # retry search for app-install-data desktop files
            if not self._found and ":" in os.path.basename(desktop_file):
                # the desktop files in app-install-data have a layout
                # like "pkg:file.desktop" so we need to take that into
                # account when searching
                desktop_file = os.path.basename(desktop_file).split(":")[1]
                self._search_gmenu_dir([root], desktop_file)
            return self._found


# these are the old static bindinds that are no longer required
# (this is just kept here in case of problems with the dynamic
#  GIR and the old gtk2 gtk ui)
class GMenuSearcherGtk2(object):

    def __init__(self):
        self._found = None

    def _search_gmenu_dir(self, dirlist, needle):
        if not dirlist[-1]:
            return

        import gmenu
        for item in dirlist[-1].get_contents():
            mtype = item.get_type()
            if mtype == gmenu.TYPE_DIRECTORY:
                self._search_gmenu_dir(dirlist + [item], needle)
            elif item.get_type() == gmenu.TYPE_ENTRY:
                desktop_file_path = item.get_desktop_file_path()
                # direct match of the desktop file name and the installed
                # desktop file name
                if os.path.basename(desktop_file_path) == needle:
                    self._found = dirlist + [item]
                    return
                # if there is no direct match, take the part of the path after
                # "applications" (e.g. kde4/amarok.desktop) and
                # change "/" to "__" and do the match again - this is what
                # the data extractor is doing
                if "applications/" in desktop_file_path:
                    path_after_applications = desktop_file_path.split(
                        "applications/")[1]
                    if needle == path_after_applications.replace("/",
                        APP_INSTALL_PATH_DELIMITER):
                        self._found = dirlist + [item]
                        return

    def get_main_menu_path(self, desktop_file, menu_files_list=None):
        if not desktop_file:
            return
        import gmenu
        # use the system ones by default, but allow override for
        # easier testing
        if menu_files_list is None:
            menu_files_list = ["applications.menu", "settings.menu"]
        for n in menu_files_list:
            tree = gmenu.lookup_tree(n)
            self._search_gmenu_dir([tree.get_root_directory()],
                                   os.path.basename(desktop_file))
            if self._found:
                return self._found
