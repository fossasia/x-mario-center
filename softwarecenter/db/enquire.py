# Copyright (C) 2011 Canonical
#
# Authors:
#  Matthew McGowan
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

import logging
import time
import threading
import xapian

from gi.repository import GObject

from softwarecenter.enums import (SortMethods,
                                  XapianValues,
                                  NonAppVisibility,
                                  DEFAULT_SEARCH_LIMIT)
from softwarecenter.db.database import (
    SearchQuery, LocaleSorter, TopRatedSorter)
from softwarecenter.distro import get_distro
from softwarecenter.utils import ExecutionTime

LOG = logging.getLogger(__name__)


class AppEnquire(GObject.GObject):
    """
    A interface to enquire data from a xapian database.
    It can combined with any xapian querry and with
    a generic filter function (that can filter on data not
    available in xapian)
    """

    # signal emited
    __gsignals__ = {"query-complete": (GObject.SIGNAL_RUN_FIRST,
                                       GObject.TYPE_NONE,
                                       ()),
                    }

    def __init__(self, cache, db):
        """
        Init a AppEnquire object

        :Parameters:
        - `cache`: apt cache (for stuff like the overlay icon)
        - `db`: a xapian.Database that contians the applications
        """
        GObject.GObject.__init__(self)
        self.cache = cache
        self.db = db
        self.distro = get_distro()
        self.search_query = SearchQuery(None)
        self.nonblocking_load = True
        self.sortmode = SortMethods.UNSORTED
        self.nonapps_visible = NonAppVisibility.MAYBE_VISIBLE
        self.limit = DEFAULT_SEARCH_LIMIT
        self.filter = None
        self.exact = False
        self.nr_pkgs = 0
        self.nr_apps = 0
        self._matches = []
        self.match_docids = set()

    def __len__(self):
        return len(self._matches)

    @property
    def matches(self):
        """ return the list of matches as xapian.MSetItem """
        return self._matches

    def _threaded_perform_search(self):
        self._perform_search_complete = False
        # generate a name and ensure we never have two threads
        # with the same name
        names = [thread.name for thread in threading.enumerate()]
        for i in range(threading.active_count() + 1, 0, -1):
            thread_name = 'ThreadedQuery-%s' % i
            if not thread_name in names:
                break
        # create and start it
        t = threading.Thread(
            target=self._blocking_perform_search, name=thread_name)
        t.start()
        # don't block the UI while the thread is running
        context = GObject.main_context_default()
        while not self._perform_search_complete:
            time.sleep(0.02)  # 50 fps
            while context.pending():
                context.iteration()
        t.join()

        # call the query-complete callback
        self.emit("query-complete")

    def _get_estimate_nr_apps_and_nr_pkgs(self, enquire, q, xfilter):
        # filter out docs of pkgs of which there exists a doc of the app
        enquire.set_query(xapian.Query(xapian.Query.OP_AND,
                                       q, xapian.Query("ATapplication")))

        try:
            tmp_matches = enquire.get_mset(0, len(self.db), None, xfilter)
        except Exception:
            LOG.exception("_get_estimate_nr_apps_and_nr_pkgs failed")
            return (0, 0)

        nr_apps = tmp_matches.get_matches_estimated()
        enquire.set_query(xapian.Query(xapian.Query.OP_AND_NOT,
                                       q, xapian.Query("XD")))
        tmp_matches = enquire.get_mset(0, len(self.db), None, xfilter)
        nr_pkgs = tmp_matches.get_matches_estimated() - nr_apps
        return (nr_apps, nr_pkgs)

    def _blocking_perform_search(self):
        # WARNING this call may run in a thread, so its *not*
        #         allowed to touch gtk, otherwise hell breaks loose

        # performance only: this is only needed to avoid the
        # python __call__ overhead for each item if we can avoid it

        # use a unique instance of both enquire and xapian database
        # so concurrent queries dont result in an inconsistent database

        # an alternative would be to serialise queries
        enquire = xapian.Enquire(self.db.xapiandb)

        if self.filter and self.filter.required:
            xfilter = self.filter
        else:
            xfilter = None

        # go over the queries
        self.nr_apps, self.nr_pkgs = 0, 0
        _matches = self._matches
        match_docids = self.match_docids

        for q in self.search_query:
            LOG.debug("initial query: '%s'" % q)

            # for searches we may want to disable show/hide
            terms = [term for term in q]
            exact_pkgname_query = (len(terms) == 1 and
                                   terms[0].startswith("XP"))

            with ExecutionTime("calculate nr_apps and nr_pkgs: "):
                nr_apps, nr_pkgs = self._get_estimate_nr_apps_and_nr_pkgs(
                    enquire, q, xfilter)
                self.nr_apps += nr_apps
                self.nr_pkgs += nr_pkgs

            # only show apps by default (unless in always visible mode)
            if self.nonapps_visible != NonAppVisibility.ALWAYS_VISIBLE:
                if not exact_pkgname_query:
                    q = xapian.Query(xapian.Query.OP_AND,
                                     xapian.Query("ATapplication"),
                                     q)

            LOG.debug("nearly completely filtered query: '%s'" % q)

            # filter out docs of pkgs of which there exists a doc of the app
            # FIXME: make this configurable again?
            enquire.set_query(xapian.Query(xapian.Query.OP_AND_NOT,
                                           q, xapian.Query("XD")))

            # sort results

            # cataloged time - what's new category
            if self.sortmode == SortMethods.BY_CATALOGED_TIME:
                if (self.db._axi_values and
                    "catalogedtime" in self.db._axi_values):
                    enquire.set_sort_by_value(
                        self.db._axi_values["catalogedtime"], reverse=True)
                else:
                    LOG.warning("no catelogedtime in axi")
            elif self.sortmode == SortMethods.BY_TOP_RATED:
                from softwarecenter.backend.reviews import get_review_loader
                review_loader = get_review_loader(self.cache, self.db)
                sorter = TopRatedSorter(self.db, review_loader)
                enquire.set_sort_by_key(sorter, reverse=True)
            # search ranking - when searching
            elif self.sortmode == SortMethods.BY_SEARCH_RANKING:
                #enquire.set_sort_by_value(XapianValues.POPCON)
                # use the default enquire.set_sort_by_relevance()
                pass
            # display name - all categories / channels
            elif (self.db._axi_values and
                  "display_name" in self.db._axi_values):
                enquire.set_sort_by_key(LocaleSorter(self.db), reverse=False)
                # fallback to pkgname - if needed?
            # fallback to pkgname - if needed?
            else:
                enquire.set_sort_by_value_then_relevance(
                    XapianValues.PKGNAME, False)

            #~ try:
            if self.limit == 0:
                matches = enquire.get_mset(0, len(self.db), None, xfilter)
            else:
                matches = enquire.get_mset(0, self.limit, None, xfilter)
            LOG.debug("found ~%i matches" % matches.get_matches_estimated())
            #~ except:
                #~ logging.exception("get_mset")
                #~ matches = []

            # promote exact matches to a "app", this will make the
            # show/hide technical items work correctly
            if exact_pkgname_query and len(matches) == 1:
                self.nr_apps += 1
                self.nr_pkgs -= 2

            # add matches, but don't duplicate docids
            with ExecutionTime("append new matches to existing ones:"):
                for match in matches:
                    if not match.docid in match_docids:
                        _matches.append(match)
                        match_docids.add(match.docid)

        # if we have no results, try forcing pkgs to be displayed
        # if not NonAppVisibility.NEVER_VISIBLE is set
        if (not _matches and
            self.nonapps_visible not in (NonAppVisibility.ALWAYS_VISIBLE,
                                         NonAppVisibility.NEVER_VISIBLE)):
            self.nonapps_visible = NonAppVisibility.ALWAYS_VISIBLE
            self._blocking_perform_search()

        # wake up the UI if run in a search thread
        self._perform_search_complete = True

    def get_estimated_matches_count(self, query):
        with ExecutionTime("estimate item count for query: '%s'" % query):
            enquire = xapian.Enquire(self.db.xapiandb)
            enquire.set_query(query)
            # no performance difference between the two
            #tmp_matches = enquire.get_mset(0, 1, None, None)
            #nr_pkgs = tmp_matches.get_matches_estimated()
            tmp_matches = enquire.get_mset(0, len(self.db), None, None)
            nr_pkgs = len(tmp_matches)
        return nr_pkgs

    def set_query(self, search_query,
                  limit=DEFAULT_SEARCH_LIMIT,
                  sortmode=SortMethods.UNSORTED,
                  filter=None,
                  exact=False,
                  nonapps_visible=NonAppVisibility.MAYBE_VISIBLE,
                  nonblocking_load=True,
                  persistent_duplicate_filter=False):
        """
        Set a new query

        :Parameters:
        - `search_query`: a single search as a xapian.Query or a list
        - `limit`: how many items the search should return (0 == unlimited)
        - `sortmode`: sort the result
        - `filter`: filter functions that can be used to filter the
                    data further. A python function that gets a pkgname
        - `exact`: If true, indexes of queries without matches will be
                    maintained in the store (useful to show e.g. a row
                    with "??? not found")
        - `nonapps_visible`: decide whether adding non apps in the model or
                             not. Can be NonAppVisibility.ALWAYS_VISIBLE
                             /NonAppVisibility.MAYBE_VISIBLE
                             /NonAppVisibility.NEVER_VISIBLE
                             (NonAppVisibility.MAYBE_VISIBLE will return non
                              apps result if no matching apps is found)
        - `nonblocking_load`: set to False to execute the query inside the
                              current thread.  Defaults to True to allow the
                              search to be performed without blocking the UI.
        - 'persistent_duplicate_filter': if True allows filtering of duplicate
                                         matches across multiple queries
        """

        self.search_query = SearchQuery(search_query)
        self.limit = limit
        self.sortmode = sortmode
        # make a copy for good measure
        if filter:
            self.filter = filter.copy()
        else:
            self.filter = None
        self.exact = exact
        self.nonblocking_load = nonblocking_load
        self.nonapps_visible = nonapps_visible

        # no search query means "all"
        if not search_query:
            self.search_query = SearchQuery(xapian.Query(""))
            self.sortmode = SortMethods.BY_ALPHABET
            self.limit = 0

        # flush old query matches
        self._matches = []
        if not persistent_duplicate_filter:
            self.match_docids = set()

        # we support single and list search_queries,
        # if list we append them one by one
        with ExecutionTime("populate model from query: '%s' (threaded: %s)" % (
                " ; ".join([str(q) for q in self.search_query]),
                self.nonblocking_load), with_traceback=False):
            if self.nonblocking_load:
                self._threaded_perform_search()
            else:
                self._blocking_perform_search()
        return True

#    def get_pkgnames(self):
#        xdb = self.db.xapiandb
#        pkgnames = []
#        for m in self.matches:
#            doc = xdb.get_document(m.docid)
#            pkgnames.append(doc.get_value(XapianValues.PKGNAME) or
#                doc.get_data())
#        return pkgnames

#    def get_applications(self):
#        apps = []
#        for pkgname in self.get_pkgnames():
#            apps.append(Application(pkgname=pkgname))
#        return apps

    def get_docids(self):
        """ get the docids of the current matches """
        xdb = self.db.xapiandb
        return [xdb.get_document(m.docid).get_docid() for m in self._matches]

    def get_documents(self):
        """ get the xapian.Document objects of the current matches """
        xdb = self.db.xapiandb
        return [xdb.get_document(m.docid) for m in self._matches]
