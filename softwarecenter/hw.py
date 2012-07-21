# Copyright (C) 2012 Canonical
# -*- coding: utf-8 -*-
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

from gettext import gettext as _
from softwarecenter.utils import utf8

# private extension over the debtagshw stuff
OPENGL_DRIVER_BLACKLIST_TAG = "x-hardware::opengl-driver-blacklist:"


TAG_DESCRIPTION = {
    # normal tags
    'hardware::webcam': _('webcam'),
    'hardware::digicam': _('digicam'),
    'hardware::input:mouse': _('mouse'),
    'hardware::input:joystick': _('joystick'),
    'hardware::input:touchscreen': _('touchscreen'),
    'hardware::gps': _('GPS'),
    'hardware::laptop': _('notebook computer'),
    'hardware::printer': _('printer'),
    'hardware::scanner': _('scanner'),
    'hardware::storage:cd': _('CD drive'),
    'hardware::storage:cd-writer': _('CD burner'),
    'hardware::storage:dvd': _('DVD drive'),
    'hardware::storage:dvd-writer': _('DVD burner'),
    'hardware::storage:floppy': _('floppy disk drive'),
    'hardware::video:opengl': _('OpenGL hardware acceleration'),
    # "special" private tag extenstion that needs special handling
    OPENGL_DRIVER_BLACKLIST_TAG: _('Graphics driver that is not %s'),
}

TAG_MISSING_DESCRIPTION = {
    'hardware::digicam': _('This software requires a digital camera, but none '
                           'are currently connected'),
    'hardware::webcam': _('This software requires a video camera, but none '
                           'are currently connected'),
    'hardware::input:mouse': _('This software requires a mouse, '
                                'but none is currently setup.'),
    'hardware::input:joystick': _('This software requires a joystick, '
                                   'but none are currently connected.'),
    'hardware::input:touchscreen': _('This software requires a touchscreen, '
                                      'but the computer does not have one.'),
    'hardware::gps': _('This software requires a GPS, '
                        'but the computer does not have one.'),
    'hardware::laptop': _('This software is for notebook computers.'),
    'hardware::printer': _('This software requires a printer, but none '
                           'are currently set up.'),
    'hardware::scanner': _('This software requires a scanner, but none are '
                            'currently set up.'),
    'hardware::stoarge:cd': _('This software requires a CD drive, but none '
                               'are currently connected.'),
    'hardware::storage:cd-writer': _('This software requires a CD burner, '
                                      'but none are currently connected.'),
    'hardware::storage:dvd': _('This software requires a DVD drive, but none '
                                'are currently connected.'),
    'hardware::storage:dvd-writer': _('This software requires a DVD burner, '
                                       'but none are currently connected.'),
    'hardware::storage:floppy': _('This software requires a floppy disk '
                                   'drive, but none are currently connected.'),
    'hardware::video:opengl': _('This computer does not have graphics fast '
                                 'enough for this software.'),
    # private extension
    OPENGL_DRIVER_BLACKLIST_TAG: _(u'This software does not work with the '
                                   u'\u201c%s\u201D graphics driver this '
                                   u'computer is using.'),
}


def get_hw_short_description(tag):
    # FIXME: deal with OPENGL_DRIVER_BLACKLIST_TAG as this needs rsplit(":")
    #        and a view of all available tags
    s = TAG_DESCRIPTION.get(tag)
    return utf8(_(s))


def get_hw_missing_long_description(tags):
    s = ""
    # build string
    for tag, supported in tags.iteritems():
        if supported == "no":
            descr = TAG_MISSING_DESCRIPTION.get(tag)
            if descr:
                s += "%s\n" % descr
            else:
                # deal with generic tags
                prefix, sep, postfix = tag.rpartition(":")
                descr = TAG_MISSING_DESCRIPTION.get(prefix + sep)
                descr = descr % postfix
                if descr:
                    s += "%s\n" % descr
    # ensure that the last \n is gone
    if s:
        s = s[:-1]
    return utf8(_(s))


def get_private_extensions_hardware_support_for_tags(tags):
    import debtagshw
    res = {}
    for tag in tags:
        if tag.startswith(OPENGL_DRIVER_BLACKLIST_TAG):
            prefix, sep, driver = tag.rpartition(":")
            if driver == debtagshw.opengl.get_driver():
                res[tag] = debtagshw.enums.HardwareSupported.NO
            else:
                res[tag] = debtagshw.enums.HardwareSupported.YES
    return res


def get_hardware_support_for_tags(tags):
    """ wrapper around the DebtagsAvailalbeHW to support adding our own
        private tag extension (like opengl-driver)
    """
    from debtagshw.debtagshw import DebtagsAvailableHW
    hw = DebtagsAvailableHW()
    support = hw.get_hardware_support_for_tags(tags)
    private_extensions = get_private_extensions_hardware_support_for_tags(
        tags)
    support.update(private_extensions)
    return support
