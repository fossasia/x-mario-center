# Copyright (C) 2010 Canonical
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

from gi.repository import GObject


class _Version:
    @property
    def description(self):
        pass

    @property
    def downloadable(self):
        pass

    @property
    def summary(self):
        pass

    @property
    def size(self):
        return self.pkginfo.get_size(self.name)

    @property
    def installed_size(self):
        return 0

    @property
    def version(self):
        pass

    @property
    def origins(self):
        return []

    @property
    def not_automatic(self):
        """ should not be installed/upgraded automatically, the user needs
            to opt-in once (used for e.g. ubuntu-backports)
        """
        return False


class _Package:
    def __init__(self, name, pkginfo):
        self.name = name
        self.pkginfo = pkginfo

    def __str__(self):
        return repr(self).replace('<', '<pkgname=%s ' % self.name)

    @property
    def installed(self):
        """ returns a _Version object """
        if self.pkginfo.is_installed(self.name):
            return self.pkginfo.get_installed(self.name)

    @property
    def candidate(self):
        """ returns a _Version object """
        return self.pkginfo.get_candidate(self.name)

    @property
    def versions(self):
        """ a list of available versions (as _Version) to install """
        return self.pkginfo.get_versions(self.name)

    @property
    def is_installed(self):
        return self.pkginfo.is_installed(self.name)

    @property
    def is_upgradable(self):
        return self.pkginfo.is_upgradable(self.name)

    @property
    def section(self):
        return self.pkginfo.get_section(self.name)

    @property
    def website(self):
        return self.pkginfo.get_website(self.name)

    @property
    def installed_files(self):
        return self.pkginfo.get_installed_files(self.name)

    @property
    def description(self):
        return self.pkginfo.get_description(self.name)

    @property
    def license(self):
        return self.pkginfo.get_license(self.name)


class PackageInfo(GObject.GObject):
    """ abstract interface for the packageinfo information """

    __gsignals__ = {'cache-ready': (GObject.SIGNAL_RUN_FIRST,
                                    GObject.TYPE_NONE,
                                    ()),
                    'cache-invalid': (GObject.SIGNAL_RUN_FIRST,
                                      GObject.TYPE_NONE,
                                      ()),
                    'cache-broken': (GObject.SIGNAL_RUN_FIRST,
                                      GObject.TYPE_NONE,
                                      ()),
                    }

    def __getitem__(self, k):
        return _Package(k, self)

    def __contains__(self, pkgname):
        return False

    @staticmethod
    def version_compare(v1, v2):
        """ compare two versions """
        return cmp(v1, v2)

    @staticmethod
    def upstream_version_compare(v1, v2):
        """ compare two versions, but ignore the distro specific revisions """
        return cmp(v1, v2)

    @staticmethod
    def upstream_version(v):
        """ Return the "upstream" version number of the given version """
        return v

    def is_installed(self, pkgname):
        pass

    def is_available(self, pkgname):
        pass

    def get_installed(self, pkgname):
        pass

    def get_candidate(self, pkgname):
        pass

    def get_versions(self, pkgname):
        return []

    def get_section(self, pkgname):
        pass

    def get_summary(self, pkgname):
        pass

    def get_description(self, pkgname):
        pass

    def get_website(self, pkgname):
        pass

    def get_installed_files(self, pkgname):
        return []

    def get_size(self, pkgname):
        return -1

    def get_installed_size(self, pkgname):
        return -1

    def get_origins(self, pkgname):
        return []

    def get_origin(self, pkgname):
        """ :return: unique origin as string """
        return ''

    def get_addons(self, pkgname, ignore_installed=False):
        """ :return: a tuple of pkgnames (recommends, suggests) """
        return ([], [])

    def get_packages_removed_on_remove(self, pkg):
        """ Returns a package names list of reverse dependencies
        which will be removed if the package is removed."""
        return []

    def get_packages_removed_on_install(self, pkg):
        """ Returns a package names list of dependencies
        which will be removed if the package is installed."""
        return []

    def get_total_size_on_install(self, pkgname,
                                  addons_install=None, addons_remove=None,
                                  archive_suite=None):
        """ Returns a tuple (download_size, installed_size)
        with disk size in KB calculated for pkgname installation
        plus addons change and a (optional) archive_suite that the
        package comes from
        """
        return (0, 0)

    def open(self):
        """
        (re)open the cache, this sends cache-invalid, cache-ready signals
        """
        pass

    @property
    def ready(self):
        pass

# singleton
pkginfo = None


def get_pkg_info():
    global pkginfo
    if pkginfo is None:
        from softwarecenter.enums import USE_PACKAGEKIT_BACKEND
        if not USE_PACKAGEKIT_BACKEND:
            from softwarecenter.db.pkginfo_impl.aptcache import AptCache
            pkginfo = AptCache()
        else:
            from softwarecenter.db.pkginfo_impl.packagekit import (
                PackagekitInfo,
            )
            pkginfo = PackagekitInfo()
    return pkginfo
