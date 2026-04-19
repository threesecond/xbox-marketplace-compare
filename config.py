#!/usr/bin/env python3
"""
Xbox Marketplace Compare - 執行期設定
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    """
    專案執行時使用的設定集合。

    這個物件的目的，是把原本散落在入口程式與流程層中的常數集中管理，
    讓 CLI、pipeline 與未來可能新增的設定檔來源都能共用同一份設定模型。
    """

    # 商店比對的來源與目標地區
    source_locale: str = "ja-JP"
    target_locale: str = "zh-TW"

    # 匯出檔案路徑
    output_csv: str = "all_games.csv"
    output_html: str = "report.html"

    # 資料庫與掃描範圍
    db_path: str = "games.db"
    max_pages: int = 0

    # 執行模式
    browse_all: int = 1
    multi_sort: int = 0
    filter_dlc: int = 1

    # 網路請求相關
    auth_token: str = ""
    request_delay: float = 1.5

    # 重檢策略
    delisted_recheck_days: int = 7
    delisted_confirm_threshold: int = 3
