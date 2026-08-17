# 資料模型

Schema 由 `backend/` 內的 Alembic migration 管理。以下為邏輯定義，實作時以 migration 為準並回頭更新本文件。

```
folders     id, name, created_at                   -- 平面資料夾（不巢狀）
documents   id, source_type(upload/url), title, status, raw_file_path,
            source_url, summary, folder_id(nullable), created_at
pages       id, document_id, page_no, markdown, image_path, status
assets      id, page_id, bbox, file_path, caption
chunks      id, document_id, content, category_id, tags[],
            embedding vector(EMBEDDING_DIM)
categories  id, name, parent_id                    -- 階層分類
questions   id, type, difficulty, status(draft/approved/rejected),
            payload jsonb, source_chunk_ids[], created_at,
            embedding vector(EMBEDDING_DIM)          -- nullable，NULL = 待向量化
conversations          id, title, created_at, updated_at
conversation_messages  id, conversation_id, role(user/assistant), content,
                       proposed_question_ids[], steps jsonb, created_at
exports     id, title, paper_size, question_ids[], docx_path,
            answer_docx_path, created_at
jobs        id, kind, payload jsonb, status, progress(text, 如 "12/40"),
            error（人話短摘要，不含 exception／payload dump）, retry_count,
            created_at, updated_at
llm_usage   id, model, purpose, prompt_tokens, completion_tokens, created_at
```

## 實作狀態

初始 migration `51e2e5d860a8`（`backend/alembic/versions/`）已建立以上全部資料表：

- 先執行 `CREATE EXTENSION IF NOT EXISTS vector` 再建表。
- 主鍵一律整數自增（單人系統，不需 UUID）。
- `chunks.embedding` 為 `vector(EMBEDDING_DIM)`，維度由設定讀入，不寫死。
- `assets.bbox` 用 jsonb 存 `[ymin, xmin, ymax, xmax]`（0–1000，見 `ingestion.md`）。
- `downgrade()` 有完整反向操作，已實測 downgrade/upgrade 可往返。

## 設計決定

- **`questions.payload` 用 jsonb**：各題型欄位差異大，jsonb + Pydantic per-type schema 驗證；新增題型不需要 migration。payload 定義見 `question-bank.md`。
- **`jobs` 表就是 work queue**：worker 用 `SELECT ... FOR UPDATE SKIP LOCKED` 領任務，不引入 Celery/Redis。
- **`source_chunk_ids` 保留出題溯源**：每題可回查生成來源，審題時可對照原文。
- **`llm_usage` 支撐用量頁面**：使用者自付 API 費，累計 token 是必要的透明度。
- **pgvector 維度綁 `EMBEDDING_DIM`**：更換 embedding model 屬重大變更（re-embed + migration），必須先告知使用者。
- **`questions.embedding` 供題目語意搜尋**：選題的檢索單位是題目本身，不是來源 chunk（同一個 chunk 可生出題型難度都不同的題，chunk 相似度分不出來）。nullable，`NULL` 即「尚未向量化」，由 `embed_questions` job 補齊；維度沿用 `EMBEDDING_DIM`，不開第二個維度設定。見 `docs/decisions/2026-08-17-bank-agent-semantic-selection.md`。
- **`conversation_messages.steps` 記錄 agent 查詢過程**：jsonb，存該回合實際跑過的搜尋條件與命中數，讓選題助手不是黑箱。`conversation_id` 為 FK `ON DELETE CASCADE`，刪對話即刪訊息。
- **`proposed_question_ids` 是提案不是選取**：agent 選出的題目存在訊息上；前端點列跳到該題，使用者自己勾選才進入匯出範圍，與「LLM 產出先進待確認」的審題原則一致。
- **`folders` 為平面結構**：單人系統文件量小，不做巢狀資料夾；`documents.folder_id` nullable FK（`ON DELETE SET NULL`，刪資料夾文件自動變未分類，不擋刪除）。資料夾只影響文件庫瀏覽，與 `categories`（LLM 知識分類，供出題範圍）互不相干。
