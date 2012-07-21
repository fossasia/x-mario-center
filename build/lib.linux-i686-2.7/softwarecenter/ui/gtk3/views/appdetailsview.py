# -*- coding: utf-8 -*-
# Copyright (C) 2009-2011 Canonical
#
# Authors:
#  Matthew McGowan
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

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Atk, Gtk, Gdk, GLib, GObject, GdkPixbuf, Pango

import datetime
import gettext
import logging
import cairo
import os

from gettext import gettext as _

import softwarecenter.paths
from softwarecenter.cmdfinder import CmdFinder
from softwarecenter.netstatus import (NetState, get_network_watcher,
                                      network_state_is_connected)
from softwarecenter.db.application import Application
from softwarecenter.db import DebFileApplication
from softwarecenter.backend.reviews import ReviewStats
from softwarecenter.enums import (AppActions,
                                  PkgStates,
                                  Icons,
                                  SOFTWARE_CENTER_PKGNAME)
from softwarecenter.utils import (is_unity_running,
                                  upstream_version,
                                  get_exec_line_from_desktop,
                                  SimpleFileDownloader,
                                  utf8)
from softwarecenter.distro import get_distro
from softwarecenter.backend.weblive import get_weblive_backend
from softwarecenter.ui.gtk3.dialogs import error

# FIXME: this is needed for the recommendations but really should become
#        a widget or something generic instead
from softwarecenter.ui.gtk3.views.catview_gtk import CategoriesViewGtk

from softwarecenter.ui.gtk3.em import StockEms, em
from softwarecenter.ui.gtk3.drawing import color_to_hex
from softwarecenter.ui.gtk3.session.appmanager import get_appmanager
from softwarecenter.ui.gtk3.widgets.labels import HardwareRequirementsBox
from softwarecenter.ui.gtk3.widgets.separators import HBar
from softwarecenter.ui.gtk3.widgets.viewport import Viewport
from softwarecenter.ui.gtk3.widgets.reviews import UIReviewsList
from softwarecenter.ui.gtk3.widgets.containers import SmallBorderRadiusFrame
from softwarecenter.ui.gtk3.widgets.stars import Star, StarRatingsWidget
from softwarecenter.ui.gtk3.widgets.description import AppDescription
from softwarecenter.ui.gtk3.widgets.thumbnail import ScreenshotGallery
from softwarecenter.ui.gtk3.widgets.videoplayer import VideoPlayer
from softwarecenter.ui.gtk3.widgets.weblivedialog import (
                                    ShowWebLiveServerChooserDialog)
from softwarecenter.ui.gtk3.widgets.recommendations import (
                                            RecommendationsPanelDetails)
from softwarecenter.ui.gtk3.gmenusearch import GMenuSearcher

import softwarecenter.ui.gtk3.dialogs as dialogs

from softwarecenter.hw import get_hw_missing_long_description
from softwarecenter.region import REGION_WARNING_STRING

from softwarecenter.backend.reviews import get_review_loader
from softwarecenter.backend import get_install_backend


LOG = logging.getLogger(__name__)


class StatusBar(Gtk.Alignment):
    """ Subclass of Gtk.Alignment that draws a small dash border
        around the rectangle.
    """

    def __init__(self, view):
        Gtk.Alignment.__init__(self, xscale=1.0, yscale=1.0)
        self.set_padding(StockEms.SMALL, StockEms.SMALL, 0, 0)

        self.hbox = Gtk.HBox()
        self.hbox.set_spacing(StockEms.SMALL)
        self.add(self.hbox)

        self.view = view
        # default bg
        self._bg = [1, 1, 1, 0.3]

        self.connect("style-updated", self.on_style_updated)

    def on_style_updated(self, widget):
        context = self.get_style_context()
        context.add_class("item-view-separator")
        context = widget.get_style_context()
        border = context.get_border(Gtk.StateFlags.NORMAL)
        self._border_width = max(1, max(border.top, border.bottom))

    def do_draw(self, cr):
        cr.save()
        a = self.get_allocation()
        width = self._border_width

        # fill bg
        cr.rectangle(-width, 0, a.width + 2 * width, a.height)
        cr.set_source_rgba(*self._bg)
        cr.fill_preserve()

        # paint dashed top/bottom borders
        context = self.get_style_context()
        context.save()
        context.add_class("item-view-separator")
        bc = context.get_border_color(self.get_state_flags())
        context.restore()

        Gdk.cairo_set_source_rgba(cr, bc)
        cr.set_dash((width, 2 * width), 1)
        cr.set_line_width(2 * width)
        cr.stroke()

        cr.restore()
        for child in self:
            self.propagate_draw(child, cr)


class WarningStatusBar(StatusBar):

    def __init__(self, view):
        StatusBar.__init__(self, view)
        self.label = Gtk.Label()
        self.label.set_line_wrap(True)
        self.label.set_alignment(0.0, 0.5)
        self.warn = Gtk.Label()
        self.warn.set_markup(
            '<span foreground="red" size="x-large">%s</span>' % u'\u26A0')
        self.hbox.pack_start(self.label, True, True, 0)
        self.hbox.pack_end(self.warn, False, False, 0)
        # override _bg
        self._bg = [1, 1, 0, 0.3]


