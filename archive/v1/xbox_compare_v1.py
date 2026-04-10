#!/usr/bin/env python3
"""
Xbox Marketplace Comparison Tool
比較不同地區的 Xbox 遊戲商店，找出特定地區的限定遊戲
"""

import requests
import csv
import json
import time
import sys
import base64
import uuid
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

# ===== 參數設定 =====
SOURCE_LOCALE   = "ja-JP"          # 來源地區（要找的遊戲清單）
TARGET_LOCALE   = "zh-TW"          # 比較地區（找出在此地區不可購買的）
OUTPUT_FILE     = "jp_only_games.csv"
DEBUG           = 1                # 0 = 只列出台灣不能購買的遊戲; 1 = 列舉所有日本和台灣遊戲對照表

AUTH_TOKEN      = "17237963958380704982;eyJhbGciOiJSU0EtT0FFUCIsImVuYyI6IkExMjhDQkMrSFMyNTYiLCJ6aXAiOiJERUYiLCJ4NXQiOiJYQmRHb0FoTDJyb3FQazcwM3NHb1lnT19oM2MiLCJjdHkiOiJKV1QifQ.Gzuw4sP_GpYs7GqamfvzcyF95rjHkTSKJJLukBs7pTHVZqivGHPGdgWkMuRZyiIsyZ8Ib556q00f35AyZi-lJz7mSldeGacld_EmAaNauWiD709MSApKXagVkENhgqoZxu5sIO17MUJsa9MqJKcCdlcQCTb2Mtc6B8tCZVOdlngoGYpy7LZ8abZfk2rVccGuH1bpopD5vLXVHSOrXHPz4NICmMT_TYqxxkHgXeREuETDrJpgPHbYKR9qoTPU53O80ONnVnwwjIevzsyx281WBk1dUteOB91GEZtx0bHE1-txCafNJ_erVz_PBuqiQnTP7pBcc4Izy8PqeOSz3L-mig.V5S5-3H7zI9xFvia4KpDGQ.MBt-LNGDCCgxF3dDHJe-tSfFpm5qPAocmEnWluVuLnhsPoWQl6FWlqA55wHGpVPxUxJte-XQSHkCUruFCgJ_OUWjYMfAcWC97hVXvykLsrdHB5xSxtGNQAc4m147td6ZTMTkJRBgiXEletAs2Lzx5YcygrTAfery-X1hrTEojrwYIhGeyB5bPbuG6ouqmkjPIcJRbegKJ76Z4AWSgym_dMDAQb5l1lFDDojIKOgmebRBbtnYdc8gvI_Oe8UTSnHIuVUNZjgs41_gpCGVa006rhqf3eABJKZVBvX0UNgWcUcQy-qiPAHfCz3y7mW0-j0-7bAhBd-Gdcb1DIoBzzaMla9kN51cwgUnuWo2DHjADlNHWdPN-8zvkUMHAS7_dNX_XCsHLWzHoP_GUoaqMZRFdGDLamVFb08S4nkJE5Qo_F2AP5OQpIk5L8xDtEWz0kpF14a5Q9FQOU7yk9BNFcIDp6QlK_lmJ0Pz_XrY4-RVpOa_dCOKTGHJJ-Sia0XzGkKnd_ubAmzZQnbCq_C72spiJEVg_I-zyIJgVweqoAP5dIIVUEf-02ETXusy2Yiv1rO0BYs68SfM0cHd1ZUP97vyuyviin_koeOf0D5IIavB-vvhSfSM85D7G9sJL6e5t5BWCvdn2fql9-zw1O1ZyIqAG8Sa4tuUUXA5RxmfYfiPw9HDJgdC_RrQqGm4IBt5pRp2UPTkqgkQiL9YPS7wIn6Jr43r08CQ277VxCHBT7dfaTnmDhKiOskZCJewzCo9oVFHlzWyGp68EUVGdMpn8EaT_fsy-6FmgWVNNORjuuUJNlH1QNozdl6AGh4R2kBMk2K2A4lBC__tG5H2SOBY1S-6ujCKBUkpTs3g8_fEK9PAqXaDiMhwT1dKXZcjI93At9eRu9MDsd_7aWMXTDeJEDnN6rke6RMwj3_ZBkihSS2EVz5s3MCUMOJeNfi9hWSYxj40gMSR9WLbKwZGEhA9RudOHQEJKNKwx8h_xqKzbBl7mRcExfmO2INSN23URFOZplfInTVUYS2jEF6CxhqnljN-aDYvHPmq49VAOaBoCXftVpBeowkbjFMsiRjP68Fju_PoiWGu80q5Tig_LJburpJBrGKXz-9unob5xt3i6h85Uwk5rUSCcWjJWhD6TsfdudY1vlzL9udWvLl3jGqbRAJz-LQ4ZL1PfyTrg5CdmvlePuHTyj9cvm4bdZ0yJWm9dxiZWWeiprthbBOWmFD--ECZhDK1WzU_T0X3JAF01yMnz7Kx0-MjOAyWlbODLsb_RLru7Zo9sYu53LdyuyNzXmcz0Dxj9iukcGD_9fhdNgVLBJU9Uh_tSKsu1EhzvSLWGYOG4ooVIWYULcCErSocVl-fTDJizZlViJX0j4dg_CXv-B7NrZta964v9dUjEpxFUN4td04cFoMczyTd8Mp-aGrzL3HnBJBZ6gT8bIUZ5HiDN86Ggcn1y-7rQ1tdoNiWxkP0bhbZZcq3yZhT2TvDLiJUPZCuW3ptwtcfTWrQLCaGCV_QsPgN9_vYyo0Lj6hIrZfTklgBxW6D_m4b157I6vm7KD90nKiSQdC35wglkMWWSvELWxie8jfThy4rt3pJuc_IFx1aqw6AQN0g6P14vLFlqAaco5wHJucG1VfH1_zcHBOY4-OYtRo1YUjpWcZmgTf5JZGRIv_AJol8zQe5l7pM06sWC5QO_bHvttObPk_rgfA_29_hFJEWa7sgDe7NRAeumuyYm4GSET_A2j6-gzCD9yPPg1Z0wWe1SbYC2lGLDsc.ZQ9No3B5gcntk5sFf4a6xB5-WWM68B7jYIoPeeNfMDI"               # 必須填入！從 DevTools 複製 curl 的 Authorization header 中的 XBL3.0 x=... 整個值
REQUEST_DELAY   = 1.5              # 每次請求間隔秒數（建議 1~2 秒）
USER_AGENT      = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
# ====================

