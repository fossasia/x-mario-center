# Copyright (C) 2009-2010 Canonical
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

import apt_pkg
import dbus
import logging
import os
import re

from gi.repository import GObject

from softwarecenter.utils import (sources_filename_from_ppa_entry,
                                  release_filename_in_lists_from_deb_line,
                                  obfuscate_private_ppa_details,
                                  utf8,
                                  )
from softwarecenter.enums import TransactionTypes

from aptdaemon import client
from aptdaemon import enums
from aptdaemon import errors
from aptsources.sourceslist import SourceEntry
from aptdaemon import policykit1

from defer import inline_callbacks, return_value

from softwarecenter.db.application import Application
from softwarecenter.backend.transactionswatcher import (
    BaseTransactionsWatcher,
    BaseTransaction,
    TransactionFinishedResult,
    TransactionProgress)
from softwarecenter.backend.installbackend import InstallBackend

from gettext import gettext as _

# its important that we only have a single dbus BusConnection
# per address when using the fake dbus aptd
buses = {}


def get_dbus_bus():
    if "SOFTWARE_CENTER_APTD_FAKE" in os.environ:
        global buses
        dbus_address = os.environ["SOFTWARE_CENTER_APTD_FAKE"]
        if dbus_address in buses:
            return buses[dbus_address]
        bus = buses[dbus_address] = dbus.bus.BusConnection(dbus_address)
    else:
        bus = dbus.SystemBus()
    return bus


class FakePurchaseTransaction(object):
    def __init__(self, app, iconname):
        self.pkgname = app.pkgname
        self.appname = app.appname
        self.iconname = iconname
        self.progress = 0


class AptdaemonTransaction(BaseTransaction):
    def __init__(self, trans):
        self._trans = trans

    @property
    def tid(self):
        return self._trans.tid

    @property
    def status_details(self):
        return self._trans.status_details

    @property
    def meta_data(self):
        return self._trans.meta_data

    @property
    def cancellable(self):
        return self._trans.cancellable

    @property
    def progress(self):
        return self._trans.progress

    def get_role_description(self, role=None):
        role = self._trans.role if role is None else role
        return enums.get_role_localised_present_from_enum(role)

    def get_status_description(self, status=None):
        status = self._trans.status if status is None else status
        return enums.get_status_string_from_enum(status)

    def is_waiting(self):
        return self._trans.status == enums.STATUS_WAITING_LOCK

    def is_downloading(self):
        return self._trans.status == enums.STATUS_DOWNLOADING

    def cancel(self):
        return self._trans.cancel()

    def connect(self, signal, handler, *args):
        """ append the real handler to the arguments """
        args = args + (handler, )
        return self._trans.connect(signal, self._handler, *args)

    def _handler(self, trans, *args):
        """ translate trans to BaseTransaction type.
        call the real handler after that
        """
        real_handler = args[-1]
        args = tuple(args[:-1])
        if isinstance(trans, client.AptTransaction):
            trans = AptdaemonTransaction(trans)
        return real_handler(trans, *args)


class AptdaemonTransactionsWatcher(BaseTransactionsWatcher):
    """
    base class for objects that need to watch the aptdaemon
    for transaction changes. it registers a handler for the daemon
    going away and reconnects when it appears again
    """

    def __init__(self):
        super(AptdaemonTransactionsWatcher, self).__init__()
        # watch the daemon exit and (re)register the signal
        bus = get_dbus_bus()
        self._owner_watcher = bus.watch_name_owner(
            "org.debian.apt", self._register_active_transactions_watch)

    def _register_active_transactions_watch(self, connection):
        #print "_register_active_transactions_watch", connection
        bus = get_dbus_bus()
        apt_daemon = client.get_aptdaemon(bus=bus)
        apt_daemon.connect_to_signal("ActiveTransactionsChanged",
                                     self._on_transactions_changed)
        current, queued = apt_daemon.GetActiveTransactions()
        self._on_transactions_changed(current, queued)

    def _on_transactions_changed(self, current, queued):
        self.emit("lowlevel-transactions-changed", current, queued)

    def get_transaction(self, tid):
        """ synchroneously return a transaction """
        try:
            trans = client.get_transaction(tid)
            return AptdaemonTransaction(trans)
        except dbus.DBusException:
            pass


