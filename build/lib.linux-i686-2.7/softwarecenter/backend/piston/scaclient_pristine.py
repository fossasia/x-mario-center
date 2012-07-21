from piston_mini_client import (PistonAPI, PistonResponseObject,
    returns_list_of, returns_json)
from piston_mini_client.validators import (validate_pattern, validate,
    oauth_protected)

# These are factored out as constants for if you need to work against a
# server that doesn't support both schemes (like http-only dev servers)
PUBLIC_API_SCHEME = 'http'
AUTHENTICATED_API_SCHEME = 'https'


class SoftwareCenterAgentAPI(PistonAPI):
    default_service_root = 'http://localhost:8000/api/2.0'

    @validate_pattern('lang', r'[^/]{1,9}$')
    @validate_pattern('series', r'[^/]{1,20}$')
    @validate_pattern('arch', r'[^/]{1,10}$')
    @returns_list_of(PistonResponseObject)
    def available_apps(self, lang, series, arch):
        """Retrieve the list of currently available apps for purchase."""
        return self._get(
            'applications/%s/ubuntu/%s/%s/' % (lang, series, arch),
            scheme=PUBLIC_API_SCHEME)

    @validate_pattern('lang', r'[^/]{1,9}$')
    @validate_pattern('series', r'[^/]{1,20}$')
    @validate_pattern('arch', r'[^/]{1,10}$')
    @oauth_protected
    @returns_list_of(PistonResponseObject)
    def available_apps_qa(self, lang, series, arch):
        """Retrieve the list of currently available apps for purchase."""
        return self._get(
            'applications_qa/%s/ubuntu/%s/%s/' % (lang, series, arch),
            scheme=AUTHENTICATED_API_SCHEME)

    @oauth_protected
    @validate('complete_only', bool, required=False)
    @returns_list_of(PistonResponseObject)
    def subscriptions_for_me(self, complete_only=False):
        return self._get('subscriptions/',
            args={'complete_only': complete_only},
            scheme=AUTHENTICATED_API_SCHEME)

    @oauth_protected
    @validate('id', int)
    @returns_json
    def subscription_by_id(self, id=None):
        return self._get('subscription/%d' % (id),
                         scheme=AUTHENTICATED_API_SCHEME)

    @validate_pattern('lang', r'[^/]{1,9}$')
    @validate_pattern('series', r'[^/]{1,20}$', required=False)
    @returns_list_of(PistonResponseObject)
    def exhibits(self, lang, series=''):
        """Retrieve the list of currently published exhibits."""
        url = 'exhibits/%s/' % lang
        if series != '':
            url += '%s/' % series
        return self._get(url)
