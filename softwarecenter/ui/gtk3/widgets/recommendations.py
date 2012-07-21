# -*- coding: utf-8 -*-
# Copyright (C) 2012 Canonical
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

from gi.repository import Gtk, GObject
import logging

from gettext import gettext as _

from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.ui.gtk3.widgets.containers import (FramedHeaderBox,
                                                       FlowableGrid)
from softwarecenter.ui.gtk3.utils import get_parent_xid
from softwarecenter.db.categories import (RecommendedForYouCategory,
                                          AppRecommendationsCategory)
from softwarecenter.backend.recagent import RecommenderAgent
from softwarecenter.backend.login_sso import get_sso_backend
from softwarecenter.backend.ubuntusso import get_ubuntu_sso_backend
from softwarecenter.enums import SOFTWARE_CENTER_NAME_KEYRING
from softwarecenter.utils import utf8
from softwarecenter.netstatus import network_state_is_connected

LOG = logging.getLogger(__name__)


class RecommendationsPanel(FramedHeaderBox):
    """
    Base class for widgets that display recommendations
    """

    __gsignals__ = {
        "application-activated": (GObject.SIGNAL_RUN_LAST,
                                  GObject.TYPE_NONE,
                                  (GObject.TYPE_PYOBJECT,),
                                 ),
        }

    def __init__(self, catview):
        FramedHeaderBox.__init__(self)
        # FIXME: we only need the catview for "add_titles_to_flowgrid"
        #        and "on_category_clicked" so we should be able to
        #        extract this to a "leaner" widget
        self.catview = catview
        self.catview.connect(
                    "application-activated", self._on_application_activated)
        self.recommender_agent = RecommenderAgent()

    def _on_application_activated(self, catview, app):
        self.emit("application-activated", app)

    def _on_recommender_agent_error(self, agent, msg):
        LOG.warn("Error while accessing the recommender agent: %s" % msg)
        # TODO: temporary, instead we will display cached recommendations here
        self._hide_recommended_for_you_panel()

    def _hide_recommended_for_you_panel(self):
        # and hide the pane
        self.hide()


class RecommendationsPanelCategory(RecommendationsPanel):
    """
    Panel for use in the category view that displays recommended apps for
    the given category
    """
    def __init__(self, catview, subcategory):
        RecommendationsPanel.__init__(self, catview)
        self.subcategory = subcategory
        if self.subcategory:
            self.set_header_label(GObject.markup_escape_text(utf8(
                _("Recommended For You in %s")) % utf8(self.subcategory.name)))
        self.recommended_for_you_content = None
        if self.recommender_agent.is_opted_in():
            self._update_recommended_for_you_content()
        else:
            self._hide_recommended_for_you_panel()

    def _update_recommended_for_you_content(self):
        # destroy the old content to ensure we don't see it twice
        if self.recommended_for_you_content:
            self.recommended_for_you_content.destroy()
        # add the new stuff
        self.recommended_for_you_content = FlowableGrid()
        self.add(self.recommended_for_you_content)
        self.spinner_notebook.show_spinner(_(u"Receiving recommendations…"))
        # get the recommendations from the recommender agent
        self.recommended_for_you_cat = RecommendedForYouCategory(
                                            subcategory=self.subcategory)
        self.recommended_for_you_cat.connect(
                                    'needs-refresh',
                                    self._on_recommended_for_you_agent_refresh)
        self.recommended_for_you_cat.connect('recommender-agent-error',
                                             self._on_recommender_agent_error)

    def _on_recommended_for_you_agent_refresh(self, cat):
        self.header_implements_more_button()
        docs = cat.get_documents(self.catview.db)
        # display the recommendedations
        if len(docs) > 0:
            self.catview._add_tiles_to_flowgrid(docs,
                                        self.recommended_for_you_content, 12)
            self.recommended_for_you_content.show_all()
            self.spinner_notebook.hide_spinner()
            self.more.connect('clicked',
                              self.catview.on_category_clicked,
                              cat)
            self.header.queue_draw()
            self.show_all()
        else:
            # hide the panel if we have no recommendations to show
            self._hide_recommended_for_you_panel()


