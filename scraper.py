#!/usr/bin/env python3
"""
Xbox 遊戲對比工具 - 爬蟲層
負責 API 請求和資料抓取
"""

import base64
import json
import time
import uuid
from typing import Dict, List, Optional, Set
from urllib.parse import quote

import requests

from dlc_identifier import is_game_base as _is_game_base


class XboxScraper:
    """Xbox Store 爬蟲類"""

    def __init__(
        self,
        auth_token: str,
        user_agent: str = None,
        request_delay: float = 1.5,
        filter_dlc: int = 1,
    ):
        """
        初始化爬蟲

        Args:
            auth_token: Xbox Live XBL3.0 token
            user_agent: 自訂 User-Agent
            request_delay: 請求間隔（秒）
            filter_dlc: DLC 過濾開關 (1=只統計遊戲本體, 0=統計所有)
        """
        self.auth_token = auth_token
        self.request_delay = request_delay
        self.filter_dlc = filter_dlc
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
        )

        # API 設定
        self.api_base_url = "https://emerald.xboxservices.com/xboxcomfd/browse"
        self.details_api_url = (
            "https://emerald.xboxservices.com/xboxcomfd/productDetails"
        )
        self.channel_key = "BROWSE_CHANNELID=_FILTERS=PLAYWITH=XBOXONE,XBOXSERIESX|S"

    def _get_headers(self) -> Dict[str, str]:
        """組建 HTTP headers"""
        ms_cv = f"{uuid.uuid4().hex.upper()}.0"

        headers = {
            "User-Agent": self.user_agent,
            "Referer": "https://www.xbox.com/",
            "Accept": "*/*",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Type": "application/json",
            "Origin": "https://www.xbox.com",
            "x-ms-api-version": "1.1",
            "ms-cv": ms_cv,
            "sec-ch-ua-platform": '"Windows"',
            "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
            "sec-ch-ua-mobile": "?0",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "priority": "u=1, i",
        }

        if self.auth_token:
            if not self.auth_token.startswith("XBL3.0"):
                headers["Authorization"] = f"XBL3.0 {self.auth_token}"
            else:
                headers["Authorization"] = self.auth_token

        return headers

    def _build_post_body(self, encoded_ct: str = "", orderby: str = None) -> Dict:
        """
        組建 POST 請求 body

        Args:
            encoded_ct: 分頁 token
            orderby: 排序方式（可選）
                - None: 預設排序
                - "Title+Asc": 標題升序 (A→Z)
                - "Title+Desc": 標題降序 (Z→A)
                - "ReleaseDate+Asc": 發行日期升序（最早優先）
                - "ReleaseDate+Desc": 發行日期降序（最新優先）
                - "Price+Asc": 價格升序（最便宜優先）
                - "Price+Desc": 價格降序（最貴優先）
        """
        filters_json = {
            "PlayWith": {
                "id": "PlayWith",
                "choices": [{"id": "XboxSeriesX|S"}, {"id": "XboxOne"}],
            }
        }
        filters_base64 = base64.b64encode(json.dumps(filters_json).encode()).decode()

        body = {
            "ChannelId": "",
            "ChannelKeyToBeUsedInResponse": self.channel_key,
            "EncodedCT": encoded_ct,
            "Filters": filters_base64,
            "ReturnFilters": False,
        }

        # 加入排序參數（如果有指定）
        if orderby:
            body["OrderBy"] = orderby

        return body

    def _fetch_page(
        self,
        locale: str,
        encoded_ct: str = "",
        orderby: str = None,
        retry_count: int = 0,
    ) -> Optional[Dict]:
        """
        取得單一頁面

        Args:
            locale: 地區代碼 (e.g., 'ja-JP')
            encoded_ct: 分頁 token
            orderby: 排序方式（可選）
            retry_count: 重試次數

        Returns:
            API response 或 None
        """
        headers = self._get_headers()
        payload = self._build_post_body(encoded_ct, orderby)
        url = f"{self.api_base_url}?locale={locale}"

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=10,
            )

            if response.status_code == 401:
                print("❌ 認證失敗 (401) - XBL3.0 token 無效或已過期")
                return None

            if response.status_code == 429:  # Rate Limited
                if retry_count < 3:
                    wait_time = 5 * (retry_count + 1)
                    print(f"⏱️  被限流 (429)，等待 {wait_time} 秒後重試...")
                    time.sleep(wait_time)
                    return self._fetch_page(
                        locale, encoded_ct, orderby, retry_count + 1
                    )
                else:
                    print("❌ 重試次數已達上限")
                    return None

            if response.status_code != 200:
                print(f"❌ API 錯誤 ({response.status_code}): {response.text[:100]}")
                return None

            return response.json()

        except requests.exceptions.Timeout:
            if retry_count < 2:
                print("⏱️  請求超時，重試中...")
                time.sleep(2)
                return self._fetch_page(locale, encoded_ct, orderby, retry_count + 1)
            return None

        except Exception as e:
            print(f"❌ 請求失敗: {e}")
            return None

    def fetch_all_games(
        self,
        locale: str,
        max_pages: Optional[int] = None,
        skip_existing: Optional[Set[str]] = None,
        orderby: str = None,
    ) -> Dict[str, Dict]:
        """
        枚舉某地區的所有遊戲

        Args:
            locale: 地區代碼
            max_pages: 最多抓取幾頁（測試用；None = 全部）
            skip_existing: 要跳過的 product_id 集合（增量更新用）
            orderby: 排序方式（可選，詳見 _build_post_body）

        Returns:
            {product_id: {title, price, currency, slug}, ...}
        """
        games = {}
        page_count = 0
        encoded_ct = ""
        skip_count = 0

        sort_label = f"({orderby})" if orderby else ""
        print(f"\n📥 開始抓取 {locale} 地區遊戲清單 {sort_label}...")
        if skip_existing:
            print(f"   (跳過已存在的 {len(skip_existing)} 款遊戲)")
        print("-" * 60)

        while True:
            page_count += 1

            response = self._fetch_page(locale, encoded_ct, orderby)
            if not response:
                print(f"❌ 第 {page_count} 頁抓取失敗，停止")
                break

            product_summaries = response.get("productSummaries", [])
            page_game_count = 0

            for product in product_summaries:
                product_id = product.get("productId")
                title = product.get("title", "Unknown")

                # 增量更新：跳過已存在的遊戲
                if skip_existing and product_id in skip_existing:
                    skip_count += 1
                    continue

                # 檢查是否有購買價格
                prices = product.get("specificPrices", {}).get("purchaseable", [])

                if prices:
                    price_info = prices[0]
                    price = price_info.get("listPrice", 0)
                    currency = price_info.get("currency", "Unknown")
                    slug = quote(title)

                    # DLC 過濾：根據 filter_dlc 參數決定是否包含
                    is_base_game = self.is_game_base(product)
                    if self.filter_dlc == 1 and not is_base_game:
                        # filter_dlc=1 只統計遊戲本體，跳過 DLC
                        continue
                    elif self.filter_dlc == 0 and is_base_game:
                        # filter_dlc=0 只統計 DLC，跳過遊戲本體
                        continue

                    games[product_id] = {
                        "title": title,
                        "price": price,
                        "currency": currency,
                        "slug": slug,
                        "is_base_game": is_base_game,  # 添加標記
                    }
                    page_game_count += 1

            # 統計資訊
            total_in_region = (
                response.get("channels", {})
                .get(self.channel_key, {})
                .get("totalItems", 0)
            )
            print(f"✅ 第 {page_count} 頁：新增 {page_game_count} 款", end="")
            if skip_existing and skip_count > 0:
                print(f"（跳過 {skip_count} 款）", end="")
            print(f"，累計 {len(games)} / {total_in_region}")

            # 檢查下一頁
            channel_data = response.get("channels", {}).get(self.channel_key, {})
            encoded_ct = channel_data.get("encodedCT", "")

            # 解碼 encodedCT 取得 HasMore
            has_more = False
            if encoded_ct:
                try:
                    ct_decoded = json.loads(base64.b64decode(encoded_ct).decode())
                    has_more = ct_decoded.get("HasMore", False)
                except:
                    has_more = False

            if not has_more:
                print(f"✅ 已抓取完成 ({len(games)} 款新遊戲)")
                break

            if max_pages and page_count >= max_pages:
                print(f"⚠️  達到頁數上限 ({max_pages} 頁)")
                break

            time.sleep(self.request_delay)

        return games

    def fetch_products_by_ids(
        self, product_ids: List[str], locale: str
    ) -> Dict[str, Dict]:
        """
        V3.0 核心方法：透過產品 ID 列表直接進行批量精準查詢

        Args:
            product_ids: ID 列表
            locale: 地區代碼
        """
        if not product_ids:
            return {}

        ids_str = ",".join(product_ids)
        url = f"{self.details_api_url}?locale={locale}&productIds={ids_str}"
        headers = self._get_headers()

        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                print(
                    f"❌ 批量查詢 {locale} 失敗 (Status: {response.status_code}): {response.text[:200]}"
                )
                return {}

            data = response.json()
            results = {}

            # 解析回傳的產品資訊
            # 注意：此 API 回傳的是以 ID 為鍵的字典，例如 {"PID1": {...}, "PID2": {...}}
            for pid, product in data.items():
                if not isinstance(product, dict):
                    continue

                prices = product.get("specificPrices", {}).get("purchaseable", [])
                title = product.get("title", "Unknown")

                results[pid] = {
                    "found": True,
                    "title": title,
                    "slug": quote(title),
                    "purchaseable": len(prices) > 0,
                    "price_list": prices,
                    "is_base_game": self.is_game_base(product),
                }
            return results

        except requests.exceptions.ConnectionError as e:
            print(f"❌ 批量查詢 {locale} 連線錯誤: {e}")
            return {}
        except Exception as e:
            print(f"❌ 批量查詢 {locale} 失敗: {e}")
            return {}

    def check_target_games_v3(
        self, source_games: Dict[str, Dict], target_locale: str, batch_size: int = 5
    ) -> Dict[str, Dict]:
        """
        V3.0 優化版檢查：直接針對 ID 清單向 API 點名，不再掃描分頁
        """
        all_target_data = {}
        product_ids = list(source_games.keys())
        total = len(product_ids)

        print(f"\n🚀 V3 模式：正在精準查詢 {total} 款遊戲在 {target_locale} 的狀態...")

        for i in range(0, total, batch_size):
            batch = product_ids[i : i + batch_size]
            print(f"   進度: {i}/{total} 款...", end="\r")

            batch_results = self.fetch_products_by_ids(batch, target_locale)
            all_target_data.update(batch_results)

            time.sleep(self.request_delay)

        # 補齊 API 完全沒回傳的 ID (視為 delisted)
        for pid in product_ids:
            if pid not in all_target_data:
                all_target_data[pid] = {"found": False, "purchaseable": False}

        return all_target_data

    def fetch_all_games_with_multiple_sorts(
        self,
        locale: str,
        max_pages: Optional[int] = None,
        skip_existing: Optional[Set[str]] = None,
        multi_sort: bool = True,
    ) -> Dict:
        """
        用多種排序方式掃描遊戲，合併結果（去重）

        用於完整掃描時，確保找到所有遊戲（browse_all=1 或 browse_all=0 時的 JP 端）
        分頁邊界問題：某些遊戲可能在某個排序的分頁邊界上被遺漏
        多排序方式可提高涵蓋率

        Args:
            locale: 地區代碼
            max_pages: 最多抓取幾頁
            skip_existing: 要跳過的 product_id 集合
            multi_sort: 是否使用多排序
                - False: 只用預設排序（快速）
                - True: 使用 5 種排序方式（完整但慢）

        Returns:
            {
                'games': {product_id: {title, price, currency, slug, is_base_game}, ...},
                'summary': {
                    'total_games': int,
                    'games_by_sort': {...},
                    'new_games_by_sort': {...}
                }
            }
        """
        all_games = {}
        games_by_sort = {}
        new_games_by_sort = {}

        # 根據 multi_sort 參數決定排序方式
        if multi_sort:
            # 排序方式列表：嘗試多種排序以提高涵蓋率
            sort_methods = [
                None,  # 預設排序
                "Title+Asc",  # 標題升序
                "Title+Desc",  # 標題降序
                "ReleaseDate+Desc",  # 最新發行優先
                "Price+Asc",  # 最便宜優先
            ]
            print(f"\n🔍 多排序方式掃描 {locale} 地區遊戲...")
            print(f"   排序方式: {[s or '預設' for s in sort_methods]}")
            print("=" * 60)
        else:
            # 只用預設排序（快速）
            sort_methods = [None]
            print(f"\n📥 掃描 {locale} 地區遊戲（預設排序）...")
            print("=" * 60)

        for sort_method in sort_methods:
            sort_label = sort_method or "預設"
            if multi_sort:
                print(f"\n🔄 掃描 [{sort_label}]...")

            games = self.fetch_all_games(
                locale,
                max_pages=max_pages,
                skip_existing=skip_existing,
                orderby=sort_method,
            )

            games_by_sort[sort_label] = len(games)

            # 統計新發現的遊戲
            new_count = sum(1 for pid in games if pid not in all_games)
            new_games_by_sort[sort_label] = new_count

            # 合併到 all_games（去重）
            all_games.update(games)

            if multi_sort and sort_method is not None:
                time.sleep(self.request_delay)

        # 統計結果
        print("\n" + "=" * 60)
        if multi_sort:
            print("📊 多排序掃描完成：")
            print("   各排序方式找到的遊戲數：")
            for sort_label, count in games_by_sort.items():
                new_count = new_games_by_sort[sort_label]
                print(f"      [{sort_label}] {count} 款 (新增 {new_count} 款)")
        print(f"   ✅ 總計：{len(all_games)} 款")
        print("=" * 60)

        return {
            "games": all_games,
            "summary": {
                "total_games": len(all_games),
                "games_by_sort": games_by_sort,
                "new_games_by_sort": new_games_by_sort,
            },
        }

    # Removed check_target_games and check_target_games_with_multiple_sorts as they are replaced by check_target_games_v3
    def is_game_base(self, product: Dict) -> bool:
        """
        判斷產品是否為遊戲本體
        調用 dlc_identifier 模組的邏輯
        """
        return _is_game_base(product)

    @staticmethod
    def determine_status(target_game_info: Dict) -> str:
        """
        判斷遊戲在目標地區的狀態

        Args:
            target_game_info: 目標地區遊戲資訊（來自 check_target_games 的結果）

        Returns:
            'available'     - 可購買
            'region-locked' - 有上架但無法購買（地區鎖定）
            'delisted'      - 未出現在目標地區商店
        """
        if not target_game_info.get("found", False):
            return "delisted"
        elif target_game_info.get("purchaseable", False):
            return "available"
        else:
            return "region-locked"


# 測試用
if __name__ == "__main__":
    import os

    # 示例（需要有效的 AUTH_TOKEN）
    auth_token = os.getenv("XBOX_AUTH_TOKEN", "your_token_here")
    scraper = XboxScraper(auth_token)

    # 爬取日本商店的前 2 頁（測試）
    ja_games = scraper.fetch_all_games("ja-JP", max_pages=2)
    print(f"\n取得 {len(ja_games)} 款遊戲")

    # V3 批量檢查台灣狀態
    tw_games = scraper.check_target_games_v3(ja_games, "zh-TW")
    print(f"\n檢查完成，共 {len(tw_games)} 筆")
