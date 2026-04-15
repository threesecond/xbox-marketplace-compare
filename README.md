# Xbox 商店遊戲對比工具 - V3 版本

支持增量更新、資料持久化、精準批量查詢、DLC 過濾與 HTML 報表的性能優化版本。

## 📦 核心功能

### 數據管理
✅ **SQLite 資料庫持久化** - 遊戲資訊永久保存，支持 2000+ 款遊戲  
✅ **DLC 識別與過濾** - 自動識別遊戲本體與 DLC，支持自定義關鍵字  
✅ **狀態變動檢測** - 自動追踪遊戲狀態變化（available ↔️ delisted/region-locked）  
✅ **掃描時間戳記錄** - 記錄每次掃描的時間，便於審計和追蹤

### 掃描策略
✅ **精準批量查詢 (V3 核心)** - 透過 Product ID 列表直接查詢目標商店，效率提升 25 倍  
✅ **雙模式掃描** - 增量模式（快速）+ 全量驗證模式（完整）  
✅ **多排序掃描策略** - 5 種排序方式確保涵蓋率（預設/標題升序/標題降序/發行日期/價格）  
✅ **可配置的多排序開關** - 根據需求選擇快速或完整掃描  
✅ **智能重檢機制** - 只重檢 delisted/region-locked 遊戲，跳過已確認 available 的遊戲

### 輸出和報告
✅ **HTML 可視化報表** - 生成漂亮的交互式網頁報告  
✅ **統計圖表** - 圓餅圖、長條圖等數據視覺化  
✅ **CSV 輸出** - 與 V1 相同的 CSV 格式相容  
✅ **實時掃描統計** - 顯示每種排序方式發現的新遊戲數  

## 🚀 快速開始

### 1. 安裝依賴

```bash
pip install requests jinja2
```

### 2. 配置設定

打開 `xbox_compare_v3.py`，在 `# ===== 設定 =====` 區域修改：

```python
# ===== 設定 =====
SOURCE_LOCALE = "ja-JP"         # 源地區（日本）
TARGET_LOCALE = "zh-TW"         # 目標地區（台灣）
FILTER_DLC = 1                  # 1=只統計遊戲本體（推薦），0=包含所有產品
MAX_PAGES = 0                   # 最多掃描頁數，0=全量掃描（僅作用於源地區掃描）
OUTPUT_HTML = "report.html"
DB_PATH = "games.db"

# 掃描模式：0=增量（日常快速），1=全量驗證（定期完整）
BROWSE_ALL = 1

# 多排序搜尋：0=預設排序（快速），1=5種排序（完整）
MULTI_SORT = 0

# AUTH_TOKEN 為選填，留空即可匿名執行
AUTH_TOKEN = ""

REQUEST_DELAY = 1.5  # 請求延遲（秒）
```

> **AUTH_TOKEN 已不再必填。** V3 改用 Microsoft DisplayCatalog 公開 API 查詢目標地區狀態，JP browse API 也支援匿名存取，直接留空執行即可。

### 3. 執行

```bash
# 使用設定的預設值
python xbox_compare_v3.py

# 或用命令行參數覆蓋
python xbox_compare_v3.py --browse-all 0 --multi-sort 0

# 測試模式：只掃描前 1 頁（預設）
python xbox_compare_v3.py --max-pages 1

# 完整掃描：掃描所有頁面
python xbox_compare_v3.py --max-pages 0
```

## 📊 輸出結果

執行後會產生：

| 檔案 | 說明 |
|------|------|
| `games.db` | SQLite 資料庫（自動建立） |
| `jp_only_games.csv` | CSV 對照表（與 V1 相同格式） |
| `report.html` | HTML 可視化報表 |

用瀏覽器打開 `report.html` 即可查看。

## 🎯 掃描模式（browse_all）

### 模式 0: 增量更新 (推薦日常使用) ⭐

```bash
python xbox_compare_v3.py --browse-all 0
```

**特點：**
- 日本 (JP): 用**多排序方式**掃描找新遊戲
- 台灣 (TW): 只重檢 `delisted` 或 `region-locked` 的遊戲
- **跳過** 已確認為 `available` 的遊戲
- **執行時間:** 快 (~5-10 分鐘，取決於新遊戲數量)

**適用場景：**
- ✅ 日常增量更新
- ✅ 快速發現新遊戲
- ✅ 檢查被下架的遊戲是否重新上架

---

### 模式 1: 全量驗證 (推薦週期性使用)

```bash
python xbox_compare_v3.py --browse-all 1
```

