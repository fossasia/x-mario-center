#!/usr/bin/python

from gi.repository import GObject
import unittest
import os

from mock import patch

from testutils import setup_test_env
setup_test_env()

from softwarecenter.backend.recagent import RecommenderAgent

from softwarecenter.testutils import (
    get_test_db
)

class TestRecommenderAgent(unittest.TestCase):
    """ tests the recommender agent """

    def setUp(self):
        self.loop = GObject.MainLoop(GObject.main_context_default())
        self.error = False
        self.orig_host = os.environ.get("SOFTWARE_CENTER_RECOMMENDER_HOST")
        if not "SOFTWARE_CENTER_RECOMMENDER_HOST" in os.environ:
	    server = "https://rec.staging.ubuntu.com"
	    #server = "https://rec.ubuntu.com"
            os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"] = server

    def tearDown(self):
        if self.orig_host is None:
            del os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"]
        else:
            os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"] = self.orig_host

    @patch('softwarecenter.backend.recagent.SpawnHelper'
           '.run_generic_piston_helper')
    def test_mocked_recagent_post_submit_profile(self, mock_spawn_helper_run):
        def _patched_on_submit_profile_data(*args, **kwargs):
            piston_submit_profile = {}
            recommender_agent.emit("submit-profile-finished", 
                                   piston_submit_profile)
        mock_spawn_helper_run.side_effect = _patched_on_submit_profile_data
        recommender_agent = RecommenderAgent()
        recommender_agent.connect("submit-profile-finished", self.on_query_done)
        recommender_agent.connect("error", self.on_query_error)
        recommender_agent._calc_profile_id = lambda profile: "i-am-random"
        db = get_test_db()
        recommender_agent.post_submit_profile(db)
        self.assertFalse(self.error)
        args, kwargs =  mock_spawn_helper_run.call_args
        self.assertNotEqual(kwargs['data'][0]['package_list'], [])

    def on_query_done(self, recagent, data):
        print "query done, data: '%s'" % data
        self.loop.quit()
        
    def on_query_error(self, recagent, error):
        print "query error received: ", error
        self.loop.quit()
        self.error = True
        
    def test_recagent_query_server_status(self):
        # NOTE: This requires a working recommender host that is reachable
        recommender_agent = RecommenderAgent()
        recommender_agent.connect("server-status", self.on_query_done)
        recommender_agent.connect("error", self.on_query_error)
        recommender_agent.query_server_status()
        self.loop.run()
        self.assertFalse(self.error)
      
    # FIXME: disabled for now as the server is not quite working  
    def disabled_test_recagent_post_submit_profile(self):
        # NOTE: This requires a working recommender host that is reachable
        recommender_agent = RecommenderAgent()
        recommender_agent.connect("submit-profile-finished", self.on_query_done)
        recommender_agent.connect("error", self.on_query_error)
        db = get_test_db()
        recommender_agent.post_submit_profile(db)
        self.loop.run()
        self.assertFalse(self.error)
        #print mock_request._post
        
     # NOTE: this server call is currently not needed and not used
#    def disabled_test_recagent_query_submit_anon_profile(self):
#        # NOTE: This requires a working recommender host that is reachable
#        recommender_agent = RecommenderAgent()
#        recommender_agent.connect("submit-anon-profile", self.on_query_done)
#        recommender_agent.connect("error", self.on_query_error)
#        recommender_agent.query_submit_anon_profile(
#                uuid=recommender_uuid,
#                installed_packages=["pitivi", "fretsonfire"],
#                extra="")
#        self.loop.run()
#        self.assertFalse(self.error)
        
    # FIXME: disabled for now as the server is not quite working
    def disabled_test_recagent_query_profile(self):
        # NOTE: This requires a working recommender host that is reachable
        recommender_agent = RecommenderAgent()
        recommender_agent.connect("profile", self.on_query_done)
        recommender_agent.connect("error", self.on_query_error)
        recommender_agent.query_profile(pkgnames=["pitivi", "fretsonfire"])
        self.loop.run()
        self.assertFalse(self.error)

    # FIXME: disabled for now as the server is not quite working
    def disabled_test_recagent_query_recommend_me(self):
        # NOTE: This requires a working recommender host that is reachable
        recommender_agent = RecommenderAgent()
        recommender_agent.connect("recommend-me", self.on_query_done)
        recommender_agent.connect("error", self.on_query_error)
        recommender_agent.query_recommend_me()
        self.loop.run()
        self.assertFalse(self.error)

    def test_recagent_query_recommend_app(self):
        # NOTE: This requires a working recommender host that is reachable
        recommender_agent = RecommenderAgent()
        recommender_agent.connect("recommend-app", self.on_query_done)
        recommender_agent.connect("error", self.on_query_error)
        recommender_agent.query_recommend_app("pitivi")
        self.loop.run()
        self.assertFalse(self.error)

    # disabled for now (2012-03-20) as the server is returning 504
    def disabled_test_recagent_query_recommend_all_apps(self):
        # NOTE: This requires a working recommender host that is reachable
        recommender_agent = RecommenderAgent()
        recommender_agent.connect("recommend-all-apps", self.on_query_done)
        recommender_agent.connect("error", self.on_query_error)
        recommender_agent.query_recommend_all_apps()
        self.loop.run()
        self.assertFalse(self.error)
        
    def test_recagent_query_recommend_top(self):
        # NOTE: This requires a working recommender host that is reachable
        recommender_agent = RecommenderAgent()
        recommender_agent.connect("recommend-top", self.on_query_done)
        recommender_agent.connect("error", self.on_query_error)
        recommender_agent.query_recommend_top()
        self.loop.run()
        self.assertFalse(self.error)
        
    def test_recagent_query_error(self):
        # NOTE: This tests the error condition itself! it simply forces an error
        #       'cuz there definitely isn't a server here  :)
        os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"] = "https://test-no-server-here.staging.ubuntu.com"
        recommender_agent = RecommenderAgent()
        recommender_agent.connect("recommend-top", self.on_query_done)
        recommender_agent.connect("error", self.on_query_error)
        recommender_agent.query_recommend_top()
        self.loop.run()
        self.assertTrue(self.error)

if __name__ == "__main__":
    #import logging
    #logging.basicConfig(level=logging.DEBUG)
    unittest.main()
