#!/usr/bin/env python3
"""
Xbox Marketplace Compare - logging 設定
"""

import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """
    初始化全域 logging 設定。

    預設格式只輸出訊息本身，保留目前 CLI 工具的閱讀體驗；
    後續如果需要改成檔案輸出或更詳細的格式，可以集中在這裡調整。
    """
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))

    root_logger.addHandler(handler)
    root_logger.setLevel(level)

