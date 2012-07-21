# Copyright (C) 2011 Canonical
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

import xapian


def get_query_for_pkgnames(pkgnames):
    """ return a xapian query that matches exactly the list of pkgnames """
    query = xapian.Query()
    for pkgname in pkgnames:
        query = xapian.Query(xapian.Query.OP_OR,
                             query,
                             xapian.Query("XP" + pkgname))
        query = xapian.Query(xapian.Query.OP_OR,
                             query,
                             xapian.Query("AP" + pkgname))
    return query


def get_installed_apps_list(db):
    """ return a list of installed applications """
    apps = set()
    for doc in db:
        if db.get_appname(doc):
            pkgname = db.get_pkgname(doc)
            if (pkgname in db._aptcache and
                db._aptcache[pkgname].is_installed):
                apps.add(db.get_application(doc))
    return apps


def get_installed_package_list():
    """ return a set of all of the currently installed packages """
    from softwarecenter.db.pkginfo import get_pkg_info
    installed_pkgs = set()
    cache = get_pkg_info()
    for pkg in cache:
        if pkg.is_installed:
            installed_pkgs.add(pkg.name)
    return installed_pkgs