**特點：**
- 日本 (JP): 用**多排序方式**掃描所有遊戲
- 台灣 (TW): 用**多排序方式**掃描所有遊戲
- 只寫入**有狀態變動**的遊戲（減少 DB 寫入）
- **執行時間:** 慢 (~30-60 分鐘)

**適用場景：**
- ✅ 週期性完整驗證（每週/每月）
- ✅ 確保數據完整性
- ✅ 發現被遺漏的狀態變動

---

### 多排序搜尋 (multi_sort 參數)

可透過 `multi_sort` 參數控制是否使用多排序掃描：

#### multi_sort = 0（只用預設排序，推薦日常使用）
```bash
python xbox_compare_v3.py --multi-sort 0  # 快速，1-2 分鐘內完成
```

- 只掃描 1 種排序（預設）
- **執行時間短**（5-10 分鐘變成 1-2 分鐘）
- 適合日常增量更新
- **API 調用量少**，不容易被限流

#### multi_sort = 1（多排序掃描，推薦定期使用）
```bash
python xbox_compare_v3.py --multi-sort 1  # 完整但慢，30-60 分鐘
```

用 5 種排序方式重複掃描：

1. **預設排序**
2. **Title+Asc** (標題升序 A→Z)
3. **Title+Desc** (標題降序 Z→A)
4. **ReleaseDate+Desc** (最新發行優先)
5. **Price+Asc** (最便宜優先)

**為什麼需要多排序？**
- 某些遊戲可能在某個排序方式的分頁邊界上被遺漏
- 用 5 種排序方式的去重結果更完整

**掃描統計輸出：**
```
🔍 多排序方式掃描 ja-JP 地區遊戲...
   排序方式: ['預設', 'Title+Asc', 'Title+Desc', 'ReleaseDate+Desc', 'Price+Asc']
============================================================
📊 多排序掃描完成：
   各排序方式找到的遊戲數：
      [預設] 2150 款 (新增 15 款)
      [Title+Asc] 2158 款 (新增 23 款)
      [Title+Desc] 2155 款 (新增 8 款)
      [ReleaseDate+Desc] 2140 款 (新增 2 款)
      [Price+Asc] 2162 款 (新增 28 款)
   ✅ 總計：2190 款
============================================================
```

---

### 推薦搭配組合

| 場景 | browse_all | multi_sort | 執行時間 | 說明 |
|------|-----------|-----------|--------|------|
| 日常快速更新 | 0 | 0 | 1-2 分鐘 | 最快，輕負載 |
| 日常完整檢查 | 0 | 1 | 10-15 分鐘 | 日常推薦 |
| 定期驗證 | 1 | 0 | 10-15 分鐘 | 全掃但單排序 |
| 定期完整驗證 | 1 | 1 | 60+ 分鐘 | 最完整 |

---

## 🎯 其他進階用法

### 只測試前 N 頁

```bash
python xbox_compare_v3.py --browse-all 1 --max-pages 2
```

> `--max-pages` 預設為 `1`，如果想抓取全部頁面請指定 `--max-pages 0`。

### 自訂資料庫路徑

```bash
python xbox_compare_v3.py --browse-all 0 --db custom_db.db
```

### 自訂請求延遲

```bash
python xbox_compare_v3.py --browse-all 1 --delay 2.0
```

### 完整參數列表

```bash
python xbox_compare_v3.py --help

optional arguments:
  --token TOKEN        Xbox Live XBL3.0 token
  --db DB              資料庫路徑（預設：games.db）
  
  --browse-all {0,1}   掃描模式 (預設: 0)
                       0 = 增量模式（日常快速更新）
                         - JP: 用配置的排序方式找新遊戲
                         - TW: 只重檢 delisted/region-locked
                       1 = 全量驗證（定期完整檢查）
                         - JP/TW: 都用配置的排序方式掃描
                         - 只寫入有狀態變動的記錄
  
  --multi-sort {0,1}   多排序搜尋開關 (預設: 0)
                       0 = 預設排序（快速，1-2 分鐘）
                       1 = 5 種排序（完整，30-60 分鐘）
  
  --recheck            （已過時）重檢 delisted 遊戲
  --max-pages N        最多抓取幾頁（測試用，預設 1；0 = 抓全部頁面）
  --delay SECONDS      請求間隔（秒，預設 1.5）
```

**注意：** 命令行參數會覆蓋設定文件中的預設值

## 📚 檔案結構

