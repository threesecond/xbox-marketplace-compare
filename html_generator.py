#!/usr/bin/env python3
"""
Xbox 遊戲對比工具 - HTML 報表生成器
產生可視化報表
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from jinja2 import Template


logger = logging.getLogger(__name__)
TEMPLATE_PATH = Path(__file__).with_name("templates") / "report.html"


class HTMLReporter:
    """HTML 報表生成器"""

    STATUS_LABELS = {
        "available": "可購買",
        "region-locked": "地區限定",
        "delisted": "已下架",
        "query-failed": "查詢失敗",
    }

    def __init__(self, template_path: Path = TEMPLATE_PATH):
        """初始化並載入模板檔。"""
        self.template_path = template_path
        self.template = Template(self.template_path.read_text(encoding="utf-8"))

    def generate_report(
        self,
        games_data: List[Dict],
        stats: Dict,
        output_file: str = "report.html",
        show_charts: bool = True,
    ):
        """
        生成 HTML 報表

        Args:
            games_data: 遊戲資料清單
            stats: 統計資訊
            output_file: 輸出檔案路徑
            show_charts: 是否顯示圖表
        """
        sorted_games = sorted(
            games_data,
            key=lambda x: (
                x["status"] == "available",
                x["ja_title"],
            ),
        )

        html_content = self.template.render(
            generated_time=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z"),
            games=sorted_games,
            stats={
                "available": stats.get("available", 0),
                "region_locked": stats.get("region_locked", 0),
                "delisted": stats.get("delisted", 0),
                "query_failed": stats.get("query_failed", 0),
                "total": stats.get("total", 0),
            },
            status_labels=self.STATUS_LABELS,
            show_charts=show_charts,
        )

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.info(f"[OK] HTML 報表已生成: {output_file}")
            return True
        except Exception as e:
            logger.error(f"[ERROR] 生成 HTML 報表失敗: {e}")
            return False

    @staticmethod
    def prepare_games_data(db_results: Dict, target_locale: str = "zh-TW") -> List[Dict]:
        """
        從資料庫結果準備遊戲資料
        """
        games = []

        for product_id, game_info in db_results.items():
            tw_info = game_info.get("regions", {}).get(target_locale, {})

            games.append(
                {
                    "product_id": product_id,
                    "ja_title": game_info.get("ja_title", "Unknown"),
                    "ja_price": game_info.get("ja_price"),
                    "tw_price": tw_info.get("price"),
                    "status": tw_info.get("status", "delisted"),
                    "last_checked": tw_info.get("last_checked_date", ""),
                    "tw_url": f"https://www.xbox.com/zh-tw/games/store/{game_info.get('ja_title', product_id)}/{product_id}",
                }
            )

        return games


if __name__ == "__main__":
    reporter = HTMLReporter()

    sample_games = [
        {
            "product_id": "123456",
            "ja_title": "Elden Ring",
            "ja_price": 8000,
            "ja_url": "https://www.xbox.com/ja-jp/games/store/Elden%20Ring/123456",
            "tw_title": None,
            "tw_price": 2580,
            "tw_url": "https://www.xbox.com/zh-tw/games/store/Elden%20Ring/123456",
            "status": "available",
            "last_checked": "2026-04-08 10:30",
        },
        {
            "product_id": "123457",
            "ja_title": "Final Fantasy XVI",
            "ja_price": 9000,
            "ja_url": "https://www.xbox.com/ja-jp/games/store/Final%20Fantasy%20XVI/123457",
            "tw_title": None,
            "tw_price": None,
            "tw_url": "https://www.xbox.com/zh-tw/games/store/Final%20Fantasy%20XVI/123457",
            "status": "region-locked",
            "last_checked": "2026-04-08 10:30",
        },
        {
            "product_id": "123458",
            "ja_title": "某限定遊戲",
            "ja_price": 5000,
            "ja_url": "https://www.xbox.com/ja-jp/games/store/%E6%9F%90%E9%99%90%E5%AE%9A%E9%81%8A%E6%88%B2/123458",
            "tw_title": None,
            "tw_price": None,
            "tw_url": "https://www.xbox.com/zh-tw/games/store/%E6%9F%90%E9%99%90%E5%AE%9A%E9%81%8A%E6%88%B2/123458",
            "status": "delisted",
            "last_checked": "2026-04-07",
        },
    ]

    sample_stats = {
        "available": 100,
        "region_locked": 50,
        "delisted": 10,
        "query_failed": 2,
        "total": 162,
    }

    reporter.generate_report(
        games_data=sample_games,
        stats=sample_stats,
        output_file="report_test.html",
    )