class AptdaemonBackend(GObject.GObject, InstallBackend):
    """ software center specific code that interacts with aptdaemon """

    __gsignals__ = {'transaction-started': (GObject.SIGNAL_RUN_FIRST,
                                            GObject.TYPE_NONE,
                                            (str, str, str, str)),
                    # emits a TransactionFinished object
                    'transaction-finished': (GObject.SIGNAL_RUN_FIRST,
                                             GObject.TYPE_NONE,
                                             (GObject.TYPE_PYOBJECT, )),
                    # emits a TransactionFinished object
                    'transaction-stopped': (GObject.SIGNAL_RUN_FIRST,
                                            GObject.TYPE_NONE,
                                            (GObject.TYPE_PYOBJECT,)),
                    # emits with a pending_transactions list object
                    'transactions-changed': (GObject.SIGNAL_RUN_FIRST,
                                             GObject.TYPE_NONE,
                                             (GObject.TYPE_PYOBJECT, )),
                    # emits pkgname, percent
                    'transaction-progress-changed': (GObject.SIGNAL_RUN_FIRST,
                                                     GObject.TYPE_NONE,
                                                     (str, int,)),
                    # the number/names of the available channels changed
                    'channels-changed': (GObject.SIGNAL_RUN_FIRST,
                                         GObject.TYPE_NONE,
                                         (bool,)),
                    # cache reload emits this specific signal as well
                    'reload-finished': (GObject.SIGNAL_RUN_FIRST,
                                        GObject.TYPE_NONE,
                                        (GObject.TYPE_PYOBJECT, bool,)),
                    }

    def __init__(self):
        GObject.GObject.__init__(self)

        bus = get_dbus_bus()
        self.aptd_client = client.AptClient(bus=bus)
        self.pending_transactions = {}
        self._transactions_watcher = AptdaemonTransactionsWatcher()
        self._transactions_watcher.connect("lowlevel-transactions-changed",
            self._on_lowlevel_transactions_changed)
        # dict of pkgname -> FakePurchaseTransaction
        self.pending_purchases = {}
        self._progress_signal = None
        self._logger = logging.getLogger("softwarecenter.backend")
        # the AptdaemonBackendUI code
        self.ui = None

    def _axi_finished(self, res):
        self.emit("channels-changed", res)

    # public methods
    def update_xapian_index(self):
        self._logger.debug("update_xapian_index")
        system_bus = get_dbus_bus()
        # axi is optional, so just do nothing if its not installed
        try:
            axi = dbus.Interface(
                system_bus.get_object("org.debian.AptXapianIndex", "/"),
                "org.debian.AptXapianIndex")
        except dbus.DBusException as e:
            self._logger.warning("axi can not be updated '%s'" % e)
            return
        axi.connect_to_signal("UpdateFinished", self._axi_finished)
        # we don't really care for updates at this point
        #axi.connect_to_signal("UpdateProgress", progress)
        try:
            # first arg is force, second update_only
            axi.update_async(True, False)
        except:
            self._logger.warning("could not update axi")

    @inline_callbacks
    def fix_broken_depends(self):
        try:
            trans = yield self.aptd_client.fix_broken_depends(defer=True)
            self.emit("transaction-started", "", "", trans.tid,
                TransactionTypes.REPAIR)
            yield self._run_transaction(trans, None, None, None)
        except Exception as error:
            self._on_trans_error(error)

    @inline_callbacks
    def fix_incomplete_install(self):
        try:
            trans = yield self.aptd_client.fix_incomplete_install(defer=True)
            self.emit("transaction-started", "", "", trans.tid,
                      TransactionTypes.REPAIR)
            yield self._run_transaction(trans, None, None, None)
        except Exception as error:
            self._on_trans_error(error)

    # FIXME: upgrade add-ons here
    @inline_callbacks
    def upgrade(self, app, iconname, addons_install=[], addons_remove=[],
        metadata=None):
        """ upgrade a single package """
        pkgname = app.pkgname
        appname = app.appname
        try:
            trans = yield self.aptd_client.upgrade_packages([pkgname],
                                                            defer=True)
            self.emit("transaction-started", pkgname, appname, trans.tid,
                TransactionTypes.UPGRADE)
            yield self._run_transaction(trans, pkgname, appname, iconname,
                metadata)
        except Exception as error:
            self._on_trans_error(error, pkgname)

