#!/usr/bin/env python3
"""
Xbox 遊戲對比工具 - HTML 報表生成器
產生可視化報表
"""

import json
from datetime import datetime
from typing import Dict, List
from jinja2 import Template


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Xbox 商店遊戲對比 - 報表</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.datatables.net/1.13.6/css/dataTables.bootstrap5.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <style>
        :root {
            --primary-color: #107C10;
            --success-color: #107C10;
            --warning-color: #FFB900;
            --danger-color: #D13438;
        }
        
        body {
            background-color: #f5f5f5;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', sans-serif;
        }
        
        .header {
            background: linear-gradient(135deg, var(--primary-color) 0%, #0078d4 100%);
            color: white;
            padding: 40px 0;
            margin-bottom: 40px;
        }
        
        .header h1 {
            margin: 0;
            font-weight: 700;
        }
        
        .header p {
            margin: 5px 0 0 0;
            opacity: 0.9;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        
        .stat-card {
            background: white;
            border-radius: 8px;
            padding: 25px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            border-left: 4px solid #ccc;
        }
        
        .stat-card h3 {
            font-size: 2em;
            margin: 0;
            color: #0078d4;
            font-weight: 700;
        }
        
        .stat-card p {
            margin: 8px 0 0 0;
            color: #666;
            font-size: 0.95em;
        }
        
        .stat-card.available { border-left-color: var(--success-color); }
        .stat-card.available h3 { color: var(--success-color); }
        
        .stat-card.region-locked { border-left-color: var(--warning-color); }
        .stat-card.region-locked h3 { color: var(--warning-color); }
        
        .stat-card.delisted { border-left-color: var(--danger-color); }
        .stat-card.delisted h3 { color: var(--danger-color); }
        
        .badge-available {
            background-color: var(--success-color);
            color: white;
        }
        
        .badge-region-locked {
            background-color: var(--warning-color);
            color: #333;
        }
        
        .badge-delisted {
            background-color: var(--danger-color);
            color: white;
        }
        
        .table-container {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            margin-bottom: 40px;
        }
        
        .table-container h2 {
            margin-top: 0;
            margin-bottom: 25px;
            font-size: 1.5em;
            color: #333;
        }
        
        table thead th {
            background-color: #f8f9fa;
            border-bottom: 2px solid #dee2e6;
            color: #333;
            font-weight: 600;
        }
        
        table tbody tr:hover {
            background-color: #f8f9fa;
        }
        
        .game-link {
            color: #0078d4;
            text-decoration: none;
            font-weight: 500;
        }
        
        .game-link:hover {
            text-decoration: underline;
        }
        
        .price {
            font-weight: 500;
            color: #333;
        }
        
        .price.zero {
            color: #999;
        }
        
        .chart-container {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            margin-bottom: 40px;
        }
        
        .chart-container h2 {
            margin-top: 0;
            margin-bottom: 25px;
            font-size: 1.5em;
            color: #333;
        }
        
        .chart-wrapper {
            position: relative;
            height: 400px;
        }
        
        .footer {
            text-align: center;
            color: #666;
            padding: 20px;
            border-top: 1px solid #eee;
            margin-top: 40px;
            font-size: 0.9em;
        }
        
        .dataTables_wrapper {
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="container">
            <h1>🎮 Xbox 商店遊戲對比</h1>
            <p>日本 (ja-JP) vs 台灣 (zh-TW)</p>
            <small>更新時間：{{ generated_time }}</small>
        </div>
    </div>
    
    <div class="container">
        <!-- 統計卡片 -->
        <div class="stats-grid">
            <div class="stat-card available">
                <h3>{{ stats.available }}</h3>
                <p>可購買遊戲</p>
            </div>
            <div class="stat-card region-locked">
                <h3>{{ stats.region_locked }}</h3>
                <p>地區限定遊戲</p>
            </div>
            <div class="stat-card delisted">
                <h3>{{ stats.delisted }}</h3>
                <p>已下架遊戲</p>
            </div>
            <div class="stat-card" style="border-left-color: #0078d4;">
                <h3>{{ stats.total }}</h3>
                <p>遊戲總數</p>
            </div>
        </div>
        
        <!-- 圓餅圖 -->
        {% if show_charts %}
        <div class="chart-container">
            <h2>遊戲狀態分佈</h2>
            <div class="chart-wrapper">
                <canvas id="statusChart"></canvas>
            </div>
        </div>
        {% endif %}
        
        <!-- 遊戲表格 -->
        <div class="table-container">
            <h2>遊戲清單</h2>
            <table id="gamesTable" class="table table-hover table-sm">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>日文遊戲名稱<br><small>（日本商店）</small></th>
                        <th>日幣價格</th>
                        <th>台灣遊戲名稱<br><small>（台灣商店）</small></th>
                        <th>台幣價格</th>
                        <th>台灣狀態</th>
                        <th>最後檢查時間</th>
                    </tr>
                </thead>
                <tbody>
                    {% for game in games %}
                    <tr>
                        <td>
                            <code style="font-size: 0.85em;">{{ game.product_id }}</code>
                        </td>
                        <td>
                            <a href="{{ game.ja_url }}" target="_blank" class="game-link" title="在日本 Xbox 商店打開">
                                {{ game.ja_title }}
                            </a>
                        </td>
                        <td class="price">
                            {% if game.ja_price %}
                                ¥{{ game.ja_price | int }}
                            {% else %}
                                -
                            {% endif %}
                        </td>
                        <td>
                            {% if game.tw_title %}
                                <a href="{{ game.tw_url }}" target="_blank" class="game-link" title="在台灣 Xbox 商店打開">
                                    {{ game.tw_title }}
                                </a>
                            {% else %}
                                <span style="color: #999;">
                                    <a href="{{ game.tw_url }}" target="_blank" class="game-link" title="在台灣 Xbox 商店打開">
                                        （查看商店）
                                    </a>
                                </span>
                            {% endif %}
                        </td>
                        <td class="price">
                            {% if game.tw_price %}
                                NT${{ game.tw_price | int }}
                            {% else %}
                                -
                            {% endif %}
                        </td>
                        <td>
                            <span class="badge badge-{{ game.status }}">
                                {{ status_labels[game.status] }}
                            </span>
                        </td>
                        <td>{{ game.last_checked }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    
    <div class="footer">
        <p>由 Xbox 商店遊戲對比工具 V2 生成 | 
        <a href="https://github.com/threesecond/xbox-marketplace-compare" target="_blank">GitHub</a></p>
    </div>
    
    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.6/js/dataTables.bootstrap5.min.js"></script>
    
    <script>
        // DataTables 初始化
        $(document).ready(function() {
            $('#gamesTable').DataTable({
                language: {
                    url: '//cdn.datatables.net/plug-ins/1.13.6/i18n/zh-HANT.json',
                    loadingRecords: '載入中...',
                    zeroRecords: '未找到相符的記錄',
                },
                pageLength: 25,
                lengthMenu: [[10, 25, 50, 100, -1], [10, 25, 50, 100, '全部']],
                order: [[5, 'asc'], [1, 'asc']],  // 按狀態排序，再按日文名稱排序
                columnDefs: [
                    {
                        targets: 0,  // ID 欄位
                        className: 'text-muted',
                        width: '80px',
                    },
                    {
                        targets: 5,  // 狀態欄位，用於排序
                        orderable: true,
                    }
                ],
            });
        });
        
        // 圓餅圖
        {% if show_charts %}
        const statusCtx = document.getElementById('statusChart').getContext('2d');
        new Chart(statusCtx, {
            type: 'doughnut',
            data: {
                labels: ['可購買', '地區限定', '已下架'],
                datasets: [{
                    data: [{{ stats.available }}, {{ stats.region_locked }}, {{ stats.delisted }}],
                    backgroundColor: [
                        '#107C10',  // 綠色 - available
                        '#FFB900',  // 黃色 - region-locked
                        '#D13438',  // 紅色 - delisted
                    ],
                    borderColor: '#fff',
                    borderWidth: 2,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const value = context.parsed;
                                const percentage = ((value / total) * 100).toFixed(1);
                                return context.label + ': ' + value + ' (' + percentage + '%)';
                            }
                        }
                    }
                }
            }
        });
        {% endif %}
    </script>
</body>
</html>
"""


class HTMLReporter:
    """HTML 報表生成器"""

    STATUS_LABELS = {
        'available': '可購買',
        'region-locked': '地區限定',
        'delisted': '已下架',
    }

    def __init__(self):
        """初始化"""
        self.template = Template(HTML_TEMPLATE)

    def generate_report(
        self,
        games_data: List[Dict],
        stats: Dict,
        output_file: str = "report.html",
        show_charts: bool = True
    ):
        """
        生成 HTML 報表

        Args:
            games_data: 遊戲資料清單
                {
                    'product_id': str (Xbox 商店 ID),
                    'ja_title': str (日文遊戲名稱),
                    'ja_price': float (日幣價格),
                    'ja_url': str (日本商店 URL),
                    'tw_title': str or None (台灣標題，目前為 None),
                    'tw_price': float (台幣價格),
                    'tw_url': str (台灣商店 URL),
                    'status': 'available' | 'region-locked' | 'delisted' (台灣狀態),
                    'last_checked': str (YYYY-MM-DD HH:MM),
                }
            stats: 統計資訊
                {
                    'available': int,
                    'region_locked': int,
                    'delisted': int,
                    'total': int,
                }
            output_file: 輸出檔案路徑
            show_charts: 是否顯示圖表
        """
        # 排序遊戲：優先顯示不可購買的
        sorted_games = sorted(
            games_data,
            key=lambda x: (
                x['status'] == 'available',
                x['ja_title']
            )
        )

        # 渲染 HTML
        html_content = self.template.render(
            generated_time=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z"),
            games=sorted_games,
            stats={
                'available': stats.get('available', 0),
                'region_locked': stats.get('region_locked', 0),
                'delisted': stats.get('delisted', 0),
                'total': stats.get('total', 0),
            },
            status_labels=self.STATUS_LABELS,
            show_charts=show_charts,
        )

        # 寫入檔案
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"[OK] HTML 報表已生成: {output_file}")
            return True
        except Exception as e:
            print(f"[ERROR] 生成 HTML 報表失敗: {e}")
            return False

    @staticmethod
    def prepare_games_data(db_results: Dict, target_locale: str = "zh-TW") -> List[Dict]:
        """
        從資料庫結果準備遊戲資料
        
        Args:
            db_results: 資料庫查詢結果
            target_locale: 目標地區
        
        Returns:
            格式化後的遊戲清單
        """
        games = []
        
        for product_id, game_info in db_results.items():
            # 取得目標地區資訊
            tw_info = game_info.get('regions', {}).get(target_locale, {})
            
            games.append({
                'product_id': product_id,
                'ja_title': game_info.get('ja_title', 'Unknown'),
                'ja_price': game_info.get('ja_price'),
                'tw_price': tw_info.get('price'),
                'status': tw_info.get('status', 'delisted'),
                'last_checked': tw_info.get('last_checked_date', ''),
                'tw_url': f"https://www.xbox.com/zh-tw/games/store/{game_info.get('ja_title', product_id)}/{product_id}",
            })
        
        return games


# 測試用
if __name__ == "__main__":
    reporter = HTMLReporter()

    # 樣本資料
    sample_games = [
        {
            'product_id': '123456',
            'ja_title': 'Elden Ring',
            'ja_price': 8000,
            'ja_url': 'https://www.xbox.com/ja-jp/games/store/Elden%20Ring/123456',
            'tw_title': None,
            'tw_price': 2580,
            'tw_url': 'https://www.xbox.com/zh-tw/games/store/Elden%20Ring/123456',
            'status': 'available',
            'last_checked': '2026-04-08 10:30',
        },
        {
            'product_id': '123457',
            'ja_title': 'Final Fantasy XVI',
            'ja_price': 9000,
            'ja_url': 'https://www.xbox.com/ja-jp/games/store/Final%20Fantasy%20XVI/123457',
            'tw_title': None,
            'tw_price': None,
            'tw_url': 'https://www.xbox.com/zh-tw/games/store/Final%20Fantasy%20XVI/123457',
            'status': 'region-locked',
            'last_checked': '2026-04-08 10:30',
        },
        {
            'product_id': '123458',
            'ja_title': '某限定遊戲',
            'ja_price': 5000,
            'ja_url': 'https://www.xbox.com/ja-jp/games/store/%E6%9F%90%E9%99%90%E5%AE%9A%E9%81%8A%E6%88%B2/123458',
            'tw_title': None,
            'tw_price': None,
            'tw_url': 'https://www.xbox.com/zh-tw/games/store/%E6%9F%90%E9%99%90%E5%AE%9A%E9%81%8A%E6%88%B2/123458',
            'status': 'delisted',
            'last_checked': '2026-04-07',
        },
    ]

    sample_stats = {
        'available': 100,
        'region_locked': 50,
        'delisted': 10,
        'total': 160,
    }

    reporter.generate_report(
        games_data=sample_games,
        stats=sample_stats,
        output_file="report_test.html"
    )
