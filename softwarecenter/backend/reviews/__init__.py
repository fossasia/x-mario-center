# -*- coding: utf-8 -*-

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

import datetime
import logging
import operator
import os
import random
import struct
import shutil
import subprocess
import time
import threading

from bsddb import db as bdb

from gi.repository import GObject

# py3 compat
try:
    import cPickle as pickle
    pickle  # pyflakes
except ImportError:
    import pickle

from softwarecenter.db.categories import get_query_for_category
from softwarecenter.db.database import Application, StoreDatabase
import softwarecenter.distro
from softwarecenter.i18n import get_languages
from softwarecenter.utils import (upstream_version_compare,
                                  uri_to_filename,
                                  get_person_from_config,
                                  wilson_score,
                                  )
from softwarecenter.paths import (SOFTWARE_CENTER_CACHE_DIR,
                                  XAPIAN_BASE_PATH,
                                  )
from softwarecenter.enums import ReviewSortMethods

from softwarecenter.backend.spawn_helper import SpawnHelper

LOG = logging.getLogger(__name__)


class ReviewStats(object):
    def __init__(self, app):
        self.app = app
        self.ratings_average = None
        self.ratings_total = 0
        self.rating_spread = [0, 0, 0, 0, 0]
        self.dampened_rating = 3.00
        self.histogram = None

    def __repr__(self):
        return ("<ReviewStats '%s' ratings_average='%s' ratings_total='%s'"
                " rating_spread='%s' dampened_rating='%s'>" %
                (self.app, self.ratings_average, self.ratings_total,
                self.rating_spread, self.dampened_rating))


class UsefulnessCache(object):

    USEFULNESS_CACHE = {}

    def __init__(self, try_server=False):
        fname = "usefulness.p"
        self.USEFULNESS_CACHE_FILE = os.path.join(SOFTWARE_CENTER_CACHE_DIR,
                                                  fname)

        self._retrieve_votes_from_cache()
        # Only try to get votes from the server if required, otherwise
        # just use cache
        if try_server:
            self._retrieve_votes_from_server()

    def _retrieve_votes_from_cache(self):
        if os.path.exists(self.USEFULNESS_CACHE_FILE):
            try:
                self.USEFULNESS_CACHE = pickle.load(
                    open(self.USEFULNESS_CACHE_FILE))
            except:
                LOG.exception("usefulness cache load fallback failure")
                os.rename(self.USEFULNESS_CACHE_FILE,
                    self.USEFULNESS_CACHE_FILE + ".fail")

    def _retrieve_votes_from_server(self):
        LOG.debug("_retrieve_votes_from_server started")
        user = get_person_from_config()

        if not user:
            LOG.warn("Could not get usefulness from server, no username "
                "in config file")
            return False

        # run the command and add watcher
        spawn_helper = SpawnHelper()
        spawn_helper.connect("data-available", self._on_usefulness_data)
        spawn_helper.run_generic_piston_helper(
            "RatingsAndReviewsAPI", "get_usefulness", username=user)

    def _on_usefulness_data(self, spawn_helper, results):
        '''called if usefulness retrieved from server'''
        LOG.debug("_usefulness_loaded started")
        self.USEFULNESS_CACHE.clear()
        for result in results:
            self.USEFULNESS_CACHE[str(result['review_id'])] = result['useful']
        if not self.save_usefulness_cache_file():
            LOG.warn("Read usefulness results from server but failed to "
                "write to cache")

    def save_usefulness_cache_file(self):
        """write the dict out to cache file"""
        cachedir = SOFTWARE_CENTER_CACHE_DIR
        try:
            if not os.path.exists(cachedir):
                os.makedirs(cachedir)
            pickle.dump(self.USEFULNESS_CACHE,
                      open(self.USEFULNESS_CACHE_FILE, "w"))
            return True
        except:
            return False

    def add_usefulness_vote(self, review_id, useful):
        """pass a review id and useful boolean vote and save it into the
           dict, then try to save to cache file
        """
        self.USEFULNESS_CACHE[str(review_id)] = useful
        if self.save_usefulness_cache_file():
            return True
        return False

    def check_for_usefulness(self, review_id):
        """pass a review id and get a True/False useful back or None if the
           review_id is not in the dict
        """
        return self.USEFULNESS_CACHE.get(str(review_id))


