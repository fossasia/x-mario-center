#!/usr/bin/python

import sys

sys.path.insert(0,"../")

from softwarecenter.backend.reviews import get_review_loader
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.utils import calc_dr

sys.path.insert(0, "../utils")


def show_top_rated_apps():
    # get the ratings
    cache = get_pkg_info()
    loader = get_review_loader(cache)
    review_stats = loader.REVIEW_STATS_CACHE
    # recalculate using different default power
    results = {}
    for i in [0.5, 0.4, 0.3, 0.2, 0.1, 0.05]:
        for (key, value) in review_stats.iteritems():
            value.dampened_rating = calc_dr(value.rating_spread, power=i)
        top_rated = loader.get_top_rated_apps(quantity=25)
        print "For power: %s" % i
        for (i, key) in enumerate(top_rated):
            item = review_stats[key]
            print "%(rang)2i: %(pkgname)-25s avg=%(avg)1.2f total=%(total)03i dampened=%(dampened)1.5f spread=%(spread)s" % { 
                'rang' : i+1,
                'pkgname' : item.app.pkgname,
                'avg' : item.ratings_average,
                'total' : item.ratings_total,
                'spread' : item.rating_spread,
                'dampened' : item.dampened_rating,
                }
        print 
        results[i] = top_rated[:]
        

if __name__ == "__main__":
    show_top_rated_apps()
