# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#
# Parts taken from gnome-app-install:utils.py (also written by Michael Vogt)
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

import apt
import apt_pkg
import logging
import os

from gi.repository import GObject
from gi.repository import Gio

from softwarecenter.enums import PkgStates

from softwarecenter.db.pkginfo import PackageInfo, _Version

LOG = logging.getLogger(__name__)


class GtkMainIterationProgress(apt.progress.base.OpProgress):
    """Progress that just runs the main loop"""
    def update(self, percent=0):
        context = GObject.main_context_default()
        while context.pending():
            context.iteration()


def convert_package_argument(f):
    """ decorator converting _Package argument to Package object from cache """
    def _converted(self, pkg, *args):
        try:
            if type(pkg) is not apt_pkg.Package:
                if type(pkg) is str:
                    pkg = self._cache[pkg]
                else:
                    pkg = self._cache[pkg.name]
        except Exception as e:
            logging.exception(e)
            pkg = None
        return f(self, pkg, *args)
    return _converted


def pkg_downloaded(pkg_version):
    filename = os.path.basename(pkg_version.filename)
    # FIXME: use relative path here
    return os.path.exists("/var/cache/apt/archives/" + filename)


class AptCacheVersion(_Version):
    def __init__(self, version):
        self.ver = version

    @property
    def description(self):
        return self.ver.description

    @property
    def summary(self):
        return self.ver.summary

    @property
    def size(self):
        return self.ver.size

    @property
    def installed_size(self):
        return self.ver.installed_size

    @property
    def version(self):
        return self.ver.version

    @property
    def origins(self):
        return self.ver.origins

    @property
    def downloadable(self):
        return self.ver.downloadable

    @property
    def not_automatic(self):
        priority = self.ver.policy_priority
        if priority <= 100 and self.ver.downloadable:
            return True
        return False


