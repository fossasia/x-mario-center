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


import logging
import os

from gettext import gettext as _
import platform

from softwarecenter.utils import UnimplementedError, utf8

LOG = logging.getLogger(__name__)


class Distro(object):
    """ abstract base class for a distribution """

    # list of code names for the distro from newest to oldest, this is
    # used e.g. in the reviews loader if no reviews for the current codename
    # are found
    DISTROSERIES = []

    # base path for the review summary, the JS will append %i.png
    # (with i={1,5})
    REVIEW_SUMMARY_STARS_BASE_PATH = ("/usr/share/software-center/images/"
        "review-summary")
    REVIEWS_SERVER = (os.environ.get("SOFTWARE_CENTER_REVIEWS_HOST") or
        "http://localhost:8000")

    # You need to set this var to enable purchases
    PURCHASE_APP_URL = ""

    # Point developers to a web page
    DEVELOPER_URL = ""

    def __init__(self):
        """Return a new generic Distro instance."""

    def get_app_name(self):
        """
        The name of the application (as displayed in the main window and
        the about window)
        """
        return _("Software Center")

    def get_app_description(self):
        """
        The description of the application displayed in the about dialog
        """
        return _("Lets you choose from thousands of applications available "
            "for your system.")

    def get_distro_channel_name(self):
        """ The name of the main channel in the Release file (e.g. Ubuntu)"""
        return "none"

    def get_distro_channel_description(self):
        """ The description for the main distro channel """
        return "none"

    def get_codename(self):
        """ The codename of the distro, e.g. lucid """
        # for tests and similar
        if "SOFTWARE_CENTER_DISTRO_CODENAME" in os.environ:
            distrocode = os.environ["SOFTWARE_CENTER_DISTRO_CODENAME"]
            LOG.warn("overriding distro codename to '%s'" % distrocode)
            return distrocode
        # normal behavior
        if not hasattr(self, "_distro_code_name"):
            self._distro_code_name = platform.dist()[2]
        return self._distro_code_name

    def get_maintenance_status(self, cache, appname, pkgname, component,
        channelname):
        raise UnimplementedError

    def get_license_text(self, component):
        raise UnimplementedError

    def is_supported(self, cache, doc, pkgname):
        """
        return True if the given document and pkgname is supported by
        the distribution
        """
        raise UnimplementedError

    def get_supported_query(self):
        """ return a xapian query that gives all supported documents """
        import xapian
        return xapian.Query()

    def get_supported_filter_name(self):
        return _("Supported Software")

    def get_install_warning_text(self, cache, pkg, appname, depends):
        primary = (utf8(_("To install %s, these items must be removed:")) %
            utf8(appname))
        button_text = _("Install Anyway")

        # alter it if a meta-package is affected
        for m in depends:
            if cache[m].section == "metapackages":
                primary = utf8(_("If you install %s, future updates will not "
                                 "include new items in <b>%s</b> set. "
                                 "Are you sure you want to continue?")) % (
                                 utf8(appname), cache[m].installed.summary)
                button_text = _("Install Anyway")
                depends = []
                break

        # alter it if an important meta-package is affected
        for m in self.IMPORTANT_METAPACKAGES:
            if m in depends:
                primary = utf8(_("Installing %s may cause core applications "
                                 "to be removed. Are you sure you want to "
                                 "continue?")) % utf8(appname)
                button_text = _("Install Anyway")
                depends = None
                break
        return (primary, button_text)

    # generic version of deauthorize, can be customized by the distro
    def get_deauthorize_text(self, account_name, purchased_packages):
        if len(purchased_packages) == 0:
            if account_name:
                primary = _('Are you sure you want to deauthorize this '
                            'computer from the "%s" account?') % account_name
            else:
                primary = _('Are you sure you want to deauthorize this '
                            'computer for purchases?')
            button_text = _('Deauthorize')
        else:
            if account_name:
                primary = _('Deauthorizing this computer from the "%s" '
                            'account will remove this purchased '
                            'software:') % account_name
            else:
                primary = _('Deauthorizing this computer for purchases '
                            'will remove the following purchased software:')
            button_text = _('Remove All')
        return (primary, button_text)

    # generic architecture detection code
    def get_architecture(self):
        pass


def _get_distro():
    distro_info = platform.linux_distribution()
    distro_id = distro_info[0]
    LOG.debug("get_distro: '%s'", distro_id)
    # start with a import, this gives us only a softwarecenter module
    module = __import__(distro_id, globals(), locals(), [], -1)
    # get the right class and instanciate it
    distro_class = getattr(module, distro_id)
    instance = distro_class()
    return instance


def get_distro():
    """ factory to return the right Distro object """
    return distro_instance


def get_current_arch():
    # for tests and similar
    if "SOFTWARE_CENTER_ARCHITECTURE" in os.environ:
        arch = os.environ["SOFTWARE_CENTER_ARCHITECTURE"]
        LOG.warn("overriding architecture to '%s'" % arch)
        return arch
    return get_distro().get_architecture()


def get_foreign_architectures():
    return get_distro().get_foreign_architectures()

# singelton
distro_instance = _get_distro()


if __name__ == "__main__":
    print(get_distro())