class RecommendationsPanelLobby(RecommendationsPanelCategory):
    """
    Panel for use in the lobby view that manages the recommendations
    experience, includes the initial opt-in screen and display of
    recommendations once they have been received from the recommender agent
    """
    __gsignals__ = {
        "recommendations-opt-in": (GObject.SIGNAL_RUN_LAST,
                                   GObject.TYPE_NONE,
                                   (),
                                  ),
        "recommendations-opt-out": (GObject.SIGNAL_RUN_LAST,
                                    GObject.TYPE_NONE,
                                    (),
                                   ),
        }

    TURN_ON_RECOMMENDATIONS_TEXT = _(u"Turn On Recommendations")
    # FIXME: This will be the default text once LP: #986437 is approved and
    #        ready to be merged/SRU'd
    FUTURE_RECOMMENDATIONS_OPT_IN_TEXT = _(u"To make recommendations, "
                 "Ubuntu Software Center "
                 "will occasionally send to Canonical a list "
                 "of software currently installed.")
    # FIXME: The following unused string can be removed and the one above used
    #        after the transition to the new string has had enough time to
    #        take effect
    # TRANSLATORS: please ignore the following string as it it just there for
    #              a transition to the updated string above
    RECOMMENDATIONS_OPT_IN_TEXT = _(u"To make recommendations, "
                 "Ubuntu Software Center "
                 "will occasionally send to Canonical an anonymous list "
                 "of software currently installed.")

    def __init__(self, catview):
        RecommendationsPanel.__init__(self, catview)
        self.subcategory = None
        self.set_header_label(_(u"Recommended For You"))
        self.recommended_for_you_content = None
        if self.recommender_agent.is_opted_in():
            self._try_sso_login()
        else:
            self._show_opt_in_view()

    def _show_opt_in_view(self):
        # opt in box
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, StockEms.MEDIUM)
        vbox.set_border_width(StockEms.MEDIUM)
        self.opt_in_vbox = vbox  # for tests
        self.recommended_for_you_content = vbox  # hook it up to the rest

        self.add(self.recommended_for_you_content)

        # opt in button
        button = Gtk.Button(_(self.TURN_ON_RECOMMENDATIONS_TEXT))
        button.connect("clicked", self._on_opt_in_button_clicked)
        hbox = Gtk.Box(Gtk.Orientation.HORIZONTAL)
        hbox.pack_start(button, False, False, 0)
        vbox.pack_start(hbox, False, False, 0)
        self.opt_in_button = button  # for tests

        # opt in text
        text = _(self.RECOMMENDATIONS_OPT_IN_TEXT)
        label = Gtk.Label()
        label.set_use_markup(True)
        markup = '<small>%s</small>'
        label.set_name("subtle-label")
        label.set_markup(markup % text)
        label.set_alignment(0, 0.5)
        label.set_line_wrap(True)
        vbox.pack_start(label, False, False, 0)

    def _on_opt_in_button_clicked(self, button):
        self.opt_in_to_recommendations_service()

    def opt_in_to_recommendations_service(self):
        # first we verify the ubuntu sso login/oath status, and if that is good
        # we upload the user profile here, and only after this is finished
        # do we fire the request for recommendations and finally display
        # them here -- a spinner is shown for this process (the spec
        # wants a progress bar, but we don't have access to real-time
        # progress info)
        self._try_sso_login()

    def opt_out_of_recommendations_service(self):
        # tell the backend that the user has opted out
        self.recommender_agent.opt_out()
        # update the UI
        if self.recommended_for_you_content:
            self.recommended_for_you_content.destroy()
        self._show_opt_in_view()
        self.remove_more_button()
        self.show_all()
        self.emit("recommendations-opt-out")
        self._disconnect_recommender_listeners()

    def _try_sso_login(self):
        # display the SSO login dialog if needed
        # FIXME: consider improving the text in the SSO dialog, for now
        #        we simply reuse the opt-in text from the panel since we
        #        are well past string freeze
        self.spinner_notebook.show_spinner()
        self.sso = get_sso_backend(get_parent_xid(self),
                                   SOFTWARE_CENTER_NAME_KEYRING,
                                   self.RECOMMENDATIONS_OPT_IN_TEXT)
        self.sso.connect("login-successful", self._maybe_login_successful)
        self.sso.connect("login-failed", self._login_failed)
        self.sso.connect("login-canceled", self._login_canceled)
        self.sso.login_or_register()

    def _maybe_login_successful(self, sso, oauth_result):
        self.ssoapi = get_ubuntu_sso_backend()
        self.ssoapi.connect("whoami", self._whoami_done)
        self.ssoapi.connect("error", self._whoami_error)
        # this will automatically verify the keyring token and retrigger
        # login (once) if its expired
        self.ssoapi.whoami()

    def _whoami_done(self, ssologin, result):
        # we are all squared up with SSO login, now we can proceed with the
        # recommendations display, or the profile upload if this is an
        # initial opt-in
        if self.recommender_agent.is_opted_in():
            self._update_recommended_for_you_content()
        else:
            self._upload_user_profile_and_get_recommendations()

    def _whoami_error(self, ssologin, e):
        self.spinner_notebook.hide_spinner()
        # FIXME: there is a race condition here if the network state changed
        #        between the call and this check, to fix this properly the
        #        spawn_helper/piston-generic-helper will need to return
        #        better error information though
        if not network_state_is_connected():
            # if there is an error in the SSO whois, first just check if we
            # have network access and if we do no, just hide the panel
            self._hide_recommended_for_you_panel()
        else:
            # an error that is not network related indicates that the user's
            # token has likely been revoked or invalidated on the server, for
            # this case we want to reset the user's opt-in status
            self.opt_out_of_recommendations_service()

    def _login_failed(self, sso):
        # if the user cancels out of the SSO dialog, reset everything to the
        # opt-in view state
        self.spinner_notebook.hide_spinner()
        self.opt_out_of_recommendations_service()

    def _login_canceled(self, sso):
        # if the user cancels out of the SSO dialog, reset everything to the
        # opt-in view state
        self.spinner_notebook.hide_spinner()
        self.opt_out_of_recommendations_service()

    def _upload_user_profile_and_get_recommendations(self):
        # initiate upload of the user profile here
        self._upload_user_profile()

    def _upload_user_profile(self):
        self.spinner_notebook.show_spinner(_(u"Submitting inventory…"))
        self.recommender_agent.connect("submit-profile-finished",
                                  self._on_profile_submitted)
        self.recommender_agent.connect("error",
                                  self._on_profile_submitted_error)
        self.recommender_agent.post_submit_profile(self.catview.db)

    def _on_profile_submitted(self, agent, profile):
        # after the user profile data has been uploaded, make the request
        # and load the the recommended_for_you content
        LOG.debug("The updated profile was successfully submitted to the "
                  "recommender service")
        # only detect the very first profile upload as that indicates
        # the user's initial opt-in
        self._update_recommended_for_you_content()
        self._disconnect_recommender_listeners()
        self.emit("recommendations-opt-in")

    def _on_profile_submitted_error(self, agent, msg):
        LOG.warn("Error while submitting the recommendations profile to the "
                 "recommender agent: %s" % msg)
        # TODO: handle this! display an error message in the panel
        # detect the very first profile upload as that indicates
        # the user's initial opt-in
        self._disconnect_recommender_listeners()
        self._hide_recommended_for_you_panel()

    def _disconnect_recommender_listeners(self):
        try:
            self.recommender_agent.disconnect_by_func(
                self._on_profile_submitted)
            self.recommender_agent.disconnect_by_func(
                self._on_profile_submitted_error)
        except TypeError:
            pass


