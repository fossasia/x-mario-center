from piston_mini_client import PistonAPI, returns_json
from piston_mini_client.validators import oauth_protected

# These are factored out as constants for if you need to work against a
# server that doesn't support both schemes (like http-only dev servers)
PUBLIC_API_SCHEME = 'http'
AUTHENTICATED_API_SCHEME = 'https'


# this is only here because:
#  a) ubuntu-sso-client does not support verifying if the credentials
#     are still valid
#  b) the restful client interface is not really needed because we just
#     need this one single call
class UbuntuSsoAPI(PistonAPI):
    default_service_root = 'http://localhost:8000/api/2.0'

    @oauth_protected
    @returns_json
    def whoami(self, id=None):
        return self._get('accounts?ws.op=me',
                         scheme=AUTHENTICATED_API_SCHEME)
