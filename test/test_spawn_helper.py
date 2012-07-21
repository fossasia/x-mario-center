#!/usr/bin/python

import unittest
from mock import patch

from testutils import setup_test_env
setup_test_env()
from softwarecenter.backend.spawn_helper import SpawnHelper

class TestSpawnHelper(unittest.TestCase):

    def test_spawn_helper_lp957599(self):
        days_delta = 6
        spawn_helper = SpawnHelper()
        with patch.object(spawn_helper, "run") as mock_run:
            spawn_helper.run_generic_piston_helper(
                "RatingsAndReviewsAPI", "review_stats", days=days_delta)
            cmd = mock_run.call_args[0][0]
            #print mock_run.call_args_list
            #print cmd
            self.assertEqual(cmd[3], 'RatingsAndReviewsAPI')
            self.assertEqual(cmd[4], 'review_stats')
            self.assertEqual(cmd[5], '{"days": 6}')



if __name__ == "__main__":
    #import logging
    #logging.basicConfig(level=logging.DEBUG)
    unittest.main()
