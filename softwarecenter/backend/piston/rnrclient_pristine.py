"""This module provides the RatingsAndReviewsAPI class for talking to the
ratings and reviews API, plus a few helper classes.
"""

from urllib import quote_plus
from piston_mini_client import (
    PistonAPI,
    PistonResponseObject,
    PistonSerializable,
    returns,
    returns_json,
    returns_list_of,
    )
from piston_mini_client.validators import validate_pattern, validate

# These are factored out as constants for if you need to work against a
# server that doesn't support both schemes (like http-only dev servers)
PUBLIC_API_SCHEME = 'http'
AUTHENTICATED_API_SCHEME = 'https'


class ReviewRequest(PistonSerializable):
    """A review request.

    Instantiate one of these objects to describe a new review you wish to
    submit, then pass it in as an argument to submit_review().
    """
    _atts = ('app_name', 'package_name', 'summary', 'version', 'review_text',
        'rating', 'language', 'origin', 'distroseries', 'arch_tag')
    app_name = ''


class ReviewsStats(PistonResponseObject):
    """A ratings summary for a package/app.

    This class will be automatically populated with JSON retrieved from the
    server.  Each ReviewStats object will have the following fields:
     * package_name
     * app_name
     * ratings_total
     * ratings_average
    """
    pass


class ReviewDetails(PistonResponseObject):
    """A detailed review description.

    This class will be automatically populated with JSON retrieved from the
    server.  Each ReviewDetails object will have the following fields:
     * id
     * package_name
     * app_name
     * language
     * date_created
     * rating
     * reviewer_username
     * summary
     * review_text
     * hide
     * version
    """
    pass


class RatingsAndReviewsAPI(PistonAPI):
    """A client for talking to the reviews and ratings API.

    If you pass no arguments into the constructor it will try to connect to
    localhost:8000 so you probably want to at least pass in the
    ``service_root`` constructor argument.
    """
    default_service_root = 'http://localhost:8000/reviews/api/1.0'
    default_content_type = 'application/x-www-form-urlencoded'

    @returns_json
    def server_status(self):
        """Check the state of the server, to see if everything's ok."""
        return self._get('server-status/', scheme=PUBLIC_API_SCHEME)

    @validate_pattern('origin', r'[0-9a-z+-.:/]+', required=False)
    @validate_pattern('distroseries', r'\w+', required=False)
    @validate('days', int, required=False)
    @returns_list_of(ReviewsStats)
    def review_stats(self, origin='any', distroseries='any', days=None,
        valid_days=(1, 3, 7)):
        """Fetch ratings for a particular distroseries"""
        url = 'review-stats/{0}/{1}/'.format(origin, distroseries)
        if days is not None:
            # the server only knows valid_days (1,3,7) currently
            for valid_day in valid_days:
                # pick the day from valid_days that is the next bigger than
                # days
                if days <= valid_day:
                    url += 'updates-last-{0}-days/'.format(valid_day)
                    break
        return self._get(url, scheme=PUBLIC_API_SCHEME)

    @validate_pattern('language', r'\w+', required=False)
    @validate_pattern('origin', r'[0-9a-z+-.:/]+', required=False)
    @validate_pattern('distroseries', r'\w+', required=False)
    @validate_pattern('version', r'[-\w+.:~]+', required=False)
    @validate_pattern('packagename', r'[a-z0-9.+-]+')
    @validate('appname', str, required=False)
    @validate('page', int, required=False)
    @validate('sort', str, required=False)
    @returns_list_of(ReviewDetails)
    def get_reviews(self, packagename, language='any', origin='any',
        distroseries='any', version='any', appname='', page=1, sort='helpful'):
        """Fetch ratings and reviews for a particular package name.

        If any of the optional arguments are provided, fetch reviews for that
        particular app, language, origin, distroseries or version.
        """
        if appname:
            appname = quote_plus(';' + appname)
        return self._get('reviews/filter/%s/%s/%s/%s/%s%s/page/%s/%s/' % (
            language, origin, distroseries, version, packagename,
            appname, page, sort),
            scheme=PUBLIC_API_SCHEME)

    @validate('review_id', int)
    @returns(ReviewDetails)
    def get_review(self, review_id):
        """Fetch a particular review via its id."""
        return self._get('reviews/%s/' % review_id)

    @validate('review', ReviewRequest)
    @returns(ReviewDetails)
    def submit_review(self, review):
        """Submit a rating/review."""
        return self._post('reviews/', data=review,
        scheme=AUTHENTICATED_API_SCHEME, content_type='application/json')

    @validate('review_id', int)
    @validate_pattern('reason', r'[^\n]+')
    @validate_pattern('text', r'[^\n]+')
    @returns_json
    def flag_review(self, review_id, reason, text):
        """Flag a review as being inappropriate"""
        data = {'reason': reason,
            'text': text,
        }
        return self._post('reviews/%s/flags/' % review_id, data=data,
        scheme=AUTHENTICATED_API_SCHEME)

    @validate('review_id', int)
    @validate_pattern('useful', 'True|False')
    @returns_json
    def submit_usefulness(self, review_id, useful):
        """Submit a usefulness vote."""
        return self._post('/reviews/%s/recommendations/' % review_id,
            data={'useful': useful}, scheme=AUTHENTICATED_API_SCHEME)

    @validate('review_id', int, required=False)
    @validate_pattern('username', r'[^\n]+', required=False)
    @returns_json
    def get_usefulness(self, review_id=None, username=None):
        """Get a list of usefulness filtered by username/review_id"""
        if not username and not review_id:
            return None

        data = {}

        if username:
            data['username'] = username
        if review_id:
            data['review_id'] = str(review_id)

        return self._get('usefulness/', args=data,
            scheme=PUBLIC_API_SCHEME)

    @validate('review_id', int)
    @returns_json
    def delete_review(self, review_id):
        """Delete a review"""
        return self._post('/reviews/delete/%s/' % review_id, data={},
            scheme=AUTHENTICATED_API_SCHEME)

    @validate('review_id', int)
    @validate('rating', int)
    @validate_pattern('summary', r'[^\n]+')
    @validate_pattern('review_text', r'[^\n]+')
    @returns(ReviewDetails)
    def modify_review(self, review_id, rating, summary, review_text):
        """Modify an existing review"""
        data = {
            'rating': rating,
            'summary': summary,
            'review_text': review_text
        }
        return self._put('/reviews/modify/%s/' % review_id, data=data,
        scheme=AUTHENTICATED_API_SCHEME)
