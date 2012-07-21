#!/usr/bin/python

import json
import subprocess
import sys

from softwarecenter.backend.piston.rnrclient import RatingsAndReviewsAPI

if __name__ == "__main__":

    rnrclient = RatingsAndReviewsAPI()
    piston_review_stats = rnrclient.review_stats(origin="ubuntu")

    # means            1  2  3  4  5 stars
    histogram_total = [0, 0, 0, 0, 0]
    for s in piston_review_stats:
        histogram = json.loads(s.histogram)
        for i in range(5):
            histogram_total[i] += histogram[i]
    print "overall distribution: ", histogram_total

    # write out data file
    f=open("reviews-spread.dat", "w")
    for i in range(5):
        f.write("%i %i\n" % (i+1, histogram_total[i]))
    f.close()

    # write out gnuplot
    f=open("reviews-spread.gnuplot", "w")
    f.write("""
set title "Reviews spread"
set xlabel "Stars"
set ylabel "Nr ratings"
set boxwidth 0.75
set term png size 800,600
set out 'review-spread.png'

plot "reviews-spread.dat" using 1:2 with boxes fs solid 0.2 title "Star distribution"
""")
    f.close()

    # run it
    res = subprocess.call(["gnuplot", "reviews-spread.gnuplot"])
    sys.exit(res)
