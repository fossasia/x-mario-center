#!/usr/bin/python

import os
import unittest

from testutils import setup_test_env
setup_test_env()
from softwarecenter.backend.ubuntusso import (UbuntuSSOAPIFake,
                                              UbuntuSSOAPI,
                                              get_ubuntu_sso_backend,
                                              )

class TestSSOAPI(unittest.TestCase):
    """ tests the ubuntu sso backend stuff """

    def test_fake_and_real_provide_similar_methods(self):
        """ test if the real and fake sso provide the same functions """
        sso_real = UbuntuSSOAPI
        sso_fake = UbuntuSSOAPIFake
        # ensure that both fake and real implement the same methods
        self.assertEqual(
            set([x for x in dir(sso_real) if not x.startswith("_")]),
            set([x for x in dir(sso_fake) if not x.startswith("_")]))

    def test_get_ubuntu_backend(self):
        # test that we get the real one
        self.assertEqual(type(get_ubuntu_sso_backend()),
                         UbuntuSSOAPI)
        # test that we get the fake one
        os.environ["SOFTWARE_CENTER_FAKE_REVIEW_API"] = "1"
        self.assertEqual(type(get_ubuntu_sso_backend()),
                         UbuntuSSOAPIFake)
        # clean the environment
        del os.environ["SOFTWARE_CENTER_FAKE_REVIEW_API"]


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