class RecommendationsPanelDetails(RecommendationsPanel):
    """
    Panel for use in the details view to display recommendations for a given
    application
    """
    def __init__(self, catview):
        RecommendationsPanel.__init__(self, catview)
        self.set_header_label(_(u"People Also Installed"))
        self.app_recommendations_content = FlowableGrid()
        self.add(self.app_recommendations_content)

    def set_pkgname(self, pkgname):
        self.pkgname = pkgname
        self._update_app_recommendations_content()

    def _update_app_recommendations_content(self):
        if self.app_recommendations_content:
            self.app_recommendations_content.remove_all()
        self.spinner_notebook.show_spinner(_(u"Receiving recommendations…"))
        # get the recommendations from the recommender agent
        self.app_recommendations_cat = AppRecommendationsCategory(self.pkgname)
        self.app_recommendations_cat.connect(
                                    'needs-refresh',
                                    self._on_app_recommendations_agent_refresh)
        self.app_recommendations_cat.connect('recommender-agent-error',
                                             self._on_recommender_agent_error)

    def _on_app_recommendations_agent_refresh(self, cat):
        docs = cat.get_documents(self.catview.db)
        # display the recommendations
        if len(docs) > 0:
            self.catview._add_tiles_to_flowgrid(docs,
                                        self.app_recommendations_content, 3)
            self.show_all()
            self.spinner_notebook.hide_spinner()
        else:
            self._hide_app_recommendations_panel()

    def _on_recommender_agent_error(self, agent, msg):
        LOG.warn("Error while accessing the recommender agent for the "
                 "details view recommendations: %s" % msg)
        # TODO: temporary, instead we will display cached recommendations here
        self._hide_app_recommendations_panel()

    def _hide_app_recommendations_panel(self):
        # and hide the pane
        self.hide()


