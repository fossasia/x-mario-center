#!/usr/bin/python

import unittest

from mock import Mock

from testutils import setup_test_env
setup_test_env()

from softwarecenter.ui.gtk3.session.navhistory import (
    NavigationHistory, NavigationItem)
from softwarecenter.ui.gtk3.panes.softwarepane import DisplayState
from softwarecenter.ui.gtk3.panes.availablepane import AvailablePane
from softwarecenter.db.categories import Category


class MockButton():

    def __init__(self):
        self.sensitive = True

    def set_sensitive(self, val):
        self.sensitive = val

    def has_focus(self):
        return False

class TestNavhistory(unittest.TestCase):
    """ basic tests for navigation history """

    def _get_boring_stuff(self):
        # mock button
        back_forward_btn = Mock()
        back_forward_btn.right = MockButton()
        back_forward_btn.left = MockButton()
        # mock options
        options = Mock()
        options.display_navlog = False
        # create navhistory
        navhistory = NavigationHistory(back_forward_btn, options)
        # mock view manager
        view_manager = Mock()
        view_manager.navhistory = navhistory
        # create a NavHistory 
        pane = Mock()
        pane.pane_name = "pane_name"
        return back_forward_btn, options, navhistory, view_manager, pane

    def test_nav_history(self):
        (back_forward_btn, options, navhistory, view_manager, pane) = self._get_boring_stuff()

        # first we must initialize the NavHistory with the equivalent of the initial category view
        item = NavigationItem(view_manager, pane, "cat_page", "cat_state", "cb")
        navhistory.append(item)
        item = NavigationItem(view_manager, pane, "a_page", "a_state", "cb")
        # add a new item and ensure that the button is now sensitive
        navhistory.append(item)
        self.assertFalse(back_forward_btn.right.sensitive)
        self.assertTrue(back_forward_btn.left.sensitive)
        # navigate back
        navhistory.nav_back()
        self.assertTrue(back_forward_btn.right.sensitive)
        self.assertFalse(back_forward_btn.left.sensitive)
        # navigate forward
        navhistory.nav_forward()
        self.assertFalse(back_forward_btn.right.sensitive)
        self.assertTrue(back_forward_btn.left.sensitive)
        # and reset
        navhistory.reset()
        self.assertFalse(back_forward_btn.right.sensitive)
        self.assertFalse(back_forward_btn.left.sensitive)
        self.assertEqual(len(navhistory.stack), 0)

    def test_navhistory_lobby_search_then_clear(self):
        (back_forward_btn, options, navhistory, view_manager, pane) = self._get_boring_stuff()

        # first we must initialize the NavHistory with the equivalent of the initial category view
        # NnavigationItem(view_manager, pane, page, view_state, callback)
        item = NavigationItem(view_manager, pane, AvailablePane.Pages.LOBBY, DisplayState(), "cb")
        navhistory.append(item)

        # append equivalent of a typed search
        dstate = DisplayState()
        dstate.search_term = "chess"
        item = NavigationItem(view_manager, pane, AvailablePane.Pages.LIST, dstate, "cb")
        navhistory.append(item)
        self.assertTrue(back_forward_btn.left.sensitive)
        self.assertFalse(back_forward_btn.right.sensitive)

        # simulate the user clearing the search entry
        dstate = DisplayState()
        dstate.search_term = ""
        item = NavigationItem(view_manager, pane, AvailablePane.Pages.LOBBY, dstate, "cb")
        navhistory.append(item)
        self.assertFalse(back_forward_btn.left.sensitive)
        self.assertFalse(back_forward_btn.right.sensitive)

    def test_navhistory_cat_search_then_clear(self):
        (back_forward_btn, options, navhistory, view_manager, pane) = self._get_boring_stuff()

        # first we must initialize the NavHistory with the equivalent of the initial category view
        # NnavigationItem(view_manager, pane, page, view_state, callback)
        item = NavigationItem(view_manager, pane, AvailablePane.Pages.LOBBY, DisplayState(), "cb")
        navhistory.append(item)

        # simulate Accessories category LIST
        dstate = DisplayState()
        dstate.category = Category('accessories', 'Accessories', 'iconname', 'query')
        item = NavigationItem(view_manager, pane, AvailablePane.Pages.LIST, dstate, "cb")
        navhistory.append(item)
        # displaying the Accessories LIST
        self.assertTrue(len(navhistory.stack) == 2)
        self.assertTrue(back_forward_btn.left.sensitive)
        self.assertFalse(back_forward_btn.right.sensitive)

        # simulate a user search
        dstate = DisplayState()
        dstate.category = Category('accessories', 'Accessories', 'iconname', 'query')
        dstate.search_term = "chess"
        item = NavigationItem(view_manager, pane, AvailablePane.Pages.LIST, dstate, "cb")
        navhistory.append(item)
        # should be displaying the search results for Accessories
        self.assertTrue(back_forward_btn.left.sensitive)
        self.assertFalse(back_forward_btn.right.sensitive)
        self.assertTrue(len(navhistory.stack) == 3)

        # simulate a user clearing the search
        dstate = DisplayState()
        dstate.category = Category('accessories', 'Accessories', 'iconname', 'query')
        dstate.search_term = ""
        item = NavigationItem(view_manager, pane, AvailablePane.Pages.LIST, dstate, "cb")
        navhistory.append(item)
        self.assertTrue(back_forward_btn.left.sensitive)
        self.assertFalse(back_forward_btn.right.sensitive)
        # should be returned to the Accessories list view
        self.assertTrue(len(navhistory.stack) == 2)


    def test_navhistory_subcat_search_then_clear(self):
        (back_forward_btn, options, navhistory, view_manager, pane) = self._get_boring_stuff()

        # first we must initialize the NavHistory with the equivalent of the initial category view
        # NnavigationItem(view_manager, pane, page, view_state, callback)
        item = NavigationItem(view_manager, pane, AvailablePane.Pages.LOBBY, DisplayState(), "cb")
        navhistory.append(item)

        board_games = Category('board-games', 'Board Games', 'iconname', 'query')
        games = Category('games', 'Games', 'iconname', 'query', subcategories=[board_games,])

        # simulate Games category (with subcats)
        dstate = DisplayState()

        dstate.category = games
        item = NavigationItem(view_manager, pane, AvailablePane.Pages.SUBCATEGORY, dstate, "cb")
        navhistory.append(item)

        # displaying the Games SUBCATEGORY
        self.assertTrue(len(navhistory.stack) == 2)
        self.assertTrue(back_forward_btn.left.sensitive)
        self.assertFalse(back_forward_btn.right.sensitive)

        # simulate Board Games subcategory LIST
        dstate = DisplayState()
        dstate.category = games
        dstate.subcategory = board_games
        item = NavigationItem(view_manager, pane, AvailablePane.Pages.LIST, dstate, "cb")
        navhistory.append(item)

        # displaying the Accessories LIST
        self.assertTrue(len(navhistory.stack) == 3)
        self.assertTrue(back_forward_btn.left.sensitive)
        self.assertFalse(back_forward_btn.right.sensitive)

        # simulate a user search within subcat
        dstate = DisplayState()
        dstate.category = games
        dstate.subcategory = board_games
        dstate.search_term = "chess"
        item = NavigationItem(view_manager, pane, AvailablePane.Pages.LIST, dstate, "cb")
        navhistory.append(item)

        # should be displaying the search results for Accessories
        self.assertTrue(back_forward_btn.left.sensitive)
        self.assertFalse(back_forward_btn.right.sensitive)
        self.assertTrue(len(navhistory.stack) == 4)

        # simulate a user clearing the search
        dstate = DisplayState()
        dstate.category = games
        dstate.subcategory = board_games
        dstate.search_term = ""
        item = NavigationItem(view_manager, pane, AvailablePane.Pages.LIST, dstate, "cb")
        navhistory.append(item)

        # should be returned to the Board Games LIST view
        self.assertTrue(back_forward_btn.left.sensitive)
        self.assertFalse(back_forward_btn.right.sensitive)
        self.assertTrue(len(navhistory.stack) == 3)

        # verify that navhistory item 2 is LIST page
        self.assertTrue(navhistory.stack[2].page == AvailablePane.Pages.LIST)
        # verify that navhistory item 1 is SUBCATEGORY page
        self.assertTrue(navhistory.stack[1].page == AvailablePane.Pages.SUBCATEGORY)
        # verify that navhistory item 0 is LOBBY page
        self.assertTrue(navhistory.stack[0].page == AvailablePane.Pages.LOBBY)



if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
