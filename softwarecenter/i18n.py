# Copyright (C) 2011 Canonical
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

import locale
import logging
import os
LOG = logging.getLogger(__name__)

# fallback if locale parsing fails
FALLBACK = "en"
# those languages need the full language-code, the other ones
# can be abbreved
FULL = ["pt_BR",
        "zh_CN", "zh_TW"]


def init_locale():
    try:
        locale.setlocale(locale.LC_ALL, "")
        # we need this for bug #846038, with en_NG setlocale() is fine
        # but the next getlocale() will crash (fun!)
        locale.getlocale()
    except:
        LOG.exception("setlocale failed, resetting to C")
        locale.setlocale(locale.LC_ALL, "C")


def get_languages():
    """Helper that returns the split up languages"""
    langs = []
    if "LANGUAGE" in os.environ:
        langs = os.environ["LANGUAGE"].split(":")
        for lang in langs[:]:
            if "_" in lang and not lang in FULL:
                langs.remove(lang)
    # ensure the data from get_language() part of the result too
    # (see LP: #979013)
    from_get_language = get_language()
    if not from_get_language in langs:
        langs.insert(0, from_get_language)
    return langs


def get_language():
    """Helper that returns the current language
    """
    try:
        language = locale.getdefaultlocale(
            ('LANGUAGE', 'LANG', 'LC_CTYPE', 'LC_ALL'))[0]
    except Exception as e:
        LOG.warn("Failed to get language: '%s'" % e)
        language = "C"
    # use fallback if we can't determine the language
    if language is None or language == "C":
        return FALLBACK
    if language in FULL:
        return language
    return language.split("_")[0]


def langcode_to_name(langcode):
    import xml.etree.ElementTree
    from gettext import dgettext
    for iso in ["iso_639_3", "iso_639"]:
        path = os.path.join("/usr/share/xml/iso-codes/", iso + ".xml")
        if os.path.exists(path):
            root = xml.etree.ElementTree.parse(path)
            xpath = ".//%s_entry[@part1_code='%s']" % (iso, langcode)
            match = root.find(xpath)
            if match is not None:
                return dgettext(iso, match.attrib["name"])
    return langcode