class Review(object):
    """A individual review object """
    def __init__(self, app):
        # a softwarecenter.db.database.Application object
        self.app = app
        self.app_name = app.appname
        self.package_name = app.pkgname
        # the review items that the object fills in
        self.id = None
        self.language = None
        self.summary = ""
        self.review_text = ""
        self.package_version = None
        self.date_created = None
        self.rating = None
        self.reviewer_username = None
        self.reviewer_displayname = None
        self.version = ""
        self.usefulness_total = 0
        self.usefulness_favorable = 0
        # this will be set if tryint to submit usefulness for this review
        # failed
        self.usefulness_submit_error = False
        self.delete_error = False
        self.modify_error = False

    def __repr__(self):
        return "[Review id=%s review_text='%s' reviewer_username='%s']" % (
            self.id, self.review_text, self.reviewer_username)

    def __cmp__(self, other):
        # first compare version, high version number first
        vc = upstream_version_compare(self.version, other.version)
        if vc != 0:
            return vc
        # then wilson score
        uc = cmp(wilson_score(self.usefulness_favorable,
                              self.usefulness_total),
                 wilson_score(other.usefulness_favorable,
                              other.usefulness_total))
        if uc != 0:
            return uc
        # last is date
        t1 = datetime.datetime.strptime(self.date_created, '%Y-%m-%d %H:%M:%S')
        t2 = datetime.datetime.strptime(other.date_created,
            '%Y-%m-%d %H:%M:%S')
        return cmp(t1, t2)

    @classmethod
    def from_piston_mini_client(cls, other):
        """ converts the rnrclieent reviews we get into
            "our" Review object (we need this as we have more
            attributes then the rnrclient review object)
        """
        app = Application("", other.package_name)
        review = cls(app)
        for (attr, value) in other.__dict__.items():
            if not attr.startswith("_"):
                setattr(review, attr, value)
        return review

    @classmethod
    def from_json(cls, other):
        """ convert json reviews into "out" review objects """
        app = Application("", other["package_name"])
        review = cls(app)
        for k, v in other.items():
            setattr(review, k, v)
        return review


