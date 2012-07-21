#!/usr/bin/python

import unittest
import xapian
from mock import patch

from testutils import setup_test_env
setup_test_env()

from softwarecenter.db.categories import (
    CategoriesParser,
    RecommendedForYouCategory,
    get_category_by_name, get_query_for_category)
from softwarecenter.testutils import (get_test_db,
                                      make_recommender_agent_recommend_me_dict)

class TestCategories(unittest.TestCase):
    
    def setUp(self):
        self.db = get_test_db()

    @patch('softwarecenter.db.categories.RecommenderAgent')
    def test_recommends_category(self, AgentMockCls):
        # ensure we use the same instance in test and code
        agent_mock_instance = AgentMockCls.return_value
        recommends_cat = RecommendedForYouCategory()
        docids = recommends_cat.get_documents(self.db)
        self.assertEqual(docids, [])
        self.assertTrue(agent_mock_instance.query_recommend_me.called)
        # ensure we get a query when the callback is called
        recommends_cat._recommend_me_result(
                                None, 
                                make_recommender_agent_recommend_me_dict())
        self.assertNotEqual(recommends_cat.get_documents(self.db), [])

    @patch('softwarecenter.db.categories.RecommenderAgent')
    def test_recommends_in_category_category(self, AgentMockCls):
        # ensure we use the same instance in test and code
        parser = CategoriesParser(self.db)
        cats = parser.parse_applications_menu("./data")
        # "2" is a multimedia query
        #     see ./test/data/desktop/software-center.menu
        recommends_cat = RecommendedForYouCategory(cats[2])
        # ensure we get a query when the callback is called
        recommends_cat._recommend_me_result(
                                None, 
                                make_recommender_agent_recommend_me_dict())
        recommendations_in_cat = recommends_cat.get_documents(self.db)
        print recommendations_in_cat
        self.assertNotEqual(recommendations_in_cat, [])

    def test_get_query(self):
        query = get_query_for_category(self.db, "Education")
        self.assertNotEqual(query, None)

class TestCatParsing(unittest.TestCase):
    """ tests the "where is it in the menu" code """

    def setUp(self):
        self.db = get_test_db()
        parser = CategoriesParser(self.db)
        self.cats = parser.parse_applications_menu(
            '/usr/share/app-install')

    def test_get_cat_by_name(self):
        cat = get_category_by_name(self.cats, 'Games')
        self.assertEqual(cat.untranslated_name, 'Games')
        cat = get_category_by_name(self.cats, 'Featured')
        self.assertEqual(cat.untranslated_name, 'Featured')

    def test_cat_has_flags(self):
        cat = get_category_by_name(self.cats, 'Featured')
        self.assertEqual(cat.flags[0], 'carousel-only')

    def test_get_documents(self):
        cat = get_category_by_name(self.cats, 'Featured')
        docs = cat.get_documents(self.db)
        self.assertNotEqual(docs, [])
        for doc in docs:
            self.assertEqual(type(doc), xapian.Document)

class TestCategoryTemplates(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = get_test_db()
        cls.parser = CategoriesParser(cls.db)
        cls.cats = cls.parser.parse_applications_menu("./data/")

    def test_category_debtags(self):
        cat = get_category_by_name(self.cats, 'Debtag')
        self.assertEqual(
            "%s" % cat.query, 
            "Xapian::Query((<alldocuments> AND XTregion::de))")

    @patch("softwarecenter.db.categories.get_region_cached")
    def test_category_dynamic_categories(self, mock_get_region_cached):
        mock_get_region_cached.return_value = { "countrycode" : "us", 
                                              }
        parser = CategoriesParser(self.db)
        cats = parser.parse_applications_menu("./data/")
        cat = get_category_by_name(cats, 'Dynamic')
        self.assertEqual(
            "%s" % cat.query, 
            "Xapian::Query((<alldocuments> AND XTregion::us))")


if __name__ == "__main__":
    #import logging
    #logging.basicConfig(level=logging.DEBUG)
    unittest.main()
