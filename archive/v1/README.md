# Archive 資料夾

此資料夾存放已棄用或舊版本的代碼。

## 內容

- **xbox_compare_v1.py** - 原始版本（已由 V2 取代）
  - 基礎爬蟲功能
  - CSV 輸出
  - 無數據庫持久化
  - 已停用，保留作參考

## 使用

目前請使用根目錄的 **V3 版本**：
```bash
python xbox_compare_v3.py --browse-all 0  # 增量更新
python xbox_compare_v3.py --browse-all 1  # 全量驗證
```

更多詳見根目錄的 `README.md`
