#!/usr/bin/python

import apt
import os
import sys
import xapian

sys.path.insert(0, "../")
from softwarecenter.enums import XAPIAN_VALUE_PKGNAME, XAPIAN_VALUE_APPNAME, XAPIAN_VALUE_SUMMARY
from softwarecenter.paths import XAPIAN_BASE_PATH


if __name__ == "__main__":

    cache = apt.Cache()

    pathname = os.path.join(XAPIAN_BASE_PATH, "xapian")
    db = xapian.Database(pathname)

    installed = []
    for m in db.postlist(""):
        doc = db.get_document(m.docid)
        pkgname = doc.get_value(XAPIAN_VALUE_PKGNAME)
        appname = doc.get_value(XAPIAN_VALUE_APPNAME)
        summary = doc.get_value(XAPIAN_VALUE_SUMMARY)
        if pkgname in cache and cache[pkgname].is_installed:
            installed.append("%s: %s [%s]" % (appname, summary, pkgname))

    print "\n".join(sorted(installed, 
                           cmp=lambda x, y: cmp(x.split(":")[0].lower(),
                                                y.split(":")[0].lower())))
