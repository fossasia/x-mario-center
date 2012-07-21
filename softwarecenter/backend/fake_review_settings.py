
import time
import os
import pickle
from softwarecenter.paths import SOFTWARE_CENTER_CACHE_DIR


# decorator to add a fake network delay if set
# in FakeReviewSettings.fake_network_delay
def network_delay(fn):
    def slp(self, *args, **kwargs):
        fake_settings = FakeReviewSettings()
        delay = fake_settings.get_setting('fake_network_delay')
        if delay:
            time.sleep(delay)
        return fn(self, *args, **kwargs)
    return slp


class FakeReviewSettings(object):
    '''An object that simply holds settings which are used by
       RatingsAndReviewsAPI in the rnrclient_fake module. Using this module
       allows a developer to test the reviews functionality without any
       interaction with a reviews server.  Each setting here provides complete
       control over how the 'server' will respond. Changes to these settings
       should be made to the class attributes directly without creating an
       instance of this class.
       The intended usage is for unit tests where a predictable response is
       required and where the application should THINK it has spoken to a
       server.
       The unit test would make changes to settings in this class before
       running the unit test.
    '''

    _FAKE_SETTINGS = {}

    #general settings
    #*****************************
    #delay (in seconds) before returning from any of the fake rnr methods
    #useful for emulating real network timings (use None for no delays)
    _FAKE_SETTINGS['fake_network_delay'] = 2

    #server status
    #*****************************
    #raises APIError if True
    _FAKE_SETTINGS['server_response_error'] = False

    #review stats
    #*****************************
    #raises APIError if True
    _FAKE_SETTINGS['review_stats_error'] = False

    #the following has no effect if review_stats_error = True
    #determines the number of package stats (i.e. ReviewStats list size) to
    #return max 15 packages (any number higher than 15 will still return 15)
    _FAKE_SETTINGS['packages_returned'] = 10

    #get reviews
    #*****************************
    #raises APIError if True
    _FAKE_SETTINGS['get_reviews_error'] = False

    #number of pages of 10 reviews to return before returning the number
    # specified in the reviews_returned value below
    _FAKE_SETTINGS['review_pages'] = 1

    #the following has no effect if get_reviews_error = True
    #determines number of reviews to return
    # (Accepts 0 to n but should really be between 1 and 10)
    _FAKE_SETTINGS['reviews_returned'] = 3

    #get review
    #*****************************
    #raises APIError if True
    _FAKE_SETTINGS['get_review_error'] = False

    #submit review
    #*****************************
    #raises APIError if True
    _FAKE_SETTINGS['submit_review_error'] = False
    #fake username(str) and review_id(int) to give back with a successful
    # review
    #leave as None to generate a random username and review_id
    _FAKE_SETTINGS['reviewer_username'] = None
    _FAKE_SETTINGS['submit_review_id'] = None

    #flag review
    #*****************************
    #raises APIError if True
    _FAKE_SETTINGS['flag_review_error'] = False
    #fake username(str) to give back as 'flagger'
    _FAKE_SETTINGS['flagger_username'] = None
    #fake package name (str) to give back as flagged app
    _FAKE_SETTINGS['flag_package_name'] = None

    #submit usefulness
    #*****************************
    #raises APIError if True
    _FAKE_SETTINGS['submit_usefulness_error'] = False

    #the following has no effect if submit_usefulness_error = True
    #which string to pretend the server returned
    #choices are "Created", "Updated", "Not modified"
    _FAKE_SETTINGS['usefulness_response_string'] = "Created"

    #get usefulness
    #*****************************
    #raises APIError if True
    _FAKE_SETTINGS['get_usefulness_error'] = False

    #the following has no effect if get_usefulness_error = True
    #how many usefulness votes to return
    _FAKE_SETTINGS['votes_returned'] = 5

    #pre-configured review ids to return in the result
    #if you don't complete this or enter less review ids than votes_returned
    #above, it will be random
    _FAKE_SETTINGS['required_review_ids'] = [3, 6, 15]

    #THE FOLLOWING SETTINGS RELATE TO LOGIN SSO FUNCTIONALITY
    # LoginBackendDbusSSO
    # login()
    #***********************
    # what to fake the login response as
    # choices (strings): "successful", "failed", "denied"
    _FAKE_SETTINGS['login_response'] = "successful"

    # UbuntuSSOAPI
    # whoami()
    #***********************
    # what to fake whoami response as
    # choices (strings): "whoami", "error"
    _FAKE_SETTINGS['whoami_response'] = "whoami"
    #this only has effect if whoami_response = 'whoami'
    #determines the username to return in a successful whoami
    #expects a string or None (for a random username)
    _FAKE_SETTINGS['whoami_username'] = None

    def __init__(self, defaults=False):
        '''Initialises the object and loads the settings into the
           _FAKE_SETTINGS dict.. If defaults is passed as True any existing
           settings in the cache file are ignored and the cache file is
           overwritten with the defaults set in the class. This is useful if
           you don't want previously used settings from the cache file being
           used again'''
        fname = 'fake_review_settings.p'
        self.LOCATION = os.path.join(SOFTWARE_CENTER_CACHE_DIR, fname)
        if defaults:
            self._save_settings()
        else:
            self._update_from_file()

    def update_setting(self, key_name, new_value):
        '''Takes a string (key_name) which corresponds to a setting in this
        object and updates it with the value passed in (new_value).
        Raises a NameError if the setting name doesn't exist'''

        if not key_name in self._FAKE_SETTINGS:
            raise NameError('Setting key name %s does not exist' % key_name)
        else:
            self._FAKE_SETTINGS[key_name] = new_value
            self._save_settings()
        return

    def update_multiple(self, settings):
        '''Takes a dict (settings) of key,value pairs to perform multiple
           updates in one action, then saves. Dict being passed should contain
           only keys that match settings in this object or a NameError will be
           raised'''
        for key, value in settings.items():
            if not key in self._FAKE_SETTINGS:
                raise NameError('Setting key name %s does not exist' % key)

        for key, value in settings.items():
            self._FAKE_SETTINGS[key] = value
        self._save_settings()
        return

    def get_setting(self, key_name):
        '''Takes a string (key_name) which corresponds to a setting in this
        object, gets the latest copy of it from the file and returns the
        setting.  Raises a NameError if the setting name doesn't exist'''
        if not key_name in self._FAKE_SETTINGS:
            raise NameError('Setting %s does not exist' % key_name)
        else:
            self._update_from_file()
            return self._FAKE_SETTINGS[key_name]

    def _update_from_file(self):
        '''Loads existing settings from cache file into _FAKE_SETTINGS dict'''
        if os.path.exists(self.LOCATION):
            try:
                self._FAKE_SETTINGS = pickle.load(open(self.LOCATION))
            except:
                os.rename(self.LOCATION, self.LOCATION + ".fail")
        return

    def _save_settings(self):
        """write the dict out to cache file"""
        try:
            if not os.path.exists(SOFTWARE_CENTER_CACHE_DIR):
                os.makedirs(SOFTWARE_CENTER_CACHE_DIR)
            pickle.dump(self._FAKE_SETTINGS, open(self.LOCATION, "w"))
            return True
        except:
            return False
