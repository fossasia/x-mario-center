"""This module provides the RatingsAndReviewsAPI class for talking to the
ratings and reviews API, plus a few helper classes.
"""

from piston_mini_client import (
    PistonAPI,
    returns,
    returns_json,
    returns_list_of,
    )
from piston_mini_client.validators import validate_pattern, validate
from piston_mini_client.failhandlers import APIError

# These are factored out as constants for if you need to work against a
# server that doesn't support both schemes (like http-only dev servers)
PUBLIC_API_SCHEME = 'http'
AUTHENTICATED_API_SCHEME = 'https'

from rnrclient_pristine import ReviewRequest, ReviewsStats, ReviewDetails
from softwarecenter.backend.fake_review_settings import (
    FakeReviewSettings,
    network_delay,
)
import json
import random
import time


class RatingsAndReviewsAPI(PistonAPI):
    """A fake client pretending to be RAtingsAndReviewsAPI from
       rnrclient_pristine.  Uses settings from
       test.fake_review_settings.FakeReviewSettings
       to provide predictable responses to methods that try to use the
       RatingsAndReviewsAPI for testing purposes (i.e. without network
       activity).
       To use this, instead of importing from rnrclient_pristine, you can
       import from rnrclient_fake instead.
    """

    default_service_root = 'http://localhost:8000/reviews/api/1.0'
    default_content_type = 'application/x-www-form-urlencoded'
    _exception_msg = 'Fake RatingsAndReviewsAPI raising fake exception'
    _PACKAGE_NAMES = ['armagetronad', 'compizconfig-settings-manager',
                      'file-roller', 'aisleriot', 'p7zip-full', 'compiz-core',
                      'banshee', 'gconf-editor', 'nanny', '3depict', 'apturl',
                      'jockey-gtk', 'alex4', 'bzr-explorer', 'aqualung']
    _USERS = ["Joe Doll", "John Foo", "Cat Lala", "Foo Grumpf",
             "Bar Tender", "Baz Lightyear"]
    _SUMMARIES = ["Cool", "Medium", "Bad", "Too difficult"]
    _TEXT = ["Review text number 1", "Review text number 2",
            "Review text number 3", "Review text number 4"]
    _fake_settings = FakeReviewSettings()

    @returns_json
    @network_delay
    def server_status(self):
        if self._fake_settings.get_setting('server_response_error'):
            raise APIError(self._exception_msg)
        return json.dumps('ok')

    @validate_pattern('origin', r'[0-9a-z+-.:/]+', required=False)
    @validate_pattern('distroseries', r'\w+', required=False)
    @validate('days', int, required=False)
    @returns_list_of(ReviewsStats)
    @network_delay
    def review_stats(self, origin='any', distroseries='any', days=None,
        valid_days=(1, 3, 7)):
        if self._fake_settings.get_setting('review_stats_error'):
            raise APIError(self._exception_msg)

        if self._fake_settings.get_setting('packages_returned') > 15:
            quantity = 15
        else:
            quantity = self._fake_settings.get_setting('packages_returned')

        stats = []

        for i in range(0, quantity):
            s = {'app_name': '',
                 'package_name': self._PACKAGE_NAMES[i],
                 'ratings_total': str(random.randrange(1, 200)),
                 'ratings_average': str(random.randrange(0, 5)),
                 'histogram': None
            }
            stats.append(s)

        return json.dumps(stats)

    @validate_pattern('language', r'\w+', required=False)
    @validate_pattern('origin', r'[0-9a-z+-.:/]+', required=False)
    @validate_pattern('distroseries', r'\w+', required=False)
    @validate_pattern('version', r'[-\w+.:~]+', required=False)
    @validate_pattern('packagename', r'[a-z0-9.+-]+')
    @validate('appname', str, required=False)
    @validate('page', int, required=False)
    @validate('sort', str, required=False)
    @returns_list_of(ReviewDetails)
    @network_delay
    def get_reviews(self, packagename, language='any', origin='any',
        distroseries='any', version='any', appname='', page=1, sort='helpful'):

        # work out how many reviews to return for pagination
        if page <= self._fake_settings.get_setting('review_pages'):
            num_reviews = 10
        elif page == self._fake_settings.get_setting('review_pages') + 1:
            num_reviews = self._fake_settings.get_setting('reviews_returned')
        else:
            num_reviews = 0

        if self._fake_settings.get_setting('get_reviews_error'):
            raise APIError(self._exception_msg)

        reviews = self._make_fake_reviews(packagename, num_reviews)
        return json.dumps(reviews)

    @validate('review_id', int)
    @returns(ReviewDetails)
    @network_delay
    def get_review(self, review_id):
        if self._fake_settings.get_setting('get_review_error'):
            raise APIError(self._exception_msg)
        review = self._make_fake_reviews(single_id=review_id)
        return json.dumps(review)

    @validate('review', ReviewRequest)
    @returns(ReviewDetails)
    @network_delay
    def submit_review(self, review):
        if self._fake_settings.get_setting('submit_review_error'):
            raise APIError(self._exception_msg)

        user = self._fake_settings.get_setting(
            'reviewer_username') or random.choice(self._USERS)
        review_id = self._fake_settings.get_setting(
            'submit_review_id') or random.randint(1, 10000)
        r = {
                "origin": review.origin,
                "rating": review.rating,
                "hide": False,
                "app_name": review.app_name,
                "language": review.language,
                "reviewer_username": user,
                "usefulness_total": 0,
                "usefulness_favorable": 0,
                "review_text": review.review_text,
                "date_deleted": None,
                "summary": review.summary,
                "version": review.version,
                "id": review_id,
                "date_created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "reviewer_displayname": "Fake User",
                "package_name": review.package_name,
                "distroseries": review.distroseries
            }
        return json.dumps(r)

    @validate('review_id', int)
    @validate_pattern('reason', r'[^\n]+')
    @validate_pattern('text', r'[^\n]+')
    @returns_json
    @network_delay
    def flag_review(self, review_id, reason, text):
        if self._fake_settings.get_setting('flag_review_error'):
            raise APIError(self._exception_msg)

        mod_id = random.randint(1, 500)
        pkg = self._fake_settings.get_setting(
            'flag_package_name') or random.choice(self._PACKAGE_NAMES)
        username = self._fake_settings.get_setting(
            'flagger_username') or random.choice(self._USERS)

        f = {
            "user_id": random.randint(1, 500),
            "description": text,
            "review_moderation_id": mod_id,
            "_user_cache": self._make_user_cache(username),
            "summary": reason,
            "_review_moderation_cache": {
                "status": 0,
                "review_id": review_id,
                "_review_cache": self._make_fake_reviews(packagename=pkg,
                                                         single_id=review_id),
                "moderation_text": text,
                "date_moderated": None,
                "moderator_id": None,
                "date_created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "id": mod_id
            },
            "date_created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "id": mod_id
        }

        return json.dumps(f)

    @validate('review_id', int)
    @validate_pattern('useful', 'True|False')
    @returns_json
    @network_delay
    def submit_usefulness(self, review_id, useful):
        if self._fake_settings.get_setting('submit_usefulness_error'):
            raise APIError(self._exception_msg)
        return json.dumps(self._fake_settings.get_setting(
            'usefulness_response_string'))

    @validate('review_id', int, required=False)
    @validate_pattern('username', r'[^\n]+', required=False)
    @returns_json
    @network_delay
    def get_usefulness(self, review_id=None, username=None):
        if not username and not review_id:
            return None

        if self._fake_settings.get_setting('get_usefulness_error'):
            raise APIError(self._exception_msg)

        #just return a single fake item if the review_id was supplied
        if review_id:
            if username:
                response_user = username
            else:
                response_user = random.choice(self._USERS)

            response = {
                'username': response_user,
                'useful': random.choice(['True', 'False']),
                'review_id': review_id
                }
            return json.dumps([response])

        #set up review ids to honour requested and also add randoms
        quantity = self._fake_settings.get_setting('votes_returned')
        id_list = self._fake_settings.get_setting('required_review_ids')
        id_quantity = len(id_list)

        #figure out if we need to accomodate requested review ids
        if id_quantity == 0:
            rand_id_start = 0
        else:
            rand_id_start = max(id_list)

        votes = []

        for i in range(0, quantity):
            #assign review ids requested if any still exist
            try:
                id = id_list[i]
            except IndexError:
                id = random.randint(rand_id_start, 10000)

            u = {
                 'username': username,
                 'useful': random.choice(['True', 'False']),
                 'review_id': id
                }
            votes.append(u)

        return json.dumps(votes)

    @validate('review_id', int)
    @returns_json
    def delete_review(self, review_id):
        """Delete a review"""
        return json.dumps(True)

    @validate('review_id', int)
    @validate('rating', int)
    @validate_pattern('summary', r'[^\n]+')
    @validate_pattern('review_text', r'[^\n]+')
    @returns(ReviewDetails)
    def modify_review(self, review_id, rating, summary, review_text):
        """Modify an existing review"""
        return json.dumps(self._make_fake_reviews()[0])

    def _make_fake_reviews(self, packagename='compiz-core',
                           quantity=1, single_id=None):
        """Make and return a requested quantity of fake reviews"""

        reviews = []

        for i in range(0, quantity):
            if quantity == 1 and single_id:
                id = single_id
            else:
                id = i * 3

            r = {
                        "origin": "ubuntu",
                        "rating": random.randint(1, 5),
                        "hide": False,
                        "app_name": "",
                        "language": "en",
                        "reviewer_username": random.choice(self._USERS),
                        "usefulness_total": random.randint(3, 6),
                        "usefulness_favorable": random.randint(1, 3),
                        "review_text": random.choice(self._TEXT),
                        "date_deleted": None,
                        "summary": random.choice(self._SUMMARIES),
                        "version": "1:0.9.4",
                        "id": id,
                        "date_created": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "reviewer_displayname": "Fake Person",
                        "package_name": packagename,
                        "distroseries": "natty"
            }
            reviews.append(r)

        #get_review wants a dict but get_reviews wants a list of dicts
        if single_id:
            return r
        else:
            return reviews

    def _make_user_cache(self, username):
        return {
            "username": username,
            "first_name": "Fake",
            "last_name": "User",
            "is_active": True,
            "email": "fakeuser@email.com",
            "is_superuser": False,
            "is_staff": False,
            "last_login": time.strftime("%Y-%m-%d %H:%M:%S"),
            "password": "!",
            "id": random.randint(1, 500),
            "date_joined": time.strftime("%Y-%m-%d %H:%M:%S")
        }
