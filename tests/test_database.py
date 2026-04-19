import csv
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from database import GameDatabase


class TestGameDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.stdout = io.StringIO()
        with redirect_stdout(self.stdout):
            self.db = GameDatabase(str(self.db_path))
            self.db.init_db()

    def tearDown(self):
        with redirect_stdout(self.stdout):
            self.db.close()
        self.temp_dir.cleanup()

    def test_add_game_returns_same_id_for_existing_product(self):
        first_id = self.db.add_game("pid-1", "Game One", 1000, "JPY", is_base_game=1)
        second_id = self.db.add_game("pid-1", "Game One", 1000, "JPY", is_base_game=1)
        self.assertEqual(first_id, second_id)

    def test_change_detection_updates_only_when_status_changes(self):
        game_id = self.db.add_game("pid-2", "Game Two", 2000, "JPY", is_base_game=1)

        first_change = self.db.update_region_status_with_change_detection(
            game_id, "zh-TW", "available", 500, "TWD", "Game Two TW"
        )
        second_change = self.db.update_region_status_with_change_detection(
            game_id, "zh-TW", "available", 500, "TWD", "Game Two TW"
        )
        third_change = self.db.update_region_status_with_change_detection(
            game_id, "zh-TW", "query-failed", None, None, None
        )

        self.assertTrue(first_change)
        self.assertFalse(second_change)
        self.assertTrue(third_change)

    def test_statistics_include_query_failed(self):
        game_id = self.db.add_game("pid-3", "Game Three", 3000, "JPY", is_base_game=1)
        self.db.update_region_status(game_id, "zh-TW", "query-failed")

        stats = self.db.get_statistics("zh-TW")
        self.assertEqual(stats["query-failed"], 1)

    def test_utc_timestamp_helpers_are_round_trippable(self):
        timestamp = self.db.utc_now_string()
        parsed = self.db.parse_db_timestamp(timestamp)

        self.assertEqual(parsed.strftime("%Y-%m-%d %H:%M:%S"), timestamp)
        self.assertEqual(parsed.tzinfo.utcoffset(parsed).total_seconds(), 0)

    def test_fetch_games_with_regions_returns_grouped_structure(self):
        game_id = self.db.add_game("pid-4", "Game Four", 4500, "JPY", is_base_game=1)
        self.db.update_region_status(game_id, "zh-TW", "available", 1350, "TWD", "Game Four TW")

        games = self.db.fetch_games_with_regions()

        self.assertIn("pid-4", games)
        self.assertEqual(games["pid-4"]["ja_title"], "Game Four")
        self.assertEqual(games["pid-4"]["regions"]["zh-TW"]["status"], "available")
        self.assertEqual(games["pid-4"]["regions"]["zh-TW"]["region_title"], "Game Four TW")

    def test_schema_version_is_recorded_after_init(self):
        self.assertEqual(self.db._get_schema_version(), 3)

    def test_export_csv_respects_mode_and_filter(self):
        base_game_id = self.db.add_game("base-1", "Base Game", 4000, "JPY", is_base_game=1)
        dlc_game_id = self.db.add_game("dlc-1", "DLC Pack", 500, "JPY", is_base_game=0)

        self.db.update_region_status(base_game_id, "zh-TW", "available", 1200, "TWD", "Base Game TW")
        self.db.update_region_status(dlc_game_id, "zh-TW", "query-failed", None, None, None)

        output_file = Path(self.temp_dir.name) / "export.csv"
        with redirect_stdout(self.stdout):
            self.db.export_csv(str(output_file), mode="full", filter_dlc=1)

        with output_file.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["productId"], "base-1")
        self.assertEqual(rows[0]["zh-TW_status"], "available")

        with redirect_stdout(self.stdout):
            self.db.export_csv(str(output_file), mode="full", filter_dlc=0)
        with output_file.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 2)
        statuses = {row["productId"]: row["zh-TW_status"] for row in rows}
        self.assertEqual(statuses["dlc-1"], "query-failed")


if __name__ == "__main__":
    unittest.main()
