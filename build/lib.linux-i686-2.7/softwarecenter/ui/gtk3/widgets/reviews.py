#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2010 Canonical
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
from gi.repository import Gtk, GObject, Pango
import datetime
import logging

import gettext
from gettext import gettext as _

from stars import Star
from softwarecenter.utils import (
    get_person_from_config,
    get_nice_date_string,
    upstream_version_compare,
    upstream_version,
    utf8,
    )


from softwarecenter.i18n import (
    get_languages,
    langcode_to_name,
    )

from softwarecenter.netstatus import (
    network_state_is_connected,
    get_network_watcher,
    )
from softwarecenter.enums import (
    PkgStates,
    ReviewSortMethods,
    )

from softwarecenter.backend.reviews import UsefulnessCache

from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.ui.gtk3.widgets.buttons import Link

LOG_ALLOCATION = logging.getLogger("softwarecenter.ui.Gtk.get_allocation()")
LOG = logging.getLogger(__name__)

(COL_LANGNAME,
 COL_LANGCODE) = range(2)


class UIReviewsList(Gtk.VBox):

    __gsignals__ = {
        'new-review': (GObject.SignalFlags.RUN_FIRST,
                    None,
                    ()),
        'report-abuse': (GObject.SignalFlags.RUN_FIRST,
                    None,
                    (GObject.TYPE_PYOBJECT,)),
        'submit-usefulness': (GObject.SignalFlags.RUN_FIRST,
                    None,
                    (GObject.TYPE_PYOBJECT, bool)),
        'modify-review': (GObject.SignalFlags.RUN_FIRST,
                    None,
                    (GObject.TYPE_PYOBJECT,)),
        'delete-review': (GObject.SignalFlags.RUN_FIRST,
                    None,
                    (GObject.TYPE_PYOBJECT,)),
        'more-reviews-clicked': (GObject.SignalFlags.RUN_FIRST,
                                None,
                                ()),
        'different-review-language-clicked': (GObject.SignalFlags.RUN_FIRST,
                                             None,
                                             (GObject.TYPE_STRING,)),
        'review-sort-changed': (GObject.SignalFlags.RUN_FIRST,
                               None,
                               (GObject.TYPE_INT,)),
    }

    def __init__(self, parent):
        GObject.GObject.__init__(self)
        self.set_spacing(12)
        self.logged_in_person = get_person_from_config()

        self._parent = parent
        # this is a list of review data (softwarecenter.backend.reviews.Review)
        self.reviews = []
        # global review stats, this includes ratings in different languages
        self.global_review_stats = None
        # usefulness stuff
        self.useful_votes = UsefulnessCache()
        self.logged_in_person = None

        # add header label
        label = Gtk.Label()
        label.set_markup('<big><b>%s</b></big>' % _("Reviews"))
        label.set_padding(6, 6)
        label.set_use_markup(True)
        label.set_alignment(0, 0.5)
        self.header = Gtk.HBox()
        self.header.pack_start(label, False, False, 0)

        # header
        self.header.set_spacing(StockEms.MEDIUM)

        # review sort method
        self.sort_combo = Gtk.ComboBoxText()
        self._current_sort = 0
        for sort_method in ReviewSortMethods.REVIEW_SORT_LIST_ENTRIES:
            self.sort_combo.append_text(_(sort_method))
        self.sort_combo.set_active(self._current_sort)
        self.sort_combo.connect('changed', self._on_sort_method_changed)
        self.header.pack_end(self.sort_combo, False, False, 3)

        # change language
        self.review_language = Gtk.ComboBox()
        cell = Gtk.CellRendererText()
        self.review_language.pack_start(cell, True)
        self.review_language.add_attribute(cell, "text", COL_LANGNAME)
        self.review_language_model = Gtk.ListStore(str, str)
        for lang in get_languages():
            self.review_language_model.append((langcode_to_name(lang), lang))
        self.review_language_model.append((_('Any language'), 'any'))
        self.review_language.set_model(self.review_language_model)
        self.review_language.set_active(0)
        self.review_language.connect(
            "changed", self._on_different_review_language_clicked)
        self.header.pack_end(self.review_language, False, True, 0)

        self.pack_start(self.header, False, False, 0)
        self.reviews_info_hbox = Gtk.HBox()
        self.new_review = Link(_('Write your own review'))
        self.new_review.connect('clicked', lambda w: self.emit('new-review'))
        self.reviews_info_hbox.pack_start(
            self.new_review, False, False, StockEms.SMALL)
        self.pack_start(self.reviews_info_hbox, True, True, 0)
        # this is where the reviews end up
        self.vbox = Gtk.VBox()
        self.vbox.set_spacing(24)
        self.pack_end(self.vbox, True, True, 0)

        # ensure network state updates
        self.no_network_msg = None
        watcher = get_network_watcher()
        watcher.connect(
            "changed", lambda w, s: self._on_network_state_change())

        self.show_all()

    def _on_network_state_change(self):
        is_connected = network_state_is_connected()
        if is_connected:
            self.new_review.set_sensitive(True)
            if self.no_network_msg:
                self.no_network_msg.hide()
        else:
            self.new_review.set_sensitive(False)
            if self.no_network_msg:
                self.no_network_msg.show()

    def _on_button_new_clicked(self, button):
        self.emit("new-review")

    def _on_sort_method_changed(self, cb):
        selection = self.sort_combo.get_active()
        if selection == self._current_sort:
            return
        else:
            self._current_sort = selection
            self.emit("review-sort-changed", selection)

    def update_useful_votes(self, my_votes):
        self.useful_votes = my_votes

    def _fill(self):
        """ take the review data object from self.reviews and build the
            UI vbox out of them
        """
        self.logged_in_person = get_person_from_config()
        is_first_for_version = None
        if self.reviews:
            previous_review = None
            for r in self.reviews:
                pkgversion = self._parent.app_details.version
                if previous_review:
                    is_first_for_version = previous_review.version != r.version
                else:
                    is_first_for_version = True
                previous_review = r
                review = UIReview(r, pkgversion, self.logged_in_person,
                    self.useful_votes, is_first_for_version)
                review.show_all()
                self.vbox.pack_start(review, True, True, 0)

    def _be_the_first_to_review(self):
        s = _('Be the first to review it')
        self.new_review.set_label(s)
        self.vbox.pack_start(NoReviewYetWriteOne(), True, True, 0)
        self.vbox.show_all()

    def _install_to_review(self):
        s = ('<small>%s</small>' %
            _("You need to install this before you can review it"))
        self.install_first_label = Gtk.Label(label=s)
        self.install_first_label.set_use_markup(True)
        self.install_first_label.set_alignment(1.0, 0.5)
        self.reviews_info_hbox.pack_start(
            self.install_first_label, False, False, 0)
        self.install_first_label.show()

    # FIXME: this needs to be smarter in the future as we will
    #        not allow multiple reviews for the same software version
    def _any_reviews_current_user(self):
        for review in self.reviews:
            if self.logged_in_person == review.reviewer_username:
                return True
        return False

    def _add_no_network_connection_msg(self):
        title = _('No network connection')
        msg = _('Connect to the Internet to see more reviews.')
        m = EmbeddedMessage(title, msg, 'network-offline')
        self.vbox.pack_start(m, True, True, 0)
        return m

    def _clear_vbox(self, vbox):
        children = vbox.get_children()
        for child in children:
            child.destroy()

    # FIXME: instead of clear/add_reviews/configure_reviews_ui we should
    #        provide a single show_reviews(reviews_data_list)
    def configure_reviews_ui(self):
        """ this needs to be called after add_reviews, it will actually
            show the reviews
        """
        #print 'Review count: %s' % len(self.reviews)

        try:
            self.install_first_label.hide()
        except AttributeError:
            pass

        self._clear_vbox(self.vbox)

        # network sensitive stuff, only show write_review if connected,
        # add msg about offline cache usage if offline
        is_connected = network_state_is_connected()
        self.no_network_msg = self._add_no_network_connection_msg()

        # only show new_review for installed stuff
        is_installed = (self._parent.app_details and
            self._parent.app_details.pkg_state == PkgStates.INSTALLED)

        # show/hide new review button
        if is_installed:
            self.new_review.show()
        else:
            self.new_review.hide()
            # if there are no reviews, the install to review text appears
            # where the reviews usually are (LP #823255)
            if self.reviews:
                self._install_to_review()

        # always hide spinner and call _fill (fine if there is nothing to do)
        self.hide_spinner()
        self._fill()

        if self.reviews:
            # adjust label if we have reviews
            if self._any_reviews_current_user():
                self.new_review.hide()
            else:
                self.new_review.set_label(_("Write your own review"))
        else:
            # no reviews, either offer to write one or show "none"
            if (self.get_active_review_language() != 'any' and
                self.global_review_stats and
                self.global_review_stats.ratings_total > 0):
                self.vbox.pack_start(NoReviewRelaxLanguage(), True, True, 0)
            elif is_installed and is_connected:
                self._be_the_first_to_review()
            else:
                self.vbox.pack_start(NoReviewYet(), True, True, 0)

        # aaronp: removed check to see if the length of reviews is divisible by
        # the batch size to allow proper fixing of LP: #794060 as when a review
        # is submitted and appears in the list, the pagination will break this
        # check and make it unreliable
        # if self.reviews and len(self.reviews) % REVIEWS_BATCH_PAGE_SIZE == 0:
        if self.reviews:
            button = Gtk.Button(_("Check for more reviews"))
            button.connect("clicked", self._on_more_reviews_clicked)
            button.show()
            self.vbox.pack_start(button, False, False, 0)

        # always run this here to make update the current ui based on the
        # network state
        self._on_network_state_change()

    def _on_more_reviews_clicked(self, button):
        # remove buttn and emit signal
        self.vbox.remove(button)
        self.emit("more-reviews-clicked")

    def _on_different_review_language_clicked(self, combo):
        language = self.get_active_review_language()
        # clean reviews so that we can show the new language
        self.clear()
        self.emit("different-review-language-clicked", language)

    def get_active_review_language(self):
        model = self.review_language.get_model()
        language = model[self.review_language.get_active_iter()][COL_LANGCODE]
        return language

    def get_all_review_ids(self):
        ids = []
        for review in self.reviews:
            ids.append(review.id)
        return ids

    def add_review(self, review):
        self.reviews.append(review)

    def replace_review(self, review):
        for r in self.reviews:
            if r.id == review.id:
                pos = self.reviews.index(r)
                self.reviews.remove(r)
                self.reviews.insert(pos, review)
                break

    def remove_review(self, review):
        for r in self.reviews:
            if r.id == review.id:
                self.reviews.remove(r)
                break

    def clear(self):
        self.reviews = []
        for review in self.vbox:
            review.destroy()
        self.new_review.hide()

    # FIXME: ideally we would have "{show,hide}_loading_notice()" to
    #        easily allow changing from e.g. spinner to text
    def show_spinner_with_message(self, message):
        try:
            self.install_first_label.hide()
        except AttributeError:
            pass

        a = Gtk.Alignment.new(0.5, 0.5, 1.0, 1.0)
        hb = Gtk.HBox(spacing=12)
        hb.show()
        a.add(hb)
        a.show()

        spinner = Gtk.Spinner()
        spinner.start()
        spinner.show()

        hb.pack_start(spinner, False, False, 0)

        l = Gtk.Label()
        l.set_markup(message)
        l.set_use_markup(True)
        l.show()

        hb.pack_start(l, False, False, 0)

        self.vbox.pack_start(a, False, False, 0)
        self.vbox.show()

    def hide_spinner(self):
        for child in self.vbox.get_children():
            if isinstance(child, Gtk.Alignment):
                child.destroy()

    def draw(self, cr, a):
        for r in self.vbox:
            if isinstance(r, (UIReview)):
                r.draw(cr, r.get_allocation())


