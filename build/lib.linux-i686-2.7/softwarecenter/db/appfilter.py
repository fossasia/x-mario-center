import xapian

from softwarecenter.distro import get_distro
from softwarecenter.enums import (XapianValues,
                                  AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME,
                                  )


class GlobalFilter(object):
    def __init__(self):
        self.supported_only = False

global_filter = GlobalFilter()


def get_global_filter():
    return global_filter


class AppFilter(xapian.MatchDecider):
    """
    Filter that can be hooked into xapian get_mset to filter for criteria that
    are based around the package details that are not listed in xapian
    (like installed_only) or archive section
    """
    def __init__(self, db, cache):
        xapian.MatchDecider.__init__(self)
        self.distro = get_distro()
        self.db = db
        self.cache = cache
        self.available_only = False
        self.supported_only = global_filter.supported_only
        self.installed_only = False
        self.not_installed_only = False
        self.restricted_list = False

    @property
    def required(self):
        """True if the filter is in a state that it should be part of a
           query
        """
        return (self.available_only or
                global_filter.supported_only or
                self.installed_only or
                self.not_installed_only or
                self.restricted_list)

    def set_available_only(self, v):
        self.available_only = v

    def set_supported_only(self, v):
        global_filter.supported_only = v

    def set_installed_only(self, v):
        self.installed_only = v

    def set_not_installed_only(self, v):
        self.not_installed_only = v

    def set_restricted_list(self, v):
        self.restricted_list = v

    def get_supported_only(self):
        return global_filter.supported_only

    def __eq__(self, other):
        if self is None and other is not None:
            return True
        if self is None or other is None:
            return False
        return (self.installed_only == other.installed_only and
                self.not_installed_only == other.not_installed_only and
                global_filter.supported_only == other.supported_only and
                self.restricted_list == other.restricted_list)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __call__(self, doc):
        """return True if the package should be displayed"""
        # get pkgname from document
        pkgname = self.db.get_pkgname(doc)
        #logging.debug(
        #    "filter: supported_only: %s installed_only: %s '%s'" % (
        #        self.supported_only, self.installed_only, pkgname))
        if self.available_only:
            # an item is considered available if it is either found
            # in the cache or is available for purchase
            if (not pkgname in self.cache and
                not doc.get_value(XapianValues.ARCHIVE_CHANNEL) ==
                    AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME):
                return False
        if self.installed_only:
            if (not pkgname in self.cache or
                not self.cache[pkgname].is_installed):
                return False
        if self.not_installed_only:
            if (pkgname in self.cache and
                self.cache[pkgname].is_installed):
                return False
        if global_filter.supported_only:
            if not self.distro.is_supported(self.cache, doc, pkgname):
                return False
        if self.restricted_list != False:  # keep != False as the set can be
                                           # empty
            if not pkgname in self.restricted_list:
                return False
        return True

    def copy(self):
        """ create a new copy of the given filter """
        new_filter = AppFilter(self.db, self.cache)
        new_filter.available_only = self.available_only
        new_filter.installed_only = self.installed_only
        new_filter.not_installed_only = self.not_installed_only
        new_filter.restricted_list = self.restricted_list
        return new_filter

    def reset(self):
        """ reset the values that are not global """
        self.available_only = False
        self.installed_only = False
        self.not_installed_only = False
        self.restricted_list = False
