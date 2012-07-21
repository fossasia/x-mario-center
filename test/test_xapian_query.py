#!/usr/bin/python

import sys
import xapian

from testutils import setup_test_env
setup_test_env()

from softwarecenter.enums import XapianValues
import softwarecenter.paths

# this is not a test as such, more a example of how xapian search
# work and useful features around them

if __name__ == "__main__":

    if len(sys.argv) > 1:
        search_term = sys.argv[1] 
    else:
        search_term = "app"

    db = xapian.Database(softwarecenter.paths.XAPIAN_PATH)

    parser = xapian.QueryParser()
    #parser.set_stemmer(xapian.Stem("english"))
    #parser.set_stemming_strategy(xapian.QueryParser.STEM_ALL)
    parser.set_database(db)
    #parser.add_prefix("pkg", "AP")
    query = parser.parse_query(search_term, 
                               xapian.QueryParser.FLAG_PARTIAL|
                               xapian.QueryParser.FLAG_WILDCARD)

    enquire = xapian.Enquire(db)
    enquire.set_sort_by_value_then_relevance(XapianValues.POPCON)
    enquire.set_query(query)
    matches = enquire.get_mset(0, db.get_doccount())
    print "Matches:"
    for m in matches:
        doc = m.document
        popcon = doc.get_value(XapianValues.POPCON)
        print doc.get_data(), "popcon:", xapian.sortable_unserialise(popcon)
        #for t in doc.termlist():
        #    print "'%s': %s (%s); " % (t.term, t.wdf, t.termfreq),
        #print "\n"
        appname = doc.get_data()
    
    # calculate a eset
    print "ESet:"
    rset = xapian.RSet()
    for m in matches:
        rset.add_document(m.docid)
    for m in enquire.get_eset(10, rset):
        print m.term


    # calulate the expansions
    completions = []
    for i, m in enumerate(db.allterms(search_term)):
        completions.append("AP"+m.term)
        completions.append(m.term)
        if i > 10:
            break
    expansion = xapian.Query(xapian.Query.OP_OR, completions)
    enquire.set_query(xapian.Query(xapian.Query.OP_OR, query, expansion))
    matches = enquire.get_mset(0, 10)
    print "\n\nExpanded Matches:"
    for m in matches:
        doc = m.document
        print doc.get_data()
        appname = doc.get_data()
    
    
    # popular
    print
    print "Popular: "
    query = xapian.Query(xapian.Query.OP_VALUE_GE,
                         XapianValues.POPCON, "100000")
    enquire.set_query(query)
    matches = enquire.get_mset(0, 10)
    for m in matches:
        doc = m.document
        print doc.get_data()
        appname = doc.get_data()
    