class UIReview(Gtk.VBox):
    """ the UI for a individual review including all button to mark
        useful/inappropriate etc
    """
    def __init__(self, review_data=None, app_version=None,
                 logged_in_person=None, useful_votes=None,
                 first_for_version=True):
        GObject.GObject.__init__(self)
        self.set_spacing(StockEms.SMALL)

        self.version_label = Gtk.Label()
        self.version_label.set_alignment(0, 0.5)

        self.header = Gtk.HBox()
        self.header.set_spacing(StockEms.MEDIUM)
        self.body = Gtk.VBox()
        self.footer = Gtk.HBox()

        self.useful = None
        self.yes_like = None
        self.no_like = None
        self.status_box = Gtk.HBox()
        self.delete_status_box = Gtk.HBox()
        self.delete_error_img = Gtk.Image()
        self.delete_error_img.set_from_stock(
                                Gtk.STOCK_DIALOG_ERROR,
                                Gtk.IconSize.SMALL_TOOLBAR)
        self.submit_error_img = Gtk.Image()
        self.submit_error_img.set_from_stock(
                                Gtk.STOCK_DIALOG_ERROR,
                                Gtk.IconSize.SMALL_TOOLBAR)
        self.submit_status_spinner = Gtk.Spinner()
        self.submit_status_spinner.set_size_request(12, 12)
        self.delete_status_spinner = Gtk.Spinner()
        self.delete_status_spinner.set_size_request(12, 12)
        self.acknowledge_error = Gtk.Button()
        label = Gtk.Label()
        label.set_markup('<small>%s</small>' % _("OK"))
        self.acknowledge_error.add(label)
        self.delete_acknowledge_error = Gtk.Button()
        delete_label = Gtk.Label()
        delete_label.set_markup('<small>%s</small>' % _("OK"))
        self.delete_acknowledge_error.add(delete_label)
        self.usefulness_error = False
        self.delete_error = False
        self.modify_error = False
        if first_for_version:
            self.pack_start(self.version_label, False, False, 0)
        self.pack_start(self.header, False, False, 0)
        self.pack_start(self.body, False, False, 0)
        self.pack_start(self.footer, False, False, StockEms.SMALL)

        self.logged_in_person = logged_in_person
        self.person = None
        self.id = None
        self.useful_votes = useful_votes

        self._allocation = None

        if review_data:
            self._build(review_data,
                        app_version,
                        logged_in_person,
                        useful_votes)

    def _on_report_abuse_clicked(self, button):
        reviews = self.get_ancestor(UIReviewsList)
        if reviews:
            reviews.emit("report-abuse", self.id)

    def _on_modify_clicked(self, button):
        reviews = self.get_ancestor(UIReviewsList)
        if reviews:
            reviews.emit("modify-review", self.id)

    def _on_useful_clicked(self, btn, is_useful):
        reviews = self.get_ancestor(UIReviewsList)
        if reviews:
            self._usefulness_ui_update('progress')
            reviews.emit("submit-usefulness", self.id, is_useful)

    def _on_error_acknowledged(self, button, current_user_reviewer,
        useful_total, useful_favorable):
        self.usefulness_error = False
        self._usefulness_ui_update('renew', current_user_reviewer,
            useful_total, useful_favorable)

    def _usefulness_ui_update(self, type, current_user_reviewer=False,
        useful_total=0, useful_favorable=0):
        self._hide_usefulness_elements()
        #print "_usefulness_ui_update: %s" % type
        if type == 'renew':
            self._build_usefulness_ui(current_user_reviewer, useful_total,
                useful_favorable, self.useful_votes)
            return
        if type == 'progress':
            self.status_label = Gtk.Label.new(
                "<small>%s</small>" % _(u"Submitting now\u2026"))
            self.status_label.set_use_markup(True)
            self.status_box.pack_start(self.submit_status_spinner, False,
                False, 0)
            self.submit_status_spinner.show()
            self.submit_status_spinner.start()
            self.status_label.set_padding(2, 0)
            self.status_box.pack_start(self.status_label, False, False, 0)
            self.status_label.show()
        if type == 'error':
            self.submit_error_img.show()
            self.status_label = Gtk.Label.new(
                "<small>%s</small>" % _("Error submitting usefulness"))
            self.status_label.set_use_markup(True)
            self.status_box.pack_start(self.submit_error_img, False, False, 0)
            self.status_label.set_padding(2, 0)
            self.status_box.pack_start(self.status_label, False, False, 0)
            self.status_label.show()
            self.acknowledge_error.show()
            self.status_box.pack_start(self.acknowledge_error, False, False, 0)
            self.acknowledge_error.connect('clicked',
                self._on_error_acknowledged, current_user_reviewer,
                useful_total, useful_favorable)
        self.status_box.show()
        self.footer.pack_start(self.status_box, False, False, 0)

    def _hide_usefulness_elements(self):
        """ hide all usefulness elements """
        for attr in ["useful", "yes_like", "no_like", "submit_status_spinner",
                     "submit_error_img", "status_box", "status_label",
                     "acknowledge_error", "yes_no_separator"
                     ]:
            widget = getattr(self, attr, None)
            if widget:
                widget.hide()

    def _get_datetime_from_review_date(self, raw_date_str):
        # example raw_date str format: 2011-01-28 19:15:21
        return datetime.datetime.strptime(raw_date_str, '%Y-%m-%d %H:%M:%S')

    def _delete_ui_update(self, type, current_user_reviewer=False,
        action=None):
        self._hide_delete_elements()
        if type == 'renew':
            self._build_delete_flag_ui(current_user_reviewer)
            return
        if type == 'progress':
            self.delete_status_spinner.start()
            self.delete_status_spinner.show()
            self.delete_status_label = Gtk.Label(
                "<small><b>%s</b></small>" % _(u"Deleting now\u2026"))
            self.delete_status_box.pack_start(self.delete_status_spinner,
                False, False, 0)
            self.delete_status_label.set_use_markup(True)
            self.delete_status_label.set_padding(2, 0)
            self.delete_status_box.pack_start(self.delete_status_label, False,
                False, 0)
            self.delete_status_label.show()
        if type == 'error':
            self.delete_error_img.show()
            # build full strings for easier i18n
            if action == 'deleting':
                s = _("Error deleting review")
            elif action == 'modifying':
                s = _("Error modifying review")
            else:
                # or unknown error, but we are in string freeze,
                # should never happen anyway
                s = _("Internal Error")
            self.delete_status_label = Gtk.Label(
                "<small><b>%s</b></small>" % s)
            self.delete_status_box.pack_start(self.delete_error_img,
                False, False, 0)
            self.delete_status_label.set_use_markup(True)
            self.delete_status_label.set_padding(2, 0)
            self.delete_status_box.pack_start(self.delete_status_label,
                False, False, 0)
            self.delete_status_label.show()
            self.delete_acknowledge_error.show()
            self.delete_status_box.pack_start(self.delete_acknowledge_error,
                False, False, 0)
            self.delete_acknowledge_error.connect('clicked',
                self._on_delete_error_acknowledged, current_user_reviewer)
        self.delete_status_box.show()
        self.footer.pack_end(self.delete_status_box, False, False, 0)

    def _on_delete_clicked(self, btn):
        reviews = self.get_ancestor(UIReviewsList)
        if reviews:
            self._delete_ui_update('progress')
            reviews.emit("delete-review", self.id)

    def _on_delete_error_acknowledged(self, button, current_user_reviewer):
        self.delete_error = False
        self._delete_ui_update('renew', current_user_reviewer)

    def _hide_delete_elements(self):
        """ hide all delete elements """
        for attr in ["complain", "edit", "delete", "delete_status_spinner",
                     "delete_error_img", "delete_status_box",
                     "delete_status_label", "delete_acknowledge_error",
                     "flagbox"
                     ]:
            o = getattr(self, attr, None)
            if o:
                o.hide()

    def _build(self, review_data, app_version, logged_in_person, useful_votes):
        # all the attributes of review_data may need markup escape,
        # depening on if they are used as text or markup
        self.id = review_data.id
        self.person = review_data.reviewer_username
        displayname = review_data.reviewer_displayname
        # example raw_date str format: 2011-01-28 19:15:21
        cur_t = self._get_datetime_from_review_date(review_data.date_created)

        review_version = review_data.version
        self.useful_total = useful_total = review_data.usefulness_total
        useful_favorable = review_data.usefulness_favorable
        useful_submit_error = review_data.usefulness_submit_error
        delete_error = review_data.delete_error
        modify_error = review_data.modify_error

        # upstream version
        version = GObject.markup_escape_text(upstream_version(review_version))
        # default string
        version_string = _("For version %(version)s") % {
            'version': version,
            }
        # If its for the same version, show it as such
        if (review_version and
            app_version and
            upstream_version_compare(review_version, app_version) == 0):
            version_string = _("For this version (%(version)s)") % {
                    'version': version,
                    }

        m = '<small>%s</small>'
        self.version_label.set_markup(m % version_string)

        m = self._whom_when_markup(self.person, displayname, cur_t)
        who_when = Gtk.Label()
        who_when.set_name("subtle-label")
        who_when.set_justify(Gtk.Justification.RIGHT)
        who_when.set_markup(m)

        summary = Gtk.Label()
        try:
            s = GObject.markup_escape_text(review_data.summary.encode("utf-8"))
            summary.set_markup('<b>%s</b>' % s)
        except Exception:
            LOG.exception("_build() failed")
            summary.set_text("Error parsing summary")

        summary.set_ellipsize(Pango.EllipsizeMode.END)
        summary.set_selectable(True)
        summary.set_alignment(0, 0.5)

        text = Gtk.Label()
        text.set_text(review_data.review_text)
        text.set_line_wrap(True)
        text.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        text.set_selectable(True)
        text.set_alignment(0, 0)

        stars = Star()
        stars.set_rating(review_data.rating)
        a = Gtk.Alignment.new(0.5, 0.5, 0, 0)
        a.add(stars)

        self.header.pack_start(a, False, False, 0)
        self.header.pack_start(summary, False, False, 0)
        self.header.pack_end(who_when, False, False, 0)
        self.body.pack_start(text, False, False, 0)

        current_user_reviewer = False
        if self.person == self.logged_in_person:
            current_user_reviewer = True

        self._build_usefulness_ui(current_user_reviewer, useful_total,
                                  useful_favorable, useful_votes,
                                  useful_submit_error)

        self.flagbox = Gtk.HBox()
        self.flagbox.set_spacing(4)
        self._build_delete_flag_ui(current_user_reviewer, delete_error,
            modify_error)
        self.footer.pack_end(self.flagbox, False, False, 0)

        # connect network signals
        self.connect("realize", lambda w: self._on_network_state_change())
        watcher = get_network_watcher()
        watcher.connect(
            "changed", lambda w, s: self._on_network_state_change())

    def _build_usefulness_ui(self, current_user_reviewer, useful_total,
                             useful_favorable, useful_votes,
                             usefulness_submit_error=False):
        if usefulness_submit_error:
            self._usefulness_ui_update('error', current_user_reviewer,
                                       useful_total, useful_favorable)
        else:
            already_voted = useful_votes.check_for_usefulness(self.id)
            #get correct label based on retrieved usefulness totals and
            # if user is reviewer
            self.useful = self._get_usefulness_label(
                current_user_reviewer, useful_total, useful_favorable,
                already_voted)
            self.useful.set_use_markup(True)
            #vertically centre so it lines up with the Yes and No buttons
            self.useful.set_alignment(0, 0.5)
            self.useful.show()
            self.footer.pack_start(self.useful, False, False, 3)
            # add here, but only populate if its not the own review
            self.likebox = Gtk.HBox()
            if already_voted == None and not current_user_reviewer:
                m = '<small>%s</small>'
                self.yes_like = Link(m % _('Yes'))
                self.yes_like.set_name("subtle-label")
                self.no_like = Link(m % _('No'))
                self.no_like.set_name("subtle-label")
                self.yes_like.connect('clicked', self._on_useful_clicked, True)
                self.no_like.connect('clicked', self._on_useful_clicked, False)
                self.yes_no_separator = Gtk.Label()
                self.yes_no_separator.set_name("subtle-label")
                self.yes_no_separator.set_markup(m % _('/'))
                self.yes_like.show()
                self.no_like.show()
                self.yes_no_separator.show()
                self.likebox.set_spacing(4)
                self.likebox.pack_start(self.yes_like, False, False, 0)
                self.likebox.pack_start(self.yes_no_separator, False, False, 0)
                self.likebox.pack_start(self.no_like, False, False, 0)
                self.footer.pack_start(self.likebox, False, False, 0)

    def _on_network_state_change(self):
        """ show/hide widgets based on network connection state """
        # FIXME: make this dynamic show/hide on network changes
        # FIXME2: make ti actually work, later show_all() kill it
        #         currently
        if network_state_is_connected():
            self.likebox.show()
            self.useful.show()
            self.flagbox.show()
        else:
            self.likebox.hide()
            # we hide the useful box because if its there it says something
            # like "10 people found this useful. Did you?" but you can't
            # actually submit anything without network
            self.useful.hide()
            self.flagbox.hide()

    def _get_usefulness_label(self, current_user_reviewer,
                              useful_total, useful_favorable, already_voted):
        '''returns Gtk.Label() to be used as usefulness label depending
           on passed in parameters
        '''
        if already_voted == None:
            if useful_total == 0 and current_user_reviewer:
                s = ""
            elif useful_total == 0:
                # no votes for the review yet
                s = _("Was this review helpful?")
            elif current_user_reviewer:
                # user has already voted for the review
                s = gettext.ngettext(
                    "%(useful_favorable)s of %(useful_total)s people "
                    "found this review helpful.",
                    "%(useful_favorable)s of %(useful_total)s people "
                    "found this review helpful.",
                    useful_total) % {
                        'useful_total': useful_total,
                        'useful_favorable': useful_favorable,
                        }
            else:
                # user has not already voted for the review
                s = gettext.ngettext(
                    "%(useful_favorable)s of %(useful_total)s people "
                    "found this review helpful. Did you?",
                    "%(useful_favorable)s of %(useful_total)s people "
                    "found this review helpful. Did you?",
                    useful_total) % {
                        'useful_total': useful_total,
                        'useful_favorable': useful_favorable,
                        }
        else:
        #only display these special strings if the user voted either way
            if already_voted:
                if useful_total == 1:
                    s = _("You found this review helpful.")
                else:
                    s = gettext.ngettext(
                        "%(useful_favorable)s of %(useful_total)s people "
                        "found this review helpful, including you",
                        "%(useful_favorable)s of %(useful_total)s people "
                        "found this review helpful, including you.",
                        useful_total) % {
                            'useful_total': useful_total,
                            'useful_favorable': useful_favorable,
                            }
            else:
                if useful_total == 1:
                    s = _("You found this review unhelpful.")
                else:
                    s = gettext.ngettext(
                        "%(useful_favorable)s of %(useful_total)s people "
                        "found this review helpful; you did not.",
                        "%(useful_favorable)s of %(useful_total)s people "
                        "found this review helpful; you did not.",
                        useful_total) % {
                            'useful_total': useful_total,
                            'useful_favorable': useful_favorable,
                            }

        m = '<small>%s</small>'
        label = Gtk.Label()
        label.set_name("subtle-label")
        label.set_markup(m % s)
        return label

    def _build_delete_flag_ui(self, current_user_reviewer, delete_error=False,
        modify_error=False):
        if delete_error:
            self._delete_ui_update('error', current_user_reviewer, 'deleting')
        elif modify_error:
            self._delete_ui_update('error', current_user_reviewer, 'modifying')
        else:
            m = '<small>%s</small>'
            if current_user_reviewer:
                self.edit = Link(m % _('Edit'))
                self.edit.set_name("subtle-label")
                self.delete = Link(m % _('Delete'))
                self.delete.set_name("subtle-label")
                self.flagbox.pack_start(self.edit, False, False, 0)
                self.flagbox.pack_start(self.delete, False, False, 0)
                self.edit.connect('clicked', self._on_modify_clicked)
                self.delete.connect('clicked', self._on_delete_clicked)
            else:
                # Translators: This link is for flagging a review as
                # inappropriate.  To minimize repetition, if at all possible,
                # keep it to a single word.  If your language has an obvious
                # verb, it won't need a question mark.
                self.complain = Link(m % _('Inappropriate?'))
                self.complain.set_name("subtle-label")
                self.flagbox.pack_start(self.complain, False, False, 0)
                self.complain.connect('clicked', self._on_report_abuse_clicked)
            self.flagbox.show_all()

    def _whom_when_markup(self, person, displayname, cur_t):
        nice_date = get_nice_date_string(cur_t)
        #dt = datetime.datetime.utcnow() - cur_t

        # prefer displayname if available
        correct_name = displayname or person

        if person == self.logged_in_person:
            m = '%s (%s), %s' % (
                GObject.markup_escape_text(utf8(correct_name)),
                # TRANSLATORS: displayed in a review after the persons name,
                # e.g. "Jane Smith (that's you), 2011-02-11"
                utf8(_(u"that\u2019s you")),
                GObject.markup_escape_text(utf8(nice_date)))
        else:
            try:
                m = '%s, %s' % (
                    GObject.markup_escape_text(correct_name.encode("utf-8")),
                    GObject.markup_escape_text(nice_date))
            except Exception:
                LOG.exception("_who_when_markup failed")
                m = "Error parsing name"

        return m

    def draw(self, widget, cr):
        pass