class ReviewLoader(GObject.GObject):
    """A loader that returns a review object list"""

    __gsignals__ = {
        "refresh-review-stats-finished": (GObject.SIGNAL_RUN_LAST,
                                          GObject.TYPE_NONE,
                                          (GObject.TYPE_PYOBJECT,),
                                         ),
    }

    # cache the ReviewStats
    REVIEW_STATS_CACHE = {}
    _cache_version_old = False
    _review_sort_methods = ReviewSortMethods.REVIEW_SORT_METHODS

    def __init__(self, cache, db, distro=None):
        GObject.GObject.__init__(self)
        self.cache = cache
        self.db = db
        self.distro = distro
        if not self.distro:
            self.distro = softwarecenter.distro.get_distro()
        fname = "%s_%s" % (uri_to_filename(self.distro.REVIEWS_SERVER),
                           "review-stats-pkgnames.p")
        self.REVIEW_STATS_CACHE_FILE = os.path.join(SOFTWARE_CENTER_CACHE_DIR,
                                                    fname)
        self.REVIEW_STATS_BSDDB_FILE = "%s__%s.%s.db" % (
            self.REVIEW_STATS_CACHE_FILE,
            bdb.DB_VERSION_MAJOR,
            bdb.DB_VERSION_MINOR)

        self.language = get_languages()[0]
        if os.path.exists(self.REVIEW_STATS_CACHE_FILE):
            try:
                self.REVIEW_STATS_CACHE = pickle.load(
                    open(self.REVIEW_STATS_CACHE_FILE))
                self._cache_version_old = self._missing_histogram_in_cache()
            except:
                LOG.exception("review stats cache load failure")
                os.rename(self.REVIEW_STATS_CACHE_FILE,
                    self.REVIEW_STATS_CACHE_FILE + ".fail")

    def _missing_histogram_in_cache(self):
        '''iterate through review stats to see if it has been fully reloaded
           with new histogram data from server update'''
        for app in self.REVIEW_STATS_CACHE.values():
            result = getattr(app, 'rating_spread', False)
            if not result:
                return True
        return False

    def get_reviews(self, application, callback, page=1, language=None,
                    sort=0, relaxed=False):
        """run callback f(app, review_list)
           with list of review objects for the given
           db.database.Application object
        """
        return []

    def update_review_stats(self, translated_application, stats):
        application = Application("", translated_application.pkgname)
        self.REVIEW_STATS_CACHE[application] = stats

    def get_review_stats(self, translated_application):
        """return a ReviewStats (number of reviews, rating)
           for a given application. this *must* be super-fast
           as it is called a lot during tree view display
        """
        # check cache
        try:
            application = Application("", translated_application.pkgname)
            if application in self.REVIEW_STATS_CACHE:
                return self.REVIEW_STATS_CACHE[application]
        except ValueError:
            pass

    def refresh_review_stats(self, callback):
        """ get the review statists and call callback when its there """
        pass

    def save_review_stats_cache_file(self, nonblocking=True):
        """ save review stats cache file in xdg cache dir """
        cachedir = SOFTWARE_CENTER_CACHE_DIR
        if not os.path.exists(cachedir):
            os.makedirs(cachedir)
        # write out the stats
        if nonblocking:
            t = threading.Thread(target=self._save_review_stats_cache_blocking)
            t.run()
        else:
            self._save_review_stats_cache_blocking()

    def _save_review_stats_cache_blocking(self):
        # dump out for software-center in simple pickle
        self._dump_pickle_for_sc()
        # dump out in c-friendly dbm format for unity
        try:
            outfile = self.REVIEW_STATS_BSDDB_FILE
            outdir = self.REVIEW_STATS_BSDDB_FILE + ".dbenv/"
            self._dump_bsddbm_for_unity(outfile, outdir)
        except bdb.DBError as e:
            # see bug #858437, db corruption seems to be rather common
            # on ecryptfs
            LOG.warn("error creating bsddb: '%s' (corrupted?)" % e)
            try:
                shutil.rmtree(outdir)
                self._dump_bsddbm_for_unity(outfile, outdir)
            except:
                LOG.exception("trying to repair DB failed")

    def _dump_pickle_for_sc(self):
        """ write out the full REVIEWS_STATS_CACHE as a pickle """
        pickle.dump(self.REVIEW_STATS_CACHE,
                      open(self.REVIEW_STATS_CACHE_FILE, "w"))

    def _dump_bsddbm_for_unity(self, outfile, outdir):
        """ write out the subset that unity needs of the REVIEW_STATS_CACHE
            as a C friendly (using struct) bsddb
        """
        env = bdb.DBEnv()
        if not os.path.exists(outdir):
            os.makedirs(outdir)
        env.open(outdir,
                 bdb.DB_CREATE | bdb.DB_INIT_CDB | bdb.DB_INIT_MPOOL |
                 bdb.DB_NOMMAP,  # be gentle on e.g. nfs mounts
                 0600)
        db = bdb.DB(env)
        db.open(outfile,
                dbtype=bdb.DB_HASH,
                mode=0600,
                flags=bdb.DB_CREATE)
        for (app, stats) in self.REVIEW_STATS_CACHE.iteritems():
            # pkgname is ascii by policy, so its fine to use str() here
            db[str(app.pkgname)] = struct.pack('iii',
                                               stats.ratings_average or 0,
                                               stats.ratings_total,
                                               stats.dampened_rating)
        db.close()
        env.close()

    def get_top_rated_apps(self, quantity=12, category=None):
        """Returns a list of the packages with the highest 'rating' based on
           the dampened rating calculated from the ReviewStats rating spread.
           Also optionally takes a category (string) to filter by"""

        cache = self.REVIEW_STATS_CACHE

        if category:
            applist = self._get_apps_for_category(category)
            cache = self._filter_cache_with_applist(cache, applist)

        #create a list of tuples with (Application,dampened_rating)
        dr_list = []
        for item in cache.items():
            if hasattr(item[1], 'dampened_rating'):
                dr_list.append((item[0], item[1].dampened_rating))
            else:
                dr_list.append((item[0], 3.00))

        #sorted the list descending by dampened rating
        sorted_dr_list = sorted(dr_list, key=operator.itemgetter(1),
                                reverse=True)

        #return the quantity requested or as much as we can
        if quantity < len(sorted_dr_list):
            return_qty = quantity
        else:
            return_qty = len(sorted_dr_list)

        top_rated = []
        for i in range(0, return_qty):
            top_rated.append(sorted_dr_list[i][0])

        return top_rated

    def _filter_cache_with_applist(self, cache, applist):
        """Take the review cache and filter it to only include the apps that
           also appear in the applist passed in"""
        filtered_cache = {}
        for key in cache.keys():
            if key.pkgname in applist:
                filtered_cache[key] = cache[key]
        return filtered_cache

    def _get_apps_for_category(self, category):
        query = get_query_for_category(self.db, category)
        if not query:
            LOG.warn("_get_apps_for_category: received invalid category")
            return []

        pathname = os.path.join(XAPIAN_BASE_PATH, "xapian")
        db = StoreDatabase(pathname, self.cache)
        db.open()
        docs = db.get_docs_from_query(query)

        #from the db docs, return a list of pkgnames
        applist = []
        for doc in docs:
            applist.append(db.get_pkgname(doc))
        return applist

    def spawn_write_new_review_ui(self, translated_app, version, iconname,
                                  origin, parent_xid, datadir, callback):
        """Spawn the UI for writing a new review and adds it automatically
        to the reviews DB.
        """
        pass

    def spawn_report_abuse_ui(self, review_id, parent_xid, datadir, callback):
        """ this spawns the UI for reporting a review as inappropriate
            and adds the review-id to the internal hide list. once the
            operation is complete it will call callback with the updated
            review list
        """
        pass

    def spawn_submit_usefulness_ui(self, review_id, is_useful, parent_xid,
        datadir, callback):
        """Spawn a helper to submit a usefulness vote."""
        pass

    def spawn_delete_review_ui(self, review_id, parent_xid, datadir, callback):
        """Spawn a helper to delete a review."""
        pass

    def spawn_modify_review_ui(self, parent_xid, iconname, datadir, review_id,
        callback):
        """Spawn a helper to modify a review."""
        pass


