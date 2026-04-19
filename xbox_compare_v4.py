#!/usr/bin/env python3
"""
Xbox 商店遊戲對比工具 - V4 版本
CLI entrypoint only; orchestration lives in pipeline.py.
"""

import argparse

from app_logging import setup_logging
from config import AppConfig
from pipeline import XboxMarketplacePipeline


DEFAULT_CONFIG = AppConfig()


def main():
    """CLI 入口"""
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Xbox 商店遊戲對比工具 V4",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例：

  # 增量模式（推薦日常使用）
  python xbox_compare_v4.py --browse-all 0

  # 全量驗證模式（推薦週期性使用）
  python xbox_compare_v4.py --browse-all 1

  # 全量模式 + 自定義延遲
  python xbox_compare_v4.py --browse-all 1 --delay 2.0

  # 只統計遊戲本體（性能優化）
  python xbox_compare_v4.py --browse-all 1 --filter-dlc 1

  # 統計所有產品（包含 DLC）
  python xbox_compare_v4.py --browse-all 1 --filter-dlc 0

詳細說明見 README.md
        """,
    )
    parser.add_argument(
        "--token", type=str, default=DEFAULT_CONFIG.auth_token, help="Xbox Live XBL3.0 token"
    )
    parser.add_argument("--db", type=str, default=DEFAULT_CONFIG.db_path, help="資料庫路徑")
    parser.add_argument(
        "--browse-all",
        type=int,
        choices=[0, 1],
        default=DEFAULT_CONFIG.browse_all,
        help=f"""掃描模式 (設定值: {DEFAULT_CONFIG.browse_all})
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
        default=DEFAULT_CONFIG.multi_sort,
        help=f"""多排序搜尋開關 (設定值: {DEFAULT_CONFIG.multi_sort})
          0 = 只用預設排序（快速）
          1 = 使用 5 種排序方式提高涵蓋率（慢但完整）""",
    )
    parser.add_argument(
        "--filter-dlc",
        type=int,
        choices=[0, 1],
        default=DEFAULT_CONFIG.filter_dlc,
        help=f"""DLC 過濾開關 (設定值: {DEFAULT_CONFIG.filter_dlc})
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
        default=DEFAULT_CONFIG.max_pages,
        help=f"最多抓取幾頁（測試用，預設 {DEFAULT_CONFIG.max_pages} 頁）",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_CONFIG.request_delay,
        help=f"請求間隔（秒，預設 {DEFAULT_CONFIG.request_delay}）",
    )

    args = parser.parse_args()

    config = AppConfig(
        auth_token=args.token,
        db_path=args.db,
        request_delay=args.delay,
        filter_dlc=args.filter_dlc,
        browse_all=args.browse_all,
        multi_sort=args.multi_sort,
        max_pages=args.max_pages,
    )
    pipeline = XboxMarketplacePipeline(config)
    pipeline.run(
        browse_all=args.browse_all,
        multi_sort=args.multi_sort,
        recheck_delisted=args.recheck,
        max_pages=args.max_pages,
    )


if __name__ == "__main__":
    main()
