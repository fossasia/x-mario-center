#!/usr/bin/python

import os
import sys
import xapian

from optparse import OptionParser

sys.path.insert(0, "../")
from softwarecenter.paths import XAPIAN_BASE_PATH
from softwarecenter.utils import ExecutionTime

def run_query(parser, search_terms, verbose):
    for search_term in search_terms:
        search_query = parser.parse_query(search_term, 
                                          xapian.QueryParser.FLAG_WILDCARD|
                                          xapian.QueryParser.FLAG_PARTIAL)
        print search_query
        enquire = xapian.Enquire(db)
        enquire.set_query(search_query)
        with ExecutionTime("enquire"):
            mset = enquire.get_mset(0, db.get_doccount())
            for m in mset:
                doc = m.document
                print doc, doc.get_data()
                if verbose:
                    for t in doc.termlist():
                        print "'%s': %s (%s); " % (t.term, t.wdf, t.termfreq),
                    print "\n"
 

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

    parser = xapian.QueryParser()
    parser.set_database(db)
    parser.add_boolean_prefix("pkg","XP")
    parser.add_boolean_prefix("pkg","AP")
    parser.add_prefix("pkg_wildcard","XP")
    parser.add_prefix("pkg_wildcard","AP")

    run_query(parser, args, options.verbose)