class ReviewLoaderFake(ReviewLoader):

    USERS = ["Joe Doll", "John Foo", "Cat Lala", "Foo Grumpf", "Bar Tender",
        "Baz Lightyear"]
    SUMMARIES = ["Cool", "Medium", "Bad", "Too difficult"]
    IPSUM = "no ipsum\n\nstill no ipsum"

    def __init__(self, cache, db):
        ReviewLoader.__init__(self, cache, db)
        self._review_stats_cache = {}
        self._reviews_cache = {}

    def _random_person(self):
        return random.choice(self.USERS)

    def _random_text(self):
        return random.choice(self.LOREM.split("\n\n"))

    def _random_summary(self):
        return random.choice(self.SUMMARIES)

    def get_reviews(self, application, callback, page=1, language=None,
        sort=0, relaxed=False):
        if not application in self._review_stats_cache:
            self.get_review_stats(application)
        stats = self._review_stats_cache[application]
        if not application in self._reviews_cache:
            reviews = []
            for i in range(0, stats.ratings_total):
                review = Review(application)
                review.id = random.randint(1, 50000)
                # FIXME: instead of random, try to match the avg_rating
                review.rating = random.randint(1, 5)
                review.summary = self._random_summary()
                review.date_created = time.strftime("%Y-%m-%d %H:%M:%S")
                review.reviewer_username = self._random_person()
                review.review_text = self._random_text().replace("\n", "")
                review.usefulness_total = random.randint(1, 20)
                review.usefulness_favorable = random.randint(1, 20)
                reviews.append(review)
            self._reviews_cache[application] = reviews
        reviews = self._reviews_cache[application]
        callback(application, reviews)

    def get_review_stats(self, application):
        if not application in self._review_stats_cache:
            stat = ReviewStats(application)
            stat.ratings_average = random.randint(1, 5)
            stat.ratings_total = random.randint(1, 20)
            self._review_stats_cache[application] = stat
        return self._review_stats_cache[application]

    def refresh_review_stats(self, callback):
        review_stats = []
        callback(review_stats)


class ReviewLoaderFortune(ReviewLoaderFake):
    def __init__(self, cache, db):
        ReviewLoaderFake.__init__(self, cache, db)
        self.LOREM = ""
        for i in range(10):
            out = subprocess.Popen(["fortune"],
                stdout=subprocess.PIPE).communicate()[0]
            self.LOREM += "\n\n%s" % out


