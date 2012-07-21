# -*- coding: utf-8 -*-
from gi.repository import Gtk, GObject

import gettext
from gettext import gettext as _

from softwarecenter.ui.gtk3.em import StockEms


class Suggestions(Gtk.VBox):

    __gsignals__ = {
        "activate-link": (GObject.SignalFlags.RUN_LAST,
                          None,
                          (GObject.TYPE_PYOBJECT, str),
                          ),
    }

    def __init__(self):
        Gtk.VBox.__init__(self)
        self.set_spacing(StockEms.MEDIUM)

        self.title = Gtk.Label()
        self.title.set_line_wrap(True)
        self.pack_start(self.title, False, False, 0)

        self.xalign = 0.0
        self.yalign = 0.0

        self._labels = []
        self._handlers = []

    def on_link_activate(self, widget, uri):
        self.reset_all()
        self.emit("activate-link", widget, uri)
        return True  # silences the gtk-warning

    def foreach(self, label_func, *args):
        for label in [self.title] + self._labels:
            label_func(label, *args)

    def set_alignment(self, xalign, yalign):
        self.xalign = xalign
        self.yalign = yalign

        self.foreach(Gtk.Label.set_alignment, xalign, yalign)

    def set_title(self, title_markup):
        self.title.set_markup(title_markup)

    def append_suggestion(self, suggestion_markup):
        label = Gtk.Label()
        label.set_alignment(self.xalign, self.yalign)
        label.set_markup(suggestion_markup)
        self.pack_start(label, False, False, 0)
        label.show()

        self._handlers.append(
                label.connect("activate-link", self.on_link_activate))
        self._labels.append(label)

    def set_suggestions(self, suggestions):
        if self._labels:
            self.reset()
        for s in suggestions:
            self.append_suggestion(s)

    def reset(self):
        for label, handler in zip(self._labels, self._handlers):
            GObject.source_remove(handler)
            label.destroy()

        self._labels = []
        self._handlers = []

    def reset_all(self):
        self.title.set_text('')
        self.reset()


class SearchAidLogic(object):

    HEADER_ICON_NAME = "face-sad"
    HEADER_MARKUP = '<b><big>%s</big></b>'
    #TRANSLATORS: this is the layout of an indented
    # line starting with a bullet point
    BULLET = unicode(_("\t• %s"), 'utf8').encode('utf8')

    def __init__(self, pane):
        self.pane = pane
        self.db = pane.db
        self.enquirer = pane.enquirer

    def is_search_aid_required(self, state):
        return (state.search_term and
                len(self.enquirer.matches) == 0)

    def get_correction(self, term):
        return self.db.get_spelling_correction(term)

    def get_title_text(self, term, category, state):
        from softwarecenter.utils import utf8

        def build_category_path():
            if not category:
                return ''
            if not state.subcategory:
                return category.name
            plain_text = _("%(category_name)s → %(subcategory_name)s")
            usable_text = unicode(plain_text, 'utf8').encode('utf8')
            return usable_text % {'category_name': category.name,
                                  'subcategory_name': state.subcategory.name}

        if not category:
            sub = utf8(_(u"No items match “%s”")) % term
        else:
            sub = utf8(_(u"No items in %s match “%s”"))
            sub = sub % (build_category_path(), term)

        return self.HEADER_MARKUP % GObject.markup_escape_text(sub)

    def get_suggestions(self, term, category, state):
        correction = self.get_correction(term)
        suggestions = []

        # offer to research in the parent category is search is
        # limited to a subcategory
        new_text = self.get_include_parent_suggestion_text(
                                                term, category, state)

        if new_text is not None:
            suggestions.append(new_text)

        # check if we are searching supported pkg, and offer to include
        # unsupported pkg's as well
        new_text = self.get_unsupported_suggestion_text(
                                                term, category, state)

        if new_text is not None:
            suggestions.append(new_text)

        # if we are in a category, suggest searching within 'All cats'
        if category:
            new_text = self.BULLET % _("Try searching across "
                      "<a href=\"search-all/\">all categories</a>"
                      " instead")
            suggestions.append(new_text)

        # If spelling correction, offer alternative term(s)
        if correction:
            correction = GObject.markup_escape_text(correction)
            ref = "<a href=\"search/%s\">%s</a>" % (correction, correction)
            new_text = self.BULLET % _("Check that your spelling is correct.  "
                                "Did you mean: %s?") % ref

            suggestions.append(new_text)

        return suggestions

    def get_suggestion_title_text(self, suggestions):
        if suggestions:
            return _("Suggestions:")
        # else, say sorry if we cannot offer any suggestions
        return _("Software Center was unable to come up with any "
                 "suggestions that may aid you in your search")

    def get_include_parent_suggestion_text(self, term, category, state):
        if not state.subcategory:
            return

        enq = self.enquirer
        query = self.db.get_query_list_from_search_entry(
                                    term,
                                    category.query)

        enq.set_query(query,
                      limit=state.limit,
                      sortmode=self.pane.get_sort_mode(),
                      nonapps_visible=self.pane.nonapps_visible,
                      filter=state.filter,
                      nonblocking_load=False)

        if enq.nr_apps > 0:
            text = self.BULLET % gettext.ngettext("Try "
                 "<a href=\"search-parent/\">the item "
                 "in %(category)s</a> that matches", "Try "
                 "<a href=\"search-parent/\">the %(n)d items "
                 "in %(category)s</a> that match",
                 n=enq.nr_apps) % \
                 {'category': category.name, 'n': enq.nr_apps}
            return text

    def get_unsupported_suggestion_text(self, term, category, state):
        if state.filter is None:
            return
        supported_only = state.filter.get_supported_only()
        if not supported_only:
            return

        state.filter.set_supported_only(False)

        #if category:
        #    category_query = category.query
        #else:
        #    category_query = None

        enq = self.enquirer
        enq.set_query(enq.search_query,
                      limit=self.pane.get_app_items_limit(),
                      sortmode=self.pane.get_sort_mode(),
                      nonapps_visible=True,
                      filter=state.filter,
                      nonblocking_load=False)

        state.filter.set_supported_only(True)

        if enq.nr_apps > 0:
            text = self.BULLET % gettext.ngettext("Try "
                 "<a href=\"search-unsupported:\">the %(amount)d item "
                 "that matches</a> in software not maintained by Canonical",
                 "Try <a href=\"search-unsupported:\">the %(amount)d items "
                 "that match</a> in software not maintained by Canonical",
                 enq.nr_apps) % {'amount': enq.nr_apps}
            return text

    def update_search_help(self, state):
        # do any non toolkit logic here
        # ...

        # do toolkit stuff here
        if hasattr(self, 'on_update_search_help'):
            self.on_update_search_help(state)

    def reset(self):
        if hasattr(self, 'on_reset'):
            self.on_reset()


