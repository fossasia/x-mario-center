#!/usr/bin/env python

import platform
import distutils
import fnmatch
import glob
import os
import re
from subprocess import call
import sys

from distutils.core import setup
from DistUtilsExtra.command import (build_extra, build_i18n, build_help,
                                    build_icons)


class PocketLint(distutils.cmd.Command):
    """ command class that runs pocketlint """
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def binary_in_path(self, binary):
        return any([os.path.exists(os.path.join(p, binary))
                    for p in os.environ["PATH"].split(":")])

    def run(self):
        if not self.binary_in_path("pocketlint"):
            sys.stderr.write("No pocketlint found in path\n"
                             "Use python-pocket-lint in natty or from "
                             "ppa:sinzui\n")
            return
        py_files = []
        for root, dirs, files in os.walk("."):
            pyl = fnmatch.filter(files, "*.py")
            py_files.extend([os.path.join(root, f) for f in pyl
                             if os.path.exists(os.path.join(root, f))])
        call(["pocketlint"] + py_files)


def merge_authors_into_about_dialog():
    fname = "./data/ui/gtk3/SoftwareCenter.ui"
    authors = open("AUTHORS").read()
    gtkbuilder = open(fname).read()
    gtkbuilder = re.sub(r'<property name="authors">.*?</property>',
                        r'<property name="authors">%s</property>' % authors,
                        gtkbuilder, flags=re.DOTALL)
    open(fname, "w").write(gtkbuilder)


def merge_extras_ubuntu_com_channel_file():
    # update ubuntu-extras.list.in (this will not be part of debian as
    # its killed of in debian/rules on a non-ubuntu build)
    DISTROSERIES = platform.dist()[2]
    channelfile = "data/channels/Ubuntu/ubuntu-extras.list"
    s = open(channelfile + ".in").read()
    open(channelfile, "w").write(s.replace("#DISTROSERIES#", DISTROSERIES))


# update version.py
line = open("debian/changelog").readline()
m = re.match("^[\w-]+ \(([\w\.~]+)\) ([\w-]+);", line)
VERSION = m.group(1)
CODENAME = m.group(2)
DISTRO = platform.dist()[0]
RELEASE = platform.dist()[1]
open("softwarecenter/version.py", "w").write("""
VERSION='%s'
CODENAME='%s'
DISTRO='%s'
RELEASE='%s'
""" % (VERSION, CODENAME, DISTRO, RELEASE))


# update po4a
if sys.argv[1] == "build":
    merge_authors_into_about_dialog()
    merge_extras_ubuntu_com_channel_file()
    call(["po4a", "po/help/po4a.conf"])

# real setup
setup(name="software-center", version=VERSION,
      scripts=["software-center",
               # gtk3
               "utils/submit_review_gtk3.py",
               "utils/report_review_gtk3.py",
               "utils/submit_usefulness_gtk3.py",
               "utils/delete_review_gtk3.py",
               "utils/modify_review_gtk3.py",
               # db helpers
               "utils/update-software-center",
               "utils/update-software-center-channels",
               "utils/update-software-center-agent",
               # generic helpers
               "utils/expunge-cache.py",
               ] + glob.glob("utils/piston-helpers/*.py"),
      packages=['softwarecenter',
                'softwarecenter.backend',
                'softwarecenter.backend.installbackend_impl',
                'softwarecenter.backend.channel_impl',
                'softwarecenter.backend.oneconfhandler',
                'softwarecenter.backend.piston',
                'softwarecenter.backend.reviews',
                'softwarecenter.db',
                'softwarecenter.db.pkginfo_impl',
                'softwarecenter.db.history_impl',
                'softwarecenter.distro',
                'softwarecenter.ui',
                'softwarecenter.ui.gtk3',
                'softwarecenter.ui.gtk3.dialogs',
                'softwarecenter.ui.gtk3.models',
                'softwarecenter.ui.gtk3.panes',
                'softwarecenter.ui.gtk3.session',
                'softwarecenter.ui.gtk3.views',
                'softwarecenter.ui.gtk3.widgets',
                'softwarecenter.ui.qml',
                ],
      data_files=[
                  # gtk3
                  ('share/software-center/ui/gtk3/',
                   glob.glob("data/ui/gtk3/*.ui")),
                  ('share/software-center/ui/gtk3/css/',
                   glob.glob("data/ui/gtk3/css/*.css")),
                  ('share/software-center/ui/gtk3/art/',
                   glob.glob("data/ui/gtk3/art/*.png")),
                  ('share/software-center/ui/gtk3/art/icons',
                   glob.glob("data/ui/gtk3/art/icons/*.png")),
                  ('share/software-center/default_banner',
                   glob.glob("data/default_banner/*")),
                  # dbus
                  ('../etc/dbus-1/system.d/',
                   ["data/com.ubuntu.SoftwareCenter.conf"]),
                  # images
                  ('share/software-center/images/',
                   glob.glob("data/images/*.png") +
                   glob.glob("data/images/*.gif")),
                  ('share/software-center/icons/',
                   glob.glob("data/emblems/*.png")),
                  # xapian
                  ('share/apt-xapian-index/plugins',
                   glob.glob("apt-xapian-index-plugin/*.py")),
                  # apport
                  ('share/apport/package-hooks/',
                   ['debian/source_software-center.py']),
                  # extra software channels (can be distro specific)
                  ('/usr/share/app-install/channels/',
                   glob.glob("data/channels/%s/*" % DISTRO)),
                  ],
      cmdclass={"build": build_extra.build_extra,
                "build_i18n": build_i18n.build_i18n,
                "build_help": build_help.build_help,
                "build_icons": build_icons.build_icons,
                "lint": PocketLint,
                },
      )
