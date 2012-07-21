# add software-center custom metadata to the index

import apt
import os
import sys
import xapian

sys.path.insert(0, "/usr/share/software-center")
from softwarecenter.enums import (
    CustomKeys,
    XapianValues,
    )
from softwarecenter.db.update import index_name
from softwarecenter.distro import get_distro


class SoftwareCenterMetadataPlugin:

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
        self.indexer = xapian.TermGenerator()

    def doc(self):
        """
        Return documentation information for this data source.

        The documentation information is a dictionary with these keys:
          name: the name for this data source
          shortDesc: a short description
          fullDoc: the full description as a chapter in ReST format
        """
        return dict(
            name="SoftwareCenterMetadata",
            shortDesc="SoftwareCenter meta information",
            fullDoc="""
            Software-center metadata
            It uses the prefixes:
              AA for the Application name
              AP for the Package name
              AC for the categories
              AT to "application" for applications
            It sets the following xapian values from the software-center
            enums:
              XapianValues.ICON
              XapianValues.ICON_NEEDS_DOWNLOAD
              XapianValues.ICON_URL
              XapianValues.SCREENSHOT_URLS
              XapianValues.THUMBNAIL_URL
            """)

    def index(self, document, pkg):
        """
        Update the document with the information from this data source.

        document  is the document to update
        pkg       is the python-apt Package object for this package
        """
        ver = pkg.candidate
        # if there is no version or the AppName custom key is not
        # found we can skip the pkg
        if ver is None or not CustomKeys.APPNAME in ver.record:
            return
        # we want to index the following custom fields:
        #   XB-AppName,
        #   XB-Icon,
        #   XB-Screenshot-Url,
        #   XB-Thumbnail-Url,
        #   XB-Category
        if CustomKeys.APPNAME in ver.record:
            name = ver.record[CustomKeys.APPNAME]
            self.indexer.set_document(document)
            index_name(document, name, self.indexer)
            # we pretend to be an application
            document.add_term("AT" + "application")
            # and we inject a custom component value to indicate "independent"
            document.add_value(XapianValues.ARCHIVE_SECTION, "independent")
        if CustomKeys.ICON in ver.record:
            icon = ver.record[CustomKeys.ICON]
            document.add_value(XapianValues.ICON, icon)
            # calculate the url and add it (but only if there actually is
            # a url)
            try:
                distro = get_distro()
                if distro:
                    base_uri = ver.uri
                    # new python-apt returns None instead of StopIteration
                    if base_uri:
                        url = distro.get_downloadable_icon_url(base_uri, icon)
                        document.add_value(XapianValues.ICON_URL, url)
            except StopIteration:
                pass
        if CustomKeys.SCREENSHOT_URLS in ver.record:
            screenshot_url = ver.record[CustomKeys.SCREENSHOT_URLS]
            document.add_value(XapianValues.SCREENSHOT_URLS, screenshot_url)
        if CustomKeys.THUMBNAIL_URL in ver.record:
            url = ver.record[CustomKeys.THUMBNAIL_URL]
            document.add_value(XapianValues.THUMBNAIL_URL, url)
        if CustomKeys.CATEGORY in ver.record:
            categories_str = ver.record[CustomKeys.CATEGORY]
            for cat in categories_str.split(";"):
                if cat:
                    document.add_term("AC" + cat.lower())

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
    return SoftwareCenterMetadataPlugin()
