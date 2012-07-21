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

from gi.repository import GObject
import gettext
import glob
import locale
import logging
import os
import string
import xapian

from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape as xml_escape
from xml.sax.saxutils import unescape as xml_unescape

from softwarecenter.enums import (
    SortMethods, NonAppVisibility)
from softwarecenter.backend.recagent import RecommenderAgent
from softwarecenter.db.appfilter import AppFilter
from softwarecenter.db.enquire import AppEnquire
from softwarecenter.db.utils import get_query_for_pkgnames
from softwarecenter.paths import APP_INSTALL_PATH
from softwarecenter.region import get_region_cached
from softwarecenter.utils import utf8

from gettext import gettext as _

# not possible not use local logger
LOG = logging.getLogger(__name__)


def get_category_by_name(categories, untrans_name):
    # find a specific category
    cat = [cat for cat in categories if cat.untranslated_name == untrans_name]
    if cat:
        return cat[0]
    return None


#def categories_sorted_by_name(categories):
    # sort categories by name
#    sorted_catnames = []
    # first pass, sort by translated names
#    for cat in categories:
#        sorted_catnames.append(cat.name)
#    sorted_catnames = sorted(sorted_catnames, cmp=locale.strcoll)

    # second pass, assemble cats by sorted their sorted catnames
#    sorted_cats = []
#    for name in sorted_catnames:
#        for cat in categories:
#            if cat.name == name:
#                sorted_cats.append(cat)
#                break
#    return sorted_cats
def categories_sorted_by_name(categories):
    # sort categories by name
    sorted_catnames = []
    # first pass, sort by translated names
    for cat in categories:
        sorted_catnames.append(cat.name)
    #sorted_catnames = sorted(sorted_catnames, cmp=locale.strcoll)

    # second pass, assemble cats by sorted their sorted catnames
    sorted_cats = []
    for name in sorted_catnames:
        for cat in categories:
            if cat.name == name:
                sorted_cats.append(cat)
                break
    return sorted_cats


def get_query_for_category(db, untranslated_category_name):
    cat_parser = CategoriesParser(db)
    categories = cat_parser.parse_applications_menu(APP_INSTALL_PATH)
    for c in categories:
        if untranslated_category_name == c.untranslated_name:
            query = c.query
            return query
    return False


class Category(GObject.GObject):
    """represents a menu category"""
    def __init__(self, untranslated_name, name, iconname, query,
                 only_unallocated=True, dont_display=False, flags=[],
                 subcategories=[], sortmode=SortMethods.BY_ALPHABET,
                 item_limit=0):
        GObject.GObject.__init__(self)
        if type(name) == str:
            self.name = unicode(name, 'utf8').encode('utf8')
        else:
            self.name = name.encode('utf8')
        self.untranslated_name = untranslated_name
        self.iconname = iconname
        for subcategory in subcategories:
            query = xapian.Query(xapian.Query.OP_OR, query, subcategory.query)
        self.query = query
        self.only_unallocated = only_unallocated
        self.subcategories = subcategories
        self.dont_display = dont_display
        self.flags = flags
        self.sortmode = sortmode
        self.item_limit = item_limit

    @property
    def is_forced_sort_mode(self):
        return (self.sortmode != SortMethods.BY_ALPHABET)

    def get_documents(self, db):
        """ return the database docids for the given category """
        enq = AppEnquire(db._aptcache, db)
        app_filter = AppFilter(db, db._aptcache)
        if "available-only" in self.flags:
            app_filter.set_available_only(True)
        if "not-installed-only" in self.flags:
            app_filter.set_not_installed_only(True)
        enq.set_query(self.query,
                      limit=self.item_limit,
                      filter=app_filter,
                      sortmode=self.sortmode,
                      nonapps_visible=NonAppVisibility.ALWAYS_VISIBLE,
                      nonblocking_load=False)
        return enq.get_documents()

    def __str__(self):
        return "<Category: name='%s', sortmode='%s', "\
               "item_limit='%s'>" % (
                   self.name, self.sortmode, self.item_limit)


