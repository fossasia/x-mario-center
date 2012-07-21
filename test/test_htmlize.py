#!/usr/bin/python

from testutils import setup_test_env
setup_test_env()
from softwarecenter.utils import htmlize_package_description

#file-roller
d1 = """
File-roller is an archive manager for the GNOME environment. It allows you to:

* Create and modify archives.
* View the content of an archive.
* View a file contained in an archive.
* Extract files from the archive.
File-roller supports the following formats:
* Tar (.tar) archives, including those compressed with
  gzip (.tar.gz, .tgz), bzip (.tar.bz, .tbz), bzip2 (.tar.bz2, .tbz2),
  compress (.tar.Z, .taz), lzip (.tar.lz, .tlz), lzop (.tar.lzo, .tzo),
  lzma (.tar.lzma) and xz (.tar.xz)
* Zip archives (.zip)
* Jar archives (.jar, .ear, .war)
* 7z archives (.7z)
* iso9660 CD images (.iso)
* Lha archives (.lzh)
* Single files compressed with gzip (.gz), bzip (.bz), bzip2 (.bz2),
  compress (.Z), lzip (.lz), lzop (.lzo), lzma (.lzma) and xz (.xz)
File-roller doesn't perform archive operations by itself, but relies on standard tools for this.
"""

#drgeo
d2 = """
This is the Gtk interactive geometry software. It allows one
to create geometric figure plus the interactive manipulation of such
figure in respect with their geometric constraints. It is usable in
teaching situation with students from primary or secondary level.

Dr. Geo comes with a complete set of tools arranged
in different categories:

 * points
 * lines
 * geometric transformations
 * numeric function
 * macro-construction
 * DGS object - Dr. Geo Guile Script
 * DSF - Dr Geo Scheme Figure, it is interactive figure defined in
   a file and evaluated with the embedded Scheme interpretor, awesome!
 * Export facilities in the LaTeX and EPS formats

Several figures and macro-constructions examples are available
in the /usr/share/drgeo/examples folder.

More information about Dr. Geo can be found at
its web site http://www.gnu.org/software/dr_geo/dr_geo.html

Installing the drgeo-doc package is also encouraged to get
more of Dr. Geo.
"""

# totem
d3 = """
Totem is a simple yet featureful media player for GNOME which can read
a large number of file formats. It features :
.
   * Shoutcast, m3u, asx, SMIL and ra playlists support
   * DVD (with menus), VCD and Digital CD (with CDDB) playback
   * TV-Out configuration with optional resolution switching
   * 4.0, 5.0, 5.1 and stereo audio output
   * Full-screen mode (move your mouse and you get nice controls) with
     Xinerama, dual-head and RandR support
   * Aspect ratio toggling, scaling based on the video's original size
   * Full keyboard control
   * Simple playlist with repeat mode and saving feature
   * GNOME, Nautilus and GIO integration
   * Screenshot of the current movie
   * Brightness and Contrast control
   * Visualisation plugin when playing audio-only files
   * Video thumbnailer for nautilus
   * Nautilus properties page
   * Works on remote displays
   * DVD, VCD and OGG/OGM subtitles with automatic language selection
   * Extensible with plugins
"""

import lxml.html
import lxml.etree
import unittest

class TestHtmlize(unittest.TestCase):

    def test_htmlize(self):
        for decr in [d1, d2, d3]:
            html_descr = htmlize_package_description(decr)
            #print html_descr
            #element = lxml.html.document_fromstring(html_descr)
            star_count = decr.count("*")
            root = lxml.etree.XML("<html>%s</html>" % html_descr)
            li_count = len(root.findall(".//li"))
            self.assertEqual(star_count, li_count)

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()

