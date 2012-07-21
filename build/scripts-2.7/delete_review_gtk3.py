#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

from gi.repository import Gtk

import gettext
import locale
import logging
import logging.handlers
import os
import sys

from gettext import gettext as _
from optparse import OptionParser

import softwarecenter.paths
from softwarecenter.paths import SOFTWARE_CENTER_CACHE_DIR
from softwarecenter.db.database import Application

from softwarecenter.ui.gtk3.review_gui_helper import (
    DeleteReviewApp,
    ReportReviewApp,
    SubmitReviewsApp,
    SubmitUsefulnessApp,
    )

#import httplib2
#httplib2.debuglevel = 1

# the glib docs tell us that this is no longer needed, but if its omited
# the system will hang on submit *sigh*
from gi.repository import GLib
GLib.threads_init()

if __name__ == "__main__":
    try:
        locale.setlocale(locale.LC_ALL, "")
    except:
        logging.exception("setlocale failed, resetting to C")
        locale.setlocale(locale.LC_ALL, "C")

    gettext.bindtextdomain("software-center", "/usr/share/locale")
    gettext.textdomain("software-center")

    if os.path.exists("./data/ui/gtk3/submit_review.ui"):
        default_datadir = "./data"
    else:
        default_datadir = "/usr/share/software-center/"

    # common options for optparse go here
    parser = OptionParser()
    parser.add_option("", "--datadir", default=default_datadir)

    logfile_path = os.path.join(
        SOFTWARE_CENTER_CACHE_DIR, "reviews-helper.log")
    logfile_handler = logging.handlers.RotatingFileHandler(
        logfile_path, maxBytes = 100 * 1000, backupCount = 5)
    logfile_handler.setLevel(logging.INFO)
    logging.getLogger().addHandler(logfile_handler)
    logging.getLogger().addHandler(logging.StreamHandler())

    # run review personality
    if "submit_review" in sys.argv[0]:
        # check options
        parser.add_option("-a", "--appname")
        parser.add_option("-p", "--pkgname")
        parser.add_option("-i", "--iconname")
        parser.add_option("-V", "--version")
        parser.add_option("-O", "--origin")
        parser.add_option("", "--parent-xid")
        parser.add_option("", "--test", action="store_true", default=False)
        parser.add_option("", "--debug",
                          action="store_true", default=False)
        (options, args) = parser.parse_args()

        softwarecenter.paths.datadir = options.datadir

        if options.test:
            options.pkgname = options.pkgname or 'apt'
            options.appname = options.appname or 'Apt'
            options.iconname = options.iconname or 'folder'
            options.version = options.version or '1.0'
            options.origin = options.origin or 'Ubuntu'
            options.parent_xid = options.parent_xid or '1'

        if not (options.pkgname and options.version):
            parser.error(_("Missing arguments"))

        if options.debug:
            logging.basicConfig(level=logging.DEBUG)

        # personality
        logging.debug("submit_review mode")

        # initialize and run
        theapp = Application(options.appname, options.pkgname)
        review_app = SubmitReviewsApp(datadir=options.datadir,
                                      app=theapp,
                                      parent_xid=options.parent_xid,
                                      iconname=options.iconname,
                                      origin=options.origin,
                                      version=options.version)
        review_app.run()

    # run "report" personality
    if "report_review" in sys.argv[0]:
        # check options
        parser.add_option("", "--review-id") 
        parser.add_option("", "--parent-xid")
        parser.add_option("", "--debug",
                          action="store_true", default=False)
        (options, args) = parser.parse_args()

        softwarecenter.paths.datadir = options.datadir

        if not (options.review_id):
            parser.error(_("Missing review-id arguments"))

        if options.debug:
            logging.basicConfig(level=logging.DEBUG)                        

        # personality
        logging.debug("report_abuse mode")

        # initialize and run
        report_app = ReportReviewApp(datadir=options.datadir,
                                      review_id=options.review_id, 
                                      parent_xid=options.parent_xid)
        report_app.run()

    if "submit_usefulness" in sys.argv[0]:
        # check options
        parser.add_option("", "--review-id") 
        parser.add_option("", "--parent-xid")
        parser.add_option("", "--is-useful")
        parser.add_option("", "--debug",
                          action="store_true", default=False)
        (options, args) = parser.parse_args()

        softwarecenter.paths.datadir = options.datadir

        if not (options.review_id):
            parser.error(_("Missing review-id arguments"))
    
        if options.debug:
            logging.basicConfig(level=logging.DEBUG)                        

        # personality
        logging.debug("report_abuse mode")

        # initialize and run
        usefulness_app = SubmitUsefulnessApp(datadir=options.datadir,
                                         review_id=options.review_id, 
                                         parent_xid=options.parent_xid,
                                         is_useful=int(options.is_useful))
        usefulness_app.run()
    
    if "delete_review" in sys.argv[0]:
        #check options
        parser.add_option("", "--review-id")
        parser.add_option("", "--parent-xid")
        parser.add_option("", "--debug",
                          action="store_true", default=False)
        (options, args) = parser.parse_args()
        
        softwarecenter.paths.datadir = options.datadir

        if not (options.review_id):
            parser.error(_("Missing review-id argument"))
    
        if options.debug:
            logging.basicConfig(level=logging.DEBUG)
        
        logging.debug("delete review mode")
        
        delete_app = DeleteReviewApp(datadir=options.datadir,
                                    review_id=options.review_id,
                                    parent_xid=options.parent_xid)
        delete_app.run()

    if "modify_review" in sys.argv[0]:
        # check options
        parser.add_option("", "--review-id")
        parser.add_option("-i", "--iconname")
        parser.add_option("", "--parent-xid")
        parser.add_option("", "--debug",
                          action="store_true", default=False)
        (options, args) = parser.parse_args()

        softwarecenter.paths.datadir = options.datadir

        if not (options.review_id):
            parser.error(_("Missing review-id argument"))
    
        if options.debug:
            logging.basicConfig(level=logging.DEBUG)

        # personality
        logging.debug("modify_review mode")

        # initialize and run
        modify_app = SubmitReviewsApp(datadir=options.datadir,
                                      app=None, 
                                      parent_xid=options.parent_xid,
                                      iconname=options.iconname,
                                      origin=None,
                                      version=None,
                                    action="modify",
                                    review_id=options.review_id
                                    )

        modify_app.run()
        
    # main
    Gtk.main()
