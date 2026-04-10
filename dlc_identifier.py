#!/usr/bin/env python3
"""
Xbox 遊戲與 DLC 識別模組
負責判定產品是否為遊戲本體
"""

from typing import Dict, List

# 可自行添加的日文 DLC 關鍵字
DLC_KEYWORDS_JA = [
    "追加コンテンツ", "パック", "シーズンパス", "通貨", 
    "ポイント", "アップグレード", "拡張", "セット", "アイテム"
]

# 可自行添加的英文 DLC 關鍵字
DLC_KEYWORDS_EN = [
    "DLC", "Add-on", "Add-in", "Season Pass", "Currency", 
    "Points", "Upgrade", "Expansion", "Pack", "Content", "Virtual"
]

# 同捆包關鍵字（優先判定為遊戲本體）
# 即使標題含 DLC 關鍵字，只要是 Bundle 就視為本體產品
BUNDLE_KEYWORDS = ["Bundle", "バンドル", "Collection", "コレクション", "エディション", "Edition", "スタンダード"]

def is_game_base(product: Dict) -> bool:
    """
    根據 Xbox API 回傳的資訊判定是否為遊戲本體
    
    邏輯優先級：
    1. 非 Game 類型 -> False
    2. 含 Bundle/Collection 關鍵字 -> True (同捆包視為本體)
    3. 含 Game Pass 關聯欄位 -> True (視為本體)
    4. 含 DLC 關鍵字 -> False
    5. 其餘 -> True
    """
    # 1. 基礎類型檢查
    if product.get("productKind") != "Game":
        return False

    title = product.get("title", "")
    categories = product.get("categories", [])
    
    # 將所有標籤與標題合併轉小寫以便比對
    search_text = (title + " " + " ".join(categories)).lower()

    # 2. 優先白名單：同捆包 (Bundle) 
    if any(k.lower() in search_text for k in BUNDLE_KEYWORDS):
        return True

    # 3. 強力白名單：Game Pass 關聯
    # 通常只有遊戲本體會出現在 Game Pass 欄位中
    if product.get("optimalSatisfyingPassId") or product.get("includedWithPassesProductIds"):
        return True

    # 4. 黑名單：排除 DLC 關鍵字
    all_dlc_keywords = DLC_KEYWORDS_JA + DLC_KEYWORDS_EN
    for keyword in all_dlc_keywords:
        if keyword.lower() in search_text:
            return False

    # 5. 預設判定為遊戲本體
    return True