class RecommendedForYouCategory(Category):

    __gsignals__ = {
        "needs-refresh": (GObject.SIGNAL_RUN_LAST,
                          GObject.TYPE_NONE,
                          (),
                         ),
        "recommender-agent-error": (GObject.SIGNAL_RUN_LAST,
                                    GObject.TYPE_NONE,
                                    (GObject.TYPE_STRING,),
                                   ),
        }

    def __init__(self, subcategory=None):
        self.subcategory = subcategory
        if subcategory:
            # this is the set of recommendations for a given subcategory
            cat_title = u"Recommended For You in %s" % (
                                                 subcategory.untranslated_name)
            tr_title = utf8(_("Recommended For You in %s")) % utf8(
                                                              subcategory.name)
        else:
            # this is the full set of recommendations for e.g. the lobby view
            cat_title = u"Recommended For You"
            tr_title = _("Recommended For You")
        super(RecommendedForYouCategory, self).__init__(
                cat_title,
                tr_title,
                None,
                xapian.Query(),
                flags=['available-only', 'not-installed-only'],
                item_limit=60)
        self.recommender_agent = RecommenderAgent()
        self.recommender_agent.connect(
            "recommend-me", self._recommend_me_result)
        self.recommender_agent.connect(
            "error", self._recommender_agent_error)
        self.recommender_agent.query_recommend_me()

    def _recommend_me_result(self, recommender_agent, result_list):
        pkgs = []
        for item in result_list['data']:
            pkgs.append(item['package_name'])
        if self.subcategory:
            self.query = xapian.Query(xapian.Query.OP_AND,
                                  get_query_for_pkgnames(pkgs),
                                  self.subcategory.query)
        else:
            self.query = get_query_for_pkgnames(pkgs)
        self.emit("needs-refresh")

    def _recommender_agent_error(self, recommender_agent, msg):
        LOG.warn("Error while accessing the recommender service: %s"
                                                            % msg)
        self.emit("recommender-agent-error", msg)


class AppRecommendationsCategory(Category):

    __gsignals__ = {
        "needs-refresh": (GObject.SIGNAL_RUN_LAST,
                          GObject.TYPE_NONE,
                          (),
                         ),
        "recommender-agent-error": (GObject.SIGNAL_RUN_LAST,
                                    GObject.TYPE_NONE,
                                    (GObject.TYPE_STRING,),
                                   ),
        }

    def __init__(self, pkgname):
        super(AppRecommendationsCategory, self).__init__(
                u"People Also Installed",
                _(u"People Also Installed"),
                None,
                xapian.Query(),
                flags=['available-only', 'not-installed-only'],
                item_limit=4)
        self.recommender_agent = RecommenderAgent()
        self.recommender_agent.connect(
            "recommend-app", self._recommend_app_result)
        self.recommender_agent.connect(
            "error", self._recommender_agent_error)
        self.recommender_agent.query_recommend_app(pkgname)

    def _recommend_app_result(self, recommender_agent, result_list):
        pkgs = []
        for item in result_list['data']:
            pkgs.append(item['package_name'])
        self.query = get_query_for_pkgnames(pkgs)
        self.emit("needs-refresh")

    def _recommender_agent_error(self, recommender_agent, msg):
        LOG.warn("Error while accessing the recommender service: %s"
                                                            % msg)
        self.emit("recommender-agent-error", msg)