API_BASE_URL = "https://emerald.xboxservices.com/xboxcomfd/browse"
CHANNEL_KEY = "BROWSE_CHANNELID=_FILTERS=PLAYWITH=XBOXONE,XBOXSERIESX|S"
CHANNEL_ID = "browsegames"


def get_headers() -> Dict[str, str]:
    """組建 HTTP headers"""
    # MS-CV 是微軟的追踪 ID，每次請求生成新的
    ms_cv = f"{uuid.uuid4().hex.upper()}.0"

    headers = {
        "User-Agent": USER_AGENT,
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

    if AUTH_TOKEN:
        headers["Authorization"] = f"XBL3.0 {AUTH_TOKEN}" if not AUTH_TOKEN.startswith("XBL3.0") else AUTH_TOKEN

    return headers


def build_post_body(encoded_ct: str = "") -> Dict:
    """組建 POST body"""
    # Filters 的 JSON 結構（然後 base64 編碼）
    filters_json = {
        "PlayWith": {
            "id": "PlayWith",
            "choices": [
                {"id": "XboxSeriesX|S"},
                {"id": "XboxOne"}
            ]
        }
    }
    filters_base64 = base64.b64encode(json.dumps(filters_json).encode()).decode()

    return {
        "ChannelId": "",
        "ChannelKeyToBeUsedInResponse": CHANNEL_KEY,
        "EncodedCT": encoded_ct,
        "Filters": filters_base64,
        "ReturnFilters": False,
    }


def fetch_games_page(locale: str, encoded_ct: str = "", retry_count: int = 0) -> Optional[Dict]:
    """
    取得單一頁面的遊戲列表

    Args:
        locale: 地區代碼 (e.g., "ja-JP", "zh-TW")
        encoded_ct: 分頁 token
        retry_count: 重試次數

    Returns:
        API response dict，或 None 若失敗
    """
    headers = get_headers()
    payload = build_post_body(encoded_ct)
    url = f"{API_BASE_URL}?locale={locale}"

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=10,
        )

        # 狀態碼檢查
        if response.status_code == 401:
            print("❌ 認證失敗 (401) - XBL3.0 token 無效或已過期")
            print("   請重新從 DevTools 複製最新的 token")
            return None

        if response.status_code == 429:  # Rate Limited
            if retry_count < 3:
                wait_time = 5 * (retry_count + 1)
                print(f"⏱️  被限流 (429)，等待 {wait_time} 秒後重試...")
                time.sleep(wait_time)
                return fetch_games_page(locale, encoded_ct, retry_count + 1)
            else:
                print("❌ 重試次數已達上限，放棄此頁")
                return None

        if response.status_code != 200:
            print(f"❌ API 錯誤：{response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return None

        return response.json()

    except requests.exceptions.Timeout:
        print(f"⏱️  請求超時 (10秒)，重試中...")
        if retry_count < 2:
            time.sleep(2)
            return fetch_games_page(locale, encoded_ct, retry_count + 1)
        return None

    except Exception as e:
        print(f"❌ 請求失敗：{e}")
        return None


def enumerate_all_games(locale: str, max_pages: Optional[int] = None) -> Dict[str, Dict]:
    """
    枚舉某地區的所有遊戲

    Args:
        locale: 地區代碼
        max_pages: 最多抓取幾頁（用於測試；None = 全部）

    Returns:
        {productId: {title, price, currency}}
    """
    games = {}
    page_count = 0
    encoded_ct = ""

    print(f"\n📥 開始抓取 {locale} 地區遊戲清單...")
    print("-" * 60)

    while True:
        page_count += 1

        # 取得分頁
        response = fetch_games_page(locale, encoded_ct)
        if not response:
            print(f"❌ 第 {page_count} 頁抓取失敗，停止")
            break

        # 解析 productSummaries
        product_summaries = response.get("productSummaries", [])
        page_game_count = 0

        for product in product_summaries:
            product_id = product.get("productId")
            title = product.get("title", "Unknown")

            # 檢查是否有購買價格
            prices = product.get("specificPrices", {}).get("purchaseable", [])

            if prices:
                # 取第一個價格
                price_info = prices[0]
                price = price_info.get("listPrice", 0)
                currency = price_info.get("currency", "Unknown")
                
                # 生成 URL slug（遊戲名稱的 URL 編碼）
                slug = quote(title)
                
                games[product_id] = {
                    "title": title,
                    "price": price,
                    "currency": currency,
                    "slug": slug,
                }
                page_game_count += 1

        total_in_region = response.get("channels", {}).get(CHANNEL_KEY, {}).get("totalItems", 0)
        print(f"✅ 第 {page_count} 頁：抓取 {page_game_count} 筆，累計 {len(games)} / {total_in_region}")

        # 檢查是否有下一頁
        channel_data = response.get("channels", {}).get(CHANNEL_KEY, {})
        encoded_ct = channel_data.get("encodedCT", "")

        # 解碼 encodedCT 來獲得 HasMore 標記
        has_more = False
        if encoded_ct:
            try:
                ct_decoded = json.loads(base64.b64decode(encoded_ct).decode())
                has_more = ct_decoded.get("HasMore", False)
            except:
                has_more = False

        if not has_more:
            print(f"✅ 已抓取全部遊戲 ({len(games)} 筆)")
            break

        # 檢查頁數限制（測試用）
        if max_pages and page_count >= max_pages:
            print(f"⚠️  達到頁數上限 ({max_pages} 頁)，停止")
            break

        # 延遲
        time.sleep(REQUEST_DELAY)

    return games


def check_game_in_target(game_id: str, target_locale: str) -> bool:
    """
    檢查遊戲在目標地區是否可購買

    Returns:
        True = 可購買, False = 不可購買或查詢失敗
    """
    response = fetch_games_page(target_locale)

    if not response:
        return False

    # 查找此 product_id
    for product in response.get("productSummaries", []):
        if product.get("productId") == game_id:
            prices = product.get("specificPrices", {}).get("purchaseable", [])
            return len(prices) > 0

    return False


def batch_check_target_games(source_games: Dict, target_locale: str) -> Dict[str, Dict]:
    """
    批量檢查遊戲在目標地區是否可購買

    使用相同的 browse API，逐頁抓取目標地區遊戲，比對是否有購買價格
    """
    target_games = {}
    page_count = 0
    encoded_ct = ""

    print(f"\n📥 開始檢查 {target_locale} 地區可購買情況...")
    print("-" * 60)

    while True:
        page_count += 1

        response = fetch_games_page(target_locale, encoded_ct)
        if not response:
            print(f"❌ 第 {page_count} 頁抓取失敗，停止")
            break

        page_game_count = 0

        for product in response.get("productSummaries", []):
            product_id = product.get("productId")

            # 只記錄源地區存在的遊戲
            if product_id in source_games:
                prices = product.get("specificPrices", {}).get("purchaseable", [])

                # 檢查 availabilitySummaries 獲取更多狀態信息
                title = product.get("title", "Unknown")
                slug = quote(title)  # 生成 URL slug
                availability_summary = {}

                # 從 response 的 availabilitySummaries 找這個遊戲
                for avail in response.get("availabilitySummaries", []):
                    if avail.get("productId") == product_id:
                        availability_summary = avail
                        break

                target_games[product_id] = {
                    "found": True,
                    "title": title,
                    "slug": slug,
                    "purchaseable": len(prices) > 0,
                    "price_list": prices,
                    "availability_summary": availability_summary,
                }
                page_game_count += 1

        total_in_region = response.get("channels", {}).get(CHANNEL_KEY, {}).get("totalItems", 0)
        print(f"✅ 第 {page_count} 頁：檢查 {page_game_count} 筆")

        # 檢查下一頁
        channel_data = response.get("channels", {}).get(CHANNEL_KEY, {})
        encoded_ct = channel_data.get("encodedCT", "")

        # 解碼 encodedCT 來獲得 HasMore 標記
        has_more = False
        if encoded_ct:
            try:
                ct_decoded = json.loads(base64.b64decode(encoded_ct).decode())
                has_more = ct_decoded.get("HasMore", False)
            except:
                has_more = False

        if not has_more:
            print(f"✅ 已檢查完目標地區")
            break

        time.sleep(REQUEST_DELAY)

    return target_games


def determine_status(target_info: Dict) -> str:
    """
    根據目標地區的信息判斷遊戲狀態

    Returns:
        available: 可購買
        region-locked: 存在但無價格（地區限定）
        delisted: 完全找不到（已下架）
    """
    if not target_info.get("found", False):
        return "delisted"
    elif target_info.get("purchaseable", False):
        return "available"
    else:
        return "region-locked"


def write_csv(
    source_games: Dict,
    target_games: Dict,
    source_locale: str,
    target_locale: str,
    output_file: str,
    debug: int = 0,
):
    """
    輸出 CSV

    debug=0: 只列出目標地區不能購買的遊戲（目標地區欄位留空）
    debug=1: 列舉所有源地區遊戲和目標地區的對照表
    """

    output_rows = []

    if debug == 0:
        # 模式 0：只列出目標地區無法購買的遊戲
        for product_id, source_info in source_games.items():
            target_info = target_games.get(product_id, {})

            # 只列出在目標地區不可購買的遊戲
            if not target_info.get("purchaseable", False):
                source_slug = source_info.get("slug", quote(source_info["title"]))
                source_url = f"https://www.xbox.com/{source_locale.lower()}/games/store/{source_slug}/{product_id}"
                target_url = f"https://www.xbox.com/{target_locale.lower()}/games/store/{source_slug}/{product_id}"
                status = determine_status(target_info)

                output_rows.append({
                    "productId": product_id,
                    f"{source_locale}_title": source_info["title"],
                    f"{source_locale}_price": source_info["price"],
                    f"{target_locale}_title": "",
                    f"{target_locale}_price": "",
                    f"{target_locale}_status": status,
                    f"{source_locale}_url": source_url,
                    f"{target_locale}_url": target_url,
                })
    else:
        # 模式 1：列舉所有源地區遊戲和目標地區對照
        for product_id, source_info in source_games.items():
            target_info = target_games.get(product_id, {})

            source_slug = source_info.get("slug", quote(source_info["title"]))
            source_url = f"https://www.xbox.com/{source_locale.lower()}/games/store/{source_slug}/{product_id}"
            
            # 目標地區的 slug（如果有找到遊戲就用目標地區的標題，否則用源地區的）
            if target_info.get("found", False):
                target_slug = target_info.get("slug", quote(target_info.get("title", source_info["title"])))
            else:
                target_slug = source_slug
            
            target_url = f"https://www.xbox.com/{target_locale.lower()}/games/store/{target_slug}/{product_id}"

            # 目標地區的價格
            target_title = target_info.get("title", "")
            target_price = ""
            if target_info.get("purchaseable", False) and target_info.get("price_list"):
                target_price = target_info["price_list"][0].get("listPrice", "")

            status = determine_status(target_info)

            output_rows.append({
                "productId": product_id,
                f"{source_locale}_title": source_info["title"],
                f"{source_locale}_price": source_info["price"],
                f"{target_locale}_title": target_title,
                f"{target_locale}_price": target_price,
                f"{target_locale}_status": status,
                f"{source_locale}_url": source_url,
                f"{target_locale}_url": target_url,
            })

    # 寫 CSV
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

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    # 統計
    print(f"\n✅ 結果已保存：{output_file}")
    if debug == 0:
        status_counts = {}
        for row in output_rows:
            status = row[f"{target_locale}_status"]
            status_counts[status] = status_counts.get(status, 0) + 1

        print(f"   找到 {len(output_rows)} 款 {source_locale} 限定遊戲：")
        print(f"      - region-locked（地區限定）: {status_counts.get('region-locked', 0)} 款")
        print(f"      - delisted（已下架）: {status_counts.get('delisted', 0)} 款")
    else:
        status_counts = {}
        for row in output_rows:
            status = row[f"{target_locale}_status"]
            status_counts[status] = status_counts.get(status, 0) + 1

        print(f"   總遊戲數：{len(output_rows)}")
        print(f"      - available（可購買）: {status_counts.get('available', 0)} 款")
        print(f"      - region-locked（地區限定）: {status_counts.get('region-locked', 0)} 款")
        print(f"      - delisted（已下架）: {status_counts.get('delisted', 0)} 款")


def main():
    print("🎮 Xbox 商店遊戲對比工具")
    print("=" * 60)
    print(f"源地區：{SOURCE_LOCALE}")
    print(f"目標地區：{TARGET_LOCALE}")
    print(f"輸出檔案：{OUTPUT_FILE}")
    print(f"請求延遲：{REQUEST_DELAY} 秒")
    debug_mode = "完整對照表 (所有遊戲)" if DEBUG == 1 else "限定遊戲清單"
    print(f"模式：{debug_mode} (DEBUG={DEBUG})")
    print("=" * 60)

    # 檢查認證 token
    if not AUTH_TOKEN:
        print("❌ 錯誤：AUTH_TOKEN 未設定")
        print("\n請按以下步驟設定：")
        print("1. 打開 Chrome DevTools (F12)")
        print("2. 進入 Network 標籤")
        print("3. 訪問 https://www.xbox.com/ja-JP/games/all-games")
        print("4. 找到 browse?locale=ja-JP 的 POST 請求")
        print("5. 右鍵 → Copy → Copy as cURL")
        print("6. 找到 Authorization: XBL3.0 x=... 這行")
        print("7. 複製 'XBL3.0 x=...' 後面的所有內容（不含 XBL3.0 前綴）")
        print("8. 貼到腳本頂部的 AUTH_TOKEN = \"...\"")
        sys.exit(1)

    # Phase 1: 抓取源地區所有遊戲
    source_games = enumerate_all_games(SOURCE_LOCALE)

    if not source_games:
        print("❌ 無法抓取源地區遊戲，終止")
        sys.exit(1)

    # Phase 2: 檢查目標地區
    target_games = batch_check_target_games(source_games, TARGET_LOCALE)

    # 標記在源地區有但在目標地區完全找不到的遊戲
    for product_id in source_games:
        if product_id not in target_games:
            source_info = source_games[product_id]
            target_games[product_id] = {
                "found": False,
                "title": "N/A",
                "slug": source_info.get("slug", quote(source_info["title"])),  # 使用源地區的 slug
                "purchaseable": False,
                "price_list": [],
                "availability_summary": {},
            }

    # Phase 3: 輸出結果
    write_csv(source_games, target_games, SOURCE_LOCALE, TARGET_LOCALE, OUTPUT_FILE, DEBUG)

    print("\n✅ 完成！")


if __name__ == "__main__":
    main()
