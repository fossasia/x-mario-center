# Copyright (C) 2010 Canonical
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
#
#
# taken from lp:~rnr-developers/rnr-server/rnrclient and put into
# rnrclient_pristine.py

import logging
import os
import sys

LOG = logging.getLogger(__name__)

# useful for debugging
if "SOFTWARE_CENTER_DEBUG_HTTP" in os.environ:
    import httplib2
    httplib2.debuglevel = 1

# get the server to use
from softwarecenter.distro import get_distro
distro = get_distro()
SERVER_ROOT = distro.REVIEWS_SERVER

try:
    if "SOFTWARE_CENTER_FAKE_REVIEW_API" in os.environ:
        from softwarecenter.backend.piston.rnrclient_fake import (
            RatingsAndReviewsAPI
        )
        RatingsAndReviewsAPI.default_service_root = SERVER_ROOT
        import rnrclient_fake
        rnrclient_fake
        LOG.warn("using FAKE review api, data returned will be dummy "
            "data only")
    else:
        # patch default_service_root
        from rnrclient_pristine import RatingsAndReviewsAPI
        RatingsAndReviewsAPI.default_service_root = SERVER_ROOT
        import rnrclient_pristine
        if "SOFTWARE_CENTER_FORCE_NON_SSL" in os.environ:
            LOG.warn("forcing transmission over NON ENCRYPTED CHANNEL")
            rnrclient_pristine.AUTHENTICATED_API_SCHEME = "http"
except ImportError:
    LOG.error("need python-piston-mini client\n"
              "available in natty or from:\n"
              "   ppa:software-store-developers/daily-build ")
    raise


if __name__ == "__main__":
    import urllib

    # force stdout to be utf-8
    import codecs
    sys.stdout = codecs.getwriter('utf8')(sys.stdout)

    # dump all reviews
    rnr = RatingsAndReviewsAPI()
    print(rnr.server_status())
    # dump all reviews
    for stat in rnr.review_stats():
        print("stats for (pkg='%s', app: '%s'):  avg=%s total=%s" % (
            stat.package_name, stat.app_name, stat.ratings_average,
                stat.ratings_total))
        reviews = rnr.get_reviews(
            language="any", origin="ubuntu", distroseries="natty",
            packagename=stat.package_name,
            appname=urllib.quote_plus(stat.app_name.encode("utf-8")))
        for review in reviews:
            print("rating: %s  user=%s" % (review.rating,
                review.reviewer_username))
            print(review.summary)
            print(review.review_text)
            print("\n")

    # get individual ones
    reviews = rnr.get_reviews(language="en", origin="ubuntu",
        distroseries="maverick", packagename="unace", appname="ACE")
    print(reviews)
    print(rnr.get_reviews(language="en", origin="ubuntu", distroseries="natty",
                          packagename="aclock.app"))
    print(rnr.get_reviews(language="en", origin="ubuntu", distroseries="natty",
                          packagename="unace", appname="ACE"))