class CategoriesParser(object):
    """
    Parser that is able to read the categories from a menu file
    """

    def __init__(self, db):
        self.db = db
        # build the string substituion support
        self._build_string_template_dict()

    def parse_applications_menu(self, datadir):
        """ parse a application menu and return a list of Category objects """
        categories = []
        # we support multiple menu files and menu drop ins
        menu_files = [datadir + "/desktop/software-center.menu"]
        menu_files += glob.glob(datadir + "/menu.d/*.menu")
        for f in menu_files:
            if not os.path.exists(f):
                continue            
            tree = ET.parse(f)
            root = tree.getroot()            
            for child in root.getchildren():
                category = None
                if child.tag == "Menu":
                    category = self._parse_menu_tag(child)
                if category:
                    categories.append(category)
        # post processing for <OnlyUnallocated>
        # now build the unallocated queries, once for top-level,
        # and for the subcategories. this means that subcategories
        # can have a "OnlyUnallocated/" that applies only to
        # unallocated entries in their sublevel
        for cat in categories:
            self._build_unallocated_queries(cat.subcategories)
        self._build_unallocated_queries(categories)

        # debug print
        for cat in categories:
            LOG.debug("%s %s %s" % (cat.name, cat.iconname, cat.query))
            print ("%s " % (cat.name))
        return categories

    def _build_string_template_dict(self):
        """ this build the dict used to substitute menu entries dynamically,
            currently used for the CURRENT_REGION
        """
        region = "%s" % get_region_cached()["countrycode"]
        self._template_dict = {'CURRENT_REGION': region}

    def _substitute_string_if_needed(self, t):
        """ substitute the given string with the current supported dynamic
            menu keys
        """
        return string.Template(t).substitute(self._template_dict)

    def _cat_sort_cmp(self, a, b):
        """sort helper for the categories sorting"""
        #print "cmp: ", a.name, b.name
        if a.untranslated_name == "System":
            return 1
        elif b.untranslated_name == "System":
            return -1
        elif a.untranslated_name == "Developer Tools":
            return 1
        elif b.untranslated_name == "Developer Tools":
            return -1
        return locale.strcoll(a.name, b.name)

    def _parse_directory_tag(self, element):
        from softwarecenter.db.update import DesktopConfigParser
        cp = DesktopConfigParser()
        fname = "/usr/share/desktop-directories/%s" % element.text
        if not os.path.exists(fname):
            return None
        LOG.debug("reading '%s'" % fname)
        cp.read(fname)
        try:
            untranslated_name = name = cp.get("Desktop Entry", "Name")
        except Exception:
            LOG.warn("'%s' has no name" % fname)
            return None
        try:
            gettext_domain = cp.get("Desktop Entry", "X-Ubuntu-Gettext-Domain")
        except:
            gettext_domain = None
        try:
            icon = cp.get("Desktop Entry", "Icon")
        except Exception:
            icon = "applications-other"
        name = cp.get_desktop("Name", translated=True)
        return (untranslated_name, name, gettext_domain, icon)

    def _parse_flags_tag(self, element):
        flags = []
        for an_elem in element.getchildren():
            flags.append(an_elem.text)
        return flags

    def _parse_and_or_not_tag(self, element, query, xapian_op):
        """parse a <And>, <Or>, <Not> tag """
        for operator_elem in element.getchildren():
            # get the query-text
            if operator_elem.text:
                qtext = self._substitute_string_if_needed(
                    operator_elem.text).lower()
            # parse the indivdual element
            if operator_elem.tag == "Not":
                query = self._parse_and_or_not_tag(
                    operator_elem, query, xapian.Query.OP_AND_NOT)
            elif operator_elem.tag == "Or":
                or_elem = self._parse_and_or_not_tag(
                    operator_elem, xapian.Query(), xapian.Query.OP_OR)
                query = xapian.Query(xapian.Query.OP_AND, or_elem, query)
            elif operator_elem.tag == "Category":
                LOG.debug("adding: %s" % operator_elem.text)
                q = xapian.Query("AC" + qtext)
                query = xapian.Query(xapian_op, query, q)
            elif operator_elem.tag == "SCSection":
                LOG.debug("adding section: %s" % operator_elem.text)
                # we have the section once in apt-xapian-index and once
                # in our own DB this is why we need two prefixes
                # FIXME: ponder if it makes sense to simply write
                #        out XS in update-software-center instead of AE?
                q = xapian.Query(xapian.Query.OP_OR,
                                 xapian.Query("XS" + qtext),
                                 xapian.Query("AE" + qtext))
                query = xapian.Query(xapian_op, query, q)
            elif operator_elem.tag == "SCType":
                LOG.debug("adding type: %s" % operator_elem.text)
                q = xapian.Query("AT" + qtext)
                query = xapian.Query(xapian_op, query, q)
            elif operator_elem.tag == "SCDebtag":
                LOG.debug("adding debtag: %s" % operator_elem.text)
                q = xapian.Query("XT" + qtext)
                query = xapian.Query(xapian_op, query, q)
            elif operator_elem.tag == "SCChannel":
                LOG.debug("adding channel: %s" % operator_elem.text)
                q = xapian.Query("AH" + qtext)
                query = xapian.Query(xapian_op, query, q)
            elif operator_elem.tag == "SCOrigin":
                LOG.debug("adding origin: %s" % operator_elem.text)
                # FIXME: origin is currently case-sensitive?!?
                q = xapian.Query("XOO" + operator_elem.text)
                query = xapian.Query(xapian_op, query, q)
            elif operator_elem.tag == "SCPkgname":
                LOG.debug("adding tag: %s" % operator_elem.text)
                # query both axi and s-c
                q1 = xapian.Query("AP" + qtext)
                q = xapian.Query(xapian.Query.OP_OR, q1,
                                 xapian.Query("XP" + qtext))
                query = xapian.Query(xapian_op, query, q)
            elif operator_elem.tag == "SCPkgnameWildcard":
                LOG.debug("adding tag: %s" % operator_elem.text)
                # query both axi and s-c
                s = "pkg_wildcard:%s" % qtext
                q = self.db.xapian_parser.parse_query(s,
                    xapian.QueryParser.FLAG_WILDCARD)
                query = xapian.Query(xapian_op, query, q)
            else:
                LOG.warn("UNHANDLED: %s %s" % (operator_elem.tag,
                    operator_elem.text))
        return query

    def _parse_include_tag(self, element):
        for include in element.getchildren():
            if include.tag == "Or":
                query = xapian.Query()
                return self._parse_and_or_not_tag(include, query,
                    xapian.Query.OP_OR)
            if include.tag == "And":
                query = xapian.Query("")
                return self._parse_and_or_not_tag(include, query,
                    xapian.Query.OP_AND)
            # without "and" tag we take the first entry
            elif include.tag == "Category":
                return xapian.Query("AC" + include.text.lower())
            else:
                LOG.warn("UNHANDLED: _parse_include_tag: %s" % include.tag)
        # empty query matches all
        return xapian.Query("")

    def _parse_menu_tag(self, item):
        name = None
        untranslated_name = None
        query = None
        icon = None
        only_unallocated = False
        dont_display = False
        flags = []
        subcategories = []
        sortmode = SortMethods.BY_ALPHABET
        item_limit = 0
        for element in item.getchildren():
            # ignore inline translations, we use gettext for this
            if (element.tag == "Name" and
                '{http://www.w3.org/XML/1998/namespace}lang' in
                element.attrib):
                continue
            if element.tag == "Name":
                untranslated_name = element.text
                # gettext/xml writes stuff from software-center.menu
                # out into the pot as escaped xml, so we need to escape
                # the name first, get the translation and unscape it again
                escaped_name = xml_escape(untranslated_name)
                name = xml_unescape(gettext.gettext(escaped_name))
            elif element.tag == "SCIcon":
                icon = element.text
            elif element.tag == 'Flags':
                flags = self._parse_flags_tag(element)
            elif element.tag == "Directory":
                l = self._parse_directory_tag(element)
                if l:
                    (untranslated_name, name, gettext_domain, icon) = l
            elif element.tag == "Include":
                query = self._parse_include_tag(element)
            elif element.tag == "OnlyUnallocated":
                only_unallocated = True
            elif element.tag == "SCDontDisplay":
                dont_display = True
            elif element.tag == "SCSortMode":
                sortmode = int(element.text)
                if not self._verify_supported_sort_mode(sortmode):
                    return None
            elif element.tag == "SCItemLimit":
                item_limit = int(element.text)
            elif element.tag == "Menu":
                subcat = self._parse_menu_tag(element)
                if subcat:
                    subcategories.append(subcat)
            else:
                LOG.warn("UNHANDLED tag in _parse_menu_tag: %s" % element.tag)

        if untranslated_name and query:
            return Category(untranslated_name, name, icon, query,
                only_unallocated, dont_display, flags, subcategories,
                sortmode, item_limit)
        else:
            LOG.warn("UNHANDLED entry: %s %s %s %s" % (name,
                                                       untranslated_name,
                                                       icon,
                                                       query))
        return None

    def _verify_supported_sort_mode(self, sortmode):
        """ verify that we use a sortmode that we know and can handle """
        # always supported
        if sortmode in (SortMethods.UNSORTED,
                        SortMethods.BY_ALPHABET,
                        SortMethods.BY_TOP_RATED,
                        SortMethods.BY_SEARCH_RANKING):
            return True
        # only supported with a apt-xapian-index version that has the
        # "catalogedtime" value
        elif sortmode == SortMethods.BY_CATALOGED_TIME:
            if self.db._axi_values and "catalogedtime" in self.db._axi_values:
                return True
            else:
                LOG.warn("sort by cataloged time requested but your a-x-i "
                             "does not seem to support that yet")
                return False
        # we don't know this sortmode
        LOG.error("unknown sort mode '%i'" % sortmode)
        return False

    def _build_unallocated_queries(self, categories):
        for cat_unalloc in categories:
            if not cat_unalloc.only_unallocated:
                continue
            for cat in categories:
                if cat.name != cat_unalloc.name:
                    cat_unalloc.query = xapian.Query(xapian.Query.OP_AND_NOT,
                        cat_unalloc.query, cat.query)
            #print cat_unalloc.name, cat_unalloc.query
        return


