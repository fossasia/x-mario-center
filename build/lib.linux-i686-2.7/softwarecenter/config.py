# Copyright (C) 20011 Canonical
#
# Authors:
#  Andrew Higginson
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

# py3 compat
try:
    from configparser import SafeConfigParser
    SafeConfigParser  # pyflakes
except ImportError:
    from ConfigParser import SafeConfigParser
import os
import logging

from paths import SOFTWARE_CENTER_CONFIG_FILE

LOG = logging.getLogger(__name__)


class SoftwareCenterConfig(SafeConfigParser):

    def __init__(self, config):
        SafeConfigParser.__init__(self)
        from utils import safe_makedirs
        safe_makedirs(os.path.dirname(config))
        # we always want this section, even on fresh installs
        self.add_section("general")
        # read the config
        self.configfile = config
        try:
            self.read(self.configfile)
        except Exception as e:
            # don't crash on a corrupted config file
            LOG.warn("Could not read the config file '%s': %s",
                     self.configfile, e)
            pass

    def write(self):
        tmpname = self.configfile + ".new"
        # see LP: #996333, its ok to remove the old configfile as
        # its rewritten anyway
        from utils import ensure_file_writable_and_delete_if_not
        ensure_file_writable_and_delete_if_not(tmpname)
        ensure_file_writable_and_delete_if_not(self.configfile)
        try:
            f = open(tmpname, "w")
            SafeConfigParser.write(self, f)
            f.close()
            os.rename(tmpname, self.configfile)
        except Exception as e:
            # don't crash if there's an error when writing to the config file
            # (LP: #996333)
            LOG.warn("Could not write the config file '%s': %s",
                     self.configfile, e)
            pass


_software_center_config = None


def get_config(filename=SOFTWARE_CENTER_CONFIG_FILE):
    """ get the global config class """
    global _software_center_config
    if not _software_center_config:
        _software_center_config = SoftwareCenterConfig(filename)
    return _software_center_config
