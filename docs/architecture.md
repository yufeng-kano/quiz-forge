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

- 前端不做常駐 container：multi-stage build 產出 `dist/`，交由 nginx serve。
- 所有 volume 用明確 bind mount，來源統一在 `data/container-mounts/` 底下（DB 資料、上傳原檔、裁切圖、匯出檔）。

## nginx 必要設定

- `client_max_body_size`：放大，容納大型掃描 PDF 上傳。
- `proxy_read_timeout`：拉長，容納長時間 API 請求。
- 若進度改用 SSE：`proxy_buffering off`（第一版用輪詢，暫不需要）。

## 背景任務：Postgres 當 queue（不用 Celery/Redis）

- `jobs` 表 + `SELECT ... FOR UPDATE SKIP LOCKED` 領任務。
- FastAPI lifespan 啟動 N 個 asyncio worker coroutine 輪詢。
- job 欄位：`status / progress / error / retry_count`；前端輪詢 `GET /api/v1/jobs/{id}`。
- 多頁文件逐頁更新 progress，使用者可看到「12/40 頁」。
- LLM 呼叫用 `asyncio.Semaphore` 限流，併發數由 `LLM_CONCURRENCY` 設定。
- 失敗以最小單位重試（單頁、單題），不整份重跑。

## 後端技術

- Python 3.13 + FastAPI，全 async handler，`uv` 管理專案。
- SQLAlchemy 2.0 async + asyncpg；pgvector 用官方 `pgvector` Python 套件的 SQLAlchemy type。
- Alembic async template（`alembic init -t async`）管 migration；第一個 migration 要 `CREATE EXTENSION IF NOT EXISTS vector`。
- API 公開路徑 `/api/v1/*`，內部 router 前綴 `/v1/*`。

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

# 基礎設施
DATABASE_URL=postgresql+asyncpg://...
DATA_DIR=/data
```

- Git 只保存 `.env.example`；真正的 `.env` 不入版控。
- `EMBEDDING_DIM` 是半固定值：pgvector 建表後更換 embedding model 需 re-embed + migration，README 要明講代價。
- 單人資料量小，向量查詢先全表掃 cosine，不建 HNSW index；效能不足時再加。