```
xbox-marketplace-compare/
├── xbox_compare_v3.py           # V3 主程序 ⭐
├── database.py                  # 資料庫層
├── scraper.py                   # 爬蟲層
├── html_generator.py            # HTML 報表生成器
├── games.db                     # 資料庫（首次運行時建立）
├── jp_only_games.csv            # 輸出 CSV
├── report.html                  # 輸出 HTML 報表
├── README.md                    # 本文件
├── archive/                     # 舊版本備份
│   ├── xbox_compare_v1.py       # V1 原始版本（已棄用）
│   └── README.md                # Archive 說明
└── .claude/
    └── projects/
        └── memory/              # 記憶系統
```

## 💡 使用建議

### 首次運行

```bash
# 首次必須用全量模式（資料庫為空）
python xbox_compare_v3.py --browse-all 1 --multi-sort 1
```

- 執行時間: 60+ 分鐘
- 建立完整的 SQLite 資料庫
- 掃描所有遊戲，進行多排序驗證
- 生成 CSV 和 HTML 報表

### 日常快速運行（推薦每日）

```bash
# 最快的增量更新
python xbox_compare_v3.py --browse-all 0 --multi-sort 0
```

- 執行時間: 1-2 分鐘
- 自動偵測 JP 新增遊戲
- 只重檢 TW 的 delisted/region-locked 遊戲
- 用預設排序（最小化 API 調用）
- 不容易被限流

### 日常完整運行（推薦每週）

```bash
# 完整的增量更新
python xbox_compare_v3.py --browse-all 0 --multi-sort 1
```

- 執行時間: 10-15 分鐘
- 自動偵測 JP 新增遊戲（用 5 種排序）
- 只重檢 TW 的 delisted/region-locked 遊戲（用 5 種排序）
- 提高涵蓋率，避免遺漏
- 推薦：每週執行一次

### 定期完整驗證（推薦每月）

```bash
# 完整的全量掃描
python xbox_compare_v3.py --browse-all 1 --multi-sort 1
```

- 執行時間: 60+ 分鐘
- 完整掃描 JP 和 TW 所有遊戲
- 用 5 種排序方式確保完整性
- 只寫入有狀態變動的記錄
- 記錄本次掃描的時間戳
- 推薦：每月執行一次

### 推薦運行計劃

| 時間 | 命令 | 執行時間 | 說明 |
|------|------|--------|------|
| 首次 | `--browse-all 1 --multi-sort 1` | 60+ 分鐘 | 建立完整數據庫 |
| 每日 | `--browse-all 0 --multi-sort 0` | 1-2 分鐘 | 快速增量更新（推薦） |
| 每週 | `--browse-all 0 --multi-sort 1` | 10-15 分鐘 | 完整增量檢查 |
| 每月 | `--browse-all 1 --multi-sort 1` | 60+ 分鐘 | 完整驗證（可選） |

### 報表功能
- 📊 **統計卡片** - 快速查看遊戲分佈
- 📈 **圓餅圖** - 視覺化狀態比例
- 🔍 **搜尋/排序** - DataTables 提供強大的表格功能
- 🔗 **商店連結** - 點擊直接打開 Xbox Store

## ⚠️ 常見問題

### Q: 我應該用哪個模式？
A:
- **首次運行**：`--browse-all 1 --multi-sort 1`（完整建立）
- **日常快速**：`--browse-all 0 --multi-sort 0`（1-2 分鐘）
- **日常完整**：`--browse-all 0 --multi-sort 1`（10-15 分鐘）
- **定期驗證**：`--browse-all 1 --multi-sort 1`（60+ 分鐘）

**簡單判斷：**
- 想快速更新？用 `--multi-sort 0`
- 想完整掃描？用 `--multi-sort 1`

### Q: browse_all=0 時為什麼 JP 也要多排序掃描？
A: 因為 JP 是數據源，可能存在 API 分頁邊界問題，導致新遊戲遺漏。用多排序方式掃描可以確保找到所有新遊戲。

### Q: 為什麼 browse_all=1 很慢？
A:
- 需要掃描**所有**遊戲（可能 2000+ 款）
- 如果用多排序 (multi_sort=1)，用 **5 種排序方式**掃描（5 倍 API 調用）
- 總計 10,000+ 個 API 請求
- 預留了 1.5 秒/請求的延遲（避免被限流）

### Q: 多排序掃描真的能找到更多遊戲嗎？
A: 是的。根據測試，不同排序方式可能在分頁邊界上遺漏遊戲。多排序方式去重結果會比單排序多 20-30 款遊戲。

### Q: multi_sort 參數有什麼用？
A:
- **multi_sort=0**（預設排序）：快速，適合日常快速檢查（1-2 分鐘）
- **multi_sort=1**（5 種排序）：完整但慢，適合需要完整性的場景

