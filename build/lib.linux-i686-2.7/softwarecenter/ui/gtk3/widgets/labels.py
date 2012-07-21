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

from gi.repository import Gtk
from gettext import gettext as _

from softwarecenter.hw import get_hw_short_description


class HardwareRequirementsLabel(Gtk.HBox):
    """ contains a single HW requirement string and a image that shows if
        the requirements are meet
    """

    SUPPORTED_SYM = {
        # TRANSLATORS: symbol for "hardware-supported"
        'yes': _(u'\u2713'),
        # TRANSLATORS: symbol for hardware "not-supported"
        'no': u'<span foreground="red">%s</span>' % _(u'\u2718'),
    }

    # TRANSLATORS: this is a substring that used to build the
    #              "hardware-supported" string, where sym is
    #              either a unicode checkmark or a cross
    #              and hardware is the short hardware description
    #              Note that this is the last substr, no trailing ","
    LABEL_LAST_ITEM = _("%(sym)s%(hardware)s")

    # TRANSLATORS: this is a substring that used to build the
    #              "hardware-supported" string, where sym is
    #              either a unicode checkmark or a cross
    #              and hardware is the short hardware description
    #              Note that the trailing ","
    LABEL = _("%(sym)s%(hardware)s,")

    def __init__(self, last_item=True):
        super(HardwareRequirementsLabel, self).__init__()
        self.tag = None
        self.result = None
        self.last_item = last_item
        self._build_ui()

    def _build_ui(self):
        self._label = Gtk.Label()
        self._label.set_selectable(True)
        self._label.show()
        self.pack_start(self._label, True, True, 0)

    def get_label(self):
        # get the right symbol
        sym = self.SUPPORTED_SYM[self.result]
        # we add a trailing
        if self.last_item:
            label_text = self.LABEL_LAST_ITEM
        else:
            label_text = self.LABEL
        short_descr = get_hw_short_description(self.tag)
        return _(label_text) % {
            "sym": sym,
            # we need unicode() here instead of utf8 or str because
            # the %s in "label_text" will cause str() to be called on the
            # encoded string, but it will not know what encoding to use
            "hardware": unicode(short_descr, "utf8", "ignore")
            }

    def set_hardware_requirement(self, tag, result):
        self.tag = tag
        self.result = result
        self._label.set_markup(self.get_label())


class HardwareRequirementsBox(Gtk.HBox):
    """ A collection of HW requirement labels """

    def __init__(self):
        super(HardwareRequirementsBox, self).__init__()

    def clear(self):
        for w in self.get_children():
            self.remove(w)

    def set_hardware_requirements(self, hw_requirements_result):
        self.clear()
        for i, (tag, sup) in enumerate(hw_requirements_result.iteritems()):
            # ignore unknown for now
            if not sup in ("yes", "no"):
                continue
            is_last_item = (i == len(hw_requirements_result) - 1)
            label = HardwareRequirementsLabel(last_item=is_last_item)
            label.set_hardware_requirement(tag, sup)
            label.show()
            self.pack_start(label, True, True, 6)

    @property
    def hw_labels(self):
        return self.get_children()


def get_test_window():
    win = Gtk.Window()
    win.set_size_request(300, 200)

    HW_TEST_RESULT = {
        'hardware::gps': 'yes',
        'hardware::video:opengl': 'no',
    }

    # add it
    hwbox = HardwareRequirementsBox()
    hwbox.set_hardware_requirements(HW_TEST_RESULT)
    win.add(hwbox)

    win.show_all()
    win.connect("destroy", Gtk.main_quit)
    return win

if __name__ == "__main__":
    win = get_test_window()
    Gtk.main()
