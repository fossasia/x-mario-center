'''apport package hook for software-center

(c) 2011 Canonical Ltd.
Author: Brian Murray <brian@ubuntu.com>
'''

from apport.hookutils import attach_file_if_exists
import os


def add_info(report):
    attach_file_if_exists(report,
        os.path.expanduser('~/.cache/software-center/software-center.log'),
        'SoftwareCenterLog')
