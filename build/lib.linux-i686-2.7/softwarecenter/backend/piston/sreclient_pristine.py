from piston_mini_client import (PistonAPI, returns_json)
from piston_mini_client.validators import (
    validate,
    validate_integer,
    validate_pattern,
    oauth_protected,
    )

# These are factored out as constants for if you need to work against a
# server that doesn't support both schemes (like http-only dev servers)
PUBLIC_API_SCHEME = 'http'
AUTHENTICATED_API_SCHEME = 'https'


class SoftwareCenterRecommenderAPI(PistonAPI):
    default_service_root = 'http://localhost:8000/api/1.0'

    @returns_json
    def server_status(self):
        return self._get('server-status/', scheme=PUBLIC_API_SCHEME)

    @oauth_protected
    @returns_json
    def profile(self, pkgnames):
        """Return True if a profile has already been uploaded."""
        return self._get('profile/', scheme=AUTHENTICATED_API_SCHEME)

    @oauth_protected
    @returns_json
    def submit_profile(self, data):
        return self._post('profile/', data=data,
            scheme=AUTHENTICATED_API_SCHEME)

    @returns_json
    def submit_anon_profile(self, uuid, installed_packages, extra):
        data = {
            'installed_packages': installed_packages,
            'extra': extra,
        }
        return self._post('profile/%s/' % uuid, data=data,
            scheme=PUBLIC_API_SCHEME)

    @oauth_protected
    @returns_json
    def recommend_me(self):
        return self._get('recommend_me/', scheme=AUTHENTICATED_API_SCHEME)

    @validate_pattern('pkgname', '[^/]+')
    @returns_json
    def recommend_app(self, pkgname):
        return self._get('recommend_app/%s/' % pkgname,
            scheme=PUBLIC_API_SCHEME)

    @returns_json
    def recommend_all_apps(self):
        return self._get('recommend_all_apps/', scheme=PUBLIC_API_SCHEME)

    @returns_json
    def recommend_top(self):
        return self._get('recommend_top/', scheme=PUBLIC_API_SCHEME)

    @oauth_protected
    @validate_pattern('rid', '\w+')
    @validate_integer('feedback')
    @returns_json
    def feedback(self, rid, feedback):
        data = {
            'feedback': feedback,
            'rid': rid,
            }
        return self._post('feedback/', data=data,
            scheme=AUTHENTICATED_API_SCHEME)

    @oauth_protected
    @returns_json
    @validate('remove', bool)
    def remove_app(self, appname, remove):
        data = {
            'app': appname,
            'remove': remove,
            }
        return self._post('remove_app/', data=data,
            scheme=AUTHENTICATED_API_SCHEME)
