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

#import gi
#gi.require_version("Gtk", "3.0")
import os
import logging

from gi.repository import Gtk

from softwarecenter.paths import ICON_PATH, SOFTWARE_CENTER_ICON_CACHE_DIR

LOG = logging.getLogger(__name__)


def get_parent(widget):
    while widget.get_parent():
        widget = widget.get_parent()
    return widget


def get_parent_xid(widget):
    window = get_parent(widget).get_window()
    #print dir(window)
    if hasattr(window, 'xid'):
        return window.xid
    return 0    # cannot figure out how to get the xid of gdkwindow under pygi


def point_in(rect, px, py):
    return (rect.x <= px <= rect.x + rect.width and
            rect.y <= py <= rect.y + rect.height)


def init_sc_css_provider(toplevel, settings, screen, datadir):
    context = toplevel.get_style_context()
    theme_name = settings.get_property("gtk-theme-name").lower()

    if hasattr(toplevel, '_css_provider'):
        # check old provider, see if we can skip setting or remove old
        # style provider
        if toplevel._css_provider._theme_name == theme_name:
            return
        else:  # clean up old css provider if exixts
            context.remove_provider_for_screen(screen, toplevel._css_provider)

    # munge css path for theme-name
    css_path = os.path.join(datadir,
                            "ui/gtk3/css/softwarecenter.%s.css" % \
                            theme_name)

    # if no css for theme-name try fallback css
    if not os.path.exists(css_path):
        css_path = os.path.join(datadir, "ui/gtk3/css/softwarecenter.css")

    if not os.path.exists(css_path):
        # check fallback exists as well... if not return None but warn
        # its not the end of the world if there is no fallback, just some
        # styling will be derived from the plain ol' Gtk theme
        msg = ("Could not set software-center CSS provider. File '%s' does "
            "not exist!")
        LOG.warn(msg % css_path)
        return

    # things seem ok, now set the css provider for softwarecenter
    msg = "Softwarecenter style provider for %s Gtk theme: %s"
    LOG.debug(msg % (theme_name, css_path))

    provider = Gtk.CssProvider()
    provider._theme_name = theme_name
    toplevel._css_provider = provider

    provider.load_from_path(css_path)
    context.add_provider_for_screen(screen, provider, 800)
    return css_path


def get_sc_icon_theme(datadir):
    # additional icons come from app-install-data
    icons = Gtk.IconTheme.get_default()
    icons.append_search_path(ICON_PATH)
    icons.append_search_path(os.path.join(datadir, "icons"))
    icons.append_search_path(os.path.join(datadir, "emblems"))

    # uninstalled run
    if os.path.exists('./data/app-stream/icons'):
        icons.append_search_path('./data/app-stream/icons')

    # add the humanity icon theme to the iconpath, as not all icon
    # themes contain all the icons we need
    # this *shouldn't* lead to any performance regressions
    path = '/usr/share/icons/Humanity'
    if os.path.exists(path):
        for subpath in os.listdir(path):
            subpath = os.path.join(path, subpath)
            if os.path.isdir(subpath):
                for subsubpath in os.listdir(subpath):
                    subsubpath = os.path.join(subpath, subsubpath)
                    if os.path.isdir(subsubpath):
                        icons.append_search_path(subsubpath)
    # add the gnome-packagekit icons
    path = '/usr/share/gnome-packagekit/icons'
    if os.path.exists(path):
        icons.append_search_path(path)

    # make the local cache directory if it doesn't already exist
    icon_cache_dir = SOFTWARE_CENTER_ICON_CACHE_DIR
    if not os.path.exists(icon_cache_dir):
        try:
            # possible race, see lp #962927
            os.makedirs(icon_cache_dir)
        except OSError:
            pass
    icons.append_search_path(icon_cache_dir)
    return icons
