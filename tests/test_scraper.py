import unittest

from scraper import XboxScraper


class TestScraperStatusMapping(unittest.TestCase):
    def test_determine_status_available(self):
        self.assertEqual(
            XboxScraper.determine_status({"found": True, "purchaseable": True}),
            "available",
        )

    def test_determine_status_region_locked(self):
        self.assertEqual(
            XboxScraper.determine_status({"found": True, "purchaseable": False}),
            "region-locked",
        )

    def test_determine_status_delisted(self):
        self.assertEqual(
            XboxScraper.determine_status({"found": False, "purchaseable": False}),
            "delisted",
        )

    def test_determine_status_query_failed(self):
        self.assertEqual(
            XboxScraper.determine_status({"query_failed": True}),
            "query-failed",
        )


if __name__ == "__main__":
    unittest.main()