class ReviewLoaderTechspeak(ReviewLoaderFake):
    """ a test review loader that does not do any network io
        and returns random review texts
    """
    LOREM = u"""This package is using cloud based technology that will
make it suitable in a distributed environment where soup and xml-rpc
are used. The backend is written in C++ but the frontend code will
utilize dynamic languages lika LUA to provide a execution environment
based on JIT technology.

The software in this packages has a wonderful GUI, its based on OpenGL
but can alternative use DirectX (on plattforms were it is
available). Dynamic shading utilizes all GPU cores and out-of-order
thread scheduling is used to visualize the data optimally on multi
core systems.

The database support in tthis application is bleding edge. Not only
classical SQL techniques are supported but also object-relational
models and advanced ORM technology that will do auto-lookups based on
dynamic join/select optimizations to leverage sharded or multihosted
databases to their peak performance.

The Enterprise computer system is controlled by three primary main
processing cores cross linked with a redundant melacortz ramistat and
fourteen kiloquad interface modules. The core elements are based on
FTL nanoprocessor units arranged into twenty-five bilateral
kelilactirals with twenty of those units being slaved to the central
heisenfram terminal. . . . Now this is the isopalavial interface which
controls the main firomactal drive unit. . . .  The ramistat kiloquad
capacity is a function of the square root of the intermix ratio times
the sum of the plasma injector quotient.

The iApp is using the new touch UI that feels more natural then
tranditional window based offerings. It supports a Job button that
will yell at you when pressed and a iAmCool mode where the logo of
your new device blinks so that you attract maximum attention.

This app is a lifestyle choice.
It sets you apart from those who are content with bland UI designed
around 1990's paradigms.  This app represents you as a dynamic trend
setter with taste.  The carefully controlled user interface is
perfectly tailored to the needs of a new age individual, and extreme
care has been taken to ensure that all buttons are large enough for even the
most robust digits.

Designed with the web 2.0 and touch screen portable technologies in
mind this app is the ultimate in media experience.  With this
lifestyle application you extend your social media and search reach.
Exciting innovations in display and video reinvigorates the user
experience, offering beautifully rendered advertisements straight to
your finger tips. This has limitless possibilities and will permeate
every facet of your life.  Believe the hype."""


class ReviewLoaderIpsum(ReviewLoaderFake):
    """ a test review loader that does not do any network io
        and returns random lorem ipsum review texts
    """
    #This text is under public domain
    #Lorem ipsum
    #Cicero
    LOREM = u"""lorem ipsum "dolor" äöü sit amet consetetur sadipscing elitr
sed diam nonumy
eirmod tempor invidunt ut labore et dolore magna aliquyam erat sed diam
voluptua at vero eos et accusam et justo duo dolores et ea rebum stet clita
kasd gubergren no sea takimata sanctus est lorem ipsum dolor sit amet lorem
ipsum dolor sit amet consetetur sadipscing elitr sed diam nonumy eirmod
tempor invidunt ut labore et dolore magna aliquyam erat sed diam voluptua at
vero eos et accusam et justo duo dolores et ea rebum stet clita kasd
gubergren no sea takimata sanctus est lorem ipsum dolor sit amet lorem ipsum
dolor sit amet consetetur sadipscing elitr sed diam nonumy eirmod tempor
invidunt ut labore et dolore magna aliquyam erat sed diam voluptua at vero
eos et accusam et justo duo dolores et ea rebum stet clita kasd gubergren no
sea takimata sanctus est lorem ipsum dolor sit amet

duis autem vel eum iriure dolor in hendrerit in vulputate velit esse
molestie consequat vel illum dolore eu feugiat nulla facilisis at vero eros
et accumsan et iusto odio dignissim qui blandit praesent luptatum zzril
delenit augue duis dolore te feugait nulla facilisi lorem ipsum dolor sit
amet consectetuer adipiscing elit sed diam nonummy nibh euismod tincidunt ut
laoreet dolore magna aliquam erat volutpat

ut wisi enim ad minim veniam quis nostrud exerci tation ullamcorper suscipit
lobortis nisl ut aliquip ex ea commodo consequat duis autem vel eum iriure
dolor in hendrerit in vulputate velit esse molestie consequat vel illum
dolore eu feugiat nulla facilisis at vero eros et accumsan et iusto odio
dignissim qui blandit praesent luptatum zzril delenit augue duis dolore te
feugait nulla facilisi

nam liber tempor cum soluta nobis eleifend option congue nihil imperdiet
doming id quod mazim placerat facer possim assum lorem ipsum dolor sit amet
consectetuer adipiscing elit sed diam nonummy nibh euismod tincidunt ut
laoreet dolore magna aliquam erat volutpat ut wisi enim ad minim veniam quis
nostrud exerci tation ullamcorper suscipit lobortis nisl ut aliquip ex ea
commodo consequat

duis autem vel eum iriure dolor in hendrerit in vulputate velit esse
molestie consequat vel illum dolore eu feugiat nulla facilisis

at vero eos et accusam et justo duo dolores et ea rebum stet clita kasd
gubergren no sea takimata sanctus est lorem ipsum dolor sit amet lorem ipsum
dolor sit amet consetetur sadipscing elitr sed diam nonumy eirmod tempor
invidunt ut labore et dolore magna aliquyam erat sed diam voluptua at vero
eos et accusam et justo duo dolores et ea rebum stet clita kasd gubergren no
sea takimata sanctus est lorem ipsum dolor sit amet lorem ipsum dolor sit
amet consetetur sadipscing elitr at accusam aliquyam diam diam dolore
dolores duo eirmod eos erat et nonumy sed tempor et et invidunt justo labore
stet clita ea et gubergren kasd magna no rebum sanctus sea sed takimata ut
vero voluptua est lorem ipsum dolor sit amet lorem ipsum dolor sit amet
consetetur sadipscing elitr sed diam nonumy eirmod tempor invidunt ut labore
et dolore magna aliquyam erat

consetetur sadipscing elitr sed diam nonumy eirmod tempor invidunt ut labore
et dolore magna aliquyam erat sed diam voluptua at vero eos et accusam et
justo duo dolores et ea rebum stet clita kasd gubergren no sea takimata
sanctus est lorem ipsum dolor sit amet lorem ipsum dolor sit amet consetetur
sadipscing elitr sed diam nonumy eirmod tempor invidunt ut labore et dolore
magna aliquyam erat sed diam voluptua at vero eos et accusam et justo duo
dolores et ea rebum stet clita kasd gubergren no sea takimata sanctus est
lorem ipsum dolor sit amet lorem ipsum dolor sit amet consetetur sadipscing
elitr sed diam nonumy eirmod tempor invidunt ut labore et dolore magna
aliquyam erat sed diam voluptua at vero eos et accusam et justo duo dolores
et ea rebum stet clita kasd gubergren no sea takimata sanctus est lorem
ipsum dolor sit amet"""


