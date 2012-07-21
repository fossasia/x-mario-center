#!/usr/bin/python

import pickle
import os
import subprocess
import time
import unittest

from testutils import setup_test_env
setup_test_env()


# FIXME:
#  - need proper fixtures for history and lists
#  - needs stats about cold/warm disk cache


class SCTestGUI(unittest.TestCase):

    def setUp(self):
        if os.path.exists("revno_to_times_list.p"):
            self.revno_to_times_list = pickle.load(open("revno_to_times_list.p"))
        else:
            self.revno_to_times_list = {}

    def tearDown(self):
        pickle.dump(
            self.revno_to_times_list, open("revno_to_times_list.p", "w"))

    # FIXME: debug why this sometimes hangs
    def disabled_for_now_untiL_hang_is_found_test_startup_time(self):
        for i in range(5):
            time_to_visible = self.create_ui_and_return_time_to_visible()
            self.record_test_run_data(time_to_visible)
        print self.revno_to_times_list 

    def create_ui_and_return_time_to_visible(self):
        now = time.time()
        # we get the time on stdout and detailed stats on stderr
        p = subprocess.Popen(["./software-center", "--measure-startup-time"],
                             cwd="..",
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.wait()
        # this is the time with the python statup overhead
        time_with_launching_python = time.time() - now

        # IMPORTANT: this read() needs to be outside of the timing stats,
        #            it takes 2s (!?!) on my 3Ghz machine
        stdoutput = p.stdout.read()
        profile_data = p.stderr.read()

        # this is the time spend inside python
        time_inside_python = stdoutput.strip().split("\n")[-1]
        # for testing
        print "time inside_python: ", time_inside_python
        print "total with launching python: ", time_with_launching_python
        print profile_data
        print

        return time_with_launching_python

    def record_test_run_data(self, time_to_visible):
        # gather stats
        revno = subprocess.Popen(
            ["bzr","revno"], stdout=subprocess.PIPE).communicate()[0].strip()
        times_list = self.revno_to_times_list.get(revno, [])
        times_list.append(time_to_visible)
        self.revno_to_times_list[revno] = times_list

if __name__ == "__main__":
    unittest.main()