**實際差異：**
```
--browse-all 0 --multi-sort 0  →  1-2 分鐘（最快）
--browse-all 0 --multi-sort 1  →  10-15 分鐘（推薦日常）
--browse-all 1 --multi-sort 0  →  10-15 分鐘（全掃單排）
--browse-all 1 --multi-sort 1  →  60+ 分鐘（最完整）
```

### Q: 遇到被限流怎麼辦？
A:
1. 用 `--multi-sort 0` 減少 API 調用
2. 增加延遲：`--delay 2.0` 或 `--delay 3.0`
3. 改用 `--browse-all 0` 避免掃描所有遊戲

### Q: 需要 Token 嗎？
A: 不需要。V3 已改用 Microsoft DisplayCatalog 公開 API，`AUTH_TOKEN` 留空即可正常執行。

### Q: 資料庫損壞了？
A: 直接刪除 `games.db`，下次運行會自動重建。注意：首次運行必須用 `--browse-all 1`。

### Q: 能支持其他地區嗎？
A: 目前只支持日本 ↔ 台灣，後續版本計畫擴展。

### Q: 報表太慢了？
A: 這是正常的。如果頻繁更新報表，建議只在必要時使用 `--browse-all 1`，日常用 `--browse-all 0` 快速更新。

## 📝 更新日誌

### V3.0 (2026-04-15) - 批量精準查詢 + 無需 Token

**架構重大變更：**
- ✨ **TW 端改用 Microsoft DisplayCatalog API** - 不再使用失效的 `productDetails` 端點
  - 無需 AUTH_TOKEN，完全匿名執行
  - 批量查詢 50+ 個 ID，效率大幅提升
  - 回傳中文標題、TWD 價格、可購買狀態
- ✨ **AUTH_TOKEN 改為選填** - JP browse API 同樣支援匿名，留空直接跑
- ✨ **DLC 識別與過濾** (`filter_dlc` 參數) - 只統計遊戲本體，掃描時間減半

**Bug 修復：**
- 🐛 修復批量查詢 API 端點錯誤（原 `productDetails` 回傳 404）
- 🐛 修復查詢失敗被誤判為「已下架」問題（原 batch_size=5 仍全數失敗）
- 🐛 修復 `filter_dlc=0` 時誤將遊戲本體過濾掉的邏輯錯誤

### V2.1 (2026-04-08) - 速度優化版本 ⚡

**新增功能：**
- ✨ **雙模式掃描** (`browse_all` 參數)
  - `browse_all=0`: 增量模式 - JP 找新遊戲，TW 只檢查問題遊戲（日常快速）
  - `browse_all=1`: 全量驗證 - JP/TW 都掃描，只寫入變動（定期完整）

- ✨ **可配置的多排序開關** (`multi_sort` 參數)
  - `multi_sort=0`: 預設排序 - 只用 1 種排序（超快，1-2 分鐘）
  - `multi_sort=1`: 多排序 - 用 5 種排序方式（完整，30-60 分鐘）
  - 靈活組合實現最適速度和涵蓋率

- ✨ **多排序掃描策略** - 5 種排序方式 (預設/標題升/標題降/發行日期/價格)
  - 克服 API 分頁邊界問題，提高涵蓋率 20-30%

- ✨ **狀態變動檢測** - 自動追踪遊戲狀態變化
  - 記錄 `status_change_count`，只寫入有變動的記錄
  - 減少資料庫寫入次數

- ✨ **掃描時間戳記錄** - `last_full_scan_date` 審計記錄

**性能改進：**
- 🚀 增量快速模式: 1-2 分鐘（vs 原本 5-10 分鐘）
- 🚀 智能重檢: 只重檢 delisted/region-locked，跳過 available
- 🚀 API 調用優化: 根據需求動態調整排序方式

**推薦組合：**
- 日常快速: `--browse-all 0 --multi-sort 0` (1-2 分鐘) ⚡
- 日常完整: `--browse-all 0 --multi-sort 1` (10-15 分鐘) 
- 定期驗證: `--browse-all 1 --multi-sort 1` (60+ 分鐘)

### V2.0 (2026-04-08) - 資料庫版本

- ✨ SQLite 資料庫層 - 遊戲資訊永久保存
- ✨ 基礎增量更新機制
- ✨ HTML 可視化報表 - 圓餅圖、長條圖等統計
- ✨ Delisted 自動重檢機制
- 🐛 保持 V1 CSV 格式相容

### V1.0 (2026-04-08) - 初版

- 基礎爬蟲功能
- CSV 輸出

## 🤝 貢獻

有問題或建議？歡迎開 Issue 或 PR！

## 📄 License

MIT License