class ReviewLoaderNull(ReviewLoader):

    """A dummy review loader which just returns empty results."""

    def __init__(self, cache, db):
        ReviewLoader.__init__(self, cache, db)
        self._review_stats_cache = {}
        self._reviews_cache = {}

    def get_reviews(self, application, callback, page=1, language=None,
        sort=0, relaxed=False):
        callback(application, [])

    def get_review_stats(self, application):
        pass

    def refresh_review_stats(self, callback):
        review_stats = []
        callback(review_stats)


review_loader = None


def get_review_loader(cache, db=None):
    """
    factory that returns a reviews loader singelton
    """
    global review_loader
    if not review_loader:
        if "SOFTWARE_CENTER_IPSUM_REVIEWS" in os.environ:
            review_loader = ReviewLoaderIpsum(cache, db)
        elif "SOFTWARE_CENTER_FORTUNE_REVIEWS" in os.environ:
            review_loader = ReviewLoaderFortune(cache, db)
        elif "SOFTWARE_CENTER_TECHSPEAK_REVIEWS" in os.environ:
            review_loader = ReviewLoaderTechspeak(cache, db)
        else:
            try:
                from softwarecenter.backend.reviews.rnr import (
                    ReviewLoaderSpawningRNRClient)
                # no service_root will raise ValueError
                review_loader = ReviewLoaderSpawningRNRClient(cache, db)
            except (ImportError, ValueError):
                review_loader = ReviewLoaderNull(cache, db)
    return review_loader

if __name__ == "__main__":
    def callback(app, reviews):
        print "app callback:"
        print app, reviews

    def stats_callback(stats):
        print "stats callback:"
        print stats

    # cache
    from softwarecenter.db.pkginfo import get_pkg_info
    cache = get_pkg_info()
    cache.open()

    db = StoreDatabase(XAPIAN_BASE_PATH + "/xapian", cache)
    db.open()

    # rnrclient loader
    app = Application("ACE", "unace")
    #app = Application("", "2vcard")

    from softwarecenter.backend.reviews.rnr import (
        ReviewLoaderSpawningRNRClient
    )
    loader = ReviewLoaderSpawningRNRClient(cache, db)
    print loader.refresh_review_stats(stats_callback)
    print loader.get_reviews(app, callback)

    print "\n\n"
    print "default loader, press ctrl-c for next loader"
    context = GObject.main_context_default()
    main = GObject.MainLoop(context)
    main.run()

    # default loader
    app = Application("", "2vcard")
    loader = get_review_loader(cache, db)
    loader.refresh_review_stats(stats_callback)
    loader.get_reviews(app, callback)
    main.run()
