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

import locale
import logging
import os
import re
import string
import threading
import xapian
from softwarecenter.db.application import Application
from softwarecenter.db.utils import get_query_for_pkgnames
from softwarecenter.db.pkginfo import get_pkg_info
import softwarecenter.paths

from gi.repository import GObject, Gio

#from softwarecenter.utils import *
from softwarecenter.enums import (
    AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME,
    PkgStates,
    XapianValues
    )

from softwarecenter.paths import XAPIAN_BASE_PATH_SOFTWARE_CENTER_AGENT
from gettext import gettext as _

LOG = logging.getLogger(__name__)


def parse_axi_values_file(filename="/var/lib/apt-xapian-index/values"):
    """ parse the apt-xapian-index "values" file and provide the
    information in the self._axi_values dict
    """
    axi_values = {}
    if not os.path.exists(filename):
        return axi_values
    for raw_line in open(filename):
        line = string.split(raw_line, "#", 1)[0]
        if line.strip() == "":
            continue
        (key, value) = line.split()
        axi_values[key] = int(value)
    return axi_values


class SearchQuery(list):
    """ a list wrapper for a search query. it can take a search string
        or a list of search strings

        It provides __eq__ to easily compare two search query lists
    """
    def __init__(self, query_string_or_list):
        if query_string_or_list is None:
            pass
        # turn single querries into a single item list
        elif isinstance(query_string_or_list, xapian.Query):
            self.append(query_string_or_list)
        else:
            self.extend(query_string_or_list)

    def __eq__(self, other):
        # turn single querries into a single item list
        if  isinstance(other, xapian.Query):
            other = [other]
        q1 = [str(q) for q in self]
        q2 = [str(q) for q in other]
        return q1 == q2

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "[%s]" % ",".join([str(q) for q in self])


class LocaleSorter(xapian.KeyMaker):
    """ Sort in a locale friendly way by using locale.xtrxfrm """
    def __init__(self, db):
        super(LocaleSorter, self).__init__()
        self.db = db

    def __call__(self, doc):
        return locale.strxfrm(
            doc.get_value(self.db._axi_values["display_name"]))


class TopRatedSorter(xapian.KeyMaker):
    """ Sort using the top rated data """
    def __init__(self, db, review_loader):
        super(TopRatedSorter, self).__init__()
        self.db = db
        self.review_loader = review_loader

    def __call__(self, doc):
        app = Application(self.db.get_appname(doc),
                          self.db.get_pkgname(doc))
        stats = self.review_loader.get_review_stats(app)
        import xapian
        if stats:
            return xapian.sortable_serialise(stats.dampened_rating)
        return xapian.sortable_serialise(0)


