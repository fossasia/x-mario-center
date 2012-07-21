#!/usr/bin/python

import httplib2
import logging
import os
import pickle
import sys

from optparse import OptionParser

from softwarecenter.paths import SOFTWARE_CENTER_CACHE_DIR
from softwarecenter.backend.piston.rnrclient import RatingsAndReviewsAPI
from softwarecenter.distro import get_distro

from piston_mini_client import APIError

LOG = logging.getLogger(__name__)

def try_get_reviews(kwargs):
    """ this tries to fetcher reviews and apply some heuristics if none
        are found (like fallback to the previous distro series)
    """
    piston_reviews = rnrclient.get_reviews(**kwargs)

    # test if we don't have reviews for the current distroseries
    # and fallback to the previous oneif that is the case
    if (piston_reviews == [] and
        kwargs["distroseries"] == distro.DISTROSERIES[0]):
        kwargs["distroseries"] = distro.DISTROSERIES[1]
        piston_reviews = rnrclient.get_reviews(**kwargs)

    # the backend sometimes returns None so we fix this here
    if piston_reviews is None:
        piston_reviews = []
    return piston_reviews    

if __name__ == "__main__":
    logging.basicConfig()

    distro = get_distro()

    # common options for optparse go here
    parser = OptionParser()

    # check options
    parser.add_option("--language", default="any")
    parser.add_option("--origin", default="any")
    parser.add_option("--distroseries", default="any")
    parser.add_option("--pkgname")
    parser.add_option("--version", default="any")
    parser.add_option("--page", default="1")
    parser.add_option("", "--debug",
                      action="store_true", default=False)
    parser.add_option("--no-pickle",
                      action="store_true", default=False)
    parser.add_option("--sort", default="helpful")
    (options, args) = parser.parse_args()

    if options.debug:
        LOG.setLevel(logging.DEBUG)

    cachedir = os.path.join(SOFTWARE_CENTER_CACHE_DIR, "rnrclient")
    rnrclient = RatingsAndReviewsAPI(cachedir=cachedir)

    kwargs = {"language": options.language, 
              "origin": options.origin,
              "distroseries": options.distroseries,
              "packagename": options.pkgname.split(':')[0], #multiarch..
              "version": options.version,
              "page": int(options.page),
              "sort" : options.sort,
              }
    piston_reviews = []
    try:
        piston_reviews = try_get_reviews(kwargs)
    except ValueError as e:
        LOG.error("failed to parse '%s'" % e)
    #bug lp:709408 - don't print 404 errors as traceback when api request 
    #                returns 404 error
    except APIError as e:
        LOG.warn("_get_reviews_threaded: no reviews able to be retrieved for package: %s (%s, origin: %s)" % (options.pkgname, options.distroseries, options.origin))
        LOG.debug("_get_reviews_threaded: no reviews able to be retrieved: %s" % e)
    except httplib2.ServerNotFoundError:
        # switch to offline mode and try again
        rnrclient._offline_mode = True
        piston_reviews = try_get_reviews(kwargs)
    except:
        LOG.exception("get_reviews")
        sys.exit(1)

    # useful for debugging        
    if options.no_pickle:
        print "\n".join(["%s: %s" % (r.reviewer_username,
                                     r.summary)
                         for r in piston_reviews])
    else:
        # print to stdout where its consumed by the parent
        try:
            print pickle.dumps(piston_reviews)
        except IOError:
            # this can happen if the parent gets killed, no need to trigger
            # apport for this
            pass



