import unittest

from dlc_identifier import is_game_base


class TestDlcIdentifier(unittest.TestCase):
    def test_non_game_product_is_filtered_out(self):
        product = {"productKind": "AvatarItem", "title": "Costume Pack", "categories": []}
        self.assertFalse(is_game_base(product))

    def test_bundle_keyword_wins_over_dlc_keyword(self):
        product = {
            "productKind": "Game",
            "title": "Mega Bundle Season Pass Edition",
            "categories": [],
        }
        self.assertTrue(is_game_base(product))

    def test_dlc_keyword_marks_non_base_game(self):
        product = {
            "productKind": "Game",
            "title": "Cool Game Expansion Pack",
            "categories": ["Add-on"],
        }
        self.assertFalse(is_game_base(product))


if __name__ == "__main__":
    unittest.main()
