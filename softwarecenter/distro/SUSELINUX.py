# Copyright (C) 2011 Canonical
#
# Authors:
#  Alex Eftimie
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
from gettext import gettext as _
from softwarecenter.distro import Distro


class SUSELINUX(Distro):
    # see __init__.py description
    DISTROSERIES = ["11.4",
                   ]

    # screenshot handling
    SCREENSHOT_THUMB_URL = ("http://screenshots.ubuntu.com/"
        "thumbnail-with-version/%(pkgname)s/%(version)s")
    SCREENSHOT_LARGE_URL = ("http://screenshots.ubuntu.com/"
        "screenshot-with-version/%(pkgname)s/%(version)s")
    SCREENSHOT_JSON_URL = "http://screenshots.ubuntu.com/json/package/%s"

    # reviews
    REVIEWS_SERVER = (os.environ.get("SOFTWARE_CENTER_REVIEWS_HOST") or
        "http://reviews.ubuntu.com/reviews/api/1.0")
    REVIEWS_URL = (REVIEWS_SERVER + "/reviews/filter/%(language)s/%(origin)s/"
        "%(distroseries)s/%(version)s/%(pkgname)s%(appname)s/")

    REVIEW_STATS_URL = REVIEWS_SERVER + "/review-stats"

    def get_app_name(self):
        return _("Software Center")

    def get_app_description(self):
        return _("Lets you choose from thousands of applications available.")

    def get_distro_channel_name(self):
        """ The name in the Release file """
        return "openSUSE"

    def get_distro_channel_description(self):
        """ The description of the main distro channel """
        return _("Provided by openSUSE")

    def get_removal_warning_text(self, cache, pkg, appname, depends):
        primary = _("To remove %s, these items must be removed "
                    "as well:") % appname
        button_text = _("Remove All")

        return (primary, button_text)

    def get_license_text(self, component):
        if component in ("main", "universe", "independent"):
            return _("Open source")
        elif component in ("restricted", "commercial"):
            return _("Proprietary")

    def is_supported(self, cache, doc, pkgname):
        # FIXME
        return False

    def get_supported_query(self):
        # FIXME
        import xapian
        query1 = xapian.Query("XOL" + "Ubuntu")
        query2a = xapian.Query("XOC" + "main")
        query2b = xapian.Query("XOC" + "restricted")
        query2 = xapian.Query(xapian.Query.OP_OR, query2a, query2b)
        return xapian.Query(xapian.Query.OP_AND, query1, query2)

    def get_maintenance_status(self, cache, appname, pkgname, component,
        channelname):
        # FIXME
        pass

    def get_downloadable_icon_url(self, full_archive_url, icon_filename):
        # FIXME
        pass