class PackageStatusBar(StatusBar):
    """ Package specific status bar that contains a state label,
        a action button and a progress bar.
    """

    def __init__(self, view):
        StatusBar.__init__(self, view)
        self.installed_icon = Gtk.Image.new_from_icon_name(
            Icons.INSTALLED_OVERLAY, Gtk.IconSize.DIALOG)
        self.label = Gtk.Label()
        self.label.set_line_wrap(True)
        self.button = Gtk.Button()
        self.combo_multiple_versions = Gtk.ComboBoxText.new()
        model = Gtk.ListStore(str, str)
        self.combo_multiple_versions.set_model(model)
        self.combo_multiple_versions.connect(
            "changed", self._on_combo_multiple_versions_changed)
        self.progress = Gtk.ProgressBar()

        self.pkg_state = None

        self.hbox.pack_start(self.installed_icon, False, False, 0)
        self.hbox.pack_start(self.label, False, False, 0)
        self.hbox.pack_end(self.button, False, False, 0)
        self.hbox.pack_end(self.combo_multiple_versions, False, False, 0)
        self.hbox.pack_end(self.progress, False, False, 0)
        self.show_all()

        self.app_manager = get_appmanager()

        self.button.connect('clicked', self._on_button_clicked)
        GObject.timeout_add(500, self._pulse_helper)

    def _pulse_helper(self):
        if (self.pkg_state == PkgStates.INSTALLING_PURCHASED and
            self.progress.get_fraction() == 0.0):
            self.progress.pulse()
        return True

    def _on_combo_multiple_versions_changed(self, combo):
        # disconnect to ensure no updates are happening in here
        model = combo.get_model()
        it = combo.get_active_iter()
        if it is None:
            return
        archive_suite = model[it][1]
        # ignore if there is nothing set here
        if archive_suite is None:
            return
        combo.disconnect_by_func(self._on_combo_multiple_versions_changed)
        # reset "default" to "" as this is what it takes to reset the
        # thing
        if archive_suite != self.view.app.archive_suite:
            # force not-automatic version
            self.view.app_details.force_not_automatic_archive_suite(
                archive_suite)
            # update it
            self.view._update_all(self.view.app_details)
        # reconnect again
        combo.connect("changed", self._on_combo_multiple_versions_changed)

    def _on_button_clicked(self, button):
        button.set_sensitive(False)
        state = self.pkg_state
        app = self.view.app
        addons_to_install = self.view.addons_manager.addons_to_install
        addons_to_remove = self.view.addons_manager.addons_to_remove
        app_manager = self.app_manager
        if state == PkgStates.INSTALLED:
            app_manager.remove(
                app, addons_to_install, addons_to_remove)
        elif state == PkgStates.PURCHASED_BUT_REPO_MUST_BE_ENABLED:
            app_manager.reinstall_purchased(app)
        elif state == PkgStates.NEEDS_PURCHASE:
            app_manager.buy_app(app)
        elif state in (PkgStates.UNINSTALLED, PkgStates.FORCE_VERSION):
            app_manager.install(
                app, addons_to_install, addons_to_remove)
        elif state == PkgStates.REINSTALLABLE:
            app_manager.install(
                app, addons_to_install, addons_to_remove)
        elif state == PkgStates.UPGRADABLE:
            app_manager.upgrade(
                app, addons_to_install, addons_to_remove)
        elif state == PkgStates.NEEDS_SOURCE:
            app_manager.enable_software_source(app)

    def set_label(self, label):
        m = '<big><b>%s</b></big>' % label
        self.label.set_markup(m)

    def get_label(self):
        return self.label.get_text()

    def set_button_label(self, label):
        self.button.set_label(label)

    def get_button_label(self):
        return self.button.get_label()

    def _build_combo_multiple_versions(self):
        # the currently forced archive_suite for the given app
        app_version = self.app_details.version
        # all available not-automatic (version, archive_suits)
        not_auto_suites = self.app_details.get_not_automatic_archive_versions()
        # populat the combobox if
        if not_auto_suites:
            combo = self.combo_multiple_versions
            combo.disconnect_by_func(self._on_combo_multiple_versions_changed)
            model = self.combo_multiple_versions.get_model()
            model.clear()
            for i, archive_suite in enumerate(not_auto_suites):
                # get the version, archive_suite
                ver, archive_suite = archive_suite
                # the string to display is something like:
                #  "v1.0 (precise-backports)"
                displayed_archive_suite = archive_suite
                if i == 0:
                    displayed_archive_suite = _("default")
                s = "v%s (%s)" % (upstream_version(ver),
                                  displayed_archive_suite)
                model.append((s, archive_suite))
                if app_version == ver:
                    self.combo_multiple_versions.set_active(i)
            # if nothing is found, set to default
            if self.combo_multiple_versions.get_active_iter() is None:
                self.combo_multiple_versions.set_active(0)
            self.combo_multiple_versions.show()
            combo.connect("changed", self._on_combo_multiple_versions_changed)
        else:
            self.combo_multiple_versions.hide()

    def configure(self, app_details, state):
        LOG.debug("configure %s state=%s pkgstate=%s" % (
                app_details.pkgname, state, app_details.pkg_state))
        self.pkg_state = state
        self.app_details = app_details

        # configure the not-automatic stuff
        self._build_combo_multiple_versions()

        if state in (PkgStates.INSTALLING,
                     PkgStates.INSTALLING_PURCHASED,
                     PkgStates.REMOVING,
                     PkgStates.UPGRADING,
                     PkgStates.ERROR,
                     AppActions.APPLY):
            self.show()
        elif state == PkgStates.NOT_FOUND:
            self.hide()
        else:
            # mvo: why do we override state here again?
            state = app_details.pkg_state
            self.pkg_state = state
            self.button.set_sensitive(True)
            self.button.show()
            self.show()
            self.progress.hide()
            self.installed_icon.hide()

        # FIXME:  Use a Gtk.Action for the Install/Remove/Buy/Add
        #         Source/Update Now action so that all UI controls
        #         (menu item, applist view button and appdetails view button)
        #         are managed centrally:  button text, button sensitivity,
        #         and the associated callback.
        if state == PkgStates.INSTALLING:
            self.set_label(_(u'Installing\u2026'))
            self.button.set_sensitive(False)
        elif state == PkgStates.INSTALLING_PURCHASED:
            self.set_label(_(u'Installing purchase\u2026'))
            self.button.hide()
            self.progress.show()
        elif state == PkgStates.REMOVING:
            self.set_label(_(u'Removing\u2026'))
            self.button.set_sensitive(False)
        elif state == PkgStates.UPGRADING:
            self.set_label(_(u'Upgrading\u2026'))
            self.button.set_sensitive(False)
        elif state == PkgStates.INSTALLED or state == PkgStates.REINSTALLABLE:
            # special label only if the app being viewed is software centre
            # itself
            self.installed_icon.show()
            if app_details.pkgname == SOFTWARE_CENTER_PKGNAME:
                self.set_label(
                    _(u'Installed (you\u2019re using it right now)'))
            else:
                if app_details.purchase_date:
                    # purchase_date is a string, must first convert to
                    # datetime.datetime
                    pdate = self._convert_purchase_date_str_to_datetime(
                        app_details.purchase_date)
                    # TRANSLATORS : %Y-%m-%d formats the date as 2011-03-31,
                    # please specify a format per your locale (if you prefer,
                    # %x can be used to provide a default locale-specific date
                    # representation)
                    self.set_label(pdate.strftime(_('Purchased on %Y-%m-%d')))
                elif app_details.installation_date:
                    # TRANSLATORS : %Y-%m-%d formats the date as 2011-03-31,
                    # please specify a format per your locale (if you prefer,
                    # %x can be used to provide a default locale-specific date
                    # representation)
                    template = _('Installed on %Y-%m-%d')
                    self.set_label(app_details.installation_date.strftime(
                            template))
                else:
                    self.set_label(_('Installed'))
            if state == PkgStates.REINSTALLABLE:  # only deb files atm
                self.set_button_label(_('Reinstall'))
            elif state == PkgStates.INSTALLED:
                self.set_button_label(_('Remove'))
        elif state == PkgStates.NEEDS_PURCHASE:
            # FIXME:  need to determine the currency dynamically once we can
            #         get that info from the software-center-agent/payments
            #         service.
            # NOTE:  the currency string for this label is purposely not
            #        translatable when hardcoded, since it (currently)
            #        won't vary based on locale and as such we don't want
            #        it translated
            self.set_label("US$ %s" % app_details.price)
            if (app_details.hardware_requirements_satisfied and
                app_details.region_requirements_satisfied):
                self.set_button_label(_(u'Buy\u2026'))
            else:
                self.set_button_label(_(u'Buy Anyway\u2026'))
        elif state == PkgStates.FORCE_VERSION:
            self.set_button_label(_('Change'))
        elif state in (
            PkgStates.PURCHASED_BUT_REPO_MUST_BE_ENABLED,
            PkgStates.PURCHASED_BUT_NOT_AVAILABLE_FOR_SERIES):

            # purchase_date is a string, must first convert to
            # datetime.datetime
            pdate = self._convert_purchase_date_str_to_datetime(
                app_details.purchase_date)
            # TRANSLATORS : %Y-%m-%d formats the date as 2011-03-31, please
            # specify a format per your locale (if you prefer, %x can be used
            # to provide a default locale-specific date representation)
            label = pdate.strftime(_('Purchased on %Y-%m-%d'))
            self.set_button_label(_('Install'))
            if state == PkgStates.PURCHASED_BUT_NOT_AVAILABLE_FOR_SERIES:
                label = pdate.strftime(
                    _('Purchased on %Y-%m-%d but not available for your '
                      'current Ubuntu version. Please contact the vendor '
                      'for an update.'))
                self.button.hide()
            self.set_label(label)

        elif state == PkgStates.UNINSTALLED:
            #special label only if the app being viewed is software centre
            # itself
            if app_details.pkgname == SOFTWARE_CENTER_PKGNAME:
                self.set_label(_(u'Removed (close it and it\u2019ll be gone)'))
            else:
                # TRANSLATORS: Free here means Gratis
                self.set_label(_("Free"))
            if (app_details.hardware_requirements_satisfied and
                app_details.region_requirements_satisfied):
                self.set_button_label(_('Install'))
            else:
                self.set_button_label(_('Install Anyway'))
        elif state == PkgStates.UPGRADABLE:
            self.set_label(_('Upgrade Available'))
            self.set_button_label(_('Upgrade'))
        elif state == AppActions.APPLY:
            self.set_label(_(u'Changing Add-ons\u2026'))
            self.button.set_sensitive(False)
        elif state == PkgStates.UNKNOWN:
            self.button.hide()
            self.set_label(_("Error"))
        elif state == PkgStates.ERROR:
            # this is used when the pkg can not be installed
            # we display the error in the description field
            self.installed_icon.hide()
            self.progress.hide()
            self.button.hide()
            self.set_label(_("Error"))
        elif state == PkgStates.NOT_FOUND:
            # this is used when the pkg is not in the cache and there is no
            # request we display the error in the summary field and hide the
            # rest
            self.button.hide()
        elif state == PkgStates.NEEDS_SOURCE:
            channelfile = self.app_details.channelfile
            # it has a price and is not available
            if channelfile:
                self.set_button_label(_("Use This Source"))
            # check if it comes from a non-enabled component
            elif self.app_details._unavailable_component():
                self.set_button_label(_("Use This Source"))
            else:
                # FIXME: This will currently not be displayed,
                #        because we don't differenciate between
                #        components that are not enabled or that just
                #        lack the "Packages" files (but are in sources.list)
                self.set_button_label(_("Update Now"))

        # this maybe a region or hw compatibility warning
        if (self.app_details.warning and
            not self.app_details.error and
            not state in (PkgStates.INSTALLING,
                          PkgStates.INSTALLING_PURCHASED,
                          PkgStates.REMOVING,
                          PkgStates.UPGRADING,
                          AppActions.APPLY)):
            self.set_label(self.app_details.warning)

        sensitive = network_state_is_connected()
        self.button.set_sensitive(sensitive)

    def _convert_purchase_date_str_to_datetime(self, purchase_date):
        if purchase_date is not None:
            return datetime.datetime.strptime(
                purchase_date, "%Y-%m-%d %H:%M:%S")


class PackageInfo(Gtk.HBox):
    """ Box with labels for package specific information like version info
    """

    def __init__(self, key, info_keys):
        Gtk.HBox.__init__(self)
        self.set_spacing(StockEms.LARGE)

        self.key = key
        self.info_keys = info_keys
        self.info_keys.append(key)
        self.value_label = Gtk.Label()
        self.value_label.set_selectable(True)
        self.value_label.set_line_wrap(True)
        self.value_label.set_alignment(0, 0.5)
        self.a11y = self.get_accessible()

        self.connect('realize', self._on_realize)

    def _on_realize(self, widget):
        # key
        k = Gtk.Label()
        k.set_name("subtle-label")
        key_markup = '<b>%s</b>'
        k.set_markup(key_markup % self.key)
        k.set_alignment(1, 0)

        # determine max width of all keys
        max_lw = 0
        for key in self.info_keys:
            l = self.create_pango_layout("")
            l.set_markup(key_markup % key, -1)
            max_lw = max(max_lw, l.get_pixel_extents()[1].width)
            del l
        k.set_size_request(max_lw, -1)
        self.pack_start(k, False, False, 0)

        # value
        self.pack_start(self.value_label, False, False, 0)

        # a11y
        kacc = k.get_accessible()
        vacc = self.value_label.get_accessible()
        kacc.add_relationship(Atk.RelationType.LABEL_FOR, vacc)
        vacc.add_relationship(Atk.RelationType.LABELLED_BY, kacc)

        self.set_property("can-focus", True)
        self.show_all()

    def set_width(self, width):
        pass

    def set_value(self, value):
        self.value_label.set_markup(value)
        self.a11y.set_name(utf8(self.key) + ' ' + utf8(value))


