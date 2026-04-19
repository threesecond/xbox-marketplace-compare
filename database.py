#!/usr/bin/env python3
"""
Xbox 遊戲對比工具 - 資料庫層
處理 SQLite 資料持久化
"""

import sqlite3
import csv
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple, Optional, Set


DB_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
CURRENT_SCHEMA_VERSION = 3
logger = logging.getLogger(__name__)


class GameDatabase:
    """SQLite 資料庫操作類"""

    def __init__(self, db_path: str = "games.db"):
        """
        初始化資料庫連接
        
        Args:
            db_path: SQLite 資料庫檔案路徑
        """
        self.db_path = db_path
        self.conn = None
        self._connect()

    def _connect(self):
        """建立與 SQLite 的連接"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            logger.info(f"✅ 資料庫連接成功: {self.db_path}")
            self._upgrade_schema()
        except sqlite3.Error as e:
            logger.error(f"❌ 資料庫連接失敗: {e}")
            raise

    @staticmethod
    def utc_now_string() -> str:
        """取得目前 UTC 時間字串，統一資料庫儲存格式。"""
        return datetime.now(timezone.utc).strftime(DB_TIMESTAMP_FORMAT)

    @staticmethod
    def parse_db_timestamp(timestamp_str: Optional[str]) -> Optional[datetime]:
        """將資料庫中的時間字串解析為 UTC datetime。"""
        if not timestamp_str:
            return None
        return datetime.strptime(timestamp_str, DB_TIMESTAMP_FORMAT).replace(
            tzinfo=timezone.utc
        )

    def _table_exists(self, table_name: str) -> bool:
        """檢查資料表是否存在"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
        return cursor.fetchone() is not None

    def _ensure_schema_meta_table(self):
        """確保 schema 版本資訊表存在。"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def _get_schema_version(self) -> int:
        """取得目前 schema 版本。"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM schema_meta WHERE key = 'schema_version';")
        row = cursor.fetchone()
        return int(row["value"]) if row else 0

    def _set_schema_version(self, version: int):
        """寫入 schema 版本。"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO schema_meta (key, value)
            VALUES ('schema_version', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value;
            """,
            (str(version),),
        )
        self.conn.commit()

    def _infer_legacy_schema_version(self) -> int:
        """
        推測舊資料庫的 schema 版本。

        這讓既有資料庫在沒有版本資訊表的情況下，也能被正確接手並補齊 migration。
        """
        if not self._table_exists("games") or not self._table_exists("regions"):
            return 0

        cursor = self.conn.cursor()
        game_columns = {
            row["name"] for row in cursor.execute("PRAGMA table_info(games);").fetchall()
        }
        region_columns = {
            row["name"] for row in cursor.execute("PRAGMA table_info(regions);").fetchall()
        }

        version = 1
        if {"region_title", "status_change_count"}.issubset(region_columns):
            version = 2
        if "is_base_game" in game_columns and version >= 2:
            version = 3
        return version

    def _migrate_to_v2(self):
        """升級到 schema v2：補齊地區標題與狀態變動次數欄位。"""
        cursor = self.conn.cursor()
        columns = {
            row["name"] for row in cursor.execute("PRAGMA table_info(regions);").fetchall()
        }

        if "region_title" not in columns:
            cursor.execute("ALTER TABLE regions ADD COLUMN region_title TEXT;")
            logger.info("✅ 已升級 regions 表：加入 region_title 欄位")
        if "status_change_count" not in columns:
            cursor.execute(
                "ALTER TABLE regions ADD COLUMN status_change_count INTEGER DEFAULT 0;"
            )
            logger.info("✅ 已升級 regions 表：加入 status_change_count 欄位")

        self.conn.commit()

    def _migrate_to_v3(self):
        """升級到 schema v3：補齊遊戲本體標記欄位。"""
        cursor = self.conn.cursor()
        columns = {
            row["name"] for row in cursor.execute("PRAGMA table_info(games);").fetchall()
        }

        if "is_base_game" not in columns:
            cursor.execute("ALTER TABLE games ADD COLUMN is_base_game INTEGER DEFAULT 1;")
            self.conn.commit()
            logger.info("✅ 已升級 games 表：加入 is_base_game 欄位")

    def _upgrade_schema(self):
        """檢查並升級資料庫 schema。"""
        self._ensure_schema_meta_table()

        version = self._get_schema_version()
        if version == 0:
            inferred_version = self._infer_legacy_schema_version()
            if inferred_version:
                version = inferred_version
                self._set_schema_version(version)

        if version < 2 and self._table_exists("regions"):
            self._migrate_to_v2()
            version = 2
            self._set_schema_version(version)

        if version < 3 and self._table_exists("games"):
            self._migrate_to_v3()
            version = 3
            self._set_schema_version(version)

    def init_db(self):
        """初始化資料庫 - 建立所有資料表"""
        cursor = self.conn.cursor()
        
        try:
            # 建表：遊戲基本資訊
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT UNIQUE NOT NULL,
                    ja_title TEXT NOT NULL,
                    ja_price REAL,
                    ja_currency TEXT,
                    en_title TEXT,
                    first_seen_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_base_game INTEGER DEFAULT 1, -- 1=遊戲本體, 0=DLC
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 建表：各地區狀態
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS regions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL,
                    locale TEXT NOT NULL,
                    region_title TEXT,
                    status TEXT,
                    price REAL,
                    currency TEXT,
                    last_checked_date TIMESTAMP,
                    last_full_scan_date TIMESTAMP,
                    check_count INTEGER DEFAULT 0,
                    status_change_count INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(game_id) REFERENCES games(id),
                    UNIQUE(game_id, locale)
                );
            """)

            # 建索引加速查詢
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_games_product_id 
                ON games(product_id);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_regions_game_id 
                ON regions(game_id);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_regions_locale 
                ON regions(locale);
            """)

            self.conn.commit()
            self._set_schema_version(CURRENT_SCHEMA_VERSION)
            logger.info("✅ 資料庫初始化完成")

        except sqlite3.Error as e:
            logger.error(f"❌ 資料庫初始化失敗: {e}")
            raise

    def close(self):
        """關閉資料庫連接"""
        if self.conn:
            self.conn.close()
            logger.info("✅ 資料庫連接已關閉")

    def get_existing_games(self) -> Set[str]:
        """
        取得所有已存在的遊戲 product_id
        
        Returns:
            product_id 的集合
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT product_id FROM games;")
        results = cursor.fetchall()
        return {row['product_id'] for row in results}

    def get_game_id(self, product_id: str) -> Optional[int]:
        """取得遊戲的內部 ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM games WHERE product_id = ?;", (product_id,))
        row = cursor.fetchone()
        return row['id'] if row else None

    def get_game_info(self, product_id: str) -> Optional[Dict]:
        """取得遊戲的完整資訊"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, product_id, ja_title, ja_price, ja_currency, en_title, is_base_game, first_seen_date
            FROM games WHERE product_id = ?;
        """, (product_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def add_game(
        self,
        product_id: str,
        ja_title: str,
        ja_price: float,
        ja_currency: str,
        en_title: str = None,
        is_base_game: int = 1,
    ) -> int:
        """
        新增遊戲記錄
        
        Args:
            product_id: Xbox API ID
            ja_title: 日本標題
            ja_price: 日本價格
            ja_currency: 日本貨幣
            en_title: 英文標題（選填）
            is_base_game: 是否為遊戲本體 (1=是, 0=否)
        
        Returns:
            遊戲的 ID
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO games (product_id, ja_title, ja_price, ja_currency, en_title, is_base_game)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (product_id, ja_title, ja_price, ja_currency, en_title, is_base_game))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # 遊戲已存在，檢查是否需要更新 is_base_game
            existing = self.get_game_info(product_id)
            if existing and existing.get('is_base_game') != is_base_game:
                cursor.execute("UPDATE games SET is_base_game = ? WHERE product_id = ?", (is_base_game, product_id))
                self.conn.commit()
            return self.get_game_id(product_id)

    def _get_region_record(self, game_id: int, locale: str):
        """取得單一地區狀態記錄。"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, status, check_count FROM regions WHERE game_id = ? AND locale = ?;",
            (game_id, locale),
        )
        return cursor.fetchone()

    def update_region_status(
        self,
        game_id: int,
        locale: str,
        status: str,
        price: float = None,
        currency: str = None,
        region_title: str = None,
    ):
        """
        更新某地區的遊戲狀態
        
        Args:
            game_id: 遊戲 ID
            locale: 地區代碼 (e.g., 'zh-TW')
            status: 狀態 ('available' / 'region-locked' / 'delisted' / 'query-failed')
            price: 該地區價格
            currency: 該地區貨幣
        """
        cursor = self.conn.cursor()
        existing = self._get_region_record(game_id, locale)
        checked_at = self.utc_now_string()

        if existing:
            # 更新現有記錄，增加 check_count
            cursor.execute("""
                UPDATE regions
                SET status = ?, price = ?, currency = ?, region_title = ?,
                    last_checked_date = ?,
                    check_count = check_count + 1,
                    updated_at = ?
                WHERE game_id = ? AND locale = ?
            """, (status, price, currency, region_title, checked_at, checked_at, game_id, locale))
        else:
            # 新增記錄
            cursor.execute("""
                INSERT INTO regions 
                (game_id, locale, region_title, status, price, currency, last_checked_date, check_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (game_id, locale, region_title, status, price, currency, checked_at, checked_at))

        self.conn.commit()

    def get_games_needing_recheck(
        self,
        locale: str,
        days_threshold: int = 7,
        status: str = "delisted"
    ) -> List[Tuple[int, str, str]]:
        """
        取得需要重新檢查的遊戲（距上次檢查超過 N 天）
        
        Args:
            locale: 地區代碼
            days_threshold: 天數閾值（預設 7 天）
            status: 要檢查的狀態（預設 'delisted'）
        
        Returns:
            [(game_id, product_id, ja_title), ...]
        """
        cursor = self.conn.cursor()
        threshold_date = (
            datetime.now(timezone.utc) - timedelta(days=days_threshold)
        ).strftime(DB_TIMESTAMP_FORMAT)

        cursor.execute("""
            SELECT g.id, g.product_id, g.ja_title, g.is_base_game
            FROM games g 
            INNER JOIN regions r ON g.id = r.game_id
            WHERE r.locale = ? AND r.status = ? 
              AND (r.last_checked_date IS NULL OR r.last_checked_date < ?)
            ORDER BY r.last_checked_date ASC;
        """, (locale, status, threshold_date))

        return cursor.fetchall()

    def get_all_games_with_status(self, locale: str) -> Dict[str, Dict]:
        """
        取得所有遊戲及其在某地區的狀態

        Args:
            locale: 地區代碼

        Returns:
            {product_id: {status, price, currency, ja_title, ...}, ...}
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT g.product_id, g.ja_title, g.is_base_game, r.status, r.price, r.currency, r.last_checked_date
            FROM games g
            LEFT JOIN regions r ON g.id = r.game_id AND r.locale = ?
            ORDER BY g.first_seen_date DESC;
        """, (locale,))

        results = {}
        for row in cursor.fetchall():
            results[row['product_id']] = {
                'ja_title': row['ja_title'],
                'status': row['status'],
                'price': row['price'],
                'currency': row['currency'],
                'last_checked_date': row['last_checked_date'],
                'is_base_game': row['is_base_game'],
            }
        return results

    def get_delisted_or_regionlocked_games(self, locale: str) -> List[Tuple[int, str, str]]:
        """
        取得狀態為 delisted、region-locked 或 query-failed 的遊戲

        用於 browse_all=0 時，只重新檢查有問題的遊戲

        Args:
            locale: 地區代碼

        Returns:
            [(game_id, product_id, ja_title), ...]
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT g.id, g.product_id, g.ja_title, g.is_base_game
            FROM games g 
            INNER JOIN regions r ON g.id = r.game_id
            WHERE r.locale = ? AND r.status IN ('delisted', 'region-locked', 'query-failed')
            ORDER BY r.updated_at DESC;
        """, (locale,))

        return cursor.fetchall()

    def get_current_status(self, product_id: str, locale: str) -> Optional[str]:
        """
        取得遊戲在某地區的當前狀態

        用於檢測狀態是否有變動

        Args:
            product_id: 遊戲 product_id
            locale: 地區代碼

        Returns:
            狀態字串或 None（如果記錄不存在）
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT r.status
            FROM games g
            INNER JOIN regions r ON g.id = r.game_id
            WHERE g.product_id = ? AND r.locale = ?;
        """, (product_id, locale))

        row = cursor.fetchone()
        return row['status'] if row else None

    def update_region_status_with_change_detection(
        self,
        game_id: int,
        locale: str,
        new_status: str,
        price: float = None,
        currency: str = None,
        region_title: str = None,
    ) -> bool:
        """
        更新地區狀態，並檢測是否有狀態變動

        當狀態有變動時，增加 status_change_count

        Args:
            game_id: 遊戲 ID
            locale: 地區代碼
            new_status: 新狀態
            price: 該地區價格
            currency: 該地區貨幣

        Returns:
            是否有狀態變動
        """
        cursor = self.conn.cursor()

        # 檢查舊狀態
        existing = self._get_region_record(game_id, locale)
        old_status = existing['status'] if existing else None
        checked_at = self.utc_now_string()

        # 判斷是否有變動
        has_change = old_status != new_status

        if existing:
            # 更新現有記錄
            if has_change:
                # 有變動：增加 status_change_count
                cursor.execute("""
                    UPDATE regions
                    SET status = ?, price = ?, currency = ?, region_title = ?,
                        last_checked_date = ?,
                        check_count = check_count + 1,
                        status_change_count = status_change_count + 1,
                        updated_at = ?
                    WHERE game_id = ? AND locale = ?
                """, (new_status, price, currency, region_title, checked_at, checked_at, game_id, locale))
            else:
                # 無變動：保持原狀
                cursor.execute("""
                    UPDATE regions
                    SET price = ?, currency = ?, region_title = ?,
                        last_checked_date = ?,
                        check_count = check_count + 1,
                        updated_at = ?
                    WHERE game_id = ? AND locale = ?
                """, (price, currency, region_title, checked_at, checked_at, game_id, locale))
        else:
            # 新增記錄
            cursor.execute("""
                INSERT INTO regions
                (game_id, locale, region_title, status, price, currency, last_checked_date, check_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (game_id, locale, region_title, new_status, price, currency, checked_at, checked_at))

        self.conn.commit()
        return has_change

    def update_full_scan_timestamp(self, locale: str, scan_time: str = None):
        """
        更新全量掃描時間戳

        用於 browse_all=1 時，記錄上次完整掃描的時間

        Args:
            locale: 地區代碼
            scan_time: 掃描時間（ISO format），預設為當前時間
        """
        if scan_time is None:
            scan_time = self.utc_now_string()

        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE regions
            SET last_full_scan_date = ?
            WHERE locale = ?;
        """, (scan_time, locale))

        self.conn.commit()

    def get_statistics(self, locale: str) -> Dict[str, int]:
        """
        取得統計資訊
        
        Args:
            locale: 地區代碼
        
        Returns:
            {available: N, region-locked: N, delisted: N, query-failed: N}
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT r.status, COUNT(*) as count
            FROM regions r
            WHERE r.locale = ?
            GROUP BY r.status;
        """, (locale,))

        stats = {
            'available': 0,
            'region-locked': 0,
            'delisted': 0,
            'query-failed': 0,
        }
        for row in cursor.fetchall():
            stats[row['status']] = row['count']
        return stats

    def export_csv(
        self,
        output_file: str,
        source_locale: str = "ja-JP",
        target_locale: str = "zh-TW",
        mode: str = "limited",
        filter_dlc: int = 1 # 新增 filter_dlc 參數
    ):
        """
        匯出 CSV（相容 V1 格式）
        
        Args:
            output_file: 輸出檔案路徑
            source_locale: 源地區
            target_locale: 目標地區
            mode: 'limited' = 只列限定遊戲，'full' = 列所有遊戲
        """
        cursor = self.conn.cursor()

        # 取得源地區所有遊戲
        cursor.execute("""
            SELECT g.id, g.product_id, g.ja_title, g.ja_price, g.is_base_game
            FROM games g
            ORDER BY g.first_seen_date DESC;
        """)
        source_games = {row['product_id']: dict(row) for row in cursor.fetchall()}

        # 取得目標地區狀態
        cursor.execute("""
            SELECT g.product_id, r.status, r.price, r.region_title
            FROM games g
            LEFT JOIN regions r ON g.id = r.game_id AND r.locale = ?
            ORDER BY g.first_seen_date DESC;
        """, (target_locale,))
        target_games = {row['product_id']: dict(row) for row in cursor.fetchall()}

        # 組建 CSV 行
        fieldnames = [
            "productId",
            f"{source_locale}_title",
            f"{source_locale}_price",
            f"{target_locale}_title",
            f"{target_locale}_price",
            f"{target_locale}_status",
            f"{source_locale}_url",
            f"{target_locale}_url",
        ]

        output_rows = []

        for product_id, source_row in source_games.items():
            # 如果 filter_dlc=1，則只匯出遊戲本體
            if filter_dlc == 1 and not source_row.get('is_base_game', 1):
                continue

            target_row = target_games.get(product_id, {})
            status = target_row.get('status', 'delisted')

            # mode='limited' 時，只列出不可購買的
            if mode == "limited" and status == 'available':
                continue

            # 生成 URL（使用 product_id）
            ja_url = f"https://www.xbox.com/ja-jp/games/store/{source_row['ja_title']}/{product_id}"
            tw_url = f"https://www.xbox.com/zh-tw/games/store/{source_row['ja_title']}/{product_id}"

            output_rows.append({
                "productId": product_id,
                f"{source_locale}_title": source_row['ja_title'],
                f"{source_locale}_price": source_row['ja_price'],
                f"{target_locale}_title": target_row.get('region_title', '') if target_row else '',
                f"{target_locale}_price": target_row.get('price', '') if target_row else '',
                f"{target_locale}_status": status,
                f"{source_locale}_url": ja_url,
                f"{target_locale}_url": tw_url,
            })

        # 寫 CSV
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(output_rows)

        logger.info(f"✅ CSV 已匯出: {output_file}")
        logger.info(f"   共 {len(output_rows)} 筆記錄")

    def fetch_games_with_regions(self) -> Dict[str, Dict]:
        """
        以報表輸出友善的結構，回傳所有遊戲與其地區資料。

        這個方法的目的，是把報表查詢與資料重組收回資料庫層，
        讓 pipeline 不需要直接操作 SQL。
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT g.product_id, g.ja_title, g.ja_price, g.ja_currency,
                   r.locale, r.region_title, r.status, r.price, r.currency,
                   r.last_checked_date, g.is_base_game
            FROM games g
            LEFT JOIN regions r ON g.id = r.game_id
            ORDER BY g.first_seen_date DESC;
        """)

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

        return games_dict

    def get_summary(self) -> Dict:
        """取得資料庫摘要"""
        cursor = self.conn.cursor()

        # 總遊戲數
        cursor.execute("SELECT COUNT(*) as count FROM games;")
        total_games = cursor.fetchone()['count']

        # 各地區紀錄數
        cursor.execute("""
            SELECT locale, COUNT(*) as count
            FROM regions
            GROUP BY locale;
        """)
        region_counts = {row['locale']: row['count'] for row in cursor.fetchall()}

        return {
            'total_games': total_games,
            'region_counts': region_counts,
            'db_file': self.db_path,
        }


# 測試用
if __name__ == "__main__":
    db = GameDatabase()
    db.init_db()

    # 插入樣本資料
    game_id = db.add_game("test123", "テストゲーム", 5000, "JPY", "Test Game")
    db.update_region_status(game_id, "zh-TW", "available", 1500, "TWD")

    # 查詢統計
    summary = db.get_summary()
    logger.info(summary)

    db.close()