# broken
#    @inline_callbacks
#    def _simulate_remove_multiple(self, pkgnames):
#        try:
#            trans = yield self.aptd_client.remove_packages(pkgnames,
#                                                           defer=True)
#            trans.connect("dependencies-changed",
#                self._on_dependencies_changed)
#        except Exception:
#            logging.exception("simulate_remove")
#        return_value(trans)
#
#   def _on_dependencies_changed(self, *args):
#        print "_on_dependencies_changed", args
#        self.have_dependencies = True
#
#    @inline_callbacks
#    def simulate_remove_multiple(self, pkgnames):
#        self.have_dependencies = False
#        trans = yield self._simulate_remove_multiple(pkgnames)
#        print trans
#        while not self.have_dependencies:
#            while gtk.events_pending():
#                gtk.main_iteration()
#            time.sleep(0.01)

    @inline_callbacks
    def remove(self, app, iconname, addons_install=[], addons_remove=[],
        metadata=None):
        """ remove a single package """
        pkgname = app.pkgname
        appname = app.appname
        try:
            trans = yield self.aptd_client.remove_packages([pkgname],
                                                           defer=True)
            self.emit("transaction-started", pkgname, appname, trans.tid,
                TransactionTypes.REMOVE)
            yield self._run_transaction(trans, pkgname, appname, iconname,
                metadata)
        except Exception as error:
            self._on_trans_error(error, pkgname)

    @inline_callbacks
    def remove_multiple(self, apps, iconnames, addons_install=[],
        addons_remove=[], metadatas=None):
        """ queue a list of packages for removal  """
        if metadatas == None:
            metadatas = []
            for item in apps:
                metadatas.append(None)
        for app, iconname, metadata in zip(apps, iconnames, metadatas):
            yield self.remove(app, iconname, metadata)

    @inline_callbacks
    def install(self, app, iconname, filename=None, addons_install=[],
        addons_remove=[], metadata=None, force=False):
        """Install a single package from the archive
           If filename is given a local deb package is installed instead.
        """
        pkgname = app.pkgname
        appname = app.appname
        # this will force aptdaemon to use the right archive suite on install
        if app.archive_suite:
            pkgname = "%s/%s" % (pkgname, app.archive_suite)
        try:
            if filename:
                # force means on lintian failure
                trans = yield self.aptd_client.install_file(
                    filename, force=force, defer=True)
                self.emit("transaction-started", pkgname, appname, trans.tid,
                    TransactionTypes.INSTALL)
                yield trans.set_meta_data(sc_filename=filename, defer=True)
            else:
                install = [pkgname] + addons_install
                remove = addons_remove
                reinstall = remove = purge = upgrade = downgrade = []
                trans = yield self.aptd_client.commit_packages(
                    install, reinstall, remove, purge, upgrade, downgrade,
                    defer=True)
                self.emit("transaction-started", pkgname, appname, trans.tid,
                    TransactionTypes.INSTALL)
            yield self._run_transaction(
                trans, pkgname, appname, iconname, metadata)
        except Exception as error:
            self._on_trans_error(error, pkgname)

    @inline_callbacks
    def install_multiple(self, apps, iconnames, addons_install=[],
        addons_remove=[], metadatas=None):
        """ queue a list of packages for install  """
        if metadatas == None:
            metadatas = []
            for item in apps:
                metadatas.append(None)
        for app, iconname, metadata in zip(apps, iconnames, metadatas):
            yield self.install(app, iconname, metadata=metadata)

    @inline_callbacks
    def apply_changes(self, app, iconname, addons_install=[],
        addons_remove=[], metadata=None):
        """ install and remove add-ons """
        pkgname = app.pkgname
        appname = app.appname
        try:
            install = addons_install
            remove = addons_remove
            reinstall = remove = purge = upgrade = downgrade = []
            trans = yield self.aptd_client.commit_packages(
                install, reinstall, remove, purge, upgrade, downgrade,
                defer=True)
            self.emit("transaction-started", pkgname, appname, trans.tid,
                TransactionTypes.APPLY)
            yield self._run_transaction(trans, pkgname, appname, iconname)
        except Exception as error:
            self._on_trans_error(error)

    @inline_callbacks
    def reload(self, sources_list=None, metadata=None):
        """ reload package list """
        # check if the sourcespart is there, if not, do a full reload
        # this can happen when the "partner" repository is added, it
        # will be in the main sources.list already and this means that
        # aptsources will just enable it instead of adding a extra
        # sources.list.d file (LP: #666956)
        d = apt_pkg.config.find_dir("Dir::Etc::sourceparts")
        if (not sources_list or
            not os.path.exists(os.path.join(d, sources_list))):
            sources_list = ""
        try:
            trans = yield self.aptd_client.update_cache(
                sources_list=sources_list, defer=True)
            yield self._run_transaction(trans, None, None, None, metadata)
        except Exception as error:
            self._on_trans_error(error)
        # note that the cache re-open will happen via the connected
        # "transaction-finished" signal

    @inline_callbacks
    def enable_component(self, component):
        self._logger.debug("enable_component: %s" % component)
        try:
            trans = yield self.aptd_client.enable_distro_component(component)
            # don't use self._run_transaction() here, to avoid sending uneeded
            # signals
            yield trans.run(defer=True)
        except Exception as error:
            self._on_trans_error(error, component)
            return_value(None)
        # now update the cache
        yield self.reload()

    @inline_callbacks
    def enable_channel(self, channelfile):
        # read channel file and add all relevant lines
        for line in open(channelfile):
            line = line.strip()
            if not line:
                continue
            entry = SourceEntry(line)
            if entry.invalid:
                continue
            sourcepart = os.path.basename(channelfile)
            yield self.add_sources_list_entry(entry, sourcepart)
            keyfile = channelfile.replace(".list", ".key")
            if os.path.exists(keyfile):
                trans = yield self.aptd_client.add_vendor_key_from_file(
                    keyfile, wait=True)
                # don't use self._run_transaction() here, to avoid sending
                # uneeded signals
                yield trans.run(defer=True)
        yield self.reload(sourcepart)

    @inline_callbacks
    def add_vendor_key_from_keyserver(self, keyid,
        keyserver="hkp://keyserver.ubuntu.com:80/", metadata=None):
        # strip the keysize
        if "/" in keyid:
            keyid = keyid.split("/")[1]
        if not keyid.startswith("0x"):
            keyid = "0x%s" % keyid
        try:
            trans = yield self.aptd_client.add_vendor_key_from_keyserver(
                keyid, keyserver, defer=True)
            yield self._run_transaction(trans, None, None, None, metadata)
        except Exception as error:
            self._on_trans_error(error)

    @inline_callbacks
    def add_sources_list_entry(self, source_entry, sourcepart=None):
        if isinstance(source_entry, basestring):
            entry = SourceEntry(source_entry)
        elif isinstance(source_entry, SourceEntry):
            entry = source_entry
        else:
            raise ValueError("Unsupported entry type %s" % type(source_entry))

        if not sourcepart:
            sourcepart = sources_filename_from_ppa_entry(entry)

        args = (entry.type, entry.uri, entry.dist, entry.comps,
                "Added by software-center", sourcepart)
        try:
            trans = yield self.aptd_client.add_repository(*args, defer=True)
            yield self._run_transaction(trans, None, None, None)
        except errors.NotAuthorizedError, err:
            self._logger.error("add_repository: '%s'" % err)
            return_value(None)
        return_value(sourcepart)

    @inline_callbacks
    def authenticate_for_purchase(self):
        """
        helper that authenticates with aptdaemon for a purchase operation
        """
        bus = get_dbus_bus()
        name = bus.get_unique_name()
        action = policykit1.PK_ACTION_INSTALL_PURCHASED_PACKAGES
        flags = policykit1.CHECK_AUTH_ALLOW_USER_INTERACTION
        yield policykit1.check_authorization_by_name(name, action, flags=flags)

    @inline_callbacks
    def add_license_key(self, license_key, license_key_path,
        license_key_oauth, pkgname):
        """ add a license key for a purchase. """
        self._logger.debug(
            "adding license_key for pkg '%s' of len: %i" % (
                pkgname, len(license_key)))

        # HOME based license keys
        if license_key_path and license_key_path.startswith("~"):
            # check if its inside HOME and if so, just create it
            dest = os.path.expanduser(os.path.normpath(license_key_path))
            dirname = os.path.dirname(dest)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            if not os.path.exists(dest):
                f = open(dest, "w")
                f.write(license_key)
                f.close()
                os.chmod(dest, 0600)
            else:
                self._logger.warn("license file '%s' already exists" % dest)
        else:
            # system-wide keys
            try:
                self._logger.info("adding license key for '%s'" % pkgname)
                server = "ubuntu-production"
                trans = yield self.aptd_client.add_license_key(
                    pkgname, license_key_oauth, server)
                yield self._run_transaction(trans, None, None, None)
            except Exception as e:
                self._logger.error("add_license_key: '%s'" % e)

    @inline_callbacks
    def add_repo_add_key_and_install_app(self,
                                         deb_line,
                                         signing_key_id,
                                         app,
                                         iconname,
                                         license_key,
                                         license_key_path,
                                         json_oauth_token=None,
                                         purchase=True):
        """
        a convenience method that combines all of the steps needed
        to install a for-pay application, including adding the
        source entry and the vendor key, reloading the package list,
        and finally installing the specified application once the
        package list reload has completed.
        """
        self.emit("transaction-started", app.pkgname, app.appname,
            "FIXME-NEED-ID-HERE", TransactionTypes.INSTALL)
        self._logger.info("add_repo_add_key_and_install_app() '%s' '%s' '%s'" %
            (re.sub("deb https://.*@", "", deb_line),  # strip out password
            signing_key_id,
            app))

        if purchase:
            # pre-authenticate
            try:
                yield self.authenticate_for_purchase()
            except:
                self._logger.exception("authenticate_for_purchase failed")
                self._clean_pending_purchases(app.pkgname)
                result = TransactionFinishedResult(None, False)
                result.pkgname = app.pkgname
                self.emit("transaction-stopped", result)
                return
            # done
            fake_trans = FakePurchaseTransaction(app, iconname)
            self.pending_purchases[app.pkgname] = fake_trans
        else:
            # FIXME: add authenticate_for_added_repo here
            pass

        # add the metadata early, add_sources_list_entry is a transaction
        # too
        trans_metadata = {
            'sc_add_repo_and_install_appname': app.appname,
            'sc_add_repo_and_install_pkgname': app.pkgname,
            'sc_add_repo_and_install_deb_line': deb_line,
            'sc_iconname': iconname,
            'sc_add_repo_and_install_try': "1",
            'sc_add_repo_and_install_license_key': license_key or "",
            'sc_add_repo_and_install_license_key_path': license_key_path or "",
            'sc_add_repo_and_install_license_key_token': \
                json_oauth_token or "",
        }

        self._logger.info("add_sources_list_entry()")
        sourcepart = yield self.add_sources_list_entry(deb_line)
        trans_metadata['sc_add_repo_and_install_sources_list'] = sourcepart

        # metadata so that we know those the add-key and reload transactions
        # are part of a group
        self._logger.info("add_vendor_key_from_keyserver()")
        yield self.add_vendor_key_from_keyserver(signing_key_id,
                                                 metadata=trans_metadata)
        self._logger.info("reload_for_commercial_repo()")
        yield self._reload_for_commercial_repo(app, trans_metadata, sourcepart)

    @inline_callbacks
    def _reload_for_commercial_repo_defer(self, app, trans_metadata,
        sources_list):
        """
        helper that reloads and registers a callback for when the reload is
        finished
        """
        trans_metadata["sc_add_repo_and_install_ignore_errors"] = "1"
        # and then queue the install only when the reload finished
        # otherwise the daemon will fail because he does not know
        # the new package name yet
        self.connect("reload-finished",
                     self._on_reload_for_add_repo_and_install_app_finished,
                     trans_metadata, app)
        # reload to ensure we have the new package data
        yield self.reload(sources_list=sources_list, metadata=trans_metadata)

    def _reload_for_commercial_repo(self, app, trans_metadata, sources_list):
        """ this reloads a commercial repo in a glib timeout
            See _reload_for_commercial_repo_inline() for the actual work
            that is done
        """
        self._logger.info("_reload_for_commercial_repo() %s" % app)
        # trigger inline_callbacked function
        self._reload_for_commercial_repo_defer(
            app, trans_metadata, sources_list)
        # return False to stop the timeout (one shot only)
        return False

    @inline_callbacks
    def _on_reload_for_add_repo_and_install_app_finished(self, backend, trans,
        result, metadata, app):
        """
        callback that is called once after reload was queued
        and will trigger the install of the for-pay package itself
        (after that it will automatically de-register)
        """
        #print "_on_reload_for_add_repo_and_install_app_finished", trans, \
        #    result, backend, self._reload_signal_id
        self._logger.info("_on_reload_for_add_repo_and_install_app_finished() "
            "%s %s %s" % (trans, result, app))

        # check if this is the transaction we waiting for
        key = "sc_add_repo_and_install_pkgname"
        if not (key in trans.meta_data and
            trans.meta_data[key] == app.pkgname):
            return_value(None)

        # get the debline and check if we have a release.gpg file
        deb_line = trans.meta_data["sc_add_repo_and_install_deb_line"]
        license_key = trans.meta_data["sc_add_repo_and_install_license_key"]
        license_key_path = trans.meta_data[
            "sc_add_repo_and_install_license_key_path"]
        license_key_oauth = trans.meta_data[
            "sc_add_repo_and_install_license_key_token"]
        release_filename = release_filename_in_lists_from_deb_line(deb_line)
        lists_dir = apt_pkg.config.find_dir("Dir::State::lists")
        release_signature = os.path.join(lists_dir, release_filename) + ".gpg"
        self._logger.info("looking for '%s'" % release_signature)
        # no Release.gpg in the newly added repository, try again,
        # this can happen e.g. on odd network proxies
        if not os.path.exists(release_signature):
            self._logger.warn("no %s found, re-trying" % release_signature)
            result = False

        # disconnect again, this is only a one-time operation
        self.disconnect_by_func(
            self._on_reload_for_add_repo_and_install_app_finished)

        # FIXME: this logic will *fail* if the sources.list of the user
        #        was broken before

        # run install action if the repo was added successfully
        if result:
            self.emit("channels-changed", True)

            # we use aptd_client.install_packages() here instead
            # of just
            #  self.install(app, "", metadata=metadata)
            # go get less authentication prompts (because of the
            # 03_auth_me_less patch in aptdaemon)
            try:
                self._logger.info("install_package()")
                trans = yield self.aptd_client.install_packages(
                    [app.pkgname], defer=True)
                self._logger.info("run_transaction()")
                yield self._run_transaction(trans, app.pkgname, app.appname,
                                            "", metadata)
            except Exception as error:
                self._on_trans_error(error, app.pkgname)
            # add license_key
            # FIXME: aptd fails if there is a license_key_path already
            #        but I wonder if we should ease that restriction
            if license_key and not os.path.exists(license_key_path):
                yield self.add_license_key(
                    license_key, license_key_path, license_key_oauth,
                    app.pkgname)

        else:
            # download failure
            # ok, here is the fun! we can not reload() immediately, because
            # there is a delay of up to 5(!) minutes between s-c-agent telling
            # us that we can download software and actually being able to
            # download it
            retry = int(trans.meta_data['sc_add_repo_and_install_try'])
            if retry > 10:
                self._logger.error("failed to add repo after 10 tries")
                self._clean_pending_purchases(
                    trans.meta_data['sc_add_repo_and_install_pkgname'])
                self._show_transaction_failed_dialog(trans, result)
                return_value(False)
            # this just sets the meta_data locally, but that is ok, the
            # whole re-try machinery will not survive anyway if the local
            # s-c instance is closed
            self._logger.info("queuing reload in 30s")
            trans.meta_data["sc_add_repo_and_install_try"] = str(retry + 1)
            sourcepart = trans.meta_data[
                "sc_add_repo_and_install_sources_list"]
            GObject.timeout_add_seconds(30, self._reload_for_commercial_repo,
                                     app, trans.meta_data, sourcepart)

    # internal helpers
    def _on_lowlevel_transactions_changed(self, watcher, current, pending):
        # cleanup progress signal (to be sure to not leave dbus
        # matchers around)
        if self._progress_signal:
            GObject.source_remove(self._progress_signal)
            self._progress_signal = None
        # attach progress-changed signal for current transaction
        if current:
            try:
                trans = client.get_transaction(current)
                self._progress_signal = trans.connect("progress-changed",
                    self._on_progress_changed)
            except dbus.DBusException:
                pass

        # now update pending transactions
        self.pending_transactions.clear()
        for tid in [current] + pending:
            if not tid:
                continue
            try:
                trans = client.get_transaction(tid,
                    error_handler=lambda x: True)
            except dbus.DBusException:
                continue
            trans_progress = TransactionProgress(trans)
            try:
                self.pending_transactions[trans_progress.pkgname] = \
                    trans_progress
            except KeyError:
                # if its not a transaction from us (sc_pkgname) still
                # add it with the tid as key to get accurate results
                # (the key of pending_transactions is never directly
                #  exposed in the UI)
                self.pending_transactions[trans.tid] = trans_progress
        # emit signal
        self.inject_fake_transactions_and_emit_changed_signal()

    def inject_fake_transactions_and_emit_changed_signal(self):
        """
        ensures that the fake transactions are considered and emits
        transactions-changed signal with the right pending transactions
        """
        # inject a bunch FakePurchaseTransaction into the transations dict
        for pkgname in self.pending_purchases:
            self.pending_transactions[pkgname] = \
                self.pending_purchases[pkgname]
        # and emit the signal
        self.emit("transactions-changed", self.pending_transactions)

    def _on_progress_changed(self, trans, progress):
        """
        internal helper that gets called on our package transaction progress
        (only showing pkg progress currently)
        """
        try:
            pkgname = trans.meta_data["sc_pkgname"]
            self.pending_transactions[pkgname].progress = progress
            self.emit("transaction-progress-changed", pkgname, progress)
        except KeyError:
            pass

    def _show_transaction_failed_dialog(self, trans, enum,
                                        alternative_action=None):
        # daemon died are messages that result from broken
        # cancel handling in aptdaemon (LP: #440941)
        # FIXME: this is not a proper fix, just a workaround
        if trans.error_code == enums.ERROR_DAEMON_DIED:
            self._logger.warn("daemon dies, ignoring: %s %s" % (trans, enum))
            return
        # hide any private ppa details in the error message since it may
        # appear in the logs for LP bugs and potentially in screenshots as well
        cleaned_error_details = obfuscate_private_ppa_details(
            trans.error_details)
        msg = utf8("%s: %s\n%s\n\n%s") % (
              utf8(_("Error")),
              utf8(enums.get_error_string_from_enum(trans.error_code)),
              utf8(enums.get_error_description_from_enum(trans.error_code)),
              utf8(cleaned_error_details))
        self._logger.error("error in _on_trans_finished '%s'" % msg)
        # show dialog to the user and exit (no need to reopen the cache)
        if not trans.error_code:
            # sometimes aptdaemon doesn't return a value for error_code
            # when the network connection has become unavailable; in
            # that case, we will assume it's a failure during a package
            # download because that is the only case where we see this
            # happening - this avoids display of an empty error dialog
            # and correctly prompts the user to check their network
            # connection (see LP: #747172)
            # FIXME: fix aptdaemon to return a valid error_code under
            # all conditions
            trans.error_code = enums.ERROR_PACKAGE_DOWNLOAD_FAILED
        # show dialog to the user and exit (no need to reopen
        # the cache)
        res = self.ui.error(None,
            utf8(enums.get_error_string_from_enum(trans.error_code)),
            utf8(enums.get_error_description_from_enum(trans.error_code)),
            utf8(cleaned_error_details),
            utf8(alternative_action))
        return res

    def _get_app_and_icon_and_deb_from_trans(self, trans):
        meta_copy = trans.meta_data.copy()
        app = Application(meta_copy.pop("sc_appname", None),
                          meta_copy.pop("sc_pkgname"))
        iconname = meta_copy.pop("sc_iconname", None)
        filename = meta_copy.pop("sc_filename", "")
        return app, iconname, filename, meta_copy

    def _on_trans_finished(self, trans, enum):
        """callback when a aptdaemon transaction finished"""
        self._logger.debug("_on_transaction_finished: %s %s %s" % (
                trans, enum, trans.meta_data))

        # show error
        if enum == enums.EXIT_FAILED:
            # Handle invalid packages separately
            if (trans.error and
                trans.error.code == enums.ERROR_INVALID_PACKAGE_FILE):
                action = _("_Ignore and install")
                res = self._show_transaction_failed_dialog(
                    trans, enum, action)
                if res == "yes":
                    # Reinject the transaction
                    app, iconname, filename, meta_copy = \
                        self._get_app_and_icon_and_deb_from_trans(trans)
                    self.install(app, iconname, filename, [], [],
                                 metadata=meta_copy, force=True)
                    return
            # on unauthenticated errors, try a "repair" using the
            # reload functionatlity
            elif (trans.error and
                  trans.error.code == enums.ERROR_PACKAGE_UNAUTHENTICATED):
                action = _("Repair")
                res = self._show_transaction_failed_dialog(
                    trans, enum, action)
                if res == "yes":
                    app, iconname, filename, meta_copy = \
                        self._get_app_and_icon_and_deb_from_trans(trans)
                    self.reload()
                    self.install(app, iconname, filename, [], [],
                                 metadata=meta_copy)
                    return
            # Finish a cancelled installation before resuming. If the
            # user e.g. rebooted during a debconf question apt
            # will hang and the user is required to call
            # dpkg --configure -a, see LP#659438
            elif (trans.error and
                  trans.error.code == enums.ERROR_INCOMPLETE_INSTALL):
                action = _("Repair")
                res = self._show_transaction_failed_dialog(trans, enum,
                                                           action)
                if res == "yes":
                    self.fix_incomplete_install()
                    return

            elif (not "sc_add_repo_and_install_ignore_errors" in
                  trans.meta_data):
                self._show_transaction_failed_dialog(trans, enum)

        # send finished signal, use "" here instead of None, because
        # dbus mangles a None to a str("None")
        pkgname = ""
        try:
            pkgname = trans.meta_data["sc_pkgname"]
            del self.pending_transactions[pkgname]
            self.emit("transaction-progress-changed", pkgname, 100)
        except KeyError:
            pass
        # if it was a cache-reload, trigger a-x-i update
        if trans.role == enums.ROLE_UPDATE_CACHE:
            if enum == enums.EXIT_SUCCESS:
                self.update_xapian_index()
            self.emit("reload-finished", trans, enum != enums.EXIT_FAILED)
        # send appropriate signals
        self.inject_fake_transactions_and_emit_changed_signal()
        self.emit("transaction-finished", TransactionFinishedResult(trans,
            enum != enums.EXIT_FAILED))

    @inline_callbacks
    def _config_file_conflict(self, transaction, old, new):
        reply = self.ui.ask_config_file_conflict(old, new)
        if reply == "replace":
            yield transaction.resolve_config_file_conflict(old, "replace",
                                                           defer=True)
        elif reply == "keep":
            yield transaction.resolve_config_file_conflict(old, "keep",
                                                           defer=True)
        else:
            raise Exception(
                "unknown reply: '%s' in _ask_config_file_conflict " % reply)

    @inline_callbacks
    def _medium_required(self, transaction, medium, drive):
        res = self.ui.ask_medium_required(medium, drive)
        if res:
            yield transaction.provide_medium(medium, defer=True)
        else:
            yield transaction.cancel(defer=True)

    @inline_callbacks
    def _run_transaction(self, trans, pkgname, appname, iconname,
                         metadata=None):
        # connect signals
        trans.connect("config-file-conflict", self._config_file_conflict)
        trans.connect("medium-required", self._medium_required)
        trans.connect("finished", self._on_trans_finished)
        try:
            # set appname/iconname/pkgname only if we actually have one
            if appname:
                yield trans.set_meta_data(sc_appname=appname, defer=True)
            if iconname:
                yield trans.set_meta_data(sc_iconname=iconname, defer=True)
            # we do not always have a pkgname, e.g. "cache_update" does not
            if pkgname:
                # ensure the metadata is just the pkgname
                sc_pkgname = pkgname.split("/")[0].split("=")[0]
                yield trans.set_meta_data(sc_pkgname=sc_pkgname, defer=True)
                # setup debconf only if we have a pkg
                yield trans.set_debconf_frontend("gnome", defer=True)
                trans.set_remove_obsoleted_depends(True, defer=True)
                self._progress_signal = trans.connect("progress-changed",
                    self._on_progress_changed)
                self.pending_transactions[pkgname] = TransactionProgress(trans)
            # generic metadata
            if metadata:
                yield trans.set_meta_data(defer=True, **metadata)
            yield trans.run(defer=True)
        except Exception as error:
            self._on_trans_error(error, pkgname)
            # on error we need to clean the pending purchases
            self._clean_pending_purchases(pkgname)
        # on success the pending purchase is cleaned when the package
        # that was purchased finished installing
        if trans.role == enums.ROLE_INSTALL_PACKAGES:
            self._clean_pending_purchases(pkgname)

    def _clean_pending_purchases(self, pkgname):
        if pkgname and pkgname in self.pending_purchases:
            del self.pending_purchases[pkgname]

    def _on_trans_error(self, error, pkgname=None):
        self._logger.warn("_on_trans_error: %s", error)
        # re-enable the action button again if anything went wrong
        result = TransactionFinishedResult(None, False)
        result.pkgname = pkgname

        # clean up pending transactions
        if pkgname and pkgname in self.pending_transactions:
            del self.pending_transactions[pkgname]

        self.emit("transaction-stopped", result)
        if isinstance(error, dbus.DBusException):
            name = error.get_dbus_name()
            if name in ["org.freedesktop.PolicyKit.Error.NotAuthorized",
                        "org.freedesktop.DBus.Error.NoReply"]:
                pass
        else:
            self._logger.exception("_on_trans_error")
            #raise error


if __name__ == "__main__":
    #c = client.AptClient()
    #c.remove_packages(["4g8"], remove_unused_dependencies=True)
    backend = AptdaemonBackend()
    #backend.reload()
    backend.enable_component("multiverse")
    from gi.repository import Gtk
    Gtk.main()
