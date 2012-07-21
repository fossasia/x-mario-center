#!/usr/bin/env python

import ldtp
import time
import unittest

start_time = time.time()


class TestCaseUSCStartStop(unittest.TestCase):

    def setUp(self):
        ldtp.launchapp('./software-center')
        assert ldtp.waittillguiexist('frmUbuntuSoftwareCent*')
        self.msgs = []
        a = "Time taken for the frame to open is: " + str(
            time.time() - start_time) + " Cpu percentage: " + str(ldtp.getcpustat('software-center')) + " Memory usage in MB: " + str(ldtp.getmemorystat('software-center'))
        self.msgs.append(a)

    def tearDown(self):
        ldtp.selectmenuitem('frmUbuntuSoftwareCent*', 'mnuClose')
        assert ldtp.waittillguinotexist('frmUbuntuSoftwareCent*')
        c = "This test took a total of " + str(time.time() - start_time) + " Cpu percentage: " + str(ldtp.getcpustat('software-center')) + " Memory usage in MB: " + str(ldtp.getmemorystat('software-center'))
        self.msgs.append(c)
        print '\n'.join(self.msgs)

    def test_1(self):
        ldtp.waittillguiexist('frmUbuntuSoftwareCent*', 'btnAccessories')
        assert ldtp.objectexist('frmUbuntuSoftwareCent*', 'btnAccessories')
        b = "Time taken from start to find the Accessories button " + str(
            time.time() - start_time) + " Cpu percentage: " + str(ldtp.getcpustat('software-center')) + " Memory usage in MB: " + str(ldtp.getmemorystat('software-center'))
        self.msgs.append(b)


if __name__ == "__main__":
    unittest.main()