class AptCache(PackageInfo):
    """
    A apt cache that opens in the background and keeps the UI alive
    """

    # dependency types we are about
    DEPENDENCY_TYPES = ("PreDepends", "Depends")
    RECOMMENDS_TYPES = ("Recommends",)
    SUGGESTS_TYPES = ("Suggests",)
    ENHANCES_TYPES = ("Enhances",)
    PROVIDES_TYPES = ("Provides",)

    # stamp file to monitor (provided by update-notifier via
    # APT::Update::Post-Invoke-Success)
    APT_FINISHED_STAMP = "/var/lib/update-notifier/dpkg-run-stamp"

    LANGPACK_PKGDEPENDS = "/usr/share/language-selector/data/pkg_depends"

    def __init__(self):
        PackageInfo.__init__(self)
        self._cache = None
        self._ready = False
        self._timeout_id = None
        # setup monitor watch for install/remove changes
        self.apt_finished_stamp = Gio.File.new_for_path(
            self.APT_FINISHED_STAMP)
        self.apt_finished_monitor = self.apt_finished_stamp.monitor_file(0,
            None)
        self.apt_finished_monitor.connect(
            "changed", self._on_apt_finished_stamp_changed)
        # this is fast, so ok
        self._language_packages = self._read_language_pkgs()

    @staticmethod
    def version_compare(a, b):
        return apt_pkg.version_compare(a, b)

    @staticmethod
    def upstream_version_compare(a, b):
        return apt_pkg.version_compare(apt_pkg.upstream_version(a),
                                       apt_pkg.upstream_version(b))

    @staticmethod
    def upstream_version(v):
        return apt_pkg.upstream_version(v)

    def is_installed(self, pkgname):
        # use the lowlevel cache here, twice as fast
        lowlevel_cache = self._cache._cache
        return (pkgname in lowlevel_cache and
                lowlevel_cache[pkgname].current_ver is not None)

    def is_upgradable(self, pkgname):
        # use the lowlevel cache here, twice as fast
        if not pkgname in self._cache:
            return False
        return self._cache[pkgname].is_upgradable

    def is_available(self, pkgname):
        return (pkgname in self._cache and
                self._cache[pkgname].candidate)

    def get_installed(self, pkgname):
        if (pkgname not in self._cache or
            not self._cache[pkgname].is_installed):
            return None
        return AptCacheVersion(self._cache[pkgname].installed)

    def get_candidate(self, pkgname):
        if (pkgname not in self._cache or
            not self._cache[pkgname].candidate):
            return None
        return AptCacheVersion(self._cache[pkgname].candidate)

    def get_versions(self, pkgname):
        if (pkgname not in self._cache or
            not self._cache[pkgname].candidate):
            return []
        return [AptCacheVersion(v) for v in self._cache[pkgname].versions]

    def get_section(self, pkgname):
        if (pkgname not in self._cache or
            not self._cache[pkgname].candidate):
            return ''
        return self._cache[pkgname].candidate.section

    def get_summary(self, pkgname):
        if (pkgname not in self._cache or
        not self._cache[pkgname].candidate):
            return ''
        return self._cache[pkgname].candidate.summary

    def get_description(self, pkgname):
        if (pkgname not in self._cache or
            not self._cache[pkgname].candidate):
            return ''
        return self._cache[pkgname].candidate.description

    def get_website(self, pkgname):
        if (pkgname not in self._cache or
            not self._cache[pkgname].candidate):
            return ''
        return self._cache[pkgname].candidate.homepage

    def get_installed_files(self, pkgname):
        if (pkgname not in self._cache):
            return []
        return self._cache[pkgname].installed_files

    def get_size(self, pkgname):
        if (pkgname not in self._cache or
            not self._cache[pkgname].candidate):
            return 0
        return self._cache[pkgname].candidate.size

    def get_installed_size(self, pkgname):
        if (pkgname not in self._cache or
            not self._cache[pkgname].candidate):
            return 0
        return self._cache[pkgname].candidate.installed_size

    @property
    def ready(self):
        return self._ready

    def get_license(self, name):
        return None

    def open(self):
        """ (re)open the cache, this sends cache-invalid, cache-ready signals
        """
        LOG.info("aptcache.open()")
        self._ready = False
        self.emit("cache-invalid")
        from softwarecenter.utils import ExecutionTime
        with ExecutionTime("open the apt cache (in event loop)"):
            if self._cache == None:
                self._cache = apt.Cache(GtkMainIterationProgress())
            else:
                self._cache.open(GtkMainIterationProgress())
        self._ready = True
        self.emit("cache-ready")
        if self._cache.broken_count > 0:
            self.emit("cache-broken")

    # implementation specific code

    # temporarely return a full apt.Package so that the tests and the
    # code keeps working for now, this needs to go away eventually
    # and get replaced with the abstract _Package class
    #def __getitem__(self, key):
    #    return self._cache[key]

    def __iter__(self):
        return self._cache.__iter__()

    def __contains__(self, k):
        return self._cache.__contains__(k)

    def _on_apt_finished_stamp_changed(self, monitor, afile, other_file,
        event):
        if not event == Gio.FileMonitorEvent.CHANGES_DONE_HINT:
            return
        if self._timeout_id:
            GObject.source_remove(self._timeout_id)
            self._timeout_id = None
        self._timeout_id = GObject.timeout_add_seconds(10, self.open)

    def _get_rdepends_by_type(self, pkg, type, onlyInstalled):
        rdeps = set()
        # make sure this is a apt.Package object
        try:
            pkg = self._cache[pkg.name]
        except KeyError:
            LOG.error("package %s not found in AptCache" % str(pkg))
            return rdeps
        for rdep in pkg._pkg.rev_depends_list:
            dep_type = rdep.dep_type_untranslated
            if dep_type in type:
                rdep_name = rdep.parent_pkg.name
                if rdep_name in self._cache and (not onlyInstalled or
                (onlyInstalled and self._cache[rdep_name].is_installed)):
                    rdeps.add(rdep.parent_pkg.name)
        return rdeps

    def _installed_dependencies(self, pkg_name, all_deps=None):
        """ recursively return all installed dependencies of a given pkg """
        #print "_installed_dependencies", pkg_name, all_deps
        if not all_deps:
            all_deps = set()
        if pkg_name not in self._cache:
            return all_deps
        cur = self._cache[pkg_name]._pkg.current_ver
        if not cur:
            return all_deps
        for t in self.DEPENDENCY_TYPES + self.RECOMMENDS_TYPES:
            try:
                for dep in cur.depends_list[t]:
                    dep_name = dep[0].target_pkg.name
                    if not dep_name in all_deps:
                        all_deps.add(dep_name)
                        all_deps |= self._installed_dependencies(dep_name,
                            all_deps)
            except KeyError:
                pass
        return all_deps

    def get_installed_automatic_depends_for_pkg(self, pkg):
        """ Get the installed automatic dependencies for this given package
            only.

            Note that the package must be marked for removal already for
            this to work
            Not: unused
        """
        installed_auto_deps = set()
        deps = self._installed_dependencies(pkg.name)
        for dep_name in deps:
            try:
                pkg = self._cache[dep_name]
            except KeyError:
                continue
            else:
                if (pkg.is_installed and
                    pkg.is_auto_removable):
                    installed_auto_deps.add(dep_name)
        return installed_auto_deps

    def get_all_origins(self):
        """
        return a set of the current channel origins from the apt.Cache itself
        """
        origins = set()
        for pkg in self._cache:
            if not pkg.candidate:
                continue
            for item in pkg.candidate.origins:
                context = GObject.main_context_default()
                while context.pending():
                    context.iteration()
                if item.origin:
                    origins.add(item.origin)
        return origins

    def get_origins(self, pkgname):
        """
        return package origins from apt.Cache
        """
        if not pkgname in self._cache or not self._cache[pkgname].candidate:
            return
        origins = set()
        for origin in self._cache[pkgname].candidate.origins:
            if origin.origin:
                origins.add(origin)
        return origins

    def get_origin(self, pkgname):
        """
        return a uniqe origin for the given package name. currently
        this will use
        """
        if not pkgname in self._cache or not self._cache[pkgname].candidate:
            return None
        origins = set([origin.origin for origin in self.get_origins(pkgname)])
        if len(origins) > 1:
            LOG.warn("more than one origin '%s'" % origins)
            return None
        if not origins:
            return None
        # we support only a single origin (but its fine if that is available
        # on multiple mirrors). lowercase as the server excepts it this way
        origin_str = origins.pop()
        return origin_str.lower()

    def component_available(self, distro_codename, component):
        """ check if the given component is enabled """
        # FIXME: test for more properties here?
        for it in self._cache._cache.file_list:
            if (it.component != "" and
                it.component == component and
                it.archive != "" and
                it.archive == distro_codename):
                return True
        return False

    @convert_package_argument
    def _get_depends_by_type(self, pkg, types):
        version = pkg.installed
        if version == None:
            version = pkg.candidate
        return version.get_dependencies(*types)

    def _get_depends_by_type_str(self, pkg, *types):
        def not_in_list(list, item):
            for i in list:
                if i == item:
                    return False
            return True
        deps = self._get_depends_by_type(pkg, *types)
        deps_str = []
        for dep in deps:
            for dep_ in dep.or_dependencies:
                if not_in_list(deps_str, dep_.name):
                    deps_str.append(dep_.name)
        return deps_str

    # FIXME: there are cleaner ways to do this than below

    # pkg relations
    def _get_depends(self, pkg):
        return self._get_depends_by_type_str(pkg, self.DEPENDENCY_TYPES)

    def _get_recommends(self, pkg):
        return self._get_depends_by_type_str(pkg, self.RECOMMENDS_TYPES)

    def _get_suggests(self, pkg):
        return self._get_depends_by_type_str(pkg, self.SUGGESTS_TYPES)

    def _get_enhances(self, pkg):
        return self._get_depends_by_type_str(pkg, self.ENHANCES_TYPES)

    @convert_package_argument
    def _get_provides(self, pkg):
        # note: can use ._cand, because pkg has been converted to apt.Package
        provides_list = pkg.candidate._cand.provides_list
        provides = []
        for provided in provides_list:
            provides.append(provided[0])  # the package name
        return provides

    # reverse pkg relations
    def _get_rdepends(self, pkg):
        return self._get_rdepends_by_type(pkg, self.DEPENDENCY_TYPES, False)

    def _get_rrecommends(self, pkg):
        return self._get_rdepends_by_type(pkg, self.RECOMMENDS_TYPES, False)

    def _get_rsuggests(self, pkg):
        return self._get_rdepends_by_type(pkg, self.SUGGESTS_TYPES, False)

    def _get_renhances(self, pkg):
        return self._get_rdepends_by_type(pkg, self.ENHANCES_TYPES, False)

    @convert_package_argument
    def _get_renhances_lowlevel_apt_pkg(self, pkg):
        """ takes a apt_pkg.Package and returns a list of pkgnames that
            enhance this package - this is needed to support enhances
            for virtual packages
        """
        renhances = []
        for dep in pkg.rev_depends_list:
            if dep.dep_type_untranslated == "Enhances":
                renhances.append(dep.parent_pkg.name)
        return renhances

    def _get_rprovides(self, pkg):
        return self._get_rdepends_by_type(pkg, self.PROVIDES_TYPES, False)

    # installed reverse pkg relations
    def get_packages_removed_on_remove(self, pkg):
        return self._get_rdepends_by_type(pkg, self.DEPENDENCY_TYPES, True)

    def get_packages_removed_on_install(self, pkg):
        depends = set()
        deps_remove = self._try_install_and_get_all_deps_removed(pkg)
        for depname in deps_remove:
            if self._cache[depname].is_installed:
                depends.add(depname)
        return depends

    def _get_installed_rrecommends(self, pkg):
        return self._get_rdepends_by_type(pkg, self.RECOMMENDS_TYPES, True)

    def _get_installed_rsuggests(self, pkg):
        return self._get_rdepends_by_type(pkg, self.SUGGESTS_TYPES, True)

    def _get_installed_renhances(self, pkg):
        return self._get_rdepends_by_type(pkg, self.ENHANCES_TYPES, True)

    def _get_installed_rprovides(self, pkg):
        return self._get_rdepends_by_type(pkg, self.PROVIDES_TYPES, True)

    # language pack stuff
    def _is_language_pkg(self, addon):
        # a simple "addon in self._language_packages" is not enough
        for template in self._language_packages:
            if addon.startswith(template):
                return True
        return False

    def _read_language_pkgs(self):
        language_packages = set()
        if not os.path.exists(self.LANGPACK_PKGDEPENDS):
            return language_packages
        for line in open(self.LANGPACK_PKGDEPENDS):
            line = line.strip()
            if line.startswith('#'):
                continue
            try:
                (cat, code, dep_pkg, language_pkg) = line.split(':')
            except ValueError:
                continue
            language_packages.add(language_pkg)
        return language_packages

    # these are used for calculating the total size
    @convert_package_argument
    def _get_changes_without_applying(self, pkg):
        try:
            if pkg.installed == None:
                pkg.mark_install()
            else:
                pkg.mark_delete()
        except SystemError:
            # TODO: ideally we now want to display an error message
            #       and block the install button
            LOG.warning("broken packages encountered while getting deps for %s"
                      % pkg.name)
            return {}
        changes_tmp = self._cache.get_changes()
        changes = {}
        for change in changes_tmp:
            if change.marked_install or change.marked_reinstall:
                changes[change.name] = PkgStates.INSTALLING
            elif change.marked_delete:
                changes[change.name] = PkgStates.REMOVING
            elif change.marked_upgrade:
                changes[change.name] = PkgStates.UPGRADING
            else:
                changes[change.name] = PkgStates.UNKNOWN
        self._cache.clear()
        return changes

    def _try_install_and_get_all_deps_installed(self, pkg):
        """ Return all dependencies of pkg that will be marked for install """
        changes = self._get_changes_without_applying(pkg)
        installing_deps = []
        for change in changes.keys():
            if change != pkg.name and changes[change] == PkgStates.INSTALLING:
                installing_deps.append(change)
        return installing_deps

    def _try_install_and_get_all_deps_removed(self, pkg):
        """ Return all dependencies of pkg that will be marked for remove"""
        changes = self._get_changes_without_applying(pkg)
        removing_deps = []
        for change in changes.keys():
            if change != pkg.name and changes[change] == PkgStates.REMOVING:
                removing_deps.append(change)
        return removing_deps

    def _set_candidate_release(self, pkg, archive_suite):
        # Check if the package is provided in the release
        for version in pkg.versions:
            if [origin for origin in version.origins
                if origin.archive == archive_suite]:
                break
        else:
            return False
        res = pkg._pcache._depcache.set_candidate_release(
            pkg._pkg, version._cand, archive_suite)
        return res

    def get_total_size_on_install(self, pkgname,
                                  addons_install=None, addons_remove=None,
                                  archive_suite=None):
        pkgs_to_install = []
        pkgs_to_remove = []
        total_download_size = 0  # in kB
        total_install_size = 0  # in kB

        if not pkgname in self._cache:
            return (0, 0)

        pkg = self._cache[pkgname]
        version = pkg.installed

        all_install = []
        if addons_install is not None:
            all_install += addons_install

        if version == None:
            # its important that its the first pkg as the depcache will
            # get cleared for each pkg and that will means that the
            # set_candidate_release is lost again
            all_install.append(pkgname)

        for p in all_install:
            # ensure that the archive_suite is set if needed, this needs to
            # be in the loop as the cache is cleared in each loop iteration
            if archive_suite:
                self._set_candidate_release(pkg, archive_suite)
            # now get the right version
            version = self._cache[p].candidate
            # this can happen on e.g. deb packages that are not in the cache
            # testcase: software-center google-chrome-stable_current_amd64.deb
            if not version:
                continue
            pkgs_to_install.append(version)
            # now do it
            deps_inst = self._try_install_and_get_all_deps_installed(
                self._cache[p])
            for dep in deps_inst:
                if self._cache[dep].installed == None:
                    dep_version = self._cache[dep].candidate
                    pkgs_to_install.append(dep_version)
            deps_remove = self._try_install_and_get_all_deps_removed(
                self._cache[p])
            for dep in deps_remove:
                if self._cache[dep].is_installed:
                    dep_version = self._cache[dep].installed
                    pkgs_to_remove.append(dep_version)

        all_remove = [] if addons_remove is None else addons_remove
        for p in all_remove:
            version = self._cache[p].installed
            pkgs_to_remove.append(version)
            deps_inst = self._try_install_and_get_all_deps_installed(
                self._cache[p])
            for dep in deps_inst:
                if self._cache[dep].installed == None:
                    version = self._cache[dep].candidate
                    pkgs_to_install.append(version)
            deps_remove = self._try_install_and_get_all_deps_removed(
                self._cache[p])
            for dep in deps_remove:
                if self._cache[dep].installed != None:
                    version = self._cache[dep].installed
                    pkgs_to_remove.append(version)

        pkgs_to_install = list(set(pkgs_to_install))
        pkgs_to_remove = list(set(pkgs_to_remove))

        for pkg in pkgs_to_install:
            if not pkg_downloaded(pkg) and not pkg.package.installed:
                total_download_size += pkg.size
            total_install_size += pkg.installed_size
        for pkg in pkgs_to_remove:
            total_install_size -= pkg.installed_size

        return (total_download_size, total_install_size)

    def get_all_deps_upgrading(self, pkg):
        # note: this seems not to be used anywhere
        changes = self._get_changes_without_applying(pkg)
        upgrading_deps = []
        for change in changes.keys():
            if change != pkg.name and changes[change] == PkgStates.UPGRADING:
                upgrading_deps.append(change)
        return upgrading_deps

    # determine the addons for a given package
    def get_addons(self, pkgname, ignore_installed=True):
        """ get the list of addons for the given pkgname

            The optional parameter "ignore_installed" controls if the output
            should be filtered and pkgs already installed should be ignored
            in the output (e.g. useful for testing).

            :return: a tuple of pkgnames (recommends, suggests)
        """
        logging.debug("get_addons for '%s'" % pkgname)

        def _addons_filter(addon):
            """ helper for get_addons that filters out unneeded ones """
            # we don't know about this one (prefectly legal for suggests)
            if not addon in self._cache:
                LOG.debug("not in cache %s" % addon)
                return False
            # can happen via "lonley" depends
            if addon == pkg.name:
                LOG.debug("circular %s" % addon)
                return False
            # child pkg is addon of parent pkg, not the other way around.
            if addon == '-'.join(pkgname.split('-')[:-1]):
                LOG.debug("child > parent %s" % addon)
                return False
            # get the pkg
            addon_pkg = self._cache[addon]
            # we don't care for essential or important (or refrences
            # to ourself)
            if (addon_pkg.essential or
                addon_pkg._pkg.important):
                LOG.debug("essential or important %s" % addon)
                return False
            # we have it in our dependencies already
            if addon in deps:
                LOG.debug("already a dependency %s" % addon)
                return False
            # its a language-pack, language-selector should deal with it
            if self._is_language_pkg(addon):
                LOG.debug("part of language pkg rdepends %s" % addon)
                return False
            # something on the system depends on it
            rdeps = self.get_packages_removed_on_remove(addon_pkg)
            if rdeps and ignore_installed:
                LOG.debug("already has a installed rdepends %s" % addon)
                return False
            # looks good
            return True
        #----------------------------------------------------------------

        def _addons_filter_slow(addon):
            """ helper for get_addons that filters out unneeded ones """
            # this addon would get installed anyway (e.g. via indirect
            # dependency) so it would be misleading to show it
            if addon in all_deps_if_installed:
                LOG.debug("would get installed automatically %s" % addon)
                return False
            return True
        #----------------------------------------------------------------
        # deb file, or pkg needing source, etc
        if (not pkgname in self._cache or
            not self._cache[pkgname].candidate):
            return ([], [])

        # initial setup
        pkg = self._cache[pkgname]

        # recommended addons
        addons_rec = self._get_recommends(pkg)
        LOG.debug("recommends: %s" % addons_rec)
        # suggested addons and renhances
        addons_sug = self._get_suggests(pkg)
        LOG.debug("suggests: %s" % addons_sug)
        renhances = self._get_renhances(pkg)
        LOG.debug("renhances: %s" % renhances)
        addons_sug += renhances
        provides = self._get_provides(pkg)
        LOG.debug("provides: %s" % provides)
        for provide in provides:
            virtual_aptpkg_pkg = self._cache._cache[provide]
            renhances = self._get_renhances_lowlevel_apt_pkg(
                virtual_aptpkg_pkg)
            LOG.debug("renhances of %s: %s" % (provide, renhances))
            addons_sug += renhances
            context = GObject.main_context_default()
            while context.pending():
                context.iteration()

        # get more addons, the idea is that if a package foo-data
        # just depends on foo we want to get the info about
        # "recommends, suggests, enhances" for foo-data as well
        #
        # FIXME: find a good package where this is actually the case and
        #        replace the existing test
        #        (arduino-core -> avrdude -> avrdude-doc) with that
        # FIXME2: if it turns out we don't have good/better examples,
        #         kill it
        deps = self._get_depends(pkg)
        for dep in deps:
            if dep in self._cache:
                pkgdep = self._cache[dep]
                if len(self._get_rdepends(pkgdep)) == 1:
                    # pkg is the only known package that depends on pkgdep
                    pkgdep_rec = self._get_recommends(pkgdep)
                    LOG.debug("recommends from lonley dependency %s: %s" % (
                            pkgdep, pkgdep_rec))
                    addons_rec += pkgdep_rec
                    pkgdep_sug = self._get_suggests(pkgdep)
                    LOG.debug("suggests from lonley dependency %s: %s" % (
                            pkgdep, pkgdep_sug))
                    addons_sug += pkgdep_sug
                    pkgdep_enh = self._get_renhances(pkgdep)
                    LOG.debug("renhances from lonley dependency %s: %s" % (
                            pkgdep, pkgdep_enh))
                    addons_sug += pkgdep_enh

            context = GObject.main_context_default()
            while context.pending():
                context.iteration()

        # remove duplicates from suggests (sets are great!)
        addons_sug = list(set(addons_sug) - set(addons_rec))

        # filter out stuff we don't want
        addons_rec = filter(_addons_filter, addons_rec)
        addons_sug = filter(_addons_filter, addons_sug)

        # this is not integrated into the filter above, as it is quite
        # expensive to run this call, so we only run it if we actually have
        # addons
        if addons_rec or addons_sug:
            # now get all_deps if the package would be installed
            try:
                all_deps_if_installed = \
                    self._try_install_and_get_all_deps_installed(pkg)
            except:
                # if we have broken packages, then we return no addons
                LOG.warn(
                    "broken packages encountered while getting deps for %s" %
                    pkgname)
                return ([], [])
            # filter out stuff we don't want
            addons_rec = filter(_addons_filter_slow, addons_rec)
            addons_sug = filter(_addons_filter_slow, addons_sug)

        return (addons_rec, addons_sug)

if __name__ == "__main__":
    c = AptCache()
    c.open()
    print("deps of unrar")
    print(c._installed_dependencies(c["unrar"].name))

    print("unused deps of 4g8")
    pkg = c._cache["4g8"]
    pkg.mark_delete()
    print(c.get_installed_automatic_depends_for_pkg(pkg))

    pkg = c["unace"]
    print(c.get_installed_automatic_depends_for_pkg(pkg))
    print(c.get_packages_removed_on_remove(pkg))
    print(c._get_installed_rrecommends(pkg))
    print(c._get_installed_rsuggests(pkg))

    print("deps of gimp")
    pkg = c["gimp"]
    print(c._get_depends(pkg))
    print(c._get_recommends(pkg))
    print(c._get_suggests(pkg))
    print(c._get_enhances(pkg))
    print(c._get_provides(pkg))

    print("rdeps of gimp")
    print(c._get_rdepends(pkg))
    print(c._get_rrecommends(pkg))
    print(c._get_rsuggests(pkg))
    print(c._get_renhances(pkg))
    print(c._get_rprovides(pkg))