class PackageInfoHW(PackageInfo):
    """ special version of packageinfo that uses the custom
        HardwareRequirementsBox as the "label"
    """
    def __init__(self, *args):
        super(PackageInfoHW, self).__init__(*args)
        self.value_label = HardwareRequirementsBox()

    def set_value(self, value):
        self.value_label.set_hardware_requirements(value)


class Addon(Gtk.HBox):
    """ Widget to select addons: CheckButton - Icon - Title (pkgname) """

    def __init__(self, db, icons, pkgname):
        Gtk.HBox.__init__(self)
        self.set_spacing(StockEms.SMALL)
        self.set_border_width(2)

        # data
        self.app = Application("", pkgname)
        self.app_details = self.app.get_details(db)

        # checkbutton
        self.checkbutton = Gtk.CheckButton()
        self.checkbutton.pkgname = self.app.pkgname
        self.pack_start(self.checkbutton, False, False, 12)
        self.connect('realize', self._on_realize, icons, pkgname)

    def _on_realize(self, widget, icons, pkgname):
        # icon
        hbox = Gtk.HBox(spacing=6)
        self.icon = Gtk.Image()
        proposed_icon = self.app_details.icon
        if not proposed_icon or not icons.has_icon(proposed_icon):
            proposed_icon = Icons.MISSING_APP
        try:
            pixbuf = icons.load_icon(proposed_icon, 22, 0)
            if pixbuf:
                pixbuf.scale_simple(22, 22, GdkPixbuf.InterpType.BILINEAR)
            self.icon.set_from_pixbuf(pixbuf)
        except:
            LOG.warning("cant set icon for '%s' " % pkgname)
        hbox.pack_start(self.icon, False, False, 0)

        # name
        title = self.app_details.display_name
        if len(title) >= 2:
            title = title[0].upper() + title[1:]

        self.title = Gtk.Label()

        context = self.get_style_context()
        context.save()
        context.add_class("subtle")
        color = color_to_hex(context.get_color(Gtk.StateFlags.NORMAL))
        context.restore()

        self.title.set_markup(
            title + ' <span color="%s">(%s)</span>' % (color, pkgname))
        self.title.set_alignment(0.0, 0.5)
        self.title.set_line_wrap(True)
        self.title.set_ellipsize(Pango.EllipsizeMode.END)
        hbox.pack_start(self.title, False, False, 0)

        loader = self.get_ancestor(AppDetailsView).review_loader
        stats = loader.get_review_stats(self.app)
        if stats != None:
            rating = Star()
            #~ rating.set_visible_window(False)
            rating.set_size_small()
            self.pack_start(rating, False, False, 0)
            rating.set_rating(stats.ratings_average)

        self.checkbutton.add(hbox)
        self.show_all()

    def get_active(self):
        return self.checkbutton.get_active()

    def set_active(self, is_active):
        self.checkbutton.set_active(is_active)

    def set_width(self, width):
        pass


class AddonsTable(Gtk.VBox):
    """ Widget to display a table of addons. """

    __gsignals__ = {'table-built': (GObject.SignalFlags.RUN_FIRST,
                                    None,
                                    ()),
                   }

    def __init__(self, addons_manager):
        Gtk.VBox.__init__(self)
        self.set_spacing(12)

        self.addons_manager = addons_manager
        self.cache = self.addons_manager.view.cache
        self.db = self.addons_manager.view.db
        self.icons = self.addons_manager.view.icons
        self.recommended_addons = None
        self.suggested_addons = None

        self.label = Gtk.Label()
        self.label.set_alignment(0, 0.5)

        markup = '<big><b>%s</b></big>' % _('Add-ons')
        self.label.set_markup(markup)
        self.pack_start(self.label, False, False, 0)

    def get_addons(self):
        # filter all children widgets and return only Addons
        return [w for w in self if isinstance(w, Addon)]

    def clear(self):
        for addon in self.get_addons():
            addon.destroy()

    def addons_set_sensitive(self, is_sensitive):
        for addon in self.get_addons():
            addon.set_sensitive(is_sensitive)

    def set_addons(self, addons):
        self.recommended_addons = sorted(addons[0])
        self.suggested_addons = sorted(addons[1])

        if not self.recommended_addons and not self.suggested_addons:
            self.addons_manager.view.addons_hbar.hide()
            return

        self.addons_manager.view.addons_hbar.show()
        # clear any existing addons
        self.clear()

        # set the new addons
        exists = set()
        for addon_name in self.recommended_addons + self.suggested_addons:
            if not addon_name in self.cache or addon_name in exists:
                continue

            addon = Addon(self.db, self.icons, addon_name)
            #addon.pkgname.connect("clicked", not yet suitable for use)
            addon.set_active(self.cache[addon_name].installed != None)
            addon.checkbutton.connect("toggled",
                                      self.addons_manager.mark_changes)
            self.pack_start(addon, False, False, 0)
            exists.add(addon_name)
        self.show_all()

        self.emit('table-built')
        return False


class AddonsStatusBar(StatusBar):
    """ Statusbar for the addons.
        This will become visible if any addons are scheduled for install
        or remove.
    """

    def __init__(self, addons_manager):
        StatusBar.__init__(self, addons_manager.view)
        self.addons_manager = addons_manager
        self.cache = self.addons_manager.view.cache

        self.applying = False

        # TRANSLATORS: Free here means Gratis
        self.label_price = Gtk.Label(_("Free"))
        self.hbox.pack_start(self.label_price, False, False, 0)

        self.hbuttonbox = Gtk.HButtonBox()
        self.hbuttonbox.set_layout(Gtk.ButtonBoxStyle.END)
        self.button_apply = Gtk.Button(_("Apply Changes"))
        self.button_apply.connect("clicked", self._on_button_apply_clicked)
        self.button_cancel = Gtk.Button(_("Cancel"))
        self.button_cancel.connect("clicked", self.addons_manager.restore)
        self.hbox.pack_end(self.button_apply, False, False, 0)
        self.hbox.pack_end(self.button_cancel, False, False, 0)
        #self.hbox.pack_start(self.hbuttonbox, False, False, 0)

    def configure(self):
        LOG.debug("AddonsStatusBarConfigure")
        # FIXME: addons are not always free, but the old implementation
        #        of determining price was buggy
        if (not self.addons_manager.addons_to_install and
            not self.addons_manager.addons_to_remove):
            self.hide()
        else:
            sensitive = network_state_is_connected()
            self.button_apply.set_sensitive(sensitive)
            self.button_cancel.set_sensitive(sensitive)
            self.show_all()

    def _on_button_apply_clicked(self, button):
        self.applying = True
        self.button_apply.set_sensitive(False)
        self.button_cancel.set_sensitive(False)
        # these two lines are the magic that make it work
        self.view.addons_to_install = self.addons_manager.addons_to_install
        self.view.addons_to_remove = self.addons_manager.addons_to_remove
        LOG.debug("ApplyButtonClicked: inst=%s rm=%s" % (
                self.view.addons_to_install, self.view.addons_to_remove))
        # apply
        app_manager = get_appmanager()
        app_manager.apply_changes(self.view.app,
                                  self.view.addons_to_install,
                                  self.view.addons_to_remove)


class AddonsManager(object):
    """ Addons manager component.
        This component deals with keeping track of what is marked
        for install or removal.
    """

    def __init__(self, view):
        self.view = view

        # add-on handling
        self.table = AddonsTable(self)
        self.status_bar = AddonsStatusBar(self)
        self.addons_to_install = []
        self.addons_to_remove = []

    def mark_changes(self, checkbutton):
        LOG.debug("mark_changes")
        addon = checkbutton.pkgname
        installed = self.view.cache[addon].installed
        if checkbutton.get_active():
            if addon not in self.addons_to_install and not installed:
                self.addons_to_install.append(addon)
            if addon in self.addons_to_remove:
                self.addons_to_remove.remove(addon)
        else:
            if addon not in self.addons_to_remove and installed:
                self.addons_to_remove.append(addon)
            if addon in self.addons_to_install:
                self.addons_to_install.remove(addon)
        self.status_bar.configure()
        GObject.idle_add(self.view.update_totalsize,
                         priority=GObject.PRIORITY_LOW)

    def configure(self, pkgname, update_addons=True):
        self.addons_to_install = []
        self.addons_to_remove = []
        if update_addons:
            self.addons = self.view.cache.get_addons(pkgname)
            self.table.set_addons(self.addons)
        self.status_bar.configure()

        sensitive = network_state_is_connected()
        self.table.addons_set_sensitive(sensitive)

    def restore(self, *button):
        self.addons_to_install = []
        self.addons_to_remove = []
        self.configure(self.view.app.pkgname)
        GObject.idle_add(self.view.update_totalsize,
                         priority=GObject.PRIORITY_LOW)


_asset_cache = {}


