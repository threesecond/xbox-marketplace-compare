# 安全提醒

## AUTH_TOKEN 管理
- **AUTH_TOKEN** 位於 `xbox_compare_v3.py` 第42行
- 每次 commit 前，請清空 `AUTH_TOKEN = ""` 中的 token 值
- 不要將真實的 token 提交到 GitHub
- Token 可以存放在 `.ai/token.txt` 文件中（此文件已被 .gitignore 忽略）

## 工作流程
1. 從 `.ai/token.txt` 複製 token 到 `AUTH_TOKEN = "your_token_here"`
2. 運行腳本
3. 運行前清空 `AUTH_TOKEN = ""`
4. 然後 commit