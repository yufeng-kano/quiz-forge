# 初始系統設計

本檔記錄專案啟動階段的技術決策與理由。系統的即時文件（隨實作同步更新）平放在 `docs/` 頂層。

## 已定案決策

### D1. 資料庫用 PostgreSQL + pgvector，不用 SQLite

穩定性優先。附帶效益：pg 可直接當 job queue（見 D2）、pgvector 供比較題配對。向量維度預設 1536（`EMBEDDING_DIM`）；更換 embedding model 需 re-embed + migration，屬重大變更。

### D2. 背景任務用 pg-as-queue，不引入 Celery/Redis

單人負載下，`jobs` 表 + `SELECT ... FOR UPDATE SKIP LOCKED` + asyncio worker 就是正經 queue。少兩個常駐容器，降低使用者部署門檻。

### D3. 部署形態：Docker Compose + nginx 反代

nginx 唯一對外：`/` serve Vue build 靜態檔、`/api/v1` proxy 到 FastAPI。前端不做常駐 container。container name 固定 `quiz-forge-backend`、`quiz-forge-db`、`quiz-forge-nginx`。

### D4. PDF 與圖片一律走 vision model，不分有無文字層

原則：簡單就要一致。單一管線換取程式簡單與輸出格式統一（Markdown + 圖表 bbox 0–1000），代價是有文字層的 PDF 也逐頁花 token——已確認接受使用者付費模式。傳統本地 OCR（PaddleOCR 等）不採用：image 肥大、CPU 慢、繁中品質差。

### D5. 網頁抓取用本地抽取，摘要僅供分類與顯示

`trafilatura` 本地抽正文（免費），LLM 只做摘要。出題一律用全文，用摘要出題會丟失細節。

### D6. LLM 一律 OpenAI-compatible，供應商走 OpenRouter

不做 Anthropic message format。OpenRouter 的 chat 與 embeddings 端點同一把 key、同一個 base_url，使用者只需一個帳號一處帳單。base_url 保留 `.env` 可換。摘要／分類／出題共用一組 `TEXT_MODEL`（gpt-5.6-luna），vision 用 `VISION_MODEL`（gemini-3.6-flash）。

### D7. 結構化輸出強制 json_schema

vision 解析、分類、出題全部用 `response_format: json_schema`，不 parse 自由文字。

### D8. 題型定案六種，payload 用 jsonb

`comparison`、`analogy`、`single_choice`、`true_false`、`fill_blank`、`short_answer`。同一份 Pydantic discriminated union 三用（API 驗證、LLM json_schema、Word renderer 輸入）；新增題型零 migration。

### D9. 審題流程必做

LLM 出題必有爛題，`draft → approved` 人工閘門是品質下限的保證，也是接案的責任切割。只有 `approved` 進題庫與匯出範圍。

### D10. 環境設定用單一根目錄 `.env`

本專案只有使用者本機一種環境，不分 local/production 兩套，降低設定負擔。Git 只保存 `.env.example`。

### D11. 技術棧

Vue 3 + FastAPI（全 async）+ SQLAlchemy 2.0 async/asyncpg + Alembic（async template）+ `uv` 管理 Python。

## 待確認

- 客戶提出的「B3」紙張尺寸較少見（台灣考卷慣用 B4），交付前向客戶確認。

## 開發順序規劃

1. 專案骨架：compose + `uv init` backend + Alembic 初始 migration（含 `CREATE EXTENSION vector`）+ `npm create vue` 前端。
2. Ingestion：上傳、vision 管線、網頁抓取、chunk 與分類。
3. 題庫：出題 job、審題頁。
4. 匯出：Word 題目卷／答案卷。
5. 收尾：用量頁面、README 部署文件。
