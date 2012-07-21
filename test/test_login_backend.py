#!/usr/bin/python

import os
import unittest

from testutils import setup_test_env
setup_test_env()
from softwarecenter.backend.login_sso import (get_sso_backend,
                                              LoginBackendDbusSSO,
                                              LoginBackendDbusSSOFake)

class TestLoginBackend(unittest.TestCase):
    """ tests the login backend stuff """

    def test_fake_and_real_provide_similar_methods(self):
        """ test if the real and fake login provide the same functions """
        login_real = LoginBackendDbusSSO
        login_fake = LoginBackendDbusSSOFake
        # ensure that both fake and real implement the same methods
        self.assertEqual(
            set([x for x in dir(login_real) if not x.startswith("_")]),
            set([x for x in dir(login_fake) if not x.startswith("_")]))

    def test_get_sso_backend(self):
        # test that we get the real one
        self.assertEqual(type(get_sso_backend(None, None, None)),
                         LoginBackendDbusSSO)
        # test that we get the fake one
        os.environ["SOFTWARE_CENTER_FAKE_REVIEW_API"] = "1"
        self.assertEqual(type(get_sso_backend(None, None, None)),
                         LoginBackendDbusSSOFake)
        # clean the environment
        del os.environ["SOFTWARE_CENTER_FAKE_REVIEW_API"]


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
