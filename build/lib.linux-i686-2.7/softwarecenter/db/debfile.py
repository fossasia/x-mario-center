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

import os

from apt.debfile import DebPackage
from gettext import gettext as _
from mimetypes import guess_type

from softwarecenter.db.application import Application, AppDetails
from softwarecenter.enums import PkgStates
from softwarecenter.utils import ExecutionTime, utf8


DEB_MIME_TYPE = 'application/x-debian-package'


def is_deb_file(debfile):
    mtype = guess_type(debfile)
    return mtype is not None and DEB_MIME_TYPE in mtype


class DebFileOpenError(Exception):
    """ Raised if a DebFile fails to open """

    def __init__(self, msg, path):
        super(DebFileOpenError, self).__init__(msg)
        self.path = path


class DebFileApplication(Application):

    def __init__(self, debfile):
        if not is_deb_file(debfile):
            raise DebFileOpenError("Could not open %r." % debfile, debfile)

        # work out debname/appname
        debname = os.path.splitext(os.path.basename(debfile))[0]
        pkgname = debname.split('_')[0].lower()
        # call the constructor
        Application.__init__(self, pkgname=pkgname, request=debfile)

    def get_details(self, db):
        with ExecutionTime("get_details for DebFileApplication"):
            details = AppDetailsDebFile(db, application=self)
        return details


class AppDetailsDebFile(AppDetails):

    def __init__(self, db, doc=None, application=None):
        super(AppDetailsDebFile, self).__init__(db, doc, application)
        if doc:
            raise DebFileOpenError("AppDetailsDebFile: doc must be None.")

        self._error = None
        # check errors before creating the DebPackage
        if not os.path.exists(self._app.request):
            self._error = _("Not found")
            self._error_not_found = utf8(_(u"The file \u201c%s\u201d "
                "does not exist.")) % utf8(self._app.request)
        elif not is_deb_file(self._app.request):
            self._error = _("Not found")
            self._error_not_found = utf8(_(u"The file \u201c%s\u201d "
                "is not a software package.")) % utf8(self._app.request)

        if self._error is not None:
            return

        try:
            with ExecutionTime("create DebPackage"):
                # Cache() used to be faster here than self._cache._cache
                # but that is no longer the case with the latest apt
                self._deb = DebPackage(self._app.request, self._cache._cache)
        except:
            self._deb = None
            # deb files which are corrupt
            self._error = _("Internal Error")
            self._error_not_found = utf8(_(u"The file \u201c%s\u201d "
                "could not be opened.")) % utf8(self._app.request)
            return

        if self.pkgname and self.pkgname != self._app.pkgname:
            # this happens when the deb file has a quirky file name
            self._app.pkgname = self.pkgname

            # load pkg cache
            self._pkg = None
            if (self._app.pkgname in self._cache and
                self._cache[self._app.pkgname].candidate):
                self._pkg = self._cache[self._app.pkgname]
            # load xapian document
            self._doc = None
            try:
                self._doc = self._db.get_xapian_document(
                    self._app.appname, self._app.pkgname)
            except:
                pass

        # check deb and set failure state on error
        with ExecutionTime("AppDetailsDebFile._deb.check()"):
            if not self._deb.check():
                self._error = self._deb._failure_string.strip()

    @property
    def description(self):
        if self._deb:
            description = self._deb._sections["Description"]
            s = ('\n').join(description.split('\n')[1:]).replace(" .\n", "")
            return utf8(s)
        return ""

    @property
    def maintenance_status(self):
        pass

    @property
    def pkgname(self):
        if self._deb:
            return self._deb._sections["Package"]

    @property
    def pkg_state(self):
        if self._error:
            if self._error_not_found:
                return PkgStates.NOT_FOUND
            else:
                return PkgStates.ERROR
        if self._deb:
            deb_state = self._deb.compare_to_version_in_cache()
            if deb_state == DebPackage.VERSION_NONE:
                return PkgStates.UNINSTALLED
            elif deb_state == DebPackage.VERSION_OUTDATED:
                if self._cache[self.pkgname].installed:
                    return PkgStates.INSTALLED
                else:
                    return PkgStates.UNINSTALLED
            elif deb_state == DebPackage.VERSION_SAME:
                return PkgStates.REINSTALLABLE
            elif deb_state == DebPackage.VERSION_NEWER:
                if self._cache[self.pkgname].installed:
                    return PkgStates.UPGRADABLE
                else:
                    return PkgStates.UNINSTALLED

    @property
    def summary(self):
        if self._deb:
            description = self._deb._sections["Description"]
            # ensure its utf8(), see #738771
            return utf8(description.split('\n')[0])

    @property
    def display_summary(self):
        if self._doc:
            name = self._db.get_appname(self._doc)
            if name:
                return self.summary
            else:
                # by spec..
                return self._db.get_pkgname(self._doc)
        return self.summary

    @property
    def version(self):
        if self._deb:
            return self._deb._sections["Version"]

    @property
    def installed_size(self):
        installed_size = 0
        if self._deb:
            try:
                installed_size = long(self._deb._sections["Installed-Size"])
            except:
                pass
        return installed_size * 1024

    @property
    def warning(self):
        # FIXME: use more concise warnings
        if self._deb:
            deb_state = self._deb.compare_to_version_in_cache(
                use_installed=False)
            if deb_state == DebPackage.VERSION_NONE:
                return utf8(
                    _("Only install this file if you trust the origin."))
            elif (not self._cache[self.pkgname].installed and
                  self._cache[self.pkgname].candidate and
                  self._cache[self.pkgname].candidate.downloadable):
                if deb_state == DebPackage.VERSION_OUTDATED:
                    return utf8(_("Please install \"%s\" via your normal "
                        "software channels. Only install this file if you "
                        "trust the origin.")) % utf8(self.name)
                elif deb_state == DebPackage.VERSION_SAME:
                    return utf8(_("Please install \"%s\" via your normal "
                        "software channels. Only install this file if you "
                        "trust the origin.")) % utf8(self.name)
                elif deb_state == DebPackage.VERSION_NEWER:
                    return utf8(_("An older version of \"%s\" is available in "
                        "your normal software channels. Only install this "
                        "file if you trust the origin.")) % utf8(self.name)

    @property
    def website(self):
        if self._deb:
            website = None
            try:
                website = self._deb._sections["Homepage"]
            except:
                pass
            if website:
                return website
