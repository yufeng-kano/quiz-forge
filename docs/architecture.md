# 系統架構

## Docker Compose 拓撲

```
Browser ──> proxy (純反向代理，唯一對外 port)
              ├── /        → website (前端靜態檔，Vue build 產物)
              └── /api/v1  → backend (uvicorn, FastAPI async)
                                └── db (PostgreSQL + pgvector)
```

| 服務 | container name | 說明 |
|---|---|---|
| `proxy` | `quiz-forge-proxy` | 純反向代理（nginx 實作）：`/` → website、`/api/v1` → backend，不 serve 靜態檔 |
| `website` | `quiz-forge-website` | 前端常駐 container，serve Vue build 靜態檔（含 SPA fallback） |
| `backend` | `quiz-forge-backend` | FastAPI，entrypoint 先跑 `alembic upgrade head` 再起 uvicorn |
| `db` | `quiz-forge-db` | `pgvector/pgvector` 官方 image |

- 前端是獨立常駐 container（見 `docs/decisions/2026-08-16-separate-frontend-container.md`）：`frontend/Dockerfile` 用 multi-stage build（node stage `npm ci && npm run build` 產出 `dist/`，final stage nginx serve 靜態檔），website 與 proxy 分離、各自獨立重建。
- `website` 不對 host 暴露 port，只走 compose 內部 network。
- 所有 volume 用明確 bind mount，來源統一在 `data/container-mounts/` 底下：`db/`（DB 資料）、`uploads/`（上傳原檔）、`assets/`（裁切圖）、`exports/`（匯出檔）。
- db 用 `pgvector/pgvector:pg17` image，設定檔 `db/postgresql.conf`。`PGDATA` 指到掛載點底下的 `pgdata/` 子目錄——掛載點根目錄有 `.gitkeep`，直接當 `PGDATA` 會被 initdb 判定為非空而失敗。
- proxy 對外 port 由 `NGINX_HTTP_PORT` 設定（預設 8080）。

## proxy 必要設定

proxy 設定檔在 `proxy/nginx.conf`，website 靜態 serve 設定檔在 `frontend/nginx.conf`；數值放設定檔不寫死在程式碼：

- `client_max_body_size 200m`（proxy）：容納大型掃描 PDF 上傳。
- `proxy_read_timeout 300s`（proxy）：容納長時間 API 請求。
- SPA fallback（website）：找不到實體檔案回 `index.html`，交給 vue-router 處理路由。
- 若進度改用 SSE：`proxy_buffering off`（第一版用輪詢，暫不需要）。

## 背景任務：Postgres 當 queue（不用 Celery/Redis）

- `jobs` 表 + `SELECT ... FOR UPDATE SKIP LOCKED` 領任務（實作在 `backend/src/backend/jobs/`）。
- FastAPI lifespan 啟動 N 個 asyncio worker coroutine 輪詢；N 由 `JOB_WORKER_COUNT` 設定、輪詢間隔 `JOB_POLL_INTERVAL_SECONDS`。
- job kind → handler 用 registry 註冊（decorator），新增 job 種類不動 queue 核心。現有 kind：`parse_document`、`parse_page`、`rechunk_document`、`generate_questions`、`export_docx`、`embed_questions`（題目補向量）、`bank_agent_turn`（題庫選題助手一個回合）。
- job 欄位：`status / progress / error / retry_count`；前端輪詢 `GET /api/v1/jobs/{id}`，`POST /api/v1/jobs/{id}/retry` 重試失敗 job。`jobs.error` 是給人看的短摘要（寫入時即為人話），完整例外只進後端 log，不進 API 回應、不進任務中心表格。
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
- 回應解析採兩段式：先以 Pydantic 對完整 content 做嚴格 `model_validate_json`；失敗時（已知案例：OpenRouter 部分 provider 未完全遵守 `strict: true`，在 JSON 物件後續上第二個物件或餘文字，造成 `trailing characters`）改用標準庫 `json.JSONDecoder().raw_decode` 抽出 content 內第一個完整 JSON 值再驗證。兩段都失敗才丟 `LLMResponseError`，不吞例外。
- 每次呼叫記錄至 `llm_usage` 表（model、用途、prompt/completion tokens），提供用量頁面。

## `.env` 變數

權威清單與註解在專案根目錄 `.env.example`。啟動前至少改 `LLM_API_KEY` 與 `POSTGRES_PASSWORD`。依用途分組如下：