class RecommendationsOptInDialog(Gtk.MessageDialog):
    """
    Dialog to display the recommendations opt-in message when opt-in is
    initiated from the menu.
    """
    def __init__(self, icons):
        Gtk.MessageDialog.__init__(self, flags=Gtk.DialogFlags.MODAL,
                                   type=Gtk.MessageType.INFO)
        self.set_title("")
        icon_name = "softwarecenter"
        if icons.has_icon(icon_name):
            icon = Gtk.Image.new_from_icon_name(icon_name,
                                                Gtk.IconSize.DIALOG)
            self.set_image(icon)
            icon.show()
        self.format_secondary_text(
            _(RecommendationsPanelLobby.RECOMMENDATIONS_OPT_IN_TEXT))
        self.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self.add_button(
            _(RecommendationsPanelLobby.TURN_ON_RECOMMENDATIONS_TEXT),
            Gtk.ResponseType.YES)
        self.set_default_response(Gtk.ResponseType.YES)


# test helpers
def get_test_window(panel_type="lobby"):
    import softwarecenter.log
    softwarecenter.log.root.setLevel(level=logging.DEBUG)
    fmt = logging.Formatter("%(name)s - %(message)s", None)
    softwarecenter.log.handler.setFormatter(fmt)

    # this is *way* too complicated we should *not* need a CatView
    # here! see FIXME in RecommendationsPanel.__init__()
    from softwarecenter.ui.gtk3.views.catview_gtk import CategoriesViewGtk
    from softwarecenter.testutils import (
        get_test_db, get_test_pkg_info, get_test_gtk3_icon_cache,
        get_test_categories)
    cache = get_test_pkg_info()
    db = get_test_db()
    icons = get_test_gtk3_icon_cache()
    catview = CategoriesViewGtk(softwarecenter.paths.datadir,
                                softwarecenter.paths.APP_INSTALL_PATH,
                                cache,
                                db,
                                icons)

    if panel_type is "lobby":
        view = RecommendationsPanelLobby(catview)
    elif panel_type is "category":
        cats = get_test_categories(db)
        view = RecommendationsPanelCategory(catview, cats[0])
    else:  # panel_type is "details":
        view = RecommendationsPanelDetails(catview)

    win = Gtk.Window()
    win.connect("destroy", lambda x: Gtk.main_quit())
    win.add(view)
    win.set_data("rec_panel", view)
    win.set_size_request(600, 200)
    win.show_all()

    return win


if __name__ == "__main__":
    win = get_test_window()
    Gtk.main()
