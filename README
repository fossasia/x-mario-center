= User notes =

The software-center application aims to make the software handling on
the computer easy and consistent.

= Developer notes =

All non UI code must come with tests in the test/ subdirectoy.

To setup your development environment, you'll need to ensure the following
extra packages are installed:

sudo apt-get install xvfb python-coverage python-mock python-aptdaemon.test \
     python-qt4 python-unittest2 python-lxml pep8
sudo apt-get build-dep software-center

You can then run tests with:

cd test;make

You can run a developer instance with:

python setup.py build
./software-center

The initial launch of this will take a bit as it will build a private
search database but this is only needed once.

== query parser ==

The query parser understands :
 "pkg:2vcard", "mime:text/html", "section:web", "origin:main"
prefixes.

== aptdaemon ==
 * the dbus limits for the system bus are rather low, this means that
   adding  <limit name="max_match_rules_per_connection">512</limit>
   and using something bigger than 512 is a good idea

== environment ==

The following environment variables are supported:

SOFTWARE_CENTER_AGENT_HOST - an alternative host to query for pay software
SOFTWARE_CENTER_REVIEWS_HOST - an alternative host for the ratings&reviews
SOFTWARE_CENTER_DEBUG_HTTP - enable httplib2 debuging
SOFTWARE_CENTER_IPSUM_REVIEWS - generate random reviews
SOFTWARE_CENTER_FAKE_REVIEW_API - use a fake server for all review network operations
SOFTWARE_CENTER_GWIBBER_MOCK_USERS=2 - use mock gwibber service
SOFTWARE_CENTER_AGENT_INCLUDE_QA - show not yet QA apps available from the agent
SOFTWARE_CENTER_NET_DISCONNECTED - make software-center's netstatus module believe network manager is in a disconnected state
SOFTWARE_CENTER_WEBLIVE_HOST - overwrite default weblive server
SOFTWARE_CENTER_DISTRO_CODENAME - overwrite "lsb_release -c -s" output
SOFTWARE_CENTER_ARCHITECTURE - overwrite the current architecture
SOFTWARE_CENTER_NO_SC_AGENT - disable the software-center-agent
SOFTWARE_CENTER_DISABLE_SPAWN_HELPER - disable everything that is run via the "SpawnHelper", i.e. recommender-agent, software-center-agent, reviews
SOFTWARE_CENTER_DEBUG_TABS - show notebook tabs for debugging
SOFTWARE_CENTER_FORCE_DISABLE_CERTS_CHECK - disables certificates checking in webkit views (for use in test environments)
SOFTWARE_CENTER_FORCE_NON_SSL - disable SSL (for use in test environments)

== applications.menu ==

The menu file parser understands:
Category, And, Or, Not

The following additional XML filters are definied:
SCType - e.g. "Applicatin"
SCChannel - e.g. "lucid-partner"
SCSection - e.g. "net"
SCPkgname - e.g. "gimp"

Additional .menu files can be added in:
/usr/share/app-install/menu.d
that software-center will read and parse.

== XAPIAN ==

The following special prefixes are used:

AA - application name (Abiword)
AP - package name (abiword)
AS - archive pocket (main)
AE - archive section (mail, base, ...)
AC - category (AudioVideo)
AM - MimeType (application/x-ogg)
AT - type (Application)
AH - channel


The following values are used:

XAPIAN_VALUE_PKGNAME - pkgname
XAPIAN_VALUE_ICON - icon name
XAPIAN_VALUE_GETTEXT_DOMAIN - gettext domain
XAPIAN_VALUE_ARCHIVE_SECTION - archive section (main, restricted, universe, multiverse)
XAPIAN_VALUE_ARCHIVE_ARCH - architectures (seperated with ",", e.g. i386,amd64) - may be empty
XAPIAN_VALUE_POPCON - popcon data
XAPIAN_VALUE_SUMMARY - summary text
XAPIAN_VALUE_DESKTOP_FILE - the desktop file that the information comes from
XAPIAN_VALUE_PRICE - the price (if its a for-pay app)
XAPIAN_VALUE_ARCHIVE_CHANNEL - channel (third party)
XAPIAN_VALUE_ARCHIVE_PPA - the PPA name that the application is in
XAPIAN_VALUE_ARCHIVE_DEBLINE - a deb line for the sources.list to access the given app
XAPIAN_VALUE_ARCHIVE_SIGNING_KEYID - signing key id for the repository
XAPIAN_VALUE_PURCHASED_DATE - the data a for-pay app was purchased (only available after the software-center-agent server was queried)
XAPIAN_VALUE_SCREENSHOT_URLS - a (optional) list of "," seperated screenshot urls that overrides the default
XAPIAN_VALUE_ICON_NEEDS_DOWNLOAD - icon needs to be fetched
XAPIAN_VALUE_THUMBNAIL_URL - thumbnail url

