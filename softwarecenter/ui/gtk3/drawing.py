from math import pi as PI
PI_OVER_180 = PI / 180

from gi.repository import Gdk


BLACK = Gdk.RGBA(red=0, green=0, blue=0)
WHITE = Gdk.RGBA(red=1, green=1, blue=1)


def color_floats(spec):
    rgba = Gdk.RGBA()
    rgba.parse(spec)
    return rgba.red, rgba.green, rgba.blue


def rgb_to_hex(r, g, b):
    if isinstance(r, float):
        r *= 255
        g *= 255
        b *= 255
    return "#%02X%02X%02X" % (r, g, b)


def color_to_hex(color):
    return rgb_to_hex(color.red, color.green, color.blue)


def mix(fgcolor, bgcolor, mix_alpha):
    """ Creates a composite rgb of a foreground rgba and a background rgb.

         - fgcolor: an rgb of floats
         - bgcolor: an rgb of floats
         - mix_alpha: (0.0 - 1.0) the proportion of fgcolor mixed
                      into bgcolor
    """

    src_r, src_g, src_b = fgcolor.red, fgcolor.green, fgcolor.blue
    bg_r, bg_g, bg_b = bgcolor.red, bgcolor.green, bgcolor.blue

    # Source: http://en.wikipedia.org/wiki/Alpha_compositing
    r = ((1 - mix_alpha) * bg_r) + (mix_alpha * src_r)
    g = ((1 - mix_alpha) * bg_g) + (mix_alpha * src_g)
    b = ((1 - mix_alpha) * bg_b) + (mix_alpha * src_b)
    return Gdk.RGBA(red=r, green=g, blue=b)


def darken(color, amount=0.3):
    return mix(BLACK, color, amount)


def lighten(color, amount=0.3):
    return mix(WHITE, color, amount)


def rounded_rect(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(r + x, r + y, r, PI, 270 * PI_OVER_180)
    cr.arc(x + w - r, r + y, r, 270 * PI_OVER_180, 0)
    cr.arc(x + w - r, y + h - r, r, 0, 90 * PI_OVER_180)
    cr.arc(r + x, y + h - r, r, 90 * PI_OVER_180, PI)
    cr.close_path()
    return


def rounded_rect2(cr, x, y, w, h, radii):
    nw, ne, se, sw = radii

    nw = max(0, nw)
    ne = max(0, ne)
    se = max(0, se)
    sw = max(0, sw)

    cr.save()
    cr.translate(x, y)
    if nw:
        cr.new_sub_path()
        cr.arc(nw, nw, nw, PI, 270 * PI_OVER_180)
    else:
        cr.move_to(0, 0)
    if ne:
        cr.arc(w - ne, ne, ne, 270 * PI_OVER_180, 0)
    else:
        cr.rel_line_to(w - nw, 0)
    if se:
        cr.arc(w - se, h - se, se, 0, 90 * PI_OVER_180)
    else:
        cr.rel_line_to(0, h - ne)
    if sw:
        cr.arc(sw, h - sw, sw, 90 * PI_OVER_180, PI)
    else:
        cr.rel_line_to(-(w - se), 0)

    cr.close_path()
    cr.restore()


def circle(cr, x, y, w, h):
    cr.new_path()

    r = min(w, h) * 0.5
    x += int((w - 2 * r) / 2)
    y += int((h - 2 * r) / 2)

    cr.arc(r + x, r + y, r, 0, 360 * PI_OVER_180)
    cr.close_path()
