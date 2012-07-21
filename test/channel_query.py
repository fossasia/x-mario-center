#!/usr/bin/python

import os
import sys
import xapian

if __name__ == "__main__":

    if len(sys.argv) > 1:
        channel_name = sys.argv[1]
    else:
        channel_name = "Ubuntu"

    xapian_base_path = "/var/cache/software-center"
    pathname = os.path.join(xapian_base_path, "xapian")
    db = xapian.Database(pathname)
    enquire = xapian.Enquire(db)

    query = xapian.Query("XOL"+channel_name)
    enquire.set_query(query)
    matches = enquire.get_mset(0, db.get_doccount())
    print "Matches: %s" % len(matches)
    apps = set()
    for m in matches:
        doc = m.document
        appname = doc.get_data()
        apps.add(appname)
        #for t in doc.termlist():
        #    print "'%s': %s (%s); " % (t.term, t.wdf, t.termfreq),
        #print "\n"
    print ";".join(sorted(apps))
    
    for i in db.postlist(""):
        doc = db.get_document(i.docid)
        for t in doc.termlist():
            if t.term.startswith("XOL"):
                print "doc: '%s', term: '%s'" % (doc.get_data(), t.term)

        