| 分組 | 變數 | 預設 | 說明 |
|---|---|---|---|
| LLM | `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | OpenAI-compatible 端點 |
| LLM | `LLM_API_KEY` | （必填） | chat 與 embeddings 共用 |
| LLM | `VISION_MODEL` | `google/gemini-3.6-flash` | 掃描件／PDF／圖片解析 |
| LLM | `TEXT_MODEL` | `openai/gpt-5.6-luna` | 摘要／分類／出題 |
| LLM | `EMBEDDING_MODEL` | `openai/text-embedding-3-small` | chunk 向量化 |
| LLM | `EMBEDDING_DIM` | `1536` | pgvector 建表維度 |
| LLM | `LLM_CONCURRENCY` | `4` | LLM 呼叫併發上限 |
| 文件輸入 | `OCR_DPI` | `200` | PDF 轉頁面圖 DPI |
| 文件輸入 | `CHUNK_MAX_CHARS` | `4000` | 單一 chunk 字元上限 |
| 文件輸入 | `CLASSIFICATION_EXISTING_SUBJECTS_LIMIT` | `50` | 分類 prompt 帶入的既有科目上限 |
| 文件輸入 | `CLASSIFICATION_EXISTING_TOPICS_PER_SUBJECT_LIMIT` | `30` | 每個科目底下帶入的既有主題上限 |
| 文件輸入 | `URL_FETCH_MAX_BYTES` | `104857600` | 網址檔案下載大小上限（100MB） |
| 文件輸入 | `URL_FETCH_TIMEOUT_SECONDS` | `30.0` | 網址下載逾時（秒） |
| 文件輸入 | `WEBPAGE_TITLE_MAX_LENGTH` | `200` | 網頁文件標題字元上限 |
| 出題 | `COMPARISON_SIMILARITY_MIN` | `0.35` | 比較題配對相似度下界 |
| 出題 | `COMPARISON_SIMILARITY_MAX` | `0.75` | 比較題配對相似度上界 |
| 題庫搜尋 | `QUESTION_SIMILARITY_MIN` | `0.2` | `similar_to` 語意搜尋的 cosine 相似度門檻 |
| 題庫搜尋 | `QUESTION_EMBED_BATCH_SIZE` | `64` | `embed_questions` job 每批送出的題數 |
| 選題助手 | `BANK_AGENT_MAX_STEPS` | `6` | 單一回合的 LLM 步數上限 |
| 選題助手 | `BANK_AGENT_SEARCH_LIMIT` | `30` | 每次搜尋回餵模型的題目摘要數上限 |
| 選題助手 | `BANK_AGENT_HISTORY_LIMIT` | `20` | 帶入 prompt 的歷史訊息則數 |
| 選題助手 | `BANK_AGENT_STEM_PREVIEW_CHARS` | `120` | 回餵摘要中題幹截斷字元數 |
| 選題助手 | `CONVERSATION_TITLE_MAX_LENGTH` | `40` | 對話標題字元上限（取自第一則使用者訊息） |
| 分頁 | `QUESTIONS_LIST_LIMIT_DEFAULT` | `50` | `GET /v1/questions` 預設每頁筆數 |
| 分頁 | `QUESTIONS_LIST_LIMIT_MAX` | `200` | 題目列表 limit 上限（超過 422） |
| 分頁 | `JOBS_LIST_LIMIT_DEFAULT` | `50` | `GET /v1/jobs` 預設每頁筆數 |
| 分頁 | `JOBS_LIST_LIMIT_MAX` | `200` | 任務列表 limit 上限（超過 422） |
| 背景任務 | `JOB_WORKER_COUNT` | `2` | asyncio worker 數量 |
| 背景任務 | `JOB_POLL_INTERVAL_SECONDS` | `1.0` | worker 空閒輪詢間隔（秒） |
| 基礎設施 | `DATABASE_URL` | `postgresql+asyncpg://quizforge:change-me@db:5432/quizforge` | backend 連線字串 |
| 基礎設施 | `DATA_DIR` | `/data` | container 內部資料根目錄 |
| PostgreSQL | `POSTGRES_USER` | `quizforge` | db 服務帳號 |
| PostgreSQL | `POSTGRES_PASSWORD` | `change-me` | db 服務密碼，部署時務必更換 |
| PostgreSQL | `POSTGRES_DB` | `quizforge` | db 服務資料庫名 |
| proxy | `NGINX_HTTP_PORT` | `8080` | 對外（host）監聽 port |

- Git 只保存 `.env.example`；真正的 `.env` 不入版控。
- `EMBEDDING_DIM` 是半固定值：pgvector 建表後更換 embedding model 需 re-embed + migration，README 要明講代價。現在有 `chunks.embedding` 與 `questions.embedding` 兩處向量，換 model 要兩邊一起重跑。
- 單人資料量小，向量查詢先全表掃 cosine，不建 HNSW index；效能不足時再加。
