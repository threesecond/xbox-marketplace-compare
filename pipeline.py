#!/usr/bin/env python3
"""
Xbox Marketplace Compare - pipeline/orchestration layer
"""

import logging
import sys
import time
from datetime import timedelta, timezone
from pathlib import Path
from typing import Dict

from config import AppConfig
from database import GameDatabase
from html_generator import HTMLReporter
from scraper import XboxScraper


QUERY_FAILED_STATUS = "query-failed"
logger = logging.getLogger(__name__)


class XboxMarketplacePipeline:
    """Coordinates scraping, persistence, and export."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.db = None
        self.scraper = None

    def _validate_auth_token(self) -> bool:
        """Validate auth token (optional in V3)."""
        if not self.config.auth_token:
            logger.info(
                "  AUTH_TOKEN 未設定，以匿名模式執行（browse API 與 DisplayCatalog 均不需要 token）"
            )
        return True

    def initialize_db(self) -> bool:
        """Initialize database connection and schema."""
        try:
            self.db = GameDatabase(self.config.db_path)

            if not Path(self.config.db_path).exists() or not self.db._table_exists("games"):
                logger.info("\n🆕 首次運行或資料庫損壞，建立資料庫...")
                self.db.init_db()
            else:
                summary = self.db.get_summary()
                logger.info(f"\n📊 資料庫已存在：{summary['total_games']} 款遊戲")
                logger.info(f"   地區資訊：{summary['region_counts']}")

            return True
        except Exception as e:
            logger.error(f"❌ 資料庫初始化失敗：{e}")
            return False

    def initialize_scraper(self) -> bool:
        """Initialize scraper client."""
        try:
            self.scraper = XboxScraper(
                auth_token=self.config.auth_token,
                request_delay=self.config.request_delay,
                filter_dlc=self.config.filter_dlc,
            )
            return True
        except Exception as e:
            logger.error(f"❌ 爬蟲初始化失敗：{e}")
            return False

    def _extract_target_price(self, target_info: Dict):
        """Extract target-region price info from API data."""
        price = None
        currency = None
        if target_info.get("purchaseable") and target_info.get("price_list"):
            price = target_info["price_list"][0].get("listPrice")
            currency = target_info["price_list"][0].get("currency")
        return price, currency

    def _persist_target_status(
        self,
        game_id: int,
        locale: str,
        status: str,
        target_info: Dict,
        browse_all: int,
    ) -> bool:
        """Persist target status and report whether a full-scan status changed."""
        price, currency = self._extract_target_price(target_info)

        if browse_all == 0:
            self.db.update_region_status(
                game_id=game_id,
                locale=locale,
                status=status,
                price=price,
                currency=currency,
                region_title=target_info.get("title"),
            )
            return False

        return self.db.update_region_status_with_change_detection(
            game_id=game_id,
            locale=locale,
            new_status=status,
            price=price,
            currency=currency,
            region_title=target_info.get("title"),
        )

    def run_incremental_update(
        self, browse_all: int = 0, multi_sort: int = 0, max_pages: int = None
    ) -> bool:
        """Run incremental update or full verification scan."""
        logger.info("\n" + "=" * 60)
        logger.info("🎮 Xbox 商店遊戲對比工具 V3")
        logger.info("=" * 60)
        logger.info(f"源地區：{self.config.source_locale}")
        logger.info(f"目標地區：{self.config.target_locale}")
        logger.info(f"資料庫：{self.config.db_path}")
        logger.info(
            f"掃描模式：{'全量驗證 (browse_all=1)' if browse_all else '增量更新 (browse_all=0)'}"
        )
        logger.info(
            f"DLC 過濾：{'只統計遊戲本體 (filter_dlc=1)' if self.config.filter_dlc else '統計所有產品 (filter_dlc=0)'}"
        )

        existing_games = self.db.get_existing_games()
        if len(existing_games) == 0 and browse_all == 0:
            logger.error("\n❌ 錯誤：資料庫為空，不能使用增量模式 (browse_all=0)")
            logger.info("   建議：")
            logger.info("   1. 使用全量掃描：--browse-all 1")
            logger.info("   2. 或者清空資料庫後重新運行")
            return False

        logger.info(f"\n【Phase 1】爬取 {self.config.source_locale} 遊戲清單")

        if browse_all == 0:
            logger.info(f"已存在記錄：{len(existing_games)} 款")
            result = self.scraper.fetch_all_games_with_multiple_sorts(
                self.config.source_locale,
                max_pages=max_pages,
                skip_existing=existing_games if len(existing_games) > 0 else None,
                multi_sort=bool(multi_sort),
            )
            source_games = result["games"]
            logger.info(f"✅ 新增遊戲：{len(source_games)} 款")
        else:
            result = self.scraper.fetch_all_games_with_multiple_sorts(
                self.config.source_locale,
                max_pages=max_pages,
                skip_existing=None,
                multi_sort=bool(multi_sort),
            )
            source_games = result["games"]
            logger.info(f"✅ 掃描完成：{len(source_games)} 款遊戲")

        if not source_games:
            logger.error("❌ 無法抓取源地區遊戲")
            return False

        logger.info(f"\n【Phase 2】檢查 {self.config.target_locale} 地區狀態")

        if browse_all == 0:
            games_to_recheck = self.db.get_delisted_or_regionlocked_games(
                self.config.target_locale
            )

            if not games_to_recheck:
                logger.info("   沒有需要重檢的遊戲（所有遊戲狀態都是 available）")
                target_games = {}
            else:
                logger.info(
                    f"   需要重檢：{len(games_to_recheck)} 款 delisted/region-locked 遊戲"
                )

                games_dict = {}
                for game_id, product_id, ja_title, is_base_game_db in games_to_recheck:
                    games_dict[product_id] = {
                        "title": ja_title,
                        "price": 0,
                        "currency": "Unknown",
                        "slug": "",
                        "is_base_game": bool(is_base_game_db),
                    }

                target_games = self.scraper.check_target_games_v3(
                    games_dict, self.config.target_locale
                )
        else:
            target_games = self.scraper.check_target_games_v3(
                source_games, self.config.target_locale
            )

        logger.info("\n【Phase 3】更新資料庫")

        games_added = 0
        games_changed = 0
        query_failed_count = 0

        for product_id, source_info in source_games.items():
            is_base_game = source_info.get("is_base_game", True)
            game_id = self.db.add_game(
                product_id=product_id,
                ja_title=source_info["title"],
                ja_price=source_info["price"],
                ja_currency=source_info["currency"],
                en_title=None,
                is_base_game=int(is_base_game),
            )

            if game_id:
                games_added += 1

            target_info = target_games.get(product_id, {})
            status = XboxScraper.determine_status(target_info)
            if status == QUERY_FAILED_STATUS:
                query_failed_count += 1

            has_change = self._persist_target_status(
                game_id=game_id,
                locale=self.config.target_locale,
                status=status,
                target_info=target_info,
                browse_all=browse_all,
            )
            if browse_all == 1 and has_change:
                games_changed += 1

        if browse_all == 1:
            self.db.update_full_scan_timestamp(self.config.target_locale)

        logger.info("✅ 資料庫已更新")
        if browse_all == 0:
            logger.info(f"   新增遊戲：{games_added} 款")
        else:
            logger.info(f"   掃描遊戲：{len(source_games)} 款")
            logger.info(f"   狀態變動：{games_changed} 款")
        if query_failed_count:
            logger.warning(
                f"   查詢失敗：{query_failed_count} 款（已保留為 query-failed，避免誤判下架）"
            )

        return True

    def recheck_delisted_games(self, max_pages: int = None) -> bool:
        """Recheck stale delisted games."""
        logger.info(f"\n【Phase 4】重檢 Delisted 遊戲（{self.config.delisted_recheck_days} 天）")

        games_to_recheck = self.db.get_games_needing_recheck(
            locale=self.config.target_locale,
            days_threshold=self.config.delisted_recheck_days,
            status="delisted",
        )

        if not games_to_recheck:
            logger.info("❌ 沒有遊戲需要重檢")
            return True

        logger.info(f"📋 需要重檢：{len(games_to_recheck)} 款")

        games_to_check = {}
        for game_id, product_id, ja_title, is_base_game_db in games_to_recheck:
            games_to_check[product_id] = {
                "title": ja_title,
                "price": 0,
                "currency": "Unknown",
                "slug": "",
                "is_base_game": bool(is_base_game_db),
            }

        target_games = self.scraper.check_target_games_v3(
            games_to_check, self.config.target_locale
        )

        query_failed_count = 0
        for product_id, target_info in target_games.items():
            game_id = self.db.get_game_id(product_id)
            if not game_id:
                continue

            status = XboxScraper.determine_status(target_info)
            if status == QUERY_FAILED_STATUS:
                query_failed_count += 1

            self._persist_target_status(
                game_id=game_id,
                locale=self.config.target_locale,
                status=status,
                target_info=target_info,
                browse_all=0,
            )

        logger.info("✅ 重檢完成")
        if query_failed_count:
            logger.warning(f"   查詢失敗：{query_failed_count} 款（狀態已標記為 query-failed）")
        return True

    def export_results(self, csv_mode: str = "full", html_mode: str = "limited") -> bool:
        """Export CSV and HTML results."""
        logger.info("\n【Phase 5】匯出結果")

        try:
            self.db.export_csv(
                self.config.output_csv,
                mode=csv_mode,
                filter_dlc=self.config.filter_dlc,
            )

            stats = self.db.get_statistics(self.config.target_locale)
            logger.info("\n📊 統計資訊：")
            logger.info(f"   可購買 (available): {stats['available']} 款")
            logger.info(f"   地區限定 (region-locked): {stats['region-locked']} 款")
            logger.info(f"   已下架 (delisted): {stats['delisted']} 款")
            logger.info(f"   查詢失敗 (query-failed): {stats['query-failed']} 款")

            logger.info("\n📄 生成 HTML 報表...")
            self._generate_html_report(stats, mode=html_mode)

            return True
        except Exception as e:
            logger.error(f"❌ 匯出失敗：{e}")
            return False

    def _generate_html_report(self, stats: Dict, mode: str = "limited"):
        """Generate HTML report from persisted data."""
        try:
            games_dict = self.db.fetch_games_with_regions()

            games_list = []
            for product_id, game_info in games_dict.items():
                tw_info = game_info["regions"].get(self.config.target_locale, {})
                status = tw_info.get("status", QUERY_FAILED_STATUS)

                if self.config.filter_dlc == 1 and not game_info.get("is_base_game", 1):
                    continue
                if mode == "limited" and status == "available":
                    continue

                tw_title = tw_info.get("region_title") or ""
                last_checked = tw_info.get("last_checked_date")
                if last_checked:
                    try:
                        parsed = self.db.parse_db_timestamp(last_checked)
                        local_time = parsed.astimezone(timezone(timedelta(hours=8)))
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

            reporter = HTMLReporter()
            reporter.generate_report(
                games_data=games_list,
                stats={
                    "available": stats["available"],
                    "region_locked": stats["region-locked"],
                    "delisted": stats["delisted"],
                    "query_failed": stats["query-failed"],
                    "total": stats["available"]
                    + stats["region-locked"]
                    + stats["delisted"]
                    + stats["query-failed"],
                },
                output_file=self.config.output_html,
                show_charts=True,
            )

        except Exception as e:
            logger.error(f"❌ 生成 HTML 報表失敗：{e}")

    def run(
        self,
        browse_all: int = 0,
        multi_sort: int = 0,
        recheck_delisted: bool = False,
        max_pages: int = None,
    ):
        """Execute the full pipeline."""
        try:
            start_time = time.time()

            if not self._validate_auth_token():
                sys.exit(1)
            if not self.initialize_db():
                sys.exit(1)
            if not self.initialize_scraper():
                sys.exit(1)
            if not self.run_incremental_update(
                browse_all=browse_all, multi_sort=multi_sort, max_pages=max_pages
            ):
                sys.exit(1)

            if recheck_delisted and browse_all == 0:
                self.recheck_delisted_games(max_pages=max_pages)

            if not self.export_results(csv_mode="full", html_mode="limited"):
                sys.exit(1)

            elapsed = time.time() - start_time
            h = int(elapsed // 3600)
            m = int((elapsed % 3600) // 60)
            s = int(elapsed % 60)
            logger.info(f"\n✅ 完成！總耗時：{h} 時 {m} 分 {s} 秒")

        finally:
            if self.db:
                self.db.close()
