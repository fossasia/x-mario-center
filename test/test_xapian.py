#!/usr/bin/python

import unittest
import os
import xapian

from testutils import setup_test_env
setup_test_env()

from softwarecenter.enums import XapianValues
from softwarecenter.db.update import rebuild_database

class testXapian(unittest.TestCase):
    """ tests the xapian database """

    def setUp(self):
        # FIXME: create a fixture DB instead of using the system one
        # but for now that does not matter that much, only if we
        # call open the db is actually read and the path checked
        pathname = "../data/xapian"
        if not os.listdir(pathname):
            rebuild_database(pathname)
        self.xapiandb = xapian.Database(pathname)
        self.enquire = xapian.Enquire(self.xapiandb)

    def test_exact_query(self):
        query = xapian.Query("APsoftware-center")
        self.enquire.set_query(query)
        matches = self.enquire.get_mset(0, 100)
        self.assertEqual(len(matches), 1)

    def test_search_term(self):
        search_term = "apt"
        parser = xapian.QueryParser()
        query = parser.parse_query(search_term)
        self.enquire.set_query(query)
        matches = self.enquire.get_mset(0, 100)
        self.assertTrue(len(matches) > 5)

    def test_category_query(self):
        query = xapian.Query("ACaudiovideo")
        self.enquire.set_query(query)
        matches = self.enquire.get_mset(0, 100)
        self.assertTrue(len(matches) > 5)

    def test_mime_query(self):
        query = xapian.Query("AMtext/html")
        self.enquire.set_query(query)
        matches = self.enquire.get_mset(0, 100)
        self.assertTrue(len(matches) > 5)
        pkgs = set()
        for match in matches:
            doc = match.document
            pkgs.add(doc.get_value(XapianValues.PKGNAME))
        self.assertTrue("firefox" in pkgs)

    def test_eset(self):
        """ test finding "similar" items than the ones found before """
        query = xapian.Query("foo")
        self.enquire.set_query(query)
        # this yields very few results
        matches = self.enquire.get_mset(0, 100)
        # create a relevance set from the query
        rset = xapian.RSet()
        #print "original finds: "
        for match in matches:
            #print match.document.get_data()
            rset.add_document(match.docid)
        # and use that to get a extended set
        eset = self.enquire.get_eset(20, rset)
        #print eset
        # build a query from the eset
        eset_query = xapian.Query(xapian.Query.OP_OR, [e.term for e in eset])
        self.enquire.set_query(eset_query)
        # ensure we have more results now than before
        eset_matches = self.enquire.get_mset(0, 100)
        self.assertTrue(len(matches) < len(eset_matches))
        #print "expanded finds: "
        #for match in eset_matches:
        #    print match.document.get_data()

    def test_spelling_correction(self):
        """ test automatic suggestions for spelling corrections """
        parser = xapian.QueryParser()
        parser.set_database(self.xapiandb)
        # mispelled search term
        search_term = "corect"
        query = parser.parse_query(
            search_term, xapian.QueryParser.FLAG_SPELLING_CORRECTION)
        self.enquire.set_query(query)
        matches = self.enquire.get_mset(0, 100)
        self.assertEqual(len(matches), 0)
        corrected_query_string = parser.get_corrected_query_string()
        self.assertEqual(corrected_query_string, "correct")
        # set the corrected one
        query = parser.parse_query(corrected_query_string)
        self.enquire.set_query(query)
        matches = self.enquire.get_mset(0, 100)
        #print len(matches)
        self.assertTrue(len(matches) > 0)

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