class AppDetailsView(Viewport):
    """ The view that shows the application details """

    # the size of the icon on the left side
    APP_ICON_SIZE = 96  # Gtk.IconSize.DIALOG ?
    # art stuff
    BACKGROUND = os.path.join(softwarecenter.paths.datadir,
                           "ui/gtk3/art/itemview-background.png")

    # need to include application-request-action here also since we are
    # multiple-inheriting
    __gsignals__ = {'selected': (GObject.SignalFlags.RUN_FIRST,
                                 None,
                                 (GObject.TYPE_PYOBJECT,)),
                    "different-application-selected": (
                        GObject.SignalFlags.RUN_LAST,
                        None,
                        (GObject.TYPE_PYOBJECT, )),
                    }

    def __init__(self, db, distro, icons, cache, datadir):
        Viewport.__init__(self)
        # basic stuff
        self.db = db
        self.distro = distro
        self.icons = icons
        self.cache = cache
        self.backend = get_install_backend()
        self.cache.connect("cache-ready", self._on_cache_ready)
        self.connect("destroy", self._on_destroy)
        self.datadir = datadir
        self.app = None
        self.appdetails = None
        self.addons_to_install = []
        self.addons_to_remove = []
        # reviews
        self.review_loader = get_review_loader(self.cache, self.db)

        # ui specific stuff
        self.set_shadow_type(Gtk.ShadowType.NONE)
        self.set_name("view")

        self.section = None
        # app specific data
        self.app = None
        self.app_details = None
        self.pkg_state = None

        self.reviews = UIReviewsList(self)

        self.adjustment_value = None

        # atk
        self.a11y = self.get_accessible()
        self.a11y.set_name("app_details pane")

        # aptdaemon
        self.backend.connect(
            "transaction-started", self._on_transaction_started)
        self.backend.connect(
            "transaction-stopped", self._on_transaction_stopped)
        self.backend.connect(
            "transaction-finished", self._on_transaction_finished)
        self.backend.connect(
            "transaction-progress-changed",
            self._on_transaction_progress_changed)

        # network status watcher
        watcher = get_network_watcher()
        watcher.connect("changed", self._on_net_state_changed)

        # addons manager
        self.addons_manager = AddonsManager(self)
        self.addons_statusbar = self.addons_manager.status_bar
        self.addons_to_install = self.addons_manager.addons_to_install
        self.addons_to_remove = self.addons_manager.addons_to_remove

        # reviews
        self._reviews_server_page = 1
        self._reviews_server_language = None
        self._reviews_relaxed = False
        self._review_sort_method = 0

        # switches
        self._show_overlay = False

        # page elements are packed into our very own lovely viewport
        self._layout_page()
        self._cache_art_assets()
        self.connect('realize', self._on_realize)
        self.loaded = True

    def _on_destroy(self, widget):
        self.cache.disconnect_by_func(self._on_cache_ready)

    def _cache_art_assets(self):
        global _asset_cache
        if _asset_cache:
            return _asset_cache
        assets = _asset_cache
        # cache the bg pattern
        surf = cairo.ImageSurface.create_from_png(self.BACKGROUND)
        ptrn = cairo.SurfacePattern(surf)
        ptrn.set_extend(cairo.EXTEND_REPEAT)
        assets["bg"] = ptrn
        return assets

    def _on_net_state_changed(self, watcher, state):
        if state in NetState.NM_STATE_DISCONNECTED_LIST:
            self._check_for_reviews()
        elif state in NetState.NM_STATE_CONNECTED_LIST:
            GObject.timeout_add(500, self._check_for_reviews)

        # set addon table and action button states based on sensitivity
        sensitive = state in NetState.NM_STATE_CONNECTED_LIST
        self.pkg_statusbar.button.set_sensitive(sensitive)
        self.addon_view.addons_set_sensitive(sensitive)
        self.addons_statusbar.button_apply.set_sensitive(sensitive)
        self.addons_statusbar.button_cancel.set_sensitive(sensitive)

    def _update_recommendations(self, pkgname):
        self.recommended_for_app_panel.set_pkgname(pkgname)

    # FIXME: should we just this with _check_for_reviews?
    def _update_reviews(self, app_details):
        self.reviews.clear()
        self._check_for_reviews()

    def _check_for_reviews(self):
        # self.app may be undefined on network state change events
        # (LP: #742635)
        if not self.app:
            return
        # review stats is fast and syncronous
        stats = self.review_loader.get_review_stats(self.app)
        self._update_review_stats_widget(stats)
        # individual reviews is slow and async so we just queue it here
        self._do_load_reviews()

    def _on_more_reviews_clicked(self, uilist):
        self._reviews_server_page += 1
        self._do_load_reviews()

    def _on_review_sort_method_changed(self, uilist, sort_method):
        self._reviews_server_page = 1
        self._reviews_relaxed = False
        self._review_sort_method = sort_method
        self.reviews.clear()
        self._do_load_reviews()

    def _on_reviews_in_different_language_clicked(self, uilist, language):
        self._reviews_server_page = 1
        self._reviews_relaxed = False
        self._reviews_server_language = language
        self.reviews.clear()
        self._do_load_reviews()

    def _do_load_reviews(self):
        self.reviews.show_spinner_with_message(_('Checking for reviews...'))
        self.review_loader.get_reviews(
            self.app, self._reviews_ready_callback,
            page=self._reviews_server_page,
            language=self._reviews_server_language,
            sort=self._review_sort_method,
            relaxed=self._reviews_relaxed)

    def _review_update_single(self, action, review):
        if action == 'replace':
            self.reviews.replace_review(review)
        elif action == 'remove':
            self.reviews.remove_review(review)

    def _update_review_stats_widget(self, stats):
        if stats:
            # ensure that the review UI knows about the stats
            self.reviews.global_review_stats = stats
            # update the widget
            self.review_stats_widget.set_avg_rating(stats.ratings_average)
            self.review_stats_widget.set_nr_reviews(stats.ratings_total)
            self.review_stats_widget.show()
        else:
            self.review_stats_widget.hide()

    def _submit_reviews_done_callback(self, spawner, error):
        self.reviews.new_review.enable()

    def _reviews_ready_callback(self, app, reviews_data, my_votes=None,
                                action=None, single_review=None):
        """ callback when new reviews are ready, cleans out the
            old ones
        """
        LOG.debug("_review_ready_callback: %s" % app)
        # avoid possible race if we already moved to a new app when
        # the reviews become ready
        # (we only check for pkgname currently to avoid breaking on
        #  software-center totem)
        if self.app.pkgname != app.pkgname:
            return

        # Start fetching relaxed reviews if we retrieved no data
        # (and if we weren't already relaxed)
        if not reviews_data and not self._reviews_relaxed:
            self._reviews_relaxed = True
            self._reviews_server_page = 1
            self.review_loader.get_reviews(
                self.app, self._reviews_ready_callback,
                page=self._reviews_server_page,
                language=self._reviews_server_language,
                sort=self._review_sort_method,
                relaxed=self._reviews_relaxed)
            return

        # update the stats (if needed). the caching can make them
        # wrong, so if the reviews we have in the list are more than the
        # stats we update manually
        old_stats = self.review_loader.get_review_stats(self.app)
        if ((old_stats is None and len(reviews_data) > 0) or
            (old_stats is not None and
             old_stats.ratings_total < len(reviews_data))):
            # generate new stats
            stats = ReviewStats(app)
            stats.ratings_total = len(reviews_data)
            if stats.ratings_total == 0:
                stats.ratings_average = 0
            else:
                stats.ratings_average = (sum([x.rating for x in reviews_data])
                    / float(stats.ratings_total))
            # update UI
            self._update_review_stats_widget(stats)
            # update global stats cache as well
            self.review_loader.update_review_stats(app, stats)

        if my_votes:
            self.reviews.update_useful_votes(my_votes)

        if action:
            self._review_update_single(action, single_review)
        else:
            curr_list = set(self.reviews.get_all_review_ids())
            retrieved_a_new_review = False
            for review in reviews_data:
                if not review.id in curr_list:
                    retrieved_a_new_review = True
                    self.reviews.add_review(review)
            if reviews_data and not retrieved_a_new_review:
                # We retrieved data, but nothing new.  Keep going.
                self._reviews_server_page += 1
                self.review_loader.get_reviews(
                    self.app, self._reviews_ready_callback,
                    page=self._reviews_server_page,
                    language=self._reviews_server_language,
                    sort=self._review_sort_method,
                    relaxed=self._reviews_relaxed)

        self.reviews.configure_reviews_ui()

    def on_weblive_progress(self, weblive, progress):
        """ When receiving connection progress, update button """
        self.test_drive.set_label(_("Connection ... (%s%%)") % (progress))

    def on_weblive_connected(self, weblive, can_disconnect):
        """ When connected, update button """
        if can_disconnect:
            self.test_drive.set_label(_("Disconnect"))
            self.test_drive.set_sensitive(True)
        else:
            self.test_drive.set_label(_("Connected"))

    def on_weblive_disconnected(self, weblive):
        """ When disconnected, reset button """
        self.test_drive.set_label(_("Test drive"))
        self.test_drive.set_sensitive(True)

    def on_weblive_exception(self, weblive, exception):
        """ When receiving an exception, reset button and show the error """
        error(None, "WebLive exception", exception)
        self.test_drive.set_label(_("Test drive"))
        self.test_drive.set_sensitive(True)

    def on_weblive_warning(self, weblive, warning):
        """ When receiving a warning, just show it """
        error(None, "WebLive warning", warning)

    def on_test_drive_clicked(self, button):
        if self.weblive.client.state == "disconnected":
            # get exec line
            exec_line = get_exec_line_from_desktop(self.desktop_file)

            # split away any arguments, gedit for example as %U
            cmd = exec_line.split()[0]

            # Get the list of servers
            servers = self.weblive.get_servers_for_pkgname(self.app.pkgname)

            if len(servers) == 0:
                error(None,
                      "No available server",
                      "There is currently no available WebLive server "
                      "for this application.\nPlease try again later.")
            elif len(servers) == 1:
                self.weblive.create_automatic_user_and_run_session(
                    session=cmd, serverid=servers[0].name)
                button.set_sensitive(False)
            else:
                d = ShowWebLiveServerChooserDialog(servers, self.app.pkgname)
                serverid = None
                if d.run() == Gtk.ResponseType.OK:
                    for server in d.servers_vbox:
                        if server.get_active():
                            serverid = server.serverid
                            break
                d.destroy()

                if serverid:
                    self.weblive.create_automatic_user_and_run_session(
                        session=cmd, serverid=serverid)
                    button.set_sensitive(False)

        elif self.weblive.client.state == "connected":
            button.set_sensitive(False)
            self.weblive.client.disconnect_session()

    def _on_addon_table_built(self, table):
        if not table.get_parent():
            self.info_vb.pack_start(table, False, False, 0)
            self.info_vb.reorder_child(table, 0)
        if not table.get_property('visible'):
            table.show_all()

    def _on_realize(self, widget):
        self.addons_statusbar.hide()
        # the install button gets initial focus
        self.pkg_statusbar.button.grab_focus()

    def _on_homepage_clicked(self, label, link):
        import webbrowser
        webbrowser.open_new_tab(link)
        return True

    def _layout_page(self):
        # setup widgets
        vb = Gtk.VBox()
        vb.set_spacing(StockEms.MEDIUM)
        vb.set_border_width(StockEms.MEDIUM)
        self.add(vb)

        # header
        hb = Gtk.HBox()
        hb.set_spacing(StockEms.MEDIUM)
        vb.pack_start(hb, False, False, 0)

        # the app icon
        self.icon = Gtk.Image()
        hb.pack_start(self.icon, False, False, 0)

        # the app title/summary
        self.title = Gtk.Label()
        self.subtitle = Gtk.Label()
        self.title.set_alignment(0, 0.5)
        self.subtitle.set_alignment(0, 0.5)
        self.title.set_line_wrap(True)
        self.title.set_selectable(True)
        self.subtitle.set_line_wrap(True)
        self.subtitle.set_selectable(True)
        vb_inner = Gtk.VBox()
        vb_inner.pack_start(self.title, False, False, 0)
        vb_inner.pack_start(self.subtitle, False, False, 0)

        # star rating box/widget
        self.review_stats_widget = StarRatingsWidget()
        self.review_stats = Gtk.HBox()
        vb_inner.pack_start(
            self.review_stats, False, False, 0)
        self.review_stats.pack_start(
            self.review_stats_widget, False, False, StockEms.SMALL)

        #~ vb_inner.set_property("can-focus", True)
        self.title.a11y = vb_inner.get_accessible()
        self.title.a11y.set_role(Atk.Role.PANEL)
        hb.pack_start(vb_inner, False, False, 0)

        # a warning bar (e.g. for HW incompatible packages)
        self.pkg_warningbar = WarningStatusBar(self)
        vb.pack_start(self.pkg_warningbar, False, False, 0)

        # the package status bar
        self.pkg_statusbar = PackageStatusBar(self)
        vb.pack_start(self.pkg_statusbar, False, False, 0)

        # installed where widget
        self.installed_where_hbox = Gtk.HBox()
        self.installed_where_hbox.set_spacing(6)
        hbox_a11y = self.installed_where_hbox.get_accessible()
        self.installed_where_hbox.a11y = hbox_a11y
        vb.pack_start(self.installed_where_hbox, False, False, 0)

        # the hbox that hold the description on the left and the screenshot
        # thumbnail on the right
        body_hb = Gtk.HBox()
        body_hb.set_spacing(12)
        vb.pack_start(body_hb, False, False, 0)

        # append the description widget, hold the formatted long description
        self.desc = AppDescription()
        self.desc.description.set_property("can-focus", True)
        self.desc.description.a11y = self.desc.description.get_accessible()
        body_hb.pack_start(self.desc, True, True, 0)

        # the thumbnail/screenshot
        self.screenshot = ScreenshotGallery(get_distro(), self.icons)
        right_vb = Gtk.VBox()
        right_vb.set_spacing(6)
        body_hb.pack_start(right_vb, False, False, 0)
        frame = SmallBorderRadiusFrame()
        frame.add(self.screenshot)
        right_vb.pack_start(frame, False, False, 0)

        # video
        mini_hb = Gtk.HBox()
        self.videoplayer = VideoPlayer()
        mini_hb.pack_start(self.videoplayer, False, False, 0)
        # add a empty label here to ensure bg is set properly
        mini_hb.pack_start(Gtk.Label(), True, True, 0)
        right_vb.pack_start(mini_hb, False, False, 0)

        # the weblive test-drive stuff
        self.weblive = get_weblive_backend()
        if self.weblive.client is not None:
            self.test_drive = Gtk.Button(_("Test drive"))
            self.test_drive.connect("clicked", self.on_test_drive_clicked)
            right_vb.pack_start(self.test_drive, False, False, 0)

            # attach to all the WebLive events
            self.weblive.client.connect("progress", self.on_weblive_progress)
            self.weblive.client.connect("connected", self.on_weblive_connected)
            self.weblive.client.connect(
                "disconnected", self.on_weblive_disconnected)
            self.weblive.client.connect("exception", self.on_weblive_exception)
            self.weblive.client.connect("warning", self.on_weblive_warning)

        # homepage link button
        self.homepage_btn = Gtk.Label()
        self.homepage_btn.set_name("subtle-label")
        self.homepage_btn.connect('activate-link', self._on_homepage_clicked)

        # support site
        self.support_btn = Gtk.Label()
        self.support_btn.set_name("subtle-label")
        self.support_btn.connect('activate-link', self._on_homepage_clicked)

        # add the links footer to the description widget
        footer_hb = Gtk.HBox(spacing=6)
        footer_hb.pack_start(self.homepage_btn, False, False, 0)
        footer_hb.pack_start(self.support_btn, False, False, 0)
        self.desc.pack_start(footer_hb, False, False, 0)

        self._hbars = [HBar(), HBar(), HBar()]
        vb.pack_start(self._hbars[0], False, False, 0)

        self.info_vb = info_vb = Gtk.VBox()
        info_vb.set_spacing(12)
        vb.pack_start(info_vb, False, False, 0)

        # add-on handling
        self.addon_view = self.addons_manager.table
        info_vb.pack_start(self.addon_view, False, False, 0)

        self.addons_statusbar = self.addons_manager.status_bar
        self.addon_view.pack_start(self.addons_statusbar, False, False, 0)
        self.addon_view.connect('table-built', self._on_addon_table_built)

        self.addons_hbar = self._hbars[1]
        info_vb.pack_start(self.addons_hbar, False, False, StockEms.SMALL)

        # recommendations
        catview = CategoriesViewGtk(
            self.datadir, None, self.cache, self.db, self.icons, None)
        self.recommended_for_app_panel = RecommendationsPanelDetails(catview)
        self.recommended_for_app_panel.connect(
            "application-activated",
            self._on_recommended_application_activated)
        self.recommended_for_app_panel.show_all()
        self.info_vb.pack_start(self.recommended_for_app_panel, False,
            False, 0)

        # package info
        self.info_keys = []

        # info header
        #~ self.info_header = Gtk.Label()
        #~ self.info_header.set_markup('<big><b>%s</b></big>' % _("Details"))
        #~ self.info_header.set_alignment(0, 0.5)
        #~ self.info_header.set_padding(0, 6)
        #~ self.info_header.set_use_markup(True)
        #~ info_vb.pack_start(self.info_header, False, False, 0)

        self.version_info = PackageInfo(_("Version"), self.info_keys)
        info_vb.pack_start(self.version_info, False, False, 0)

        self.hardware_info = PackageInfoHW(_("Also requires"), self.info_keys)
        info_vb.pack_start(self.hardware_info, False, False, 0)

        self.totalsize_info = PackageInfo(_("Total size"), self.info_keys)
        info_vb.pack_start(self.totalsize_info, False, False, 0)

        self.license_info = PackageInfo(_("License"), self.info_keys)
        info_vb.pack_start(self.license_info, False, False, 0)

        self.support_info = PackageInfo(_("Updates"), self.info_keys)
        info_vb.pack_start(self.support_info, False, False, 0)

        vb.pack_start(self._hbars[2], False, False, 0)

        # reviews cascade
        self.reviews.connect("new-review", self._on_review_new)
        self.reviews.connect("report-abuse", self._on_review_report_abuse)
        self.reviews.connect("submit-usefulness",
            self._on_review_submit_usefulness)
        self.reviews.connect("modify-review", self._on_review_modify)
        self.reviews.connect("delete-review", self._on_review_delete)
        self.reviews.connect("more-reviews-clicked",
                             self._on_more_reviews_clicked)
        self.reviews.connect("different-review-language-clicked",
                             self._on_reviews_in_different_language_clicked)
        self.reviews.connect("review-sort-changed",
                             self._on_review_sort_method_changed)
        if get_distro().REVIEWS_SERVER:
            vb.pack_start(self.reviews, False, False, 0)

        self.show_all()

        # signals!
        self.connect('size-allocate', lambda w, a: w.queue_draw())

    def _on_recommended_application_activated(self, recwidget, app):
        self.emit("different-application-selected", app)

    def _on_review_new(self, button):
        self._review_write_new()

    def _on_review_modify(self, button, review_id):
        self._review_modify(review_id)

    def _on_review_delete(self, button, review_id):
        self._review_delete(review_id)

    def _on_review_report_abuse(self, button, review_id):
        self._review_report_abuse(str(review_id))

    def _on_review_submit_usefulness(self, button, review_id, is_useful):
        self._review_submit_usefulness(review_id, is_useful)

    def _update_title_markup(self, appname, summary):
        # make title font size fixed as they should look good compared to the
        # icon (also fixed).
        font_size = em(1.6) * Pango.SCALE
        markup = '<span font_size="%s"><b>%s</b></span>'
        markup = markup % (font_size, appname)
        self.title.set_markup(markup)
        self.title.a11y.set_name(appname + '. ' + summary)
        self.subtitle.set_markup(summary)

    def _update_app_icon(self, app_details):
        pb = self._get_icon_as_pixbuf(app_details)
        # should we show the green tick?
