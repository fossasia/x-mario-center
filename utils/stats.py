#!/usr/bin/python
# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
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


import os
import sys
import xapian

sys.path.insert(0, "../")
from softwarecenter.enums import XAPIAN_VALUE_PKGNAME
from softwarecenter.paths import XAPIAN_BASE_PATH

if __name__ == "__main__":

    # mapping from a package to the apps it has
    pkg_to_app = {}

    # mapping from applications names to packages (a generic name
    # like Terminal may be provided by multiple packages)
    app_to_pkg = {}

    # gather data
    pathname = os.path.join(XAPIAN_BASE_PATH, "xapian")
    db = xapian.Database(pathname)
    for m in db.postlist(""):
        doc = db.get_document(m.docid)
        appname = doc.get_data()
        pkgname = doc.get_value(XAPIAN_VALUE_PKGNAME)
        # add data
        if not pkgname in pkg_to_app:
            pkg_to_app[pkgname] = set()
        pkg_to_app[pkgname].add(appname)
        if not appname in app_to_pkg:
            app_to_pkg[appname] = set()
        app_to_pkg[appname].add(pkgname)

    # analyize
    print "Applications with the same name from multiple packages:"
    for app in app_to_pkg:
        if len(app_to_pkg[app]) > 1:
            print "app: %s (%s): %s" % (app, 
                                       len(app_to_pkg[app]), 
                                       sorted(app_to_pkg[app]))
    print
    
    print "Packages with multiple Applications:"
    for pkg in pkg_to_app:
        if len(pkg_to_app[pkg]) > 1:
            print "pkg: %s (%s):  %s" % (pkg, 
                                         len(pkg_to_app[pkg]), 
                                         sorted(pkg_to_app[pkg]))
