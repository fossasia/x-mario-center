#!/usr/bin/python
# Copyright (C) 2012 Canonical
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

"""
Expunge httplib2 caches
"""

import argparse
import logging
import os
import sys

from softwarecenter.expunge import ExpungeCache


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='clean software-center httplib2 cache')
    parser.add_argument(
        '--debug', action="store_true",
        help='show debug output')
    parser.add_argument(
        '--dry-run', action="store_true",
        help='do not act, just show what would be done')
    parser.add_argument(
        'directories', metavar='directory', nargs='+', type=str,
        help='directories to be checked')
    parser.add_argument(
        '--by-days', type=int, default=0,
        help='expire everything older than N days')
    parser.add_argument(
        '--by-unsuccessful-http-states', action="store_true",
        help='expire any non 200 status responses')
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # sanity checking
    if args.by_days == 0 and not args.by_unsuccessful_http_states:
        print "Need either --by-days or --by-unsuccessful-http-states argument"
        sys.exit(1)

    # be nice
    os.nice(19)

    # do it
    cleaner = ExpungeCache(args.directories, 
                           args.by_days, 
                           args.by_unsuccessful_http_states,
                           args.dry_run)
    cleaner.clean()
