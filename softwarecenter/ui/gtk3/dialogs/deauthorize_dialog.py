# Copyright (C) 2011 Canonical
#
# Authors:
#  Gary Lasker
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
import logging

from gettext import gettext as _

from softwarecenter.ui.gtk3.dialogs import SimpleGtkbuilderDialog

from softwarecenter.distro import get_distro
from softwarecenter.enums import Icons
from softwarecenter.ui.gtk3.views.pkgnamesview import PackageNamesView
import softwarecenter.ui.gtk3.dialogs as dialogs

LOG = logging.getLogger(__name__)

#FIXME: These need to come from the main app
ICON_SIZE = 24


def deauthorize_computer(parent, datadir, db, icons, account_name,
    purchased_packages):
    """ Display a dialog to deauthorize the current computer for purchases
    """
    cache = db._aptcache
    distro = get_distro()

    (primary, button_text) = distro.get_deauthorize_text(account_name,
                                                         purchased_packages)

    # build the dialog
    glade_dialog = SimpleGtkbuilderDialog(datadir, domain="software-center")
    dialog = glade_dialog.dialog_deauthorize
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_default_size(360, -1)

    # use the icon for software-center in the dialog
    icon_name = "softwarecenter"
    if (icon_name is None or
        not icons.has_icon(icon_name)):
        icon_name = Icons.MISSING_APP
    glade_dialog.image_icon.set_from_icon_name(icon_name,
                                               Gtk.IconSize.DIALOG)

    # set the texts
    glade_dialog.label_deauthorize_primary.set_text(
        "<span font_weight=\"bold\" font_size=\"large\">%s</span>" % primary)
    glade_dialog.label_deauthorize_primary.set_use_markup(True)
    glade_dialog.button_deauthorize_do.set_label(button_text)

    # add the list of packages to remove, if there are any
    if len(purchased_packages) > 0:
        view = PackageNamesView(_("Deauthorize"), cache, purchased_packages,
            icons, ICON_SIZE, db)
        view.set_headers_visible(False)
        # FIXME: work out how not to select?/focus?/activate? first item
        glade_dialog.scrolledwindow_purchased_packages.add(view)
        glade_dialog.scrolledwindow_purchased_packages.show_all()
    else:
        glade_dialog.viewport_purchased_packages.hide()

    result = dialog.run()
    dialog.hide()
    if result == Gtk.ResponseType.ACCEPT:
        return True
    return False


if __name__ == "__main__":
    import sys
    import os

    if len(sys.argv) > 1:
        datadir = sys.argv[1]
    elif os.path.exists("./data"):
        datadir = "./data"
    else:
        datadir = "/usr/share/software-center"

    from softwarecenter.ui.gtk3.utils import get_sc_icon_theme
    icons = get_sc_icon_theme(datadir)

    Gtk.Window.set_default_icon_name("softwarecenter")

    from softwarecenter.db.pkginfo import get_pkg_info
    cache = get_pkg_info()
    cache.open()

    # xapian
    import xapian
    from softwarecenter.paths import XAPIAN_BASE_PATH
    from softwarecenter.db.database import StoreDatabase
    xapian_base_path = XAPIAN_BASE_PATH
    pathname = os.path.join(xapian_base_path, "xapian")
    try:
        db = StoreDatabase(pathname, cache)
        db.open()
    except xapian.DatabaseOpeningError:
        # Couldn't use that folder as a database
        # This may be because we are in a bzr checkout and that
        #   folder is empty. If the folder is empty, and we can find the
        # script that does population, populate a database in it.
        if os.path.isdir(pathname) and not os.listdir(pathname):
            from softwarecenter.db.update import rebuild_database
            logging.info("building local database")
            rebuild_database(pathname)
            db = StoreDatabase(pathname, cache)
            db.open()
    except xapian.DatabaseCorruptError as e:
        logging.exception("xapian open failed")
        dialogs.error(None,
                           _("Sorry, can not open the software database"),
                           _("Please re-install the 'software-center' "
                             "package."))
        # FIXME: force rebuild by providing a dbus service for this
        sys.exit(1)

    purchased_packages = set()
    purchased_packages.add('file-roller')
    purchased_packages.add('alarm-clock')
    purchased_packages.add('pitivi')
    purchased_packages.add('chromium-browser')
    purchased_packages.add('cheese')
    purchased_packages.add('aisleriot')

    account_name = "max.fischer@rushmoreacademy.edu"

    deauthorize_computer(None,
                         "./data",
                         db,
                         icons,
                         account_name,
                         purchased_packages)