class EmbeddedMessage(UIReview):

    def __init__(self, title='', message='', icon_name=''):
        UIReview.__init__(self)
        self.label = None
        self.image = None

        a = Gtk.Alignment.new(0.5, 0.5, 1.0, 1.0)
        self.body.pack_start(a, False, False, 0)

        hb = Gtk.HBox()
        hb.set_spacing(12)
        a.add(hb)

        if icon_name:
            self.image = Gtk.Image.new_from_icon_name(icon_name,
                                                      Gtk.IconSize.DIALOG)
            hb.pack_start(self.image, False, False, 0)

        self.label = Gtk.Label()
        self.label.set_line_wrap(True)
        self.label.set_alignment(0, 0.5)

        if title:
            self.label.set_markup('<b><big>%s</big></b>\n%s' %
                (title, message))
        else:
            self.label.set_markup(message)

        hb.pack_start(self.label, True, True, 0)
        self.show_all()

    def draw(self, cr, a):
        pass


class NoReviewRelaxLanguage(EmbeddedMessage):
    """ represents if there are no reviews yet and the app is not installed """
    def __init__(self, *args, **kwargs):
        # TRANSLATORS: displayed if there are no reviews for the app in
        #              the current language, but there are some in other
        #              languages
        title = _("This app has not been reviewed yet in your language")
        msg = _('Try selecting a different language, or even "Any language"'
            ' in the language dropdown')
        EmbeddedMessage.__init__(self, title, msg)


