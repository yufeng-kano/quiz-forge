# 系統架構

## Docker Compose 拓撲

```
Browser ──> nginx (唯一對外 port)
              ├── /        → 前端靜態檔（Vue build 產物）
              └── /api/v1  → backend (uvicorn, FastAPI async)
                                └── db (PostgreSQL + pgvector)
```

| 服務 | container name | 說明 |
|---|---|---|
| `nginx` | `quiz-forge-nginx` | 反向代理，serve 前端靜態檔 |
| `backend` | `quiz-forge-backend` | FastAPI，entrypoint 先跑 `alembic upgrade head` 再起 uvicorn |
| `db` | `quiz-forge-db` | `pgvector/pgvector` 官方 image |

- 前端不做常駐 container：nginx 的 Dockerfile 用 multi-stage build（node stage `npm ci && npm run build` 產出 `dist/`），交由 nginx serve。
- 所有 volume 用明確 bind mount，來源統一在 `data/container-mounts/` 底下：`db/`（DB 資料）、`uploads/`（上傳原檔）、`assets/`（裁切圖）、`exports/`（匯出檔）。
- db 用 `pgvector/pgvector:pg17` image，設定檔 `db/postgresql.conf`。`PGDATA` 指到掛載點底下的 `pgdata/` 子目錄——掛載點根目錄有 `.gitkeep`，直接當 `PGDATA` 會被 initdb 判定為非空而失敗。
- nginx 對外 port 由 `NGINX_HTTP_PORT` 設定（預設 8080）。

## nginx 必要設定

設定檔在 `nginx/nginx.conf`，數值放設定檔不寫死在程式碼：

- `client_max_body_size 200m`：容納大型掃描 PDF 上傳。
- `proxy_read_timeout 300s`：容納長時間 API 請求。
- 若進度改用 SSE：`proxy_buffering off`（第一版用輪詢，暫不需要）。

## 背景任務：Postgres 當 queue（不用 Celery/Redis）

- `jobs` 表 + `SELECT ... FOR UPDATE SKIP LOCKED` 領任務（實作在 `backend/src/backend/jobs/`）。
- FastAPI lifespan 啟動 N 個 asyncio worker coroutine 輪詢；N 由 `JOB_WORKER_COUNT` 設定、輪詢間隔 `JOB_POLL_INTERVAL_SECONDS`。
- job kind → handler 用 registry 註冊（decorator），新增 job 種類不動 queue 核心。
- job 欄位：`status / progress / error / retry_count`；前端輪詢 `GET /api/v1/jobs/{id}`，`POST /api/v1/jobs/{id}/retry` 重試失敗 job。
- `progress` 為文字欄位（如 `12/40`），多頁文件逐頁更新，使用者可看到「12/40 頁」。
- 啟動時將殘留 `running` 的 job 重排回 `pending`（單機部署的 crash 復原）。
- LLM 呼叫用 `asyncio.Semaphore` 限流，併發數由 `LLM_CONCURRENCY` 設定。
- 失敗以最小單位重試（單頁、單題），不整份重跑。

## 後端技術

- Python 3.13 + FastAPI，全 async handler，`uv` 管理專案（src layout：`backend/src/backend/`）。
- 模組劃分：`core/config.py`（pydantic-settings 讀根目錄 `.env`）、`db/`（async engine/session）、`models/`（ORM，每表一檔）、`api/v1/`（router）。
- SQLAlchemy 2.0 async + asyncpg；pgvector 用官方 `pgvector` Python 套件的 SQLAlchemy type。
- Alembic async template（`alembic init -t async`）管 migration；初始 migration（`51e2e5d860a8`）先 `CREATE EXTENSION IF NOT EXISTS vector` 再建全部資料表，`downgrade()` 有完整反向操作。
- API 公開路徑 `/api/v1/*`，內部 router 前綴 `/v1/*`；骨架先提供 `GET /v1/health`。

## LLM 介接

- 一律 OpenAI-compatible 介面，不做 Anthropic message format。
- 預設供應商 OpenRouter（chat + embeddings 同一把 key、同一個 base_url）。
- 結構化輸出一律 `response_format: json_schema`，不 parse 自由文字。
- 每次呼叫記錄至 `llm_usage` 表（model、用途、prompt/completion tokens），提供用量頁面。

## `.env` 變數

```env
# LLM（全走 OpenAI-compatible，預設 OpenRouter）
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=sk-or-...
VISION_MODEL=google/gemini-3.6-flash
TEXT_MODEL=openai/gpt-5.6-luna
EMBEDDING_MODEL=openai/text-embedding-3-small
EMBEDDING_DIM=1536
LLM_CONCURRENCY=4
OCR_DPI=200
CHUNK_MAX_CHARS=4000

# 背景 job worker
JOB_WORKER_COUNT=2
JOB_POLL_INTERVAL_SECONDS=1

# 基礎設施
DATABASE_URL=postgresql+asyncpg://...
DATA_DIR=/data

# PostgreSQL（db 服務憑證）
POSTGRES_USER=quizforge
POSTGRES_PASSWORD=change-me
POSTGRES_DB=quizforge

# nginx 對外 port
NGINX_HTTP_PORT=8080
```

- Git 只保存 `.env.example`；真正的 `.env` 不入版控。
- `EMBEDDING_DIM` 是半固定值：pgvector 建表後更換 embedding model 需 re-embed + migration，README 要明講代價。
- 單人資料量小，向量查詢先全表掃 cosine，不建 HNSW index；效能不足時再加。