#        self._show_overlay = app_details.pkg_state == PkgStates.INSTALLED
        w, h = pb.get_width(), pb.get_height()

        tw = self.APP_ICON_SIZE  # target width
        if pb.get_width() < tw:
            pb = pb.scale_simple(tw, tw, GdkPixbuf.InterpType.TILES)

        self.icon.set_from_pixbuf(pb)
        self.icon.set_size_request(self.APP_ICON_SIZE, self.APP_ICON_SIZE)

    def _update_layout_error_status(self, pkg_error):
        # if we have an error or if we need to enable a source
        # then hide everything else
        if pkg_error:
            self.addon_view.hide()
            self.reviews.hide()
            self.review_stats.hide()
            self.screenshot.hide()
            #~ self.info_header.hide()
            self.info_vb.hide()
            for hbar in self._hbars:
                hbar.hide()
        else:
            self.addon_view.show()
            self.reviews.show()
            self.review_stats.show()
            self.screenshot.show()
            #~ self.info_header.show()
            self.info_vb.show()
            for hbar in self._hbars:
                hbar.show()

    def _update_app_description(self, app_details, appname):
        # format new app description
        description = app_details.description
        if not description:
            description = " "
        self.desc.set_description(description, appname)

        # a11y for description
        self.desc.description.a11y.set_name(description)

    def _update_description_footer_links(self, app_details):
        # show or hide the homepage button and set uri if homepage specified
        if app_details.website:
            self.homepage_btn.show()
            self.homepage_btn.set_markup("<a href=\"%s\">%s</a>" % (
                    self.app_details.website, _('Developer Web Site')))
            self.homepage_btn.set_tooltip_text(app_details.website)
        else:
            self.homepage_btn.hide()
        # support too
        if app_details.supportsite:
            self.support_btn.show()
            self.support_btn.set_markup("<a href=\"%s\">%s</a>" % (
                    self.app_details.supportsite, _('Support Web Site')))
            self.support_btn.set_tooltip_text(app_details.supportsite)
        else:
            self.support_btn.hide()

    def _update_app_video(self, app_details):
        self.videoplayer.uri = app_details.video_url
        if app_details.video_url:
            self.videoplayer.show()
        else:
            self.videoplayer.hide()

    def _update_app_screenshot(self, app_details):
        # get screenshot urls and configure the ScreenshotView...
        if app_details.thumbnail and app_details.screenshot:
            self.screenshot.fetch_screenshots(app_details)

    def _update_weblive(self, app_details):
        if self.weblive.client is None:
            return
        self.desktop_file = app_details.desktop_file
        # only enable test drive if we have a desktop file and exec line
        if (not self.weblive.ready or
            not self.weblive.is_pkgname_available_on_server(
                app_details.pkgname) or
            not os.path.exists(self.desktop_file) or
            not get_exec_line_from_desktop(self.desktop_file)):
            self.test_drive.hide()
        else:
            self.test_drive.show()

    def _update_warning_bar(self, app_details):
        # generic error wins over HW issue
        if app_details.pkg_state == PkgStates.ERROR:
            self.pkg_warningbar.show()
            self.pkg_warningbar.label.set_text(app_details.error)
            return
        if (app_details.hardware_requirements_satisfied and
            app_details.region_requirements_satisfied):
            self.pkg_warningbar.hide()
        else:
            s = get_hw_missing_long_description(
                app_details.hardware_requirements)
            if not app_details.region_requirements_satisfied:
                if len(s) > 0:
                    s += "\n" + REGION_WARNING_STRING
                else:
                    s = REGION_WARNING_STRING
            self.pkg_warningbar.label.set_text(s)
            self.pkg_warningbar.show()

    def _update_pkg_info_table(self, app_details):
        # set the strings in the package info table
        if app_details.version:
            version = '%s %s' % (app_details.pkgname, app_details.version)
        else:
            version = utf8(_("%s (unknown version)")) % utf8(
                app_details.pkgname)
        if app_details.license:
            license = GObject.markup_escape_text(app_details.license)
        else:
            license = _("Unknown")
        if app_details.maintenance_status:
            support = GObject.markup_escape_text(
                app_details.maintenance_status)
        else:
            support = _("Unknown")
        # regular label updates
        self.version_info.set_value(version)
        self.license_info.set_value(license)
        self.support_info.set_value(support)
        # this is slightly special as its not using a label but a special
        # widget
        self.hardware_info.set_value(app_details.hardware_requirements)
        if self.app_details.hardware_requirements:
            self.hardware_info.show()
        else:
            self.hardware_info.hide()

    def _update_addons(self, app_details):
        # refresh addons interface
        self.addon_view.hide()
        if self.addon_view.get_parent():
            self.info_vb.remove(self.addon_view)

        if not app_details.error:
            self.addons_manager.configure(app_details.pkgname)

        # Update total size label
        self.totalsize_info.set_value(_("Calculating..."))
        GObject.timeout_add(500, self.update_totalsize)

        # Update addons state bar
        self.addons_statusbar.configure()

    def _update_all(self, app_details, skip_update_addons=False):
        # reset view to top left
        vadj = self.get_vadjustment()
        hadj = self.get_hadjustment()
        if vadj:
            vadj.set_value(0)
        if hadj:
            hadj.set_value(0)

        # set button sensitive again
        self.pkg_statusbar.button.set_sensitive(True)

        pkg_ambiguous_error = app_details.pkg_state in (PkgStates.NOT_FOUND,
                                                        PkgStates.NEEDS_SOURCE)

        appname = GObject.markup_escape_text(app_details.display_name)

        if app_details.pkg_state == PkgStates.NOT_FOUND:
            summary = app_details._error_not_found
        else:
            summary = GObject.markup_escape_text(app_details.display_summary)
        if not summary:
            summary = ""

        # depending on pkg install state set action labels
        self.pkg_statusbar.configure(app_details, app_details.pkg_state)

        self._update_layout_error_status(pkg_ambiguous_error)
        self._update_title_markup(appname, summary)
        self._update_app_icon(app_details)
        self._update_app_description(app_details, app_details.pkgname)
        self._update_description_footer_links(app_details)
        self._update_app_screenshot(app_details)
        self._update_app_video(app_details)
        self._update_weblive(app_details)
        self._update_pkg_info_table(app_details)
        self._update_warning_bar(app_details)
        if not skip_update_addons:
            self._update_addons(app_details)
        else:
            self.addon_view.hide()
            if self.addon_view.get_parent():
                self.info_vb.remove(self.addon_view)
            self.totalsize_info.set_value(_("Calculating..."))
            GObject.idle_add(self.update_totalsize,
                             priority=GObject.PRIORITY_LOW)
        self._update_recommendations(app_details.pkgname)
        self._update_reviews(app_details)

        # show where it is
        self._configure_where_is_it()

    def _update_minimal(self, app_details):
        self._update_app_icon(app_details)
        self._update_pkg_info_table(app_details)
        self._update_warning_bar(app_details)