# static category mapping for the tiles

category_cat = {
'Utility': 'Accessories',
'System': 'Accessories',
'Education': 'Education',
'Game': 'Games',
'Sports': 'Games',
'Graphics': 'Graphics',
'Network': 'Internet',
'Office': 'Office',
'Science': 'Science & Engineering',
'Audio': 'Sound & Video',
'AudioVideo': 'Sound & Video',
'Video': 'Sound & Video',
'Settings': 'Themes & Tweaks',
'Accessibility': 'Universal Access',
'Development': 'Developer Tools',
'X-Publishing': 'Books & Magazines',
}

category_subcat = {
'BoardGame': 'Games;Board Games',
'CardGame': 'Games;Card Games',
'LogicGame': 'Games;Puzzles',
'RolePlaying': 'Games;Role Playing',
'SportsGame': 'Games;Sports',
'3DGraphics': 'Graphics;3D Graphics',
'VectorGraphics': 'Graphics;Drawing',
'RasterGraphics': 'Graphics;Painting & Editing',
'Photography': 'Graphics;Photography',
'Publishing': 'Graphics;Publishing',
'Scanning': 'Graphics;Scanning & OCR',
'OCR': 'Graphics;Scanning & OCR',
'Viewer': 'Graphics;Viewers',
'InstantMessaging': 'Internet;Chat',
'IRCClient': 'Internet;Chat',
'FileTransfer': 'Internet;File Sharing',
'Email': 'Internet;Mail',
'WebBrowser': 'Internet;Web Browsers',
'Astronomy': 'Science & Engineering;Astronomy',
'Biology': 'Science & Engineering;Biology',
'Chemistry': 'Science & Engineering;Chemistry',
'ArtificialIntelligence': 'Science & Engineering;Computing & Robotics',
'ComputerScience': 'Science & Engineering;Computing & Robotics',
'Robotics': 'Science & Engineering;Computing & Robotics',
'Electronics': 'Science & Engineering;Electronics',
'Engineering': 'Science & Engineering;Engineering',
'Geography': 'Science & Engineering;Geography',
'Geology': 'Science & Engineering;Geology',
'Geoscience': 'Science & Engineering;Geology',
'DataVisualization': 'Science & Engineering;Mathematics',
'Math': 'Science & Engineering;Mathematics',
'NumericalAnalysis': 'Science & Engineering;Mathematics',
'MedicalSoftware': 'Science & Engineering;Medicine',
'Electricity': 'Science & Engineering;Physics',
'Physics': 'Science & Engineering;Physics',
'Debugger': 'Developer Tools;Debugging',
'GUIDesigner': 'Developer Tools;Graphic Interface Design',
'IDE': 'Developer Tools;IDEs',
'Translation': 'Developer Tools;Localization',
'Profiling': 'Developer Tools;Profiling',
'RevisionControl': 'Developer Tools;Version Control',
'WebDevelopment': 'Developer Tools;Web Development',
}