class SearchAid(Gtk.Table, SearchAidLogic):

    def __init__(self, pane):
        SearchAidLogic.__init__(self, pane)
        # gtk box basics
        Gtk.Table.__init__(self)
        self.resize(2, 2)
        self.set_border_width(2 * StockEms.XLARGE)

        # no results (sad face) image
        image = Gtk.Image.new_from_icon_name(self.HEADER_ICON_NAME,
                                             Gtk.IconSize.DIALOG)
        self.attach(image,
                    0, 1,  # left_attach, right_attach
                    0, 1,  # top_attach, bottom_attach
                    Gtk.AttachOptions.SHRINK,
                    Gtk.AttachOptions.SHRINK,
                    StockEms.LARGE, 0)

        # title
        self.title = Gtk.Label()
        self.title.set_use_markup(True)
        self.title.set_alignment(0.0, 0.5)
        self.attach(self.title,
                    1, 2,  # left_attach, right_attach
                    0, 1,  # top_attach, bottom_attach
                    Gtk.AttachOptions.FILL,
                    Gtk.AttachOptions.FILL,
                    StockEms.MEDIUM, 0)

        # suggestion label
        self.suggestion = Suggestions()
        self.suggestion.set_alignment(0.0, 0.5)
        self.attach(self.suggestion,
                    1, 2,  # left_attach, right_attach
                    1, 2,  # top_attach, bottom_attach
                    Gtk.AttachOptions.FILL | Gtk.AttachOptions.EXPAND,
                    Gtk.AttachOptions.FILL,
                    StockEms.MEDIUM, StockEms.MEDIUM)

        self.suggestion.connect("activate-link", self.on_link_activate)

    def on_update_search_help(self, state):
        if not self.is_search_aid_required(state):
            # catchall
            self.pane.app_view.set_visible(True)
            self.set_visible(False)
            return

        self.pane.app_view.set_visible(False)
        self.set_visible(True)

        term = state.search_term
        category = state.category

        # set the title
        title_markup = self.get_title_text(term, category, state)
        self.title.set_markup(title_markup)

        suggestions = self.get_suggestions(term, category, state)
        suggestions_title = self.get_suggestion_title_text(suggestions)
        self.suggestion.set_title(suggestions_title)
        self.suggestion.set_suggestions(suggestions)

    def on_reset(self):
        self.suggestion.reset_all()

    def on_link_activate(self, suggestions, link, uri):
        markup = self.HEADER_MARKUP % _('Trying suggestion ...')
        self.title.set_markup(markup)
        GObject.timeout_add(750, self._handle_suggestion_action, uri)

    def _handle_suggestion_action(self, uri):
        self = self.pane
        if uri.startswith("search/"):
            self.searchentry.set_text(uri[len("search/"):])
        elif uri.startswith("search-all/"):
            self.unset_current_category()
            self.refresh_apps()
        elif uri.startswith("search-parent/"):
            self.state.subcategory = None
            self.refresh_apps()
        elif uri.startswith("search-unsupported:"):
            self.state.filter.set_supported_only(False)
            self.refresh_apps()
        # FIXME: add ability to remove categories restriction here
        # True stops event propergation
        return False