#        self._update_addons_minimal(app_details)

        # depending on pkg install state set action labels
        self.pkg_statusbar.configure(app_details, app_details.pkg_state)

#        # show where it is
        self._configure_where_is_it()

    def _add_where_is_it_commandline(self, pkgname):
        cmdfinder = CmdFinder(self.cache)
        cmds = cmdfinder.find_cmds_from_pkgname(pkgname)
        if not cmds:
            return
        vb = Gtk.VBox()
        vb.set_spacing(12)
        self.installed_where_hbox.pack_start(vb, False, False, 0)
        msg = gettext.ngettext(
            _('This program is run from a terminal: '),
            _('These programs are run from a terminal: '),
            len(cmds))
        title = Gtk.Label()
        title.set_alignment(0, 0)
        title.set_markup(msg)
        title.set_line_wrap(True)
        #~ title.set_size_request(self.get_allocation().width-24, -1)
        vb.pack_start(title, False, False, 0)
        cmds_str = ", ".join(cmds)
        cmd_label = Gtk.Label(
            label='<span font_desc="monospace bold 9">%s</span>' % cmds_str)
        cmd_label.set_selectable(True)
        cmd_label.set_use_markup(True)
        cmd_label.set_alignment(0, 0.5)
        cmd_label.set_padding(12, 0)
        cmd_label.set_line_wrap(True)
        vb.pack_start(cmd_label, False, False, 0)
        self.installed_where_hbox.show_all()

    def _add_where_is_it_launcher(self, desktop_file):
        searcher = GMenuSearcher()
        where = searcher.get_main_menu_path(desktop_file)
        if not where:
            return
        # display launcher location
        label = Gtk.Label(label=_("Find it in the menu: "))
        self.installed_where_hbox.pack_start(label, False, False, 0)
        for (i, item) in enumerate(where):
            icon = None
            iconname = None
            if hasattr(item, "get_icon"):
                icon = item.get_icon()
            elif hasattr(item, "get_app_info"):
                app_info = item.get_app_info()
                icon = app_info.get_icon()
            if icon:
                iconinfo = self.icons.lookup_by_gicon(icon, 18, 0)
                iconname = iconinfo.get_filename()

            # we get the right name from the lookup we did before
            if iconname and os.path.exists(iconname):
                image = Gtk.Image()
                pb = GdkPixbuf.Pixbuf.new_from_file_at_size(iconname, 18, 18)
                if pb:
                    image.set_from_pixbuf(pb)
                self.installed_where_hbox.pack_start(image, False, False, 0)

            label_name = Gtk.Label()
            if hasattr(item, "get_name"):
                label_name.set_text(item.get_name())
            elif hasattr(item, "get_app_info"):
                app_info = item.get_app_info()
                label_name.set_text(app_info.get_name())

            self.installed_where_hbox.pack_start(label_name, False, False, 0)
            if i + 1 < len(where):
                right_arrow = Gtk.Arrow.new(Gtk.ArrowType.RIGHT,
                    Gtk.ShadowType.NONE)
                self.installed_where_hbox.pack_start(right_arrow,
                                                         False, False, 0)

        # create our a11y text
        a11y_text = ""
        for widget in self.installed_where_hbox:
            if isinstance(widget, Gtk.Label):
                a11y_text += ' > ' + widget.get_text()
        self.installed_where_hbox.a11y.set_name(a11y_text)
        self.installed_where_hbox.set_property("can-focus", True)
        self.installed_where_hbox.show_all()

    def _configure_where_is_it(self):

        def get_desktop_file():
            # we should know the desktop file
            if self.app_details.desktop_file:
                return self.app_details.desktop_file
            # fallback mode
            pkgname = self.app_details.pkgname
            desktop_file = "/usr/share/applications/%s.desktop" % pkgname
            if not os.path.exists(desktop_file):
                    return None
            return desktop_file

        # remove old content
        self.installed_where_hbox.foreach(lambda w, d: w.destroy(), None)
        self.installed_where_hbox.set_property("can-focus", False)
        self.installed_where_hbox.a11y.set_name('')

        # display where-is-it for non-Unity configurations only
        if is_unity_running():
            # but still display available commands, even in unity
            # because these are not easily discoverable and we don't
            # offer a launcher
            if not get_desktop_file():
                self._add_where_is_it_commandline(self.app_details.pkgname)
            return

        # see if we have the location if its installed
        if self.app_details.pkg_state == PkgStates.INSTALLED:
            # first try the desktop file from the DB, then see if
            # there is a local desktop file with the same name as
            # the package
            # try to show menu location if there is a desktop file, but
            # never show commandline programs for apps with a desktop file
            # to cover cases like "file-roller" that have NoDisplay=true
            desktop_file = get_desktop_file()
            if desktop_file:
                self._add_where_is_it_launcher(desktop_file)
            # if there is no desktop file, show commandline
            else:
                self._add_where_is_it_commandline(self.app_details.pkgname)

    # public API
    def show_app(self, app, force=False):
        LOG.debug("AppDetailsView.show_app '%s'" % app)
        if app is None:
            LOG.debug("no app selected")
            return

        same_app = (self.app and
                    self.app.pkgname and
                    self.app.appname == app.appname and
                    self.app.pkgname == app.pkgname)
        #print 'SameApp:', same_app

        # init data
        self.app = app
        self.app_details = app.get_details(self.db)

        # check if app just became available and if so, force full
        # refresh
        if same_app:
            # if the app was in one of the states, force refresh if its
            # no longer in this state
            for state in [PkgStates.NEEDS_SOURCE, PkgStates.NOT_FOUND]:
                if (self.pkg_state == state and
                    self.app_details.pkg_state != state):
                    force = True
        self.pkg_state = self.app_details.pkg_state

        # for compat with the base class
        self.appdetails = self.app_details

        # update content
        # layout page
        if same_app and not force:
            self._update_minimal(self.app_details)
        else:
            # reset reviews_page
            self._reviews_server_page = 1
            # update all (but skip the addons calculation if this is a
            # DebFileApplication as this is not useful for this case and it
            # increases the view load time dramatically)
            skip_update_addons = isinstance(self.app, DebFileApplication)
            self._update_all(self.app_details,
                             skip_update_addons=skip_update_addons)

        # this is a bit silly, but without it and self.title being selectable
        # gtk will select the entire title (which looks ugly). this grab works
        # around that
        self.pkg_statusbar.button.grab_focus()

        self.emit("selected", self.app)

    def refresh_app(self):
        self.show_app(self.app)

    # common code
    def _review_write_new(self):
        if (not self.app or
            not self.app.pkgname in self.cache or
            not self.cache[self.app.pkgname].candidate):
            dialogs.error(None,
                          _("Version unknown"),
                          _("The version of the application can not "
                            "be detected. Entering a review is not "
                            "possible."))
            return
        # gather data
        pkg = self.cache[self.app.pkgname]
        version = pkg.candidate.version
        origin = self.cache.get_origin(self.app.pkgname)

        # FIXME: probably want to not display the ui if we can't review it
        if not origin:
            dialogs.error(None,
                        _("Origin unknown"),
                        _("The origin of the application can not "
                          "be detected. Entering a review is not "
                          "possible."))
            return

        if pkg.installed:
            version = pkg.installed.version
        # call the loader to do call out the right helper and collect the
        # result
        parent_xid = ''
        #parent_xid = get_parent_xid(self)
        self.reviews.new_review.disable()
        self.review_loader.spawn_write_new_review_ui(
            self.app, version, self.appdetails.icon, origin,
            parent_xid, self.datadir,
            self._reviews_ready_callback,
            done_callback=self._submit_reviews_done_callback)

    def _review_report_abuse(self, review_id):
        parent_xid = ''
        #parent_xid = get_parent_xid(self)
        self.review_loader.spawn_report_abuse_ui(
            review_id, parent_xid, self.datadir, self._reviews_ready_callback)

    def _review_submit_usefulness(self, review_id, is_useful):
        parent_xid = ''
        #parent_xid = get_parent_xid(self)
        self.review_loader.spawn_submit_usefulness_ui(
            review_id, is_useful, parent_xid, self.datadir,
            self._reviews_ready_callback)

    def _review_modify(self, review_id):
        parent_xid = ''
        #parent_xid = get_parent_xid(self)
        self.review_loader.spawn_modify_review_ui(
            parent_xid, self.appdetails.icon, self.datadir, review_id,
            self._reviews_ready_callback)

    def _review_delete(self, review_id):
        parent_xid = ''
        #parent_xid = get_parent_xid(self)
        self.review_loader.spawn_delete_review_ui(
            review_id, parent_xid, self.datadir, self._reviews_ready_callback)

    # internal callbacks
    def _on_cache_ready(self, cache):
        # re-show the application if the cache changes, it may affect the
        # current application
        LOG.debug("on_cache_ready")
        self.show_app(self.app)

    def _update_interface_on_trans_ended(self, result):
        state = self.pkg_statusbar.pkg_state

        # handle purchase: install purchased has multiple steps
        if (state == PkgStates.INSTALLING_PURCHASED and
            result and
            not result.pkgname):
            self.pkg_statusbar.configure(self.app_details,
                PkgStates.INSTALLING_PURCHASED)
        elif (state == PkgStates.INSTALLING_PURCHASED and
              result and
              result.pkgname):
            self.pkg_statusbar.configure(self.app_details, PkgStates.INSTALLED)
            # reset the reviews UI now that we have installed the package
            self.reviews.configure_reviews_ui()
        # normal states
        elif state == PkgStates.REMOVING:
            self.pkg_statusbar.configure(self.app_details,
                PkgStates.UNINSTALLED)
        elif state == PkgStates.INSTALLING:
            self.pkg_statusbar.configure(self.app_details, PkgStates.INSTALLED)
        elif state == PkgStates.UPGRADING:
            self.pkg_statusbar.configure(self.app_details, PkgStates.INSTALLED)
        # addons modified, order is important here
        elif self.addons_statusbar.applying:
            self.pkg_statusbar.configure(self.app_details, PkgStates.INSTALLED)
            self.addons_manager.configure(self.app_details.name, False)
            self.addons_statusbar.configure()
        # cancellation of dependency dialog
        elif state == PkgStates.INSTALLED:
            self.pkg_statusbar.configure(self.app_details, PkgStates.INSTALLED)
            # reset the reviews UI now that we have installed the package
            self.reviews.configure_reviews_ui()
        elif state == PkgStates.UNINSTALLED:
            self.pkg_statusbar.configure(self.app_details,
                PkgStates.UNINSTALLED)
        self.adjustment_value = None

        if self.addons_statusbar.applying:
            self.addons_statusbar.applying = False

        return False

    def _on_transaction_started(self, backend, pkgname, appname, trans_id,
                                trans_type):
        if self.addons_statusbar.applying:
            self.pkg_statusbar.configure(self.app_details, AppActions.APPLY)
            return

        state = self.pkg_statusbar.pkg_state
        LOG.debug("_on_transaction_started %s" % state)
        if state == PkgStates.NEEDS_PURCHASE:
            self.pkg_statusbar.configure(self.app_details,
                                         PkgStates.INSTALLING_PURCHASED)
        elif (state == PkgStates.UNINSTALLED or
              state == PkgStates.FORCE_VERSION):
            self.pkg_statusbar.configure(self.app_details,
                PkgStates.INSTALLING)
        elif state == PkgStates.INSTALLED:
            self.pkg_statusbar.configure(self.app_details, PkgStates.REMOVING)
        elif state == PkgStates.UPGRADABLE:
            self.pkg_statusbar.configure(self.app_details, PkgStates.UPGRADING)
        elif state == PkgStates.REINSTALLABLE:
            self.pkg_statusbar.configure(self.app_details,
                PkgStates.INSTALLING)
            # FIXME: is there a way to tell if we are installing/removing?
            # we will assume that it is being installed, but this means that
            # during removals we get the text "Installing.."
            # self.pkg_statusbar.configure(self.app_details,
            #     PkgStates.REMOVING)

    def _on_transaction_stopped(self, backend, result):
        self.pkg_statusbar.progress.hide()
        self._update_interface_on_trans_ended(result)

    def _on_transaction_finished(self, backend, result):
        self.pkg_statusbar.progress.hide()
        self._update_interface_on_trans_ended(result)

    def _on_transaction_progress_changed(self, backend, pkgname, progress):
        if (self.app_details and
            self.app_details.pkgname and
            self.app_details.pkgname == pkgname):
            if not self.pkg_statusbar.progress.get_property('visible'):
                self.pkg_statusbar.button.hide()
                self.pkg_statusbar.combo_multiple_versions.hide()
                self.pkg_statusbar.progress.show()
            if pkgname in backend.pending_transactions:
                self.pkg_statusbar.progress.set_fraction(progress / 100.0)
            if progress >= 100:
                self.pkg_statusbar.progress.set_fraction(1)
                adj = self.get_vadjustment()
                if adj:
                    self.adjustment_value = adj.get_value()

    def get_app_icon_details(self):
        """ helper for unity dbus support to provide details about the
            application icon as it is displayed on-screen
        """
        icon_size = self._get_app_icon_size_on_screen()
        (icon_x, icon_y) = self._get_app_icon_xy_position_on_screen()
        return (icon_size, icon_x, icon_y)

    def _get_app_icon_size_on_screen(self):
        """ helper for unity dbus support to get the size of the maximum side
            for the application icon as it is displayed on-screen
        """
        icon_size = self.APP_ICON_SIZE
        if self.icon.get_storage_type() == Gtk.ImageType.PIXBUF:
            pb = self.icon.get_pixbuf()
            if pb.get_width() > pb.get_height():
                icon_size = pb.get_width()
            else:
                icon_size = pb.get_height()
        return icon_size

    def _get_app_icon_xy_position_on_screen(self):
        """ helper for unity dbus support to get the x,y position of
            the application icon as it is displayed on-screen. if the icon's
            position cannot be determined for any reason, then the value (0,0)
            is returned
        """
        # find toplevel parent
        parent = self
        while parent.get_parent():
            parent = parent.get_parent()
        # get x, y relative to toplevel
        try:
            (x, y) = self.icon.translate_coordinates(parent, 0, 0)
        except Exception as e:
            LOG.warning("couldn't translate icon coordinates on-screen "
                        "for unity dbus message: %s" % e)
            return (0, 0)
        # get toplevel window position
        (px, py) = parent.get_position()
        return (px + x, py + y)

    def _get_icon_as_pixbuf(self, app_details):
        if app_details.icon:
            if self.icons.has_icon(app_details.icon):
                try:
                    return self.icons.load_icon(app_details.icon,
                                                self.APP_ICON_SIZE, 0)
                except GObject.GError as e:
                    logging.warn("failed to load '%s': %s" % (
                            app_details.icon, e))
                    return self.icons.load_icon(Icons.MISSING_APP,
                                                self.APP_ICON_SIZE, 0)
            elif app_details.icon_url:
                LOG.debug("did not find the icon locally, must download it")

                def on_image_download_complete(downloader, image_file_path):
                    # when the download is complete, replace the icon in the
                    # view with the downloaded one
                    logging.debug("_get_icon_as_pixbuf:image_downloaded() %s" %
                        image_file_path)
                    try:
                        pb = GdkPixbuf.Pixbuf.new_from_file(image_file_path)
                        # fixes crash in testsuite if window is destroyed
                        # and after that this callback is called (wouldn't
                        # it be nice if gtk would do that automatically?)
                        if self.icon.get_property("visible"):
                            self.icon.set_from_pixbuf(pb)
                    except Exception as e:
                        LOG.warning(
                            "couldn't load downloadable icon file '%s': %s" %
                            (image_file_path, e))

                image_downloader = SimpleFileDownloader()
                image_downloader.connect(
                    'file-download-complete', on_image_download_complete)
                image_downloader.download_file(
                    app_details.icon_url, app_details.cached_icon_file_path)
        return self.icons.load_icon(Icons.MISSING_APP, self.APP_ICON_SIZE, 0)

    def update_totalsize(self):
        if not self.totalsize_info.get_property('visible'):
            return False

        while Gtk.events_pending():
            Gtk.main_iteration()

        label_string = ""

        res = self.cache.get_total_size_on_install(
            self.app_details.pkgname,
            self.addons_manager.addons_to_install,
            self.addons_manager.addons_to_remove,
            self.app.archive_suite)
        total_download_size, total_install_size = res
        if res == (0, 0) and isinstance(self.app, DebFileApplication):
            total_install_size = self.app_details.installed_size
        if total_download_size > 0:
            download_size = GLib.format_size(total_download_size)
            label_string += _("%s to download, ") % (download_size)
        if total_install_size > 0:
            install_size = GLib.format_size(total_install_size)
            label_string += _("%s when installed") % (install_size)
        elif (total_install_size == 0 and
              self.app_details.pkg_state == PkgStates.INSTALLED and
              not self.addons_manager.addons_to_install and
              not self.addons_manager.addons_to_remove):
            pkg_version = self.cache[self.app_details.pkgname].installed
            # we may not always get a pkg_version returned (LP: #870822),
            # in that case, we'll just have to display "Unknown"
            if pkg_version:
                install_size = GLib.format_size(pkg_version.installed_size)
                # FIXME: this is not really a good indication of the size
                # on disk
                label_string += _("%s on disk") % (install_size)
        elif total_install_size < 0:
            remove_size = GLib.format_size(-total_install_size)
            label_string += _("%s to be freed") % (remove_size)

        self.totalsize_info.set_value(label_string or _("Unknown"))
