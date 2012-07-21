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

import datetime
import locale
import logging
import os
import re

from apt.utils import (get_release_filename_for_pkg,
                       get_release_date_from_release_file,
                       get_maintenance_end_date)
from gettext import gettext as _
from softwarecenter.distro.Debian import Debian
from softwarecenter.enums import BUY_SOMETHING_HOST
from softwarecenter.utils import utf8

LOG = logging.getLogger(__name__)


class Ubuntu(Debian):

    # see __init__.py description
    DISTROSERIES = ["precise",
                    "oneiric",
                    "natty",
                   ]

    # metapackages
    IMPORTANT_METAPACKAGES = ("ubuntu-desktop", "kubuntu-desktop")

    # screenshot handling
    SCREENSHOT_THUMB_URL = ("http://screenshots.ubuntu.com/"
        "thumbnail-with-version/%(pkgname)s/%(version)s")
    SCREENSHOT_LARGE_URL = ("http://screenshots.ubuntu.com/"
        "screenshot-with-version/%(pkgname)s/%(version)s")

    # the json description of the available screenshots
    SCREENSHOT_JSON_URL = "http://screenshots.ubuntu.com/json/package/%s"

    # purchase subscription
    PURCHASE_APP_URL = (BUY_SOMETHING_HOST + "/subscriptions/%s/ubuntu/%s/"
        "+new/?%s")

    # reviews
    REVIEWS_SERVER = (os.environ.get("SOFTWARE_CENTER_REVIEWS_HOST") or
        "http://reviews.ubuntu.com/reviews/api/1.0")
    REVIEWS_URL = (REVIEWS_SERVER + "/reviews/filter/%(language)s/%(origin)s/"
        "%(distroseries)s/%(version)s/%(pkgname)s%(appname)s/")

    #REVIEW_STATS_URL = (REVIEWS_SERVER + "/reviews/api/1.0/%(language)s/"
    #    "%(origin)s/%(distroseries)s/review-stats/")
    # FIXME: does that make sense?!?
    REVIEW_STATS_URL = REVIEWS_SERVER + "/review-stats"

    # Starting point for Ubuntu app developers
    DEVELOPER_URL = "http://developer.ubuntu.com/"

    def get_app_name(self):
        return _("X-Mario App Store")

    def get_app_description(self):
        return _("Lets you choose from thousands of applications available "
            "for Ubuntu.")

    def get_distro_channel_name(self):
        """ The name in the Release file """
        return "Ubuntu"

    def get_distro_channel_description(self):
        """ The description of the main distro channel """
        return _("Provided by Ubuntu")

    def get_removal_warning_text(self, cache, pkg, appname, depends):
        primary = _("To remove %s, these items must be removed "
                    "as well:") % utf8(appname)
        button_text = _("Remove All")

        # alter it if a meta-package is affected
        for m in depends:
            if cache[m].section == "metapackages":
                primary = _("If you uninstall %s, future updates will not "
                              "include new items in <b>%s</b> set. "
                              "Are you sure you want to continue?") % (appname,
                              cache[m].installed.summary)
                button_text = _("Remove Anyway")
                depends = []
                break

        # alter it if an important meta-package is affected
        for m in self.IMPORTANT_METAPACKAGES:
            if m in depends:
                primary = _("%s is a core application in Ubuntu. "
                              "Uninstalling it may cause future upgrades "
                              "to be incomplete. Are you sure you want to "
                              "continue?") % appname
                button_text = _("Remove Anyway")
                depends = None
                break
        return (primary, button_text)

    def get_license_text(self, component):
        if component in ("main", "universe", "independent"):
            return _("Open source")
        elif component == "restricted":
            return _("Proprietary")
        else:
            # commercial apps provide license info via the
            # software-center-agent, but if a given commercial app does not
            # provide this for some reason, default to a license type of
            # "Unknown"
            return _("Unknown")

    def is_supported(self, cache, doc, pkgname):
        # the doc does not by definition contain correct data regarding the
        # section. Looking up in the cache seems just as fast/slow.
        if pkgname in cache and cache[pkgname].candidate:
            for origin in cache[pkgname].candidate.origins:
                if (origin.origin == "Ubuntu" and
                    origin.trusted and
                    (origin.component == "main" or
                     origin.component == "restricted")):
                    return True
        return False

    def get_supported_query(self):
        import xapian
        query1 = xapian.Query("XOL" + "Ubuntu")
        query2a = xapian.Query("XOC" + "main")
        query2b = xapian.Query("XOC" + "restricted")
        query2 = xapian.Query(xapian.Query.OP_OR, query2a, query2b)
        return xapian.Query(xapian.Query.OP_AND, query1, query2)

    def get_supported_filter_name(self):
        return _("Canonical-Maintained Software")

    def get_maintenance_status(self, cache, appname, pkgname, component,
        channelname):
        # try to figure out the support dates of the release and make
        # sure to look only for stuff in "Ubuntu" and "distro_codename"
        # (to exclude stuff in ubuntu-updates for the support time
        # calculation because the "Release" file time for that gets
        # updated regularly)
        if not hasattr(cache, '_cache') or not pkgname:
            return
        releasef = get_release_filename_for_pkg(cache._cache, pkgname,
                                                "Ubuntu",
                                                self.get_codename())
        time_t = get_release_date_from_release_file(releasef)
        # check the release date and show support information
        # based on this
        if time_t:
            release_date = datetime.datetime.fromtimestamp(time_t)
            #print "release_date: ", release_date
            now = datetime.datetime.now()
            #release_age = (now - release_date).days
            #print "release age: ", release_age

            # init with the default time
            support_month = 18

            # see if we have a "Supported" entry in the pkg record
            if (pkgname in cache and
                cache[pkgname].candidate):
                support_time = cache._cache[pkgname].candidate.record.get(
                    "Supported")
                if support_time:
                    if support_time.endswith("y"):
                        support_month = 12 * int(support_time.strip("y"))
                    elif support_time.endswith("m"):
                        support_month = int(support_time.strip("m"))
                    else:
                        LOG.warning("unsupported 'Supported' string '%s'" %
                            support_time)

            # mvo: we do not define the end date very precisely
            #      currently this is why it will just display a end
            #      range
            # print release_date, support_month
            (support_end_year, support_end_month) = get_maintenance_end_date(
                release_date, support_month)
            support_end_month_str = locale.nl_langinfo(
                getattr(locale, "MON_%d" % support_end_month))
             # check if the support has ended
            support_ended = (now.year >= support_end_year and
                             now.month > support_end_month)
            if component == "main":
                if support_ended:
                    return _("Canonical does no longer provide "
                             "updates for %s in Ubuntu %s. "
                             "Updates may be available in a newer version of "
                             "Ubuntu.") % (appname, self.get_distro_release())
                else:
                    return _("Canonical provides critical updates for "
                             "%(appname)s until %(support_end_month_str)s "
                             "%(support_end_year)s.") % {
                                'appname': appname,
                                'support_end_month_str': support_end_month_str,
                                'support_end_year': support_end_year}
            elif component == "restricted":
                if support_ended:
                    return _("Canonical does no longer provide "
                             "updates for %s in Ubuntu %s. "
                             "Updates may be available in a newer version of "
                             "Ubuntu.") % (appname, self.get_distro_release())
                else:
                    return _("Canonical provides critical updates supplied "
                             "by the developers of %(appname)s until "
                             "%(support_end_month_str)s "
                             "%(support_end_year)s.") % {
                                'appname': appname,
                                'support_end_month_str': support_end_month_str,
                                'support_end_year': support_end_year,
                            }

        # if we couldn't determine a support date, use a generic maintenance
        # string without the date
        if (channelname or
            component in ("partner", "independent", "commercial")):
            return _("Provided by the vendor.")
        elif component == "main":
            return _("Canonical provides critical updates for %s.") % appname
        elif component == "restricted":
            return _("Canonical provides critical updates supplied by the "
                     "developers of %s.") % appname
        elif component == "universe" or component == "multiverse":
            return _("Canonical does not provide updates for %s. "
                     "Some updates may be provided by the "
                     "Ubuntu community.") % appname
        #return (_("Application %s has an unknown maintenance status.") %
        #    appname)

    def get_downloadable_icon_url(self, full_archive_url, icon_filename):
        """
        generates the url for a downloadable icon based on the download
        uri and the icon filename itself
        """
        split_at_pool = full_archive_url.split("pool")[0]
        # support ppas and extras.ubuntu.com
        if split_at_pool.endswith("/ppa/ubuntu/"):
            # it's a ppa, generate the icon_url for a ppa
            split_at_ppa = split_at_pool.split("/ppa/")[0]
            downloadable_icon_url = []
            downloadable_icon_url.append(split_at_ppa)
            downloadable_icon_url.append("/meta/ppa/")
            downloadable_icon_url.append(icon_filename)
            return "".join(downloadable_icon_url)
        elif re.match("http://(.*)extras.ubuntu.com/", split_at_pool):
            # it's from extras.ubuntu.com, generate the icon_url for a ppa
            split_at_ubuntu = split_at_pool.split("/ubuntu/")[0]
            downloadable_icon_url = []
            downloadable_icon_url.append(split_at_ubuntu)
            downloadable_icon_url.append("/meta/")
            downloadable_icon_url.append(icon_filename)
            return "".join(downloadable_icon_url)
        else:
            #raise ValueError("we currently support downloadable icons in "
            #    "ppa's only")
            LOG.warning("downloadable icon is not supported for archive: '%s'"
                % full_archive_url)
            return ''

if __name__ == "__main__":
    import apt
    cache = apt.Cache()
    print cache.get_maintenance_status(cache, "synaptic app", "synaptic",
        "main", None)
    print cache.get_maintenance_status(cache, "3dchess app", "3dchess",
        "universe", None)
