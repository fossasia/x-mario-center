#!/usr/bin/python

import unittest

from testutils import setup_test_env
setup_test_env()

from softwarecenter.backend.piston.rnrclient import RatingsAndReviewsAPI
from softwarecenter.backend.piston.rnrclient_fake import RatingsAndReviewsAPI as RatingsAndReviewsAPIFake

class TestRNRAPI(unittest.TestCase):
    """ tests the rnr backend stuff """

    def test_fake_and_real_provide_similar_methods(self):
        """ test if the real and fake sso provide the same functions """
        rnr_real = RatingsAndReviewsAPI
        rnr_fake = RatingsAndReviewsAPIFake
        # ensure that both fake and real implement the same methods
        self.assertEqual(
            set([x for x in dir(rnr_real) if not x.startswith("_")]),
            set([x for x in dir(rnr_fake) if not x.startswith("_")]))



if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
