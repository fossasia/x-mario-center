#!/usr/bin/python

import os
import sys
import xapian

from optparse import OptionParser

sys.path.insert(0, "../")
from softwarecenter.paths import XAPIAN_BASE_PATH
from softwarecenter.utils import ExecutionTime

if __name__ == "__main__":

    parser = OptionParser()
    parser.add_option("-v", "--verbose", action="store_true",
                      default=False,
                      help="print found apps/pkgs too")
    (options, args) = parser.parse_args()

    pathname = os.path.join(XAPIAN_BASE_PATH, "xapian")
    db = xapian.Database(pathname)

    axi = xapian.Database("/var/lib/apt-xapian-index/index")
    db.add_database(axi)

    query_set = set()
    with ExecutionTime("allterms XP/AP"):
        for search_term in args:
            for m in db.allterms("XP"):
                term = m.term
                if search_term in term:
                    query_set.add(term)
            for m in db.allterms("AP"):
                term = m.term
                if search_term in term:
                    query_set.add(term)

    print "found terms: ", len(query_set)
    if options.verbose:
        print sorted(query_set)