class NoReviewYet(EmbeddedMessage):
    """ represents if there are no reviews yet and the app is not installed """
    def __init__(self, *args, **kwargs):
        # TRANSLATORS: displayed if there are no reviews for the app yet
        #              and the user does not have it installed
        title = _("This app has not been reviewed yet")
        msg = _('You need to install this before you can review it')
        EmbeddedMessage.__init__(self, title, msg)


class NoReviewYetWriteOne(EmbeddedMessage):
    """ represents if there are no reviews yet and the app is installed """
    def __init__(self, *args, **kwargs):

        # TRANSLATORS: displayed if there are no reviews yet and the user
        #              has the app installed
        title = _('Got an opinion?')
        msg = _('Be the first to contribute a review for this application')

        EmbeddedMessage.__init__(self, title, msg, 'text-editor')


def get_test_reviews_window():
    from mock import Mock

    appdetails_mock = Mock()
    appdetails_mock.version = "2.0"

    parent = Mock()
    parent.app_details = appdetails_mock

    review_data = Mock()
    review_data.app_name = "app"
    review_data.usefulness_favorable = 10
    review_data.usefulness_total = 12
    review_data.usefulness_submit_error = False
    review_data.reviewer_username = "name"
    review_data.reviewer_displayname = "displayname"
    review_data.date_created = "2011-01-01 18:00:00"
    review_data.summary = "summary"
    review_data.review_text = 10 * "loonng text"
    review_data.rating = "3.0"
    review_data.version = "1.0"

    # create reviewslist
    vb = UIReviewsList(parent)
    vb.add_review(review_data)
    vb.configure_reviews_ui()

    win = Gtk.Window()
    win.set_size_request(200, 200)
    win.add(vb)
    win.connect('destroy', Gtk.main_quit)
    win.show_all()
    return win

if __name__ == "__main__":
    import softwarecenter.paths
    softwarecenter.paths.datadir = "./data"

    win = get_test_reviews_window()

    Gtk.main()
