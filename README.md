# QuizForge

單一使用者自架的題庫生成系統。把教材（掃描件、PDF、Word、圖片或網頁）丟進系統，自動文字化、分類、出題，經人工審題後匯出可列印的 Word 考卷。

## 核心流程

1. **文件輸入**：上傳 PDF／圖片／Word，或輸入網址抓取正文。
2. **文字化**：PDF 與圖片一律走 vision model 解析成 Markdown（含圖表裁切）；網頁走本地正文抽取（不花 token）。
3. **分類**：內容切 chunk，由 LLM 標註科目／主題／難度／標籤，並計算 embedding 存 pgvector。
4. **出題**：六種題型（比較、類比、單選、是非、填充、問答），structured output 強制 JSON。
5. **審題**：生成題目先進 `draft`，網頁上編輯、採用或丟棄；只有 `approved` 進題庫。
6. **匯出**：從題庫選題，生成題目卷與答案卷兩份 `.docx`，支援 A4／B4／B3（JIS）紙張。

## 需求

- Docker 與 Docker Compose
- [OpenRouter](https://openrouter.ai/) API key（chat 與 embeddings 同一把 key；**LLM 費用由你自行負擔**）

## 啟動

```bash
git clone <this-repo>
cd quiz-forge
cp .env.example .env
# 編輯 .env，至少填入 LLM_API_KEY，並更換 POSTGRES_PASSWORD
docker compose up -d --build
```

開瀏覽器進 `http://localhost:8080`（port 可用 `.env` 的 `NGINX_HTTP_PORT` 調整）。

backend 啟動時會自動執行資料庫 migration（`alembic upgrade head`），不需手動建表。

## 架構

```
Browser ──> proxy (純反向代理，唯一對外 port)
              ├── /        → website (Vue 3 前端靜態檔)
              └── /api/v1  → FastAPI backend
                                └── PostgreSQL + pgvector
```

- 四個 container：`quiz-forge-proxy`（反向代理）、`quiz-forge-website`（前端）、`quiz-forge-backend`、`quiz-forge-db`。
- 背景任務用 Postgres 當 queue（`SELECT ... FOR UPDATE SKIP LOCKED`），不需要 Redis/Celery。
- 所有資料落在 `data/container-mounts/`（DB 資料、上傳原檔、裁切圖、匯出檔），備份帶走這個資料夾即可。

## 費用與模型

模型全部在 `.env` 設定（預設 OpenRouter）：

| 用途 | 變數 | 預設 |
|---|---|---|
| vision 解析 | `VISION_MODEL` | `google/gemini-3.6-flash` |
| 摘要／分類／出題 | `TEXT_MODEL` | `openai/gpt-5.6-luna` |
| embedding | `EMBEDDING_MODEL` | `openai/text-embedding-3-small` |

- 每次 LLM 呼叫都會記錄 model 與 token 用量，「用量」頁可看累計統計。
- 有文字層的 PDF 也走 vision 管線（換取管線一致），每頁都會花 token。
- **注意**：`EMBEDDING_DIM` 綁定 pgvector 欄位維度；更換 embedding model 需要 re-embed 全部資料並跑 migration，屬重大變更。

## 開發

文件以 `docs/` 為唯一真實來源，動手前先讀 `docs/index.md`。

```bash
# Python 一律走 uv
uv run --project backend ruff check backend
uv run --project backend basedpyright -p backend
uv run --project backend pytest            # DB 測試需要一個可連的 Postgres（見 backend/tests/conftest.py）

# 前端
cd frontend && npm install
npm run build && npm run lint

# migration
cd backend && uv run alembic revision -m "..."
```

## 安全

- 這是單人本機系統，不做帳號與登入；**不要**把 nginx port 暴露到公網。
- `.env`（含 API key 與 DB 密碼）已被 `.gitignore` 排除，不會進版本紀錄。
