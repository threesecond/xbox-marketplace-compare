#!/usr/bin/env python3
"""
Xbox 商店遊戲對比工具 - V3 版本
支持增量更新、資料持久化、HTML 報表、DLC 過濾
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict

from database import GameDatabase
from html_generator import HTMLReporter
from scraper import XboxScraper

# ===== 設定 =====
SOURCE_LOCALE = "ja-JP"
TARGET_LOCALE = "zh-TW"
OUTPUT_CSV = "jp_only_games.csv"
OUTPUT_HTML = "report.html"
DB_PATH = "games.db"
MAX_PAGES = 2  # 0 = 不限制頁數，測試時可設置為較小的值（如 5 或 10）

# 掃描模式
# 0: 增量模式 - JP 找新遊戲, TW 只檢查 delisted/region-locked (快速，日常用)
# 1: 全量驗證 - JP/TW 都掃描，只寫入有變動的 (完整，定期用)
BROWSE_ALL = 1

# 多排序搜尋開關
# 0: 只用預設排序（快速）
# 1: 使用 5 種排序方式提高涵蓋率（慢但完整）
MULTI_SORT = 0

# DLC 過濾開關
# 1: 只統計遊戲本體（性能優化模式）
# 0: 統計 DLC 與所有其他產品（完整模式）
FILTER_DLC = 1

# 需要從 DevTools 複製
AUTH_TOKEN = ""  # 請在此輸入您的 XBL3.0 token（運行前請填入，commit 前請清空）

REQUEST_DELAY = 1.5
DELISTED_RECHECK_DAYS = 7
DELISTED_CONFIRM_THRESHOLD = 3


class XboxMarketplaceComparerV3:
    """V3 主程序類"""

    def __init__(
        self,
        auth_token: str,
        db_path: str = DB_PATH,
        request_delay: float = REQUEST_DELAY,
        filter_dlc: int = FILTER_DLC,
    ):
        """初始化"""
        self.auth_token = auth_token
        self.db_path = db_path
        self.request_delay = request_delay
        self.filter_dlc = filter_dlc
        self.db = None
        self.scraper = None

    def _validate_auth_token(self) -> bool:
        """驗證 auth token"""
        if not self.auth_token:
            print("❌ 錯誤：AUTH_TOKEN 未設定")
            print("\n請按以下步驟設定：")
            print("1. 登入 Xbox 帳號")
            print("2. 訪問 https://www.xbox.com/ja-JP/games/browse?orderby=Title+Asc")
            print("3. 打開 Chrome DevTools (F12)")
            print("4. 進入 Network 標籤")
            print("5. 找到 browse?locale=ja-JP 的 POST 請求")
            print("6. 右鍵 → Copy → Copy as cURL")
            print("7. 複製 Authorization header 的 token 值")
            print('8. 貼到腳本頂部的 AUTH_TOKEN = "..."')
            return False
        return True

    def initialize_db(self) -> bool:
        """初始化資料庫"""
        try:
            self.db = GameDatabase(self.db_path)

            # 檢查是否首次運行或資料庫損壞
            if not Path(self.db_path).exists() or not self.db._table_exists("games"):
                print("\n🆕 首次運行或資料庫損壞，建立資料庫...")
                self.db.init_db()
            else:
                summary = self.db.get_summary()
                print(f"\n📊 資料庫已存在：{summary['total_games']} 款遊戲")
                print(f"   地區資訊：{summary['region_counts']}")

            return True
        except Exception as e:
            print(f"❌ 資料庫初始化失敗：{e}")
            return False

    def initialize_scraper(self) -> bool:
        """初始化爬蟲"""
        try:
            self.scraper = XboxScraper(
                auth_token=self.auth_token,
                request_delay=self.request_delay,
                filter_dlc=self.filter_dlc,
            )
            return True
        except Exception as e:
            print(f"❌ 爬蟲初始化失敗：{e}")
            return False

    def run_incremental_update(
        self, browse_all: int = 0, multi_sort: int = 0, max_pages: int = None
    ) -> bool:
        """
        執行增量更新或全量掃描流程

        Args:
            browse_all: 掃描模式
                - 0: 增量模式（推薦日常使用）
                    - JP: 掃描遊戲找新遊戲
                    - TW: 只重檢 delisted/region-locked 遊戲
                    - 速度快，適合日常運行
                - 1: 全量驗證模式（推薦週期性使用）
                    - JP: 掃描所有遊戲
                    - TW: 掃描所有遊戲
                    - 只寫入有狀態變動的記錄
                    - 速度較慢，適合完整驗證
            multi_sort: 多排序搜尋開關
                - 0: 只用預設排序（快速）
                - 1: 使用 5 種排序方式提高涵蓋率（慢但完整）
            max_pages: 最多抓取幾頁（測試用）

        Returns:
            是否成功
        """
        print("\n" + "=" * 60)
        print("🎮 Xbox 商店遊戲對比工具 V3")
        print("=" * 60)
        print(f"源地區：{SOURCE_LOCALE}")
        print(f"目標地區：{TARGET_LOCALE}")
        print(f"資料庫：{self.db_path}")
        print(
            f"掃描模式：{'全量驗證 (browse_all=1)' if browse_all else '增量更新 (browse_all=0)'}"
        )
        print(
            f"DLC 過濾：{'只統計遊戲本體 (filter_dlc=1)' if self.filter_dlc else '統計所有產品 (filter_dlc=0)'}"
        )

        # 檢查首次運行邏輯
        existing_games = self.db.get_existing_games()
        if len(existing_games) == 0 and browse_all == 0:
            print("\n❌ 錯誤：資料庫為空，不能使用增量模式 (browse_all=0)")
            print("   建議：")
            print("   1. 使用全量掃描：--browse-all 1")
            print("   2. 或者清空資料庫後重新運行")
            return False

        # ===== Phase 1: 爬取/掃描源地區遊戲 =====
        print(f"\n【Phase 1】爬取 {SOURCE_LOCALE} 遊戲清單")

        if browse_all == 0:
            # 增量模式：用配置的排序方式找新遊戲
            print(f"已存在記錄：{len(existing_games)} 款")
            result = self.scraper.fetch_all_games_with_multiple_sorts(
                SOURCE_LOCALE,
                max_pages=max_pages,
                skip_existing=existing_games if len(existing_games) > 0 else None,
                multi_sort=bool(multi_sort),
            )
            source_games = result["games"]
            print(f"✅ 新增遊戲：{len(source_games)} 款")
        else:
            # 全量模式：用配置的排序方式掃描所有遊戲
            result = self.scraper.fetch_all_games_with_multiple_sorts(
                SOURCE_LOCALE,
                max_pages=max_pages,
                skip_existing=None,  # 不跳過任何遊戲
                multi_sort=bool(multi_sort),
            )
            source_games = result["games"]
            print(f"✅ 掃描完成：{len(source_games)} 款遊戲")

        if not source_games:
            print("❌ 無法抓取源地區遊戲")
            return False

        # ===== Phase 2: 檢查目標地區狀態 =====
        print(f"\n【Phase 2】檢查 {TARGET_LOCALE} 地區狀態")

        if browse_all == 0:
            # 增量模式：只重檢 delisted/region-locked 的遊戲，並使用 V3 批量查詢
            games_to_recheck = self.db.get_delisted_or_regionlocked_games(TARGET_LOCALE)

            if not games_to_recheck:
                print("   沒有需要重檢的遊戲（所有遊戲狀態都是 available）")
                target_games = {}
            else:
                print(
                    f"   需要重檢：{len(games_to_recheck)} 款 delisted/region-locked 遊戲"
                )

                # 構建要檢查的遊戲字典
                games_dict = {}
                for game_id, product_id, ja_title, is_base_game_db in games_to_recheck:
                    games_dict[product_id] = {
                        "title": ja_title,
                        "price": 0,
                        "currency": "Unknown",
                        "slug": "",
                        "is_base_game": bool(is_base_game_db),
                    }

                # V3 批量查詢：直接針對 ID 清單點名
                target_games = self.scraper.check_target_games_v3(
                    games_dict, TARGET_LOCALE
                )
        else:
            # 全量模式：V3 批量查詢
            target_games = self.scraper.check_target_games_v3(
                source_games, TARGET_LOCALE
            )

        # ===== Phase 3: 寫入資料庫 =====
        print("\n【Phase 3】更新資料庫")

        games_added = 0
        games_changed = 0

        for product_id, source_info in source_games.items():
            # 新增或更新遊戲
            is_base_game = source_info.get("is_base_game", True)
            game_id = self.db.add_game(
                product_id=product_id,
                ja_title=source_info["title"],
                ja_price=source_info["price"],
                ja_currency=source_info["currency"],
                en_title=None,  # TODO: 從 API 或爬蟲取得
                is_base_game=int(is_base_game),
            )

            if game_id:
                games_added += 1

            # 檢查目標地區狀態
            target_info = target_games.get(product_id, {})
            status = XboxScraper.determine_status(target_info)

            price = None
            currency = None
            if target_info.get("purchaseable") and target_info.get("price_list"):
                price = target_info["price_list"][0].get("listPrice")
                currency = target_info["price_list"][0].get("currency")

            # 根據模式決定是否寫入
            if browse_all == 0:
                # 增量模式：直接更新
                self.db.update_region_status(
                    game_id=game_id,
                    locale=TARGET_LOCALE,
                    status=status,
                    price=price,
                    currency=currency,
                    region_title=target_info.get("title"),
                )
            else:
                # 全量模式：只寫入有變動的
                has_change = self.db.update_region_status_with_change_detection(
                    game_id=game_id,
                    locale=TARGET_LOCALE,
                    new_status=status,
                    price=price,
                    currency=currency,
                    region_title=target_info.get("title"),
                )
                if has_change:
                    games_changed += 1

        # 更新全量掃描時間戳（僅 browse_all=1）
        if browse_all == 1:
            self.db.update_full_scan_timestamp(TARGET_LOCALE)

        print("✅ 資料庫已更新")
        if browse_all == 0:
            print(f"   新增遊戲：{games_added} 款")
        else:
            print(f"   掃描遊戲：{len(source_games)} 款")
            print(f"   狀態變動：{games_changed} 款")

        return True

    def recheck_delisted_games(self, max_pages: int = None) -> bool:
        """
        重新檢查舊 delisted 遊戲（可選）

        Args:
            max_pages: 最多抓取幾頁

        Returns:
            是否成功
        """
        print(f"\n【Phase 4】重檢 Delisted 遊戲（{DELISTED_RECHECK_DAYS} 天）")

        games_to_recheck = self.db.get_games_needing_recheck(
            locale=TARGET_LOCALE,
            days_threshold=DELISTED_RECHECK_DAYS,
            status="delisted",
        )

        if not games_to_recheck:
            print("❌ 沒有遊戲需要重檢")
            return True

        print(f"📋 需要重檢：{len(games_to_recheck)} 款")

        # 構建要檢查的遊戲字典
        games_to_check = {}
        for game_id, product_id, ja_title, is_base_game_db in games_to_recheck:
            games_to_check[product_id] = {
                "title": ja_title,
                "price": 0,
                "currency": "Unknown",
                "slug": "",
                "is_base_game": bool(is_base_game_db),
            }

        # V3 批量檢查台灣狀態
        target_games = self.scraper.check_target_games_v3(games_to_check, TARGET_LOCALE)

        # 更新資料庫
        for product_id, target_info in target_games.items():
            game_id = self.db.get_game_id(product_id)
            if not game_id:
                continue

            status = XboxScraper.determine_status(target_info)
            price = None
            currency = None

            if target_info.get("purchaseable") and target_info.get("price_list"):
                price = target_info["price_list"][0].get("listPrice")
                currency = target_info["price_list"][0].get("currency")

            self.db.update_region_status(
                game_id=game_id,
                locale=TARGET_LOCALE,
                status=status,
                price=price,
                currency=currency,
                region_title=target_info.get("title"),
            )

        print("✅ 重檢完成")
        return True

    def export_results(self, mode: str = "limited") -> bool:
        """
        匯出結果（CSV + HTML 報表）

        Args:
            mode: 'limited' = 只列限定遊戲，'full' = 列所有遊戲

        Returns:
            是否成功
        """
        print("\n【Phase 5】匯出結果")

        try:
            # 匯出 CSV (會根據 self.filter_dlc 決定是否只匯出遊戲本體)
            self.db.export_csv(OUTPUT_CSV, mode=mode, filter_dlc=self.filter_dlc)

            # 統計資訊
            stats = self.db.get_statistics(TARGET_LOCALE)
            print("\n📊 統計資訊：")
            print(f"   可購買 (available): {stats['available']} 款")
            print(f"   地區限定 (region-locked): {stats['region-locked']} 款")
            print(f"   已下架 (delisted): {stats['delisted']} 款")

            # 生成 HTML 報表
            print("\n📄 生成 HTML 報表...")
            self._generate_html_report(stats, mode=mode)

            return True
        except Exception as e:
            print(f"❌ 匯出失敗：{e}")
            return False

    def _generate_html_report(self, stats: Dict, mode: str = "limited"):
        """
        生成 HTML 報表

        Args:
            stats: 統計資訊
            mode: 輸出模式
        """
        try:
            # 準備遊戲資料
            games_with_regions = []
            cursor = self.db.conn.cursor()

            # 查詢所有遊戲及其在各地區的狀態
            cursor.execute("""
                SELECT g.product_id, g.ja_title, g.ja_price, g.ja_currency,
                       r.locale, r.region_title, r.status, r.price, r.currency,
                       r.last_checked_date, g.is_base_game
                FROM games g
                LEFT JOIN regions r ON g.id = r.game_id
                ORDER BY g.first_seen_date DESC;
            """)

            # 重組資料結構
            games_dict = {}
            for row in cursor.fetchall():
                product_id = row["product_id"]
                if product_id not in games_dict:
                    games_dict[product_id] = {
                        "product_id": product_id,
                        "ja_title": row["ja_title"],
                        "ja_price": row["ja_price"],
                        "ja_currency": row["ja_currency"],
                        "regions": {},
                        "is_base_game": row["is_base_game"],
                    }

                if row["locale"]:
                    games_dict[product_id]["regions"][row["locale"]] = {
                        "region_title": row["region_title"],
                        "status": row["status"],
                        "price": row["price"],
                        "currency": row["currency"],
                        "last_checked_date": row["last_checked_date"],
                    }

            # 轉換為 HTML 所需的格式
            games_list = []
            for product_id, game_info in games_dict.items():
                tw_info = game_info["regions"].get(TARGET_LOCALE, {})
                status = tw_info.get("status", "delisted")

                # 如果 filter_dlc=1，則只顯示遊戲本體
                if self.filter_dlc == 1 and not game_info.get("is_base_game", 1):
                    continue

                # mode='limited' 時只列不可購買的
                if mode == "limited" and status == "available":
                    continue

                tw_title = tw_info.get("region_title") or ""
                last_checked = tw_info.get("last_checked_date")
                if last_checked:
                    try:
                        parsed = datetime.strptime(last_checked, "%Y-%m-%d %H:%M:%S")
                        local_time = parsed + timedelta(hours=8)
                        last_checked = local_time.strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        pass

                games_list.append(
                    {
                        "product_id": product_id,
                        "ja_title": game_info["ja_title"],
                        "ja_price": game_info["ja_price"],
                        "ja_url": f"https://www.xbox.com/ja-jp/games/store/{game_info['ja_title']}/{product_id}",
                        "tw_title": tw_title,
                        "tw_price": tw_info.get("price"),
                        "tw_url": f"https://www.xbox.com/zh-tw/games/store/{game_info['ja_title']}/{product_id}",
                        "status": status,
                        "last_checked": last_checked or "未檢查",
                    }
                )

            # 生成報表
            reporter = HTMLReporter()
            reporter.generate_report(
                games_data=games_list,
                stats={
                    "available": stats["available"],
                    "region_locked": stats["region-locked"],
                    "delisted": stats["delisted"],
                    "total": stats["available"]
                    + stats["region-locked"]
                    + stats["delisted"],
                },
                output_file=OUTPUT_HTML,
                show_charts=True,
            )

        except Exception as e:
            print(f"❌ 生成 HTML 報表失敗：{e}")

    def run(
        self,
        browse_all: int = 0,
        multi_sort: int = 0,
        recheck_delisted: bool = False,
        max_pages: int = None,
    ):
        """
        執行完整流程

        Args:
            browse_all: 掃描模式 (0 = 增量, 1 = 全量驗證)
            multi_sort: 多排序搜尋開關 (0 = 預設排序, 1 = 多排序)
            recheck_delisted: 是否重檢 delisted 遊戲（已過時，browse_all 優先）
            max_pages: 最多抓取幾頁（測試用）
        """
        try:
            # 驗證 token
            if not self._validate_auth_token():
                sys.exit(1)

            # 初始化 DB
            if not self.initialize_db():
                sys.exit(1)

            # 初始化爬蟲
            if not self.initialize_scraper():
                sys.exit(1)

            # 執行更新（根據 browse_all 模式）
            if not self.run_incremental_update(
                browse_all=browse_all, multi_sort=multi_sort, max_pages=max_pages
            ):
                sys.exit(1)

            # 可選：重檢 delisted 遊戲（向後相容）
            if recheck_delisted and browse_all == 0:
                self.recheck_delisted_games(max_pages=max_pages)

            # 匯出結果
            if not self.export_results(mode="limited"):
                sys.exit(1)

            print("\n✅ 完成！")

        finally:
            if self.db:
                self.db.close()


def main():
    """CLI 入口"""
    parser = argparse.ArgumentParser(
        description="Xbox 商店遊戲對比工具 V3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例：

  # 增量模式（推薦日常使用）
  python xbox_compare_v3.py --browse-all 0

  # 全量驗證模式（推薦週期性使用）
  python xbox_compare_v3.py --browse-all 1

  # 全量模式 + 自定義延遲
  python xbox_compare_v3.py --browse-all 1 --delay 2.0

  # 只統計遊戲本體（性能優化）
  python xbox_compare_v3.py --browse-all 1 --filter-dlc 1

  # 統計所有產品（包含 DLC）
  python xbox_compare_v3.py --browse-all 1 --filter-dlc 0

詳細說明見 README.md
        """,
    )
    parser.add_argument(
        "--token", type=str, default=AUTH_TOKEN, help="Xbox Live XBL3.0 token"
    )
    parser.add_argument("--db", type=str, default=DB_PATH, help="資料庫路徑")
    parser.add_argument(
        "--browse-all",
        type=int,
        choices=[0, 1],
        default=BROWSE_ALL,
        help=f"""掃描模式 (設定值: {BROWSE_ALL})
          0 = 增量模式（日常使用）
              - JP: 掃描找新遊戲
              - TW: 只重檢 delisted/region-locked
              - 快速，適合每日運行
          1 = 全量驗證（定期使用）
              - JP: 完整掃描所有遊戲
              - TW: 完整掃描所有遊戲
              - 只寫入有狀態變動的
              - 較慢，適合週期性檢查""",
    )
    parser.add_argument(
        "--multi-sort",
        type=int,
        choices=[0, 1],
        default=MULTI_SORT,
        help=f"""多排序搜尋開關 (設定值: {MULTI_SORT})
          0 = 只用預設排序（快速）
          1 = 使用 5 種排序方式提高涵蓋率（慢但完整）""",
    )
    parser.add_argument(
        "--filter-dlc",
        type=int,
        choices=[0, 1],
        default=FILTER_DLC,
        help=f"""DLC 過濾開關 (設定值: {FILTER_DLC})
          1 = 只統計遊戲本體（性能優化模式）
          0 = 統計 DLC 與所有其他產品（完整模式）""",
    )
    parser.add_argument(
        "--recheck",
        action="store_true",
        help="（已過時）重檢 delisted 遊戲，用 --browse-all 0 代替",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=MAX_PAGES,
        help=f"最多抓取幾頁（測試用，預設 {MAX_PAGES} 頁）",
    )
    parser.add_argument(
        "--delay", type=float, default=REQUEST_DELAY, help="請求間隔（秒，預設 1.5）"
    )

    args = parser.parse_args()

    # 執行
    comparer = XboxMarketplaceComparerV3(
        auth_token=args.token,
        db_path=args.db,
        request_delay=args.delay,
        filter_dlc=args.filter_dlc,
    )
    comparer.run(
        browse_all=args.browse_all,
        multi_sort=args.multi_sort,
        recheck_delisted=args.recheck,
        max_pages=args.max_pages,
    )


if __name__ == "__main__":
    main()
