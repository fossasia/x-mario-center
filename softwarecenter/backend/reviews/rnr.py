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

import logging
import json
import os
import time

from softwarecenter.backend.spawn_helper import SpawnHelper
from softwarecenter.backend.reviews import (
                                            ReviewLoader,
                                            Review,
                                            ReviewStats,
                                            UsefulnessCache,
                                            )
from softwarecenter.backend.piston.rnrclient import RatingsAndReviewsAPI
from softwarecenter.backend.piston.rnrclient_pristine import ReviewDetails
from softwarecenter.db.database import Application
import softwarecenter.distro
from softwarecenter.netstatus import network_state_is_connected
from softwarecenter.paths import (SOFTWARE_CENTER_CACHE_DIR,
                                  PistonHelpers,
                                  RNRApps,
                                  )
from softwarecenter.utils import calc_dr, utf8, save_person_to_config


LOG = logging.getLogger(__name__)


# this code had several incernations:
# - python threads, slow and full of latency (GIL)
# - python multiprocesing, crashed when accessibility was turned on,
#                          does not work in the quest session (#743020)
# - GObject.spawn_async() looks good so far (using the SpawnHelper code)
class ReviewLoaderSpawningRNRClient(ReviewLoader):
    """ loader that uses multiprocessing to call rnrclient and
        a glib timeout watcher that polls periodically for the
        data
    """

    def __init__(self, cache, db, distro=None):
        super(ReviewLoaderSpawningRNRClient, self).__init__(cache, db, distro)
        cachedir = os.path.join(SOFTWARE_CENTER_CACHE_DIR, "rnrclient")
        self.rnrclient = RatingsAndReviewsAPI(cachedir=cachedir)
        cachedir = os.path.join(SOFTWARE_CENTER_CACHE_DIR, "rnrclient")
        self.rnrclient = RatingsAndReviewsAPI(cachedir=cachedir)
        self._reviews = {}

    def _update_rnrclient_offline_state(self):
        # this needs the lp:~mvo/piston-mini-client/offline-mode branch
        self.rnrclient._offline_mode = not network_state_is_connected()

    # reviews
    def get_reviews(self, translated_app, callback, page=1,
                    language=None, sort=0, relaxed=False):
        """ public api, triggers fetching a review and calls callback
            when its ready
        """
        # its fine to use the translated appname here, we only submit the
        # pkgname to the server
        app = translated_app
        self._update_rnrclient_offline_state()
        sort_method = self._review_sort_methods[sort]
        if language is None:
            language = self.language
        # gather args for the helper
        if relaxed:
            origin = 'any'
            distroseries = 'any'
        else:
            try:
                origin = self.cache.get_origin(app.pkgname)
            except:
                # this can happen if e.g. the app has multiple origins, this
                # will be handled later
                origin = None
            # special case for not-enabled PPAs
            if not origin and self.db:
                details = app.get_details(self.db)
                ppa = details.ppaname
                if ppa:
                    origin = "lp-ppa-%s" % ppa.replace("/", "-")
            # if there is no origin, there is nothing to do
            if not origin:
                callback(app, [])
                return
            distroseries = self.distro.get_codename()
        # run the command and add watcher
        cmd = [os.path.join(softwarecenter.paths.datadir,
            PistonHelpers.GET_REVIEWS),
               "--language", language,
               "--origin", origin,
               "--distroseries", distroseries,
               "--pkgname", str(app.pkgname),  # ensure its str, not unicode
               "--page", str(page),
               "--sort", sort_method,
              ]
        spawn_helper = SpawnHelper()
        spawn_helper.connect(
            "data-available", self._on_reviews_helper_data, app, callback)
        spawn_helper.run(cmd)

    def _on_reviews_helper_data(self, spawn_helper, piston_reviews, app,
        callback):
        # convert into our review objects
        reviews = []
        for r in piston_reviews:
            reviews.append(Review.from_piston_mini_client(r))
        # add to our dicts and run callback
        self._reviews[app] = reviews
        callback(app, self._reviews[app])
        return False

    # stats
    def refresh_review_stats(self, callback):
        """ public api, refresh the available statistics """
        try:
            mtime = os.path.getmtime(self.REVIEW_STATS_CACHE_FILE)
            days_delta = int((time.time() - mtime) // (24 * 60 * 60))
            days_delta += 1
        except OSError:
            days_delta = 0
        LOG.debug("refresh with days_delta: %s" % days_delta)
        # FIXME: the server currently has bug (#757695) so we
        #        can not turn this on just yet and need to use
        #        the old "catch-all" review-stats for now
        #origin = "any"
        #distroseries = self.distro.get_codename()
        spawn_helper = SpawnHelper()
        spawn_helper.connect("data-available", self._on_review_stats_data,
            callback)
        if days_delta:
            spawn_helper.run_generic_piston_helper(
                "RatingsAndReviewsAPI", "review_stats", days=days_delta)
        else:
            spawn_helper.run_generic_piston_helper(
                "RatingsAndReviewsAPI", "review_stats")

    def _on_review_stats_data(self, spawn_helper, piston_review_stats,
        callback):
        """ process stdout from the helper """
        review_stats = self.REVIEW_STATS_CACHE

        if self._cache_version_old and self._server_has_histogram(
            piston_review_stats):
            self.REVIEW_STATS_CACHE = {}
            self.save_review_stats_cache_file()
            self.refresh_review_stats(callback)
            return

        # convert to the format that s-c uses
        for r in piston_review_stats:
            s = ReviewStats(Application("", r.package_name))
            s.ratings_average = float(r.ratings_average)
            s.ratings_total = float(r.ratings_total)
            if r.histogram:
                s.rating_spread = json.loads(r.histogram)
            else:
                s.rating_spread = [0, 0, 0, 0, 0]
            s.dampened_rating = calc_dr(s.rating_spread)
            review_stats[s.app] = s
        self.REVIEW_STATS_CACHE = review_stats
        callback(review_stats)
        self.emit("refresh-review-stats-finished", review_stats)
        self.save_review_stats_cache_file()

    def _server_has_histogram(self, piston_review_stats):
        '''check response from server to see if histogram is supported'''
        supported = getattr(piston_review_stats[0], "histogram", False)
        if not supported:
            return False
        return True

    # writing new reviews spawns external helper
    # FIXME: instead of the callback we should add proper gobject signals
    def spawn_write_new_review_ui(self, translated_app, version, iconname,
                                  origin, parent_xid, datadir, callback,
                                  done_callback=None):
        """ this spawns the UI for writing a new review and
            adds it automatically to the reviews DB """
        app = translated_app.get_untranslated_app(self.db)
        cmd = [os.path.join(datadir, RNRApps.SUBMIT_REVIEW),
               "--pkgname", app.pkgname,
               "--iconname", iconname,
               "--parent-xid", "%s" % parent_xid,
               "--version", version,
               "--origin", origin,
               "--datadir", datadir,
               ]
        if app.appname:
            # needs to be (utf8 encoded) str, otherwise call fails
            cmd += ["--appname", utf8(app.appname)]
        spawn_helper = SpawnHelper(format="json")
        spawn_helper.connect(
            "data-available", self._on_submit_review_data, app, callback)
        if done_callback:
            spawn_helper.connect("exited", done_callback)
            spawn_helper.connect("error", done_callback)
        spawn_helper.run(cmd)

    def _on_submit_review_data(self, spawn_helper, review_json, app, callback):
        """ called when submit_review finished, when the review was send
            successfully the callback is triggered with the new reviews
        """
        LOG.debug("_on_submit_review_data")
        # read stdout from submit_review
        review = ReviewDetails.from_dict(review_json)
        # FIXME: ideally this would be stored in ubuntu-sso-client
        #        but it dosn't so we store it here
        save_person_to_config(review.reviewer_username)
        if not app in self._reviews:
            self._reviews[app] = []
        self._reviews[app].insert(0, Review.from_piston_mini_client(review))
        callback(app, self._reviews[app])

    def spawn_report_abuse_ui(self, review_id, parent_xid, datadir, callback):
        """ this spawns the UI for reporting a review as inappropriate
            and adds the review-id to the internal hide list. once the
            operation is complete it will call callback with the updated
            review list
        """
        cmd = [os.path.join(datadir, RNRApps.REPORT_REVIEW),
               "--review-id", review_id,
               "--parent-xid", "%s" % parent_xid,
               "--datadir", datadir,
              ]
        spawn_helper = SpawnHelper("json")
        spawn_helper.connect("exited",
                             self._on_report_abuse_finished,
                             review_id, callback)
        spawn_helper.run(cmd)

    def _on_report_abuse_finished(self, spawn_helper, exitcode, review_id,
        callback):
        """ called when report_absuse finished """
        LOG.debug("hide id %s " % review_id)
        if exitcode == 0:
            for (app, reviews) in self._reviews.items():
                for review in reviews:
                    if str(review.id) == str(review_id):
                        # remove the one we don't want to see anymore
                        self._reviews[app].remove(review)
                        callback(app, self._reviews[app], None, 'remove',
                            review)
                        break

    def spawn_submit_usefulness_ui(self, review_id, is_useful, parent_xid,
        datadir, callback):
        cmd = [os.path.join(datadir, RNRApps.SUBMIT_USEFULNESS),
               "--review-id", "%s" % review_id,
               "--is-useful", "%s" % int(is_useful),
               "--parent-xid", "%s" % parent_xid,
               "--datadir", datadir,
              ]
        spawn_helper = SpawnHelper(format="none")
        spawn_helper.connect("exited",
                             self._on_submit_usefulness_finished,
                             review_id, is_useful, callback)
        spawn_helper.connect("error",
                             self._on_submit_usefulness_error,
                             review_id, callback)
        spawn_helper.run(cmd)

    def _on_submit_usefulness_finished(self, spawn_helper, res, review_id,
        is_useful, callback):
        """ called when report_usefulness finished """
        # "Created", "Updated", "Not modified" -
        # once lp:~mvo/rnr-server/submit-usefulness-result-strings makes it
        response = spawn_helper._stdout
        if response == '"Not modified"':
            self._on_submit_usefulness_error(spawn_helper, response, review_id,
                callback)
            return

        LOG.debug("usefulness id %s " % review_id)
        useful_votes = UsefulnessCache()
        useful_votes.add_usefulness_vote(review_id, is_useful)
        for (app, reviews) in self._reviews.items():
            for review in reviews:
                if str(review.id) == str(review_id):
                    # update usefulness, older servers do not send
                    # usefulness_{total,favorable} so we use getattr
                    review.usefulness_total = getattr(review,
                        "usefulness_total", 0) + 1
                    if is_useful:
                        review.usefulness_favorable = getattr(review,
                            "usefulness_favorable", 0) + 1
                        callback(app, self._reviews[app], useful_votes,
                            'replace', review)
                        break

    def _on_submit_usefulness_error(self, spawn_helper, error_str, review_id,
        callback):
        LOG.warn("submit usefulness id=%s failed with error: %s" %
                 (review_id, error_str))
        for (app, reviews) in self._reviews.items():
            for review in reviews:
                if str(review.id) == str(review_id):
                    review.usefulness_submit_error = True
                    callback(app, self._reviews[app], None, 'replace', review)
                    break

    def spawn_delete_review_ui(self, review_id, parent_xid, datadir, callback):
        cmd = [os.path.join(datadir, RNRApps.DELETE_REVIEW),
               "--review-id", "%s" % review_id,
               "--parent-xid", "%s" % parent_xid,
               "--datadir", datadir,
              ]
        spawn_helper = SpawnHelper(format="none")
        spawn_helper.connect("exited",
                             self._on_delete_review_finished,
                             review_id, callback)
        spawn_helper.connect("error", self._on_delete_review_error,
                             review_id, callback)
        spawn_helper.run(cmd)

    def _on_delete_review_finished(self, spawn_helper, res, review_id,
        callback):
        """ called when delete_review finished"""
        LOG.debug("delete id %s " % review_id)
        for (app, reviews) in self._reviews.items():
            for review in reviews:
                if str(review.id) == str(review_id):
                    # remove the one we don't want to see anymore
                    self._reviews[app].remove(review)
                    callback(app, self._reviews[app], None, 'remove', review)
                    break

    def _on_delete_review_error(self, spawn_helper, error_str, review_id,
        callback):
        """called if delete review errors"""
        LOG.warn("delete review id=%s failed with error: %s" % (review_id,
            error_str))
        for (app, reviews) in self._reviews.items():
            for review in reviews:
                if str(review.id) == str(review_id):
                    review.delete_error = True
                    callback(app, self._reviews[app], action='replace',
                             single_review=review)
                    break

    def spawn_modify_review_ui(self, parent_xid, iconname, datadir, review_id,
        callback):
        """ this spawns the UI for writing a new review and
            adds it automatically to the reviews DB """
        cmd = [os.path.join(datadir, RNRApps.MODIFY_REVIEW),
               "--parent-xid", "%s" % parent_xid,
               "--iconname", iconname,
               "--datadir", "%s" % datadir,
               "--review-id", "%s" % review_id,
               ]
        spawn_helper = SpawnHelper(format="json")
        spawn_helper.connect("data-available",
                             self._on_modify_review_finished,
                             review_id, callback)
        spawn_helper.connect("error", self._on_modify_review_error,
                             review_id, callback)
        spawn_helper.run(cmd)

    def _on_modify_review_finished(self, spawn_helper, review_json, review_id,
        callback):
        """called when modify_review finished"""
        LOG.debug("_on_modify_review_finished")
        #review_json = spawn_helper._stdout
        mod_review = ReviewDetails.from_dict(review_json)
        for (app, reviews) in self._reviews.items():
            for review in reviews:
                if str(review.id) == str(review_id):
                    # remove the one we don't want to see anymore
                    self._reviews[app].remove(review)
                    new_review = Review.from_piston_mini_client(mod_review)
                    self._reviews[app].insert(0, new_review)
                    callback(app, self._reviews[app], action='replace',
                             single_review=new_review)
                    break

    def _on_modify_review_error(self, spawn_helper, error_str, review_id,
        callback):
        """called if modify review errors"""
        LOG.debug("modify review id=%s failed with error: %s" %
            (review_id, error_str))
        for (app, reviews) in self._reviews.items():
            for review in reviews:
                if str(review.id) == str(review_id):
                    review.modify_error = True
                    callback(app, self._reviews[app], action='replace',
                             single_review=review)
                    break