class StoreDatabase(GObject.GObject):
    """thin abstraction for the xapian database with convenient functions"""

    # TRANSLATORS: List of "grey-listed" words sperated with ";"
    # Do not translate this list directly. Instead,
    # provide a list of words in your language that people are likely
    # to include in a search but that should normally be ignored in
    # the search.
    SEARCH_GREYLIST_STR = _("app;application;package;program;programme;"
                            "suite;tool")

    # signal emited
    __gsignals__ = {"reopen": (GObject.SIGNAL_RUN_FIRST,
                               GObject.TYPE_NONE,
                               ()),
                    "open": (GObject.SIGNAL_RUN_FIRST,
                             GObject.TYPE_NONE,
                             (GObject.TYPE_STRING,)),
                    }

    def __init__(self, pathname=None, cache=None):
        GObject.GObject.__init__(self)
        # initialize at creation time to avoid spurious AttributeError
        self._use_agent = False
        self._use_axi = False

        if pathname is None:
            pathname = softwarecenter.paths.XAPIAN_PATH
        self._db_pathname = pathname
        if cache is None:
            cache = get_pkg_info()
        self._aptcache = cache
        self._additional_databases = []
        # the xapian values as read from /var/lib/apt-xapian-index/values
        self._axi_values = {}
        # we open one db per thread, thread names are reused eventually
        # so no memory leak
        self._db_per_thread = {}
        self._parser_per_thread = {}
        self._axi_stamp_monitor = None

    @property
    def xapiandb(self):
        """ returns a per thread db """
        thread_name = threading.current_thread().name
        if not thread_name in self._db_per_thread:
            self._db_per_thread[thread_name] = self._get_new_xapiandb()
        return self._db_per_thread[thread_name]

    @property
    def xapian_parser(self):
        """ returns a per thread query parser """
        thread_name = threading.current_thread().name
        if not thread_name in self._parser_per_thread:
            xapian_parser = self._get_new_xapian_parser()
            self._parser_per_thread[thread_name] = xapian_parser
        return self._parser_per_thread[thread_name]

    def _get_new_xapiandb(self):
        xapiandb = xapian.Database(self._db_pathname)
        if self._use_axi:
            try:
                axi = xapian.Database(
                    softwarecenter.paths.APT_XAPIAN_INDEX_DB_PATH)
                xapiandb.add_database(axi)
            except:
                LOG.exception("failed to add apt-xapian-index")
        if (self._use_agent and
            os.path.exists(XAPIAN_BASE_PATH_SOFTWARE_CENTER_AGENT)):
            try:
                sca = xapian.Database(XAPIAN_BASE_PATH_SOFTWARE_CENTER_AGENT)
                xapiandb.add_database(sca)
            except Exception as e:
                logging.warn("failed to add sca db %s" % e)
        for db in self._additional_databases:
            xapiandb.add_database(db)
        return xapiandb

    def _get_new_xapian_parser(self):
        xapian_parser = xapian.QueryParser()
        xapian_parser.set_database(self.xapiandb)
        xapian_parser.add_boolean_prefix("pkg", "XP")
        xapian_parser.add_boolean_prefix("pkg", "AP")
        xapian_parser.add_boolean_prefix("mime", "AM")
        xapian_parser.add_boolean_prefix("section", "XS")
        xapian_parser.add_boolean_prefix("origin", "XOC")
        xapian_parser.add_prefix("pkg_wildcard", "XP")
        xapian_parser.add_prefix("pkg_wildcard", "AP")
        xapian_parser.set_default_op(xapian.Query.OP_AND)
        return xapian_parser

    def open(self, pathname=None, use_axi=True, use_agent=True):
        """ open the database """
        LOG.info("open() database: path=%s use_axi=%s "
                          "use_agent=%s" % (pathname, use_axi, use_agent))
        if pathname:
            self._db_pathname = pathname
        # clean existing DBs on open
        self._db_per_thread = {}
        self._parser_per_thread = {}
        # add the apt-xapian-database for here (we don't do this
        # for now as we do not have a good way to integrate non-apps
        # with the UI)
        self.nr_databases = 0
        self._use_axi = use_axi
        self._use_agent = use_agent
        if use_axi:
            if self._axi_stamp_monitor:
                self._axi_stamp_monitor.disconnect_by_func(
                    self._on_axi_stamp_changed)
            self._axi_values = parse_axi_values_file()
            self.nr_databases += 1
            # mvo: we could monitor changes in
            #       softwarecenter.paths.APT_XAPIAN_INDEX_DB_PATH here too
            #       as its a text file that points to the current DB
            #       *if* we do that, we need to change the event == ATTRIBUTE
            #       change in _on_axi_stamp_changed too
            self._axi_stamp = Gio.File.new_for_path(
                softwarecenter.paths.APT_XAPIAN_INDEX_UPDATE_STAMP_PATH)
            self._timeout_id = None
            self._axi_stamp_monitor = self._axi_stamp.monitor_file(0, None)
            self._axi_stamp_monitor.connect(
                "changed", self._on_axi_stamp_changed)
        if use_agent:
            self.nr_databases += 1
        # additional dbs
        for db in self._additional_databases:
            self.nr_databases += 1
        self.emit("open", self._db_pathname)

    def _on_axi_stamp_changed(self, monitor, afile, otherfile, event):
        # we only care about the utime() update from update-a-x-i
        if not event == Gio.FileMonitorEvent.ATTRIBUTE_CHANGED:
            return
        LOG.info("afile '%s' changed" % afile)
        if self._timeout_id:
            GObject.source_remove(self._timeout_id)
            self._timeout_id = None
        self._timeout_id = GObject.timeout_add(500, self.reopen)

    def add_database(self, database):
        self._additional_databases.append(database)
        self.xapiandb.add_database(database)
        self.reopen()

    def del_database(self, database):
        self._additional_databases.remove(database)
        self.reopen()

    def schema_version(self):
        """Return the version of the database layout

           This is useful to ensure we force a rebuild if its
           older than what we expect
        """
        return self.xapiandb.get_metadata("db-schema-version")

    def reopen(self):
        """ reopen the database """
        LOG.info("reopen() database")
        self.open(use_axi=self._use_axi, use_agent=self._use_agent)
        self.emit("reopen")

    @property
    def popcon_max(self):
        popcon_max = xapian.sortable_unserialise(self.xapiandb.get_metadata(
            "popcon_max_desktop"))
        assert popcon_max > 0
        return popcon_max

    def get_query_list_from_search_entry(self, search_term,
        category_query=None):
        """ get xapian.Query from a search term string and a limit the
            search to the given category
        """
        def _add_category_to_query(query):
            """ helper that adds the current category to the query"""
            if not category_query:
                return query
            return xapian.Query(xapian.Query.OP_AND,
                                category_query,
                                query)
        # empty query returns a query that matches nothing (for performance
        # reasons)
        if search_term == "" and category_query is None:
            return SearchQuery(xapian.Query())
        # we cheat and return a match-all query for single letter searches
        if len(search_term) < 2:
            return SearchQuery(_add_category_to_query(xapian.Query("")))

        # check if there is a ":" in the search, if so, it means the user
        # is using a xapian prefix like "pkg:" or "mime:" and in this case
        # we do not want to alter the search term (as application is in the
        # greylist but a common mime-type prefix)
        if not ":" in search_term:
            # filter query by greylist (to avoid overly generic search terms)
            orig_search_term = search_term
            for item in self.SEARCH_GREYLIST_STR.split(";"):
                (search_term, n) = re.subn('\\b%s\\b' % item, '', search_term)
                if n:
                    LOG.debug("greylist changed search term: '%s'" %
                        search_term)
        # restore query if it was just greylist words
        if search_term == '':
            LOG.debug("grey-list replaced all terms, restoring")
            search_term = orig_search_term
        # we have to strip the leading and trailing whitespaces to avoid having
        # different results for e.g. 'font ' and 'font' (LP: #506419)
        search_term = search_term.strip()
        # get a pkg query
        if "," in search_term:
            pkg_query = get_query_for_pkgnames(search_term.split(","))
        else:
            pkg_query = xapian.Query()
            for term in search_term.split():
                pkg_query = xapian.Query(xapian.Query.OP_OR,
                                         xapian.Query("XP" + term),
                                         pkg_query)
        pkg_query = _add_category_to_query(pkg_query)

        # get a search query
        if not ':' in search_term:  # ie, not a mimetype query
            # we need this to work around xapian oddness
            search_term = search_term.replace('-', '_')
        fuzzy_query = self.xapian_parser.parse_query(search_term,
                                           xapian.QueryParser.FLAG_PARTIAL |
                                           xapian.QueryParser.FLAG_BOOLEAN)
        # if the query size goes out of hand, omit the FLAG_PARTIAL
        # (LP: #634449)
        if fuzzy_query.get_length() > 1000:
            fuzzy_query = self.xapian_parser.parse_query(search_term,
                                            xapian.QueryParser.FLAG_BOOLEAN)
        # now add categories
        fuzzy_query = _add_category_to_query(fuzzy_query)
        return SearchQuery([pkg_query, fuzzy_query])

    def get_matches_from_query(self, query, start=0, end=-1, category=None):
        enquire = xapian.Enquire(self.xapiandb)
        if isinstance(query, str):
            if query == "":
                query = xapian.Query("")
            else:
                query = self.xapian_parser.parse_query(query)
        if category:
            query = xapian.Query(xapian.Query.OP_AND, category.query, query)
        enquire.set_query(query)
        if end == -1:
            end = len(self)
        return enquire.get_mset(start, end)

    def get_docs_from_query(self, query, start=0, end=-1, category=None):
        matches = self.get_matches_from_query(query, start, end, category)
        return [m.document for m in matches]

    def get_spelling_correction(self, search_term):
        # get a search query
        if not ':' in search_term:  # ie, not a mimetype query
            # we need this to work around xapian oddness
            search_term = search_term.replace('-', '_')
        self.xapian_parser.parse_query(
            search_term, xapian.QueryParser.FLAG_SPELLING_CORRECTION)
        return self.xapian_parser.get_corrected_query_string()

    def get_most_popular_applications_for_mimetype(self, mimetype,
        only_uninstalled=True, num=3):
        """ return a list of the most popular applications for the given
            mimetype
        """
        # sort by popularity by default
        enquire = xapian.Enquire(self.xapiandb)
        enquire.set_sort_by_value_then_relevance(XapianValues.POPCON)
        # query mimetype
        query = xapian.Query("AM%s" % mimetype)
        enquire.set_query(query)
        # mset just needs to be "big enough""
        matches = enquire.get_mset(0, 100)
        apps = []
        for match in matches:
            doc = match.document
            app = Application(self.get_appname(doc), self.get_pkgname(doc),
                              popcon=self.get_popcon(doc))
            if only_uninstalled:
                if app.get_details(self).pkg_state == PkgStates.UNINSTALLED:
                    apps.append(app)
            else:
                apps.append(app)
            if len(apps) == num:
                break
        return apps

    def get_summary(self, doc):
        """ get human readable summary of the given document """
        summary = doc.get_value(XapianValues.SUMMARY)
        channel = doc.get_value(XapianValues.ARCHIVE_CHANNEL)
        # if we do not have the summary in the xapian db, get it
        # from the apt cache
        if not summary and self._aptcache.ready:
            pkgname = self.get_pkgname(doc)
            if (pkgname in self._aptcache and
                self._aptcache[pkgname].candidate):
                return  self._aptcache[pkgname].candidate.summary
            elif channel:
                # FIXME: print something if available for our arch
                pass
        return summary

    def get_application(self, doc):
        """ Return a application from a xapian document """
        appname = self.get_appname(doc)
        pkgname = self.get_pkgname(doc)
        iconname = self.get_iconname(doc)
        return Application(appname, pkgname, iconname)

    def get_pkgname(self, doc):
        """ Return a packagename from a xapian document """
        pkgname = doc.get_value(XapianValues.PKGNAME)
        # if there is no value it means we use the apt-xapian-index
        # that stores the pkgname in the data field or as a value
        if not pkgname:
            # the doc says that get_value() is quicker than get_data()
            # so we use that if we have a updated DB, otherwise
            # fallback to the old way (the xapian DB may not yet be rebuild)
            if self._axi_values and "pkgname" in self._axi_values:
                pkgname = doc.get_value(self._axi_values["pkgname"])
            else:
                pkgname = doc.get_data()
        return pkgname

    def get_appname(self, doc):
        """ Return a appname from a xapian document, or None if
            a value for appname cannot be found in the document
         """
        return doc.get_value(XapianValues.APPNAME)

    def get_iconname(self, doc):
        """ Return the iconname from the xapian document """
        iconname = doc.get_value(XapianValues.ICON)
        return iconname

    def pkg_in_category(self, pkgname, cat_query):
        """ Return True if the given pkg is in the given category """
        pkg_query1 = xapian.Query("AP" + pkgname)
        pkg_query2 = xapian.Query("XP" + pkgname)
        pkg_query = xapian.Query(xapian.Query.OP_OR, pkg_query1, pkg_query2)
        pkg_and_cat_query = xapian.Query(xapian.Query.OP_AND, pkg_query,
            cat_query)
        enquire = xapian.Enquire(self.xapiandb)
        enquire.set_query(pkg_and_cat_query)
        matches = enquire.get_mset(0, len(self))
        if matches:
            return True
        return False

    def get_apps_for_pkgname(self, pkgname):
        """ Return set of docids with the matching applications for the
            given pkgname """
        result = set()
        for m in self.xapiandb.postlist("AP" + pkgname):
            result.add(m.docid)
        return result

    def get_icon_download_url(self, doc):
        """ Return the url of the icon or None """
        url = doc.get_value(XapianValues.ICON_URL)
        return url

    def get_popcon(self, doc):
        """ Return a popcon value from a xapian document """
        popcon_raw = doc.get_value(XapianValues.POPCON)
        if popcon_raw:
            popcon = xapian.sortable_unserialise(popcon_raw)
        else:
            popcon = 0
        return popcon

    def get_xapian_document(self, appname, pkgname):
        """Get the machting xapian document for appname, pkgname.

        If no document is found, raise a IndexError.

        """
        #LOG.debug("get_xapian_document app='%s' pkg='%s'" % (appname,
        #    pkgname))
        # first search for appname in the app-install-data namespace
        for m in self.xapiandb.postlist("AA" + appname):
            doc = self.xapiandb.get_document(m.docid)
            if doc.get_value(XapianValues.PKGNAME) == pkgname:
                return doc
        # then search for pkgname in the app-install-data namespace
        for m in self.xapiandb.postlist("AP" + pkgname):
            doc = self.xapiandb.get_document(m.docid)
            if doc.get_value(XapianValues.PKGNAME) == pkgname:
                return doc
        # then look for matching packages from a-x-i
        for m in self.xapiandb.postlist("XP" + pkgname):
            doc = self.xapiandb.get_document(m.docid)
            return doc
        # no matching document found
        raise IndexError("No app '%s' for '%s' in database" % (appname,
            pkgname))

    def is_pkgname_known(self, pkgname):
        """Check if 'pkgname' is known to this database.

        Note that even if this function returns True, it may mean that the
        package needs  to be purchased first or is available in a
        not-yet-enabled source.

        """
        # check cache first, then our own database
        return (pkgname in self._aptcache or
                any(self.xapiandb.postlist("AP" + pkgname)))

    def is_appname_duplicated(self, appname):
        """Check if the given appname is stored multiple times in the db.

        This can happen for generic names like "Terminal".

        """
        for (i, m) in enumerate(self.xapiandb.postlist("AA" + appname)):
            if i > 0:
                return True
        return False

    def get_installed_purchased_packages(self):
        """ return a set() of packagenames of purchased apps that are
            currently installed
        """
        for_purchase_query = xapian.Query(
            "AH" + AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME)
        enquire = xapian.Enquire(self.xapiandb)
        enquire.set_query(for_purchase_query)
        matches = enquire.get_mset(0, self.xapiandb.get_doccount())
        installed_purchased_packages = set()
        for m in matches:
            pkgname = self.get_pkgname(m.document)
            if (pkgname in self._aptcache and
                self._aptcache[pkgname].is_installed):
                installed_purchased_packages.add(pkgname)
        return installed_purchased_packages

    def get_origins_from_db(self):
        """ return all origins available in the current database """
        origins = set()
        for term in self.xapiandb.allterms("XOO"):
            if term.term[3:]:
                origins.add(term.term[3:])
        return list(origins)

    def get_exact_matches(self, pkgnames=[]):
        """Returns a list of fake MSetItems. If the pkgname is available, then
           MSetItem.document is pkgnames proper xapian document. If the pkgname
           is not available, then MSetItem is actually an Application.
        """
        matches = []
        for pkgname in pkgnames:
            app = Application('', pkgname.split('?')[0])
            if '?' in pkgname:
                app.request = pkgname.split('?')[1]
            match = app
            for m in  self.xapiandb.postlist("XP" + app.pkgname):
                match = self.xapiandb.get_document(m.docid)
            for m in self.xapiandb.postlist("AP" + app.pkgname):
                match = self.xapiandb.get_document(m.docid)
            matches.append(FakeMSetItem(match))
        return matches

    def __len__(self):
        """return the doc count of the database"""
        return self.xapiandb.get_doccount()

    def __iter__(self):
        """ support iterating over the documents """
        for it in self.xapiandb.postlist(""):
            doc = self.xapiandb.get_document(it.docid)
            yield doc


class FakeMSetItem():
    def __init__(self, doc):
        self.document = doc

if __name__ == "__main__":
    import apt
    import sys

    db = StoreDatabase("/var/cache/software-center/xapian", apt.Cache())
    db.open()

    if len(sys.argv) < 2:
        search = "apt,apport"
    else:
        search = sys.argv[1]
    query = db.get_query_list_from_search_entry(search)
    print(query)
    enquire = xapian.Enquire(db.xapiandb)
    enquire.set_query(query)
    matches = enquire.get_mset(0, len(db))
    for m in matches:
        doc = m.document
        print(doc.get_data())

    # test origin
    query = xapian.Query("XOL" + "Ubuntu")
    enquire = xapian.Enquire(db.xapiandb)
    enquire.set_query(query)
    matches = enquire.get_mset(0, len(db))
    print("Ubuntu origin: %s" % len(matches))
