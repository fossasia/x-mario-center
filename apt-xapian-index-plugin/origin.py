# Add origin tags to the index

import apt
import os


class OriginPlugin:

    def info(self):
        """
        Return general information about the plugin.

        The information returned is a dict with various keywords:

         timestamp (required)
           the last modified timestamp of this data source.  This will be used
           to see if we need to update the database or not.  A timestamp of 0
           means that this data source is either missing or always up to date.
         values (optional)
           an array of dicts { name: name, desc: description }, one for every
           numeric value indexed by this data source.

        Note that this method can be called before init.  The idea is that, if
        the timestamp shows that this plugin is currently not needed, then the
        long initialisation can just be skipped.
        """
        file = apt.apt_pkg.config.find_file("Dir::Cache::pkgcache")
        if not os.path.exists(file):
            return dict(timestamp=0)
        return dict(timestamp=os.path.getmtime(file))

    def init(self, info, progress):
        """
        If needed, perform long initialisation tasks here.

        info is a dictionary with useful information.  Currently it contains
        the following values:

          "values": a dict mapping index mnemonics to index numbers

        The progress indicator can be used to report progress.
        """
        pass

    def doc(self):
        """
        Return documentation information for this data source.

        The documentation information is a dictionary with these keys:
          name: the name for this data source
          shortDesc: a short description
          fullDoc: the full description as a chapter in ReST format
        """
        return dict(
            name="Origin",
            shortDesc="Origin information",
            fullDoc="""
            The Origin data source indexes origin information
            It uses the prefix XO
            """)

    def index(self, document, pkg):
        """
        Update the document with the information from this data source.

        document  is the document to update
        pkg       is the python-apt Package object for this package
        """
        ver = pkg.candidate
        if ver is None:
            return
        if not ver.downloadable:
            document.add_term("XOL" + "notdownloadable")
        for origin in ver.origins:
            document.add_term("XOA" + origin.archive)
            document.add_term("XOC" + origin.component)
            document.add_term("XOL" + origin.label)
            document.add_term("XOO" + origin.origin)
            document.add_term("XOS" + origin.site)

        # FIXME: this doesn't really belong in this file, but we can put it in
        #        here until we get a display_name/display_summary plugin which
        #        is being prepared in the experimental-fastlist branch.
        if '-' in pkg.name:
            # we need this to work around xapian oddness
            document.add_term(pkg.name.replace('-', '_'))

    def indexDeb822(self, document, pkg):
        """
        Update the document with the information from this data source.

        This is alternative to index, and it is used when indexing with package
        data taken from a custom Packages file.

        document  is the document to update
        pkg       is the Deb822 object for this package
        """
        # NOTHING here, does not make sense for non-downloadable data
        return


def init():
    """
    Create and return the plugin object.
    """
    return OriginPlugin()