#        self.totalsize_info.show_all()
        return False

    def set_section(self, section):
        self.section = section


def get_test_window_appdetails():

    from softwarecenter.db.pkginfo import get_pkg_info
    cache = get_pkg_info()
    cache.open()

    from softwarecenter.db.database import StoreDatabase
    xapian_base_path = "/var/cache/software-center"
    pathname = os.path.join(xapian_base_path, "xapian")
    db = StoreDatabase(pathname, cache)
    db.open()

    import softwarecenter.paths
    datadir = softwarecenter.paths.datadir

    from softwarecenter.ui.gtk3.utils import get_sc_icon_theme
    icons = get_sc_icon_theme(datadir)

    import softwarecenter.distro
    distro = softwarecenter.distro.get_distro()

    # gui
    win = Gtk.Window()
    scroll = Gtk.ScrolledWindow()
    view = AppDetailsView(db, distro, icons, cache, datadir)

    import sys
    if len(sys.argv) > 1:
        pkgname = sys.argv[1]
    else:
        pkgname = "totem"

    view.show_app(Application("", pkgname))
    #view.show_app(Application("Pay App Example", "pay-app"))
    #view.show_app(Application("3D Chess", "3dchess"))
    #view.show_app(Application("Movie Player", "totem"))
    #view.show_app(Application("ACE", "unace"))
    #~ view.show_app(Application("", "apt"))

    #view.show_app("AMOR")
    #view.show_app("Configuration Editor")
    #view.show_app("Artha")
    #view.show_app("cournol")
    #view.show_app("Qlix")

    scroll.add(view)
    scroll.show()
    win.add(scroll)
    win.set_size_request(600, 800)
    win.show()
    win.connect('destroy', Gtk.main_quit)
    win.set_data("view", view)
    return win


if __name__ == "__main__":
    def _show_app(view):
        if view.app.pkgname == "totem":
            view.show_app(Application("Pithos", "pithos"))
        else:
            view.show_app(Application("Movie Player", "totem"))
        return True

    win = get_test_window_appdetails()

    # keep it spinning to test for re-draw issues and memleaks
    #view = win.get_data("view")
    #GObject.timeout_add_seconds(2, _show_app, view)

    # run it
    Gtk.main()
