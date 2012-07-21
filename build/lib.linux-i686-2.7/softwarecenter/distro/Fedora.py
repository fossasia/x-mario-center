# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#  Julian Andres Klode
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

from softwarecenter.distro import Distro
from gettext import gettext as _


class Fedora(Distro):
    DISTROSERIES = [
        'Beefy Miracle',
        'Verne',
        'Lovelock',
        'Laughlin',
        'Leonidas',
        'Constantine',
    ]

    # disable paid software
    PURCHASE_APP_URL = None

    # screenshot handling
    # FIXME - fedora should get its own proxy eventually
    SCREENSHOT_THUMB_URL = ("http://screenshots.ubuntu.com/"
        "thumbnail-with-version/%(pkgname)s/%(version)s")
    SCREENSHOT_LARGE_URL = ("http://screenshots.ubuntu.com/"
        "screenshot-with-version/%(pkgname)s/%(version)s")
    SCREENSHOT_JSON_URL = "http://screenshots.ubuntu.com/json/package/%s"

    # reviews
    # FIXME: fedora will want to get their own review server instance at
    #        some point I imagine :) (or a alternative backend)
    #
    REVIEWS_SERVER = (os.environ.get("SOFTWARE_CENTER_REVIEWS_HOST") or
        "http://reviews.ubuntu.com/reviews/api/1.0")
    REVIEWS_URL = (REVIEWS_SERVER + "/reviews/filter/%(language)s/%(origin)s/"
        "%(distroseries)s/%(version)s/%(pkgname)s%(appname)s/")

    REVIEW_STATS_URL = REVIEWS_SERVER + "/review-stats"

    def get_distro_channel_name(self):
        """ The name of the primary repository """
        return "fedora"

    def get_distro_channel_description(self):
        """ The description of the main distro channel
            Overrides what's present in yum.conf for fedora, updates,
            updates-testing, their respective -source and -debuginfo
        """
        return _("Provided by Fedora")

    def get_app_name(self):
        return _("Fedora Software Center")

    def get_removal_warning_text(self, cache, pkg, appname, depends):
        primary = _("To remove %s, these items must be removed "
                    "as well:") % appname
        button_text = _("Remove All")

        return (primary, button_text)

    def get_license_text(self, component):
        # with a PackageKit backend, component is always 'main'
        # (but we have license in the individual packages)
        return _("Open source")

    def get_architecture(self):
        return os.uname()[4]

    def get_foreign_architectures(self):
        return []

    def is_supported(self, cache, doc, pkgname):
        origin = cache.get_origin(pkgname)
        return origin == 'fedora' or origin == 'updates'

    def get_maintenance_status(self, cache, appname, pkgname, component,
        channelname):
        # FIXME
        pass

    def get_supported_query(self):
        import xapian
        query1 = xapian.Query("XOO" + "fedora")
        query2 = xapian.Query("XOO" + "updates")
        return xapian.Query(xapian.Query.OP_OR, query1, query2)
