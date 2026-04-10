#!/usr/bin/env python3
"""
Xbox 遊戲對比工具 - 資料庫層
處理 SQLite 資料持久化
"""

import sqlite3
import os
import csv
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Set
from pathlib import Path


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
            print(f"✅ 資料庫連接成功: {self.db_path}")
            self._upgrade_schema()
        except sqlite3.Error as e:
            print(f"❌ 資料庫連接失敗: {e}")
            raise

    def _table_exists(self, table_name: str) -> bool:
        """檢查資料表是否存在"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
        return cursor.fetchone() is not None

    def _upgrade_schema(self):
        """檢查並升級資料庫 schema"""
        # 只有在 regions 表存在時才檢查升級
        if self._table_exists('regions'):
            cursor = self.conn.cursor()
            cursor.execute("PRAGMA table_info(regions);")
            columns = {row['name'] for row in cursor.fetchall()}
            
            # 添加 region_title 列（如果不存在）
            if 'region_title' not in columns:
                try:
                    cursor.execute("ALTER TABLE regions ADD COLUMN region_title TEXT;")
                    self.conn.commit()
                    print("✅ 已升級 regions 表：加入 region_title 欄位")
                except sqlite3.Error:
                    pass
            
            # 添加 status_change_count 列（如果不存在）
            if 'status_change_count' not in columns:
                try:
                    cursor.execute("ALTER TABLE regions ADD COLUMN status_change_count INTEGER DEFAULT 0;")
                    self.conn.commit()
                    print("✅ 已升級 regions 表：加入 status_change_count 欄位")
                except sqlite3.Error:
                    pass

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
            print("✅ 資料庫初始化完成")

        except sqlite3.Error as e:
            print(f"❌ 資料庫初始化失敗: {e}")
            raise

    def close(self):
        """關閉資料庫連接"""
        if self.conn:
            self.conn.close()
            print("✅ 資料庫連接已關閉")

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

    def add_game(
        self,
        product_id: str,
        ja_title: str,
        ja_price: float,
        ja_currency: str,
        en_title: str = None,
    ) -> int:
        """
        新增遊戲記錄
        
        Args:
            product_id: Xbox API ID
            ja_title: 日本標題
            ja_price: 日本價格
            ja_currency: 日本貨幣
            en_title: 英文標題（選填）
        
        Returns:
            遊戲的 ID
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO games (product_id, ja_title, ja_price, ja_currency, en_title)
                VALUES (?, ?, ?, ?, ?)
            """, (product_id, ja_title, ja_price, ja_currency, en_title))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # 遊戲已存在，直接回傳 ID
            return self.get_game_id(product_id)

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
            status: 狀態 ('available' / 'region-locked' / 'delisted')
            price: 該地區價格
            currency: 該地區貨幣
        """
        cursor = self.conn.cursor()
        
        # 檢查記錄是否存在
        cursor.execute(
            "SELECT id, check_count FROM regions WHERE game_id = ? AND locale = ?;",
            (game_id, locale)
        )
        existing = cursor.fetchone()

        if existing:
            # 更新現有記錄，增加 check_count
            cursor.execute("""
                UPDATE regions
                SET status = ?, price = ?, currency = ?, region_title = ?,
                    last_checked_date = CURRENT_TIMESTAMP, 
                    check_count = check_count + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE game_id = ? AND locale = ?
            """, (status, price, currency, region_title, game_id, locale))
        else:
            # 新增記錄
            cursor.execute("""
                INSERT INTO regions 
                (game_id, locale, region_title, status, price, currency, last_checked_date, check_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 1, CURRENT_TIMESTAMP)
            """, (game_id, locale, region_title, status, price, currency))

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
        threshold_date = (datetime.now() - timedelta(days=days_threshold)).isoformat()

        cursor.execute("""
            SELECT g.id, g.product_id, g.ja_title
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
            SELECT g.product_id, g.ja_title, r.status, r.price, r.currency, r.last_checked_date
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
            }
        return results

    def get_delisted_or_regionlocked_games(self, locale: str) -> List[Tuple[int, str, str]]:
        """
        取得狀態為 delisted 或 region-locked 的遊戲

        用於 browse_all=0 時，只重新檢查有問題的遊戲

        Args:
            locale: 地區代碼

        Returns:
            [(game_id, product_id, ja_title), ...]
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT g.id, g.product_id, g.ja_title
            FROM games g
            INNER JOIN regions r ON g.id = r.game_id
            WHERE r.locale = ? AND r.status IN ('delisted', 'region-locked')
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
        cursor.execute(
            "SELECT status FROM regions WHERE game_id = ? AND locale = ?;",
            (game_id, locale)
        )
        existing = cursor.fetchone()
        old_status = existing['status'] if existing else None

        # 判斷是否有變動
        has_change = old_status != new_status

        if existing:
            # 更新現有記錄
            if has_change:
                # 有變動：增加 status_change_count
                cursor.execute("""
                    UPDATE regions
                    SET status = ?, price = ?, currency = ?, region_title = ?,
                        last_checked_date = CURRENT_TIMESTAMP,
                        check_count = check_count + 1,
                        status_change_count = status_change_count + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE game_id = ? AND locale = ?
                """, (new_status, price, currency, region_title, game_id, locale))
            else:
                # 無變動：保持原狀
                cursor.execute("""
                    UPDATE regions
                    SET price = ?, currency = ?, region_title = ?,
                        last_checked_date = CURRENT_TIMESTAMP,
                        check_count = check_count + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE game_id = ? AND locale = ?
                """, (price, currency, region_title, game_id, locale))
        else:
            # 新增記錄
            cursor.execute("""
                INSERT INTO regions
                (game_id, locale, region_title, status, price, currency, last_checked_date, check_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 1, CURRENT_TIMESTAMP)
            """, (game_id, locale, region_title, new_status, price, currency))

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
            scan_time = datetime.now().isoformat()

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
            {available: N, region-locked: N, delisted: N}
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT r.status, COUNT(*) as count
            FROM regions r
            WHERE r.locale = ?
            GROUP BY r.status;
        """, (locale,))

        stats = {'available': 0, 'region-locked': 0, 'delisted': 0}
        for row in cursor.fetchall():
            stats[row['status']] = row['count']
        return stats

    def export_csv(
        self,
        output_file: str,
        source_locale: str = "ja-JP",
        target_locale: str = "zh-TW",
        mode: str = "limited"
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
            SELECT g.id, g.product_id, g.ja_title, g.ja_price
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
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(output_rows)

        print(f"✅ CSV 已匯出: {output_file}")
        print(f"   共 {len(output_rows)} 筆記錄")

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
    print(summary)

    db.close()
