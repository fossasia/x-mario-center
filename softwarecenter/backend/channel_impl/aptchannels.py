# Copyright (C) 2010 Canonical
#
# Authors:
#  Gary Lasker
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

import os
import logging
import xapian

import softwarecenter.paths

from gi.repository import GObject

from aptsources.sourceslist import SourceEntry, SourcesList

from softwarecenter.backend import get_install_backend
from softwarecenter.backend.channel import (ChannelsManager,
                                            SoftwareChannel)
from softwarecenter.distro import get_distro
from softwarecenter.utils import human_readable_name_from_ppa_uri

from softwarecenter.enums import (ViewPages,
                                  AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME,
                                  )

LOG = logging.getLogger(__name__)


class AptChannelsManager(ChannelsManager):

    def __init__(self, db):
        self.db = db
        self.distro = get_distro()
        self.backend = get_install_backend()
        self.backend.connect("channels-changed",
                             self._remove_no_longer_needed_extra_channels)
        # kick off a background check for changes that may have been made
        # in the channels list
        GObject.timeout_add_seconds(60, self._check_for_channel_updates_timer)
        # extra channels from e.g. external sources
        self.extra_channels = []
        self._logger = LOG

    # external API
    @property
    def channels(self):
        """
        return a list of SoftwareChannel objects in display order
        according to:
            Distribution, Partners, PPAs alphabetically,
            Other channels alphabetically, Unknown channel last
        """
        return self._get_channels()

    @property
    def channels_installed_only(self):
        """
        return a list of SoftwareChannel objects displaying installed
        packages only in display order according to:
            Distribution, Partners, PPAs alphabetically,
            Other channels alphabetically, Unknown channel last
        """
        return self._get_channels(installed_only=True)

    def feed_in_private_sources_list_entries(self, entries):
        added = False
        for entry in entries:
            added |= self._feed_in_private_sources_list_entry(entry)
        if added:
            self.backend.emit("channels-changed", True)

    def add_channel(self, name, icon, query):
        """
        create a channel with the name, icon and query specified and append
        it to the set of channels
        return the new channel object
        """
        # print name, icon, query
        channel = SoftwareChannel(name, None, None,
                                  channel_icon=icon,
                                  channel_query=query)
        self.extra_channels.append(channel)
        self.backend.emit("channels-changed", True)

        if channel.installed_only:
            channel._channel_view_id = ViewPages.INSTALLED
        else:
            channel._channel_view_id = ViewPages.AVAILABLE
        return channel

    @staticmethod
    def channel_available(channelname):
        import apt_pkg
        p = os.path.join(apt_pkg.config.find_dir("Dir::Etc::sourceparts"),
                         "%s.list" % channelname)
        return os.path.exists(p)

    # internal
    def _feed_in_private_sources_list_entry(self, source_entry):
        """
        this feeds in a private sources.list entry that is
        available to the user (like a private PPA) that may or
        may not be active
        """
        # FIXME: strip out password and use apt/auth.conf
        potential_new_entry = SourceEntry(source_entry)
        # look if we have it
        sources = SourcesList()
        for source in sources.list:
            if source == potential_new_entry:
                return False
        # need to add it as a not yet enabled channel
        name = human_readable_name_from_ppa_uri(potential_new_entry.uri)
        # FIXME: use something better than uri as name
        private_channel = SoftwareChannel(name, None, None,
                                          source_entry=source_entry)
        private_channel.needs_adding = True
        if private_channel in self.extra_channels:
            return False
        # add it
        self.extra_channels.append(private_channel)
        return True

    def _remove_no_longer_needed_extra_channels(self, backend, res):
        """ go over the extra channels and remove no longer needed ones"""
        removed = False
        for channel in self.extra_channels:
            if not channel._source_entry:
                continue
            sources = SourcesList()
            for source in sources.list:
                if source == SourceEntry(channel._source_entry):
                    self.extra_channels.remove(channel)
                    removed = True
        if removed:
            self.backend.emit("channels-changed", True)

    def _check_for_channel_updates_timer(self):
        """
        run a background timer to see if the a-x-i data we have is
        still fresh or if the cache has changed since
        """
        # this is expensive and does not need UI to we shove it out
        channel_update = os.path.join(
            softwarecenter.paths.datadir, "update-software-center-channels")
        (pid, stdin, stdout, stderr) = GObject.spawn_async(
            [channel_update],
            flags=GObject.SPAWN_DO_NOT_REAP_CHILD)
        GObject.child_watch_add(
            pid, self._on_check_for_channel_updates_finished)

    def _on_check_for_channel_updates_finished(self, pid, condition):
        # exit status of 1 means stuff changed
        if os.WEXITSTATUS(condition) == 1:
            self.db.reopen()

    def _get_channels(self, installed_only=False):
        """
        (internal) implements 'channels()' and 'channels_installed_only()'
        properties
        """
        distro_channel_name = self.distro.get_distro_channel_name()

        # gather the set of software channels and order them
        other_channel_list = []
        cached_origins = []
        for channel_iter in self.db.xapiandb.allterms("XOL"):
            if len(channel_iter.term) == 3:
                continue
            channel_name = channel_iter.term[3:]
            channel_origin = ""

            # get origin information for this channel
            m = self.db.xapiandb.postlist_begin(channel_iter.term)
            doc = self.db.xapiandb.get_document(m.get_docid())
            for term_iter in doc.termlist():
                if (term_iter.term.startswith("XOO") and
                      len(term_iter.term) > 3):
                    channel_origin = term_iter.term[3:]
                    break
            self._logger.debug("channel_name: %s" % channel_name)
            self._logger.debug("channel_origin: %s" % channel_origin)
            if channel_origin not in cached_origins:
                other_channel_list.append((channel_name, channel_origin))
                cached_origins.append(channel_origin)

        dist_channel = None
        partner_channel = None
        for_purchase_channel = None
        new_apps_channel = None
        ppa_channels = []
        other_channels = []
        unknown_channel = []
        local_channel = None

        for (channel_name, channel_origin) in other_channel_list:
            if not channel_name:
                unknown_channel.append(SoftwareChannel(channel_name,
                    channel_origin,
                    None,
                    installed_only=installed_only))
            elif channel_name == distro_channel_name:
                dist_channel = (SoftwareChannel(distro_channel_name,
                                                channel_origin,
                                                None,
                                                installed_only=installed_only))
            elif channel_name == "Partner archive":
                partner_channel = SoftwareChannel(channel_name,
                    channel_origin,
                    "partner",
                    installed_only=installed_only)
            elif channel_name == "notdownloadable":
                if installed_only:
                    local_channel = SoftwareChannel(channel_name,
                        None,
                        None,
                        installed_only=installed_only)
            elif (channel_origin and
                 channel_origin.startswith("LP-PPA-commercial-ppa-uploaders")):
                # do not display commercial private PPAs, they will all be
                # displayed in the "for-purchase" node anyway
                pass
            elif channel_origin and channel_origin.startswith("LP-PPA"):
                if channel_origin == "LP-PPA-app-review-board":
                    new_apps_channel = SoftwareChannel(channel_name,
                        channel_origin,
                        None,
                        installed_only=installed_only)
                else:
                    ppa_channels.append(SoftwareChannel(channel_name,
                        channel_origin,
                        None,
                        installed_only=installed_only))
            # TODO: detect generic repository source (e.g., Google, Inc.)
            else:
                other_channels.append(SoftwareChannel(channel_name,
                    channel_origin,
                    None,
                    installed_only=installed_only))

        # always display the partner channel, even if its source is not enabled
        if not partner_channel and distro_channel_name == "Ubuntu":
            partner_channel = SoftwareChannel("Partner archive",
                                              "Canonical",
                                              "partner",
                                              installed_only=installed_only)

        # create a "magic" channel to display items available for purchase
        for_purchase_query = xapian.Query("AH" +
            AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME)
        for_purchase_channel = SoftwareChannel("For Purchase",
            "software-center-agent", None,
            channel_icon=None,  # FIXME:  need an icon
            channel_query=for_purchase_query,
            installed_only=installed_only)

        # set them in order
        channels = []
        if dist_channel is not None:
            channels.append(dist_channel)
        if partner_channel is not None:
            channels.append(partner_channel)
        if get_distro().PURCHASE_APP_URL:
            channels.append(for_purchase_channel)
        if new_apps_channel is not None:
            channels.append(new_apps_channel)
        channels.extend(ppa_channels)
        channels.extend(other_channels)
        channels.extend(unknown_channel)
        channels.extend(self.extra_channels)
        if local_channel is not None:
            channels.append(local_channel)

        for channel in channels:
            if installed_only:
                channel._channel_view_id = ViewPages.INSTALLED
            else:
                channel._channel_view_id = ViewPages.AVAILABLE
        return channels
