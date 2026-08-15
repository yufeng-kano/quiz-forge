# 文件索引

執行任何任務前先讀本文件。`docs/` 是專案唯一真實來源；文件異動必須同步更新本索引。

文件分兩類：

- `docs/decisions/`：決策文件，檔名 `YYYY-MM-DD-主題.md`，記錄當下的決策與理由，之後不回改；推翻舊決策時新增一份新的決策文件。
- `docs/` 頂層：系統即時文件，平放不分子資料夾，實作變更時必須同步更新。

## 專案根目錄

| 路徑 | 用途 |
|---|---|
| `.rule` | 給 LLM 的專案規則主檔 |
| `CLAUDE.md`、`AGENTS.md` | 指向 `.rule` 的 symlink |
| `.env.example` | 環境變數範本（真正的 `.env` 不入 Git） |
| `docs/` | 專案文件（本目錄） |
| `data/` | 樣本資料與 container mount 掛載點，見 `docs/data-inventory.md` |
| `backend/` | Python FastAPI 服務（uv 管理、Alembic migration），見 `docs/architecture.md` |
| `frontend/` | Vue 3 前端骨架，見 `docs/frontend.md` |
| `nginx/` | 反向代理設定與 Dockerfile（multi-stage build 前端） |
| `db/` | PostgreSQL（pgvector）設定檔 |
| `docker-compose.yml` | 服務編排（backend / db / nginx） |

## 文件清單

| 文件 | 摘要 |
|---|---|
| `docs/index.md` | 本索引 |
| `docs/overview.md` | 系統定位、核心流程、範圍界定、使用模型 |
| `docs/architecture.md` | Docker Compose 拓撲、nginx 設定、pg-as-queue、後端技術、LLM 介接、`.env` 變數 |
| `docs/data-model.md` | 資料表邏輯定義與設計決定 |
| `docs/ingestion.md` | 文件輸入管線：vision 解析契約（Markdown + bbox）、圖表裁切、網頁抽取、chunk 與分類 |
| `docs/question-bank.md` | 六題型 payload schema、出題流程、審題流程 |
| `docs/export.md` | Word 匯出：題目卷／答案卷、紙張尺寸、render 設計 |
| `docs/frontend.md` | 前端技術（router/Pinia/i18n 規範）、頁面清單、視覺風格（白色簡潔）、互動原則 |
| `docs/data-inventory.md` | `data/` 內資料清單與用途 |

## 決策文件

| 文件 | 摘要 |
|---|---|
| `docs/decisions/2026-08-15-initial-system-design.md` | 初始系統設計：D1–D11 技術決策、待確認事項、開發順序 |
