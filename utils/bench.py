#!/usr/bin/python

import os
import sys
import xapian

sys.path.insert(0, "../")
from softwarecenter.enums import XAPIAN_VALUE_PKGNAME, XAPIAN_VALUE_APPNAME
from softwarecenter.paths import XAPIAN_BASE_PATH
from softwarecenter.utils import ExecutionTime


def run_benchmark(db):
    # test postlist
    with ExecutionTime('postlist("")'):
        for m in db.postlist(""):
            pass

    # test postlist + get_document
    with ExecutionTime('postlist+get_document'):
        for m in db.postlist(""):
            doc = db.get_document(m.docid)

    # test postlist + get_document
    with ExecutionTime('postlist+get_document+get_value'):
        for m in db.postlist(""):
            doc = db.get_document(m.docid)
            doc.get_value(XAPIAN_VALUE_PKGNAME)


def run_query(parser, search_term):
    search_query = parser.parse_query(search_term,
                                      xapian.QueryParser.FLAG_PARTIAL |
                                      xapian.QueryParser.FLAG_BOOLEAN)
    enquire = xapian.Enquire(db)
    enquire.set_query(search_query)
    with ExecutionTime("enquire"):
        mset = enquire.get_mset(0, db.get_doccount())
        print "len mset: ", len(mset)


if __name__ == "__main__":

    pathname = os.path.join(XAPIAN_BASE_PATH, "xapian")
    db = xapian.Database(pathname)

    print "app db only"
    run_benchmark(db)

    print "with apt-xapian-index"
    axi = xapian.Database("/var/lib/apt-xapian-index/index")
    db.add_database(axi)
    run_benchmark(db)

    print "simple query: a"
    parser = xapian.QueryParser()
    run_query(parser, "a")
    run_query(parser, "ab")
    run_query(parser, "abc")

    print "with db query: a"
    parser.set_database(db)
    parser.add_boolean_prefix("pkg", "AP")
    parser.set_default_op(xapian.Query.OP_AND)
    run_query(parser, "a")
    run_query(parser, "ab")
    run_query(parser, "abc")

    print "query for all !ATapplication"
    search_query = xapian.Query(xapian.Query.OP_AND_NOT,
                                xapian.Query(""),
                                xapian.Query("ATapplication"))
    enquire = xapian.Enquire(db)
    enquire.set_query(search_query)
    with ExecutionTime("enquire"):
        mset = enquire.get_mset(0, db.get_doccount())
        print "len mset: ", len(mset)

    print "look at all !ATapplication"
    search_query = xapian.Query(xapian.Query.OP_AND_NOT,
                                xapian.Query(""),
                                xapian.Query("ATapplication"))
    enquire = xapian.Enquire(db)
    enquire.set_query(search_query)
    with ExecutionTime("enquire"):
        mset = enquire.get_mset(0, db.get_doccount())
        print "len mset: ", len(mset)
        for m in mset:
            doc = m.document
            appname = doc.get_value(XAPIAN_VALUE_APPNAME)
            pkgname = doc.get_value(XAPIAN_VALUE_PKGNAME)
