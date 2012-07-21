import gi
from gi.repository import Pango
from gi.repository import Gtk
gi.require_version("Gtk", "3.0")

import logging

LOG = logging.getLogger(__name__)


def get_em(size=""):
    # calc the height of a character, use as 1em
    if size:
        m = '<%s>M</%s>' % (size, size)
    else:
        m = 'M'

    l = Gtk.Label()
    l.set_markup(m)
    w, h = l.get_layout().get_size()
    return h / Pango.SCALE


def get_small_em():
    return get_em("small")


def get_big_em():
    return get_em("big")


EM = get_em()
SMALL_EM = get_small_em()
BIG_EM = get_big_em()
LOG.debug("EM's: %s %s %s" % (EM, SMALL_EM, BIG_EM))


def em(multiplier=1, min=1):
    return max(int(min), int(round(EM * multiplier, 0)))


def small_em(multiplier=1, min=1):
    return max(int(min), int(round(SMALL_EM * multiplier, 0)))


def big_em(multiplier=1, min=1):
    return max(int(min), int(round(BIG_EM * multiplier, 0)))


# common values
class StockEms:
    XLARGE = em(1.33, 5)
    LARGE = em(min=3)
    MEDIUM = em(0.666, 2)
    SMALL = em(0.333, 1)
