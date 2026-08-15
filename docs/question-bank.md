# 題庫：題型定義、出題與審題

## 題型與 payload schema

`questions` 共用欄位：`id, type, difficulty, status, source_chunk_ids[], payload jsonb`。

同一份 Pydantic discriminated union（以 `type` 區分）同時作為：API 驗證、LLM structured output 的 json_schema、Word renderer 的輸入型別。新增題型 = 新增一個 Pydantic model + 一個 render 函式，零 migration。

### `comparison` 比較題

```json
{
  "stem": "試比較光合作用與呼吸作用之異同。",
  "subject_a": "光合作用",
  "subject_b": "呼吸作用",
  "aspects": ["場所", "能量轉換", "原料與產物"],
  "model_answer": {
    "similarities": ["皆為細胞內能量代謝反應"],
    "differences": [
      {"aspect": "場所", "a": "葉綠體", "b": "粒線體"}
    ]
  }
}
```

答案結構化成異同表，答案卷 render 成表格（面向 × A × B）。

### `analogy` 類比題

```json
{
  "a": "筆", "b": "寫字", "c": "剪刀",
  "answer": "剪裁",
  "options": ["剪裁", "縫紉", "烹飪", "測量"],
  "explanation": "工具之於其功能"
}
```

- 不存題幹、存槽位：題幹「A 之於 B，猶如 C 之於＿＿」由 renderer 組出，格式恆一致。
- `options` 為 null 時 render 成填空形式，有值時 render 成單選形式。

### `single_choice` 單選題

```json
{"stem": "...", "options": ["...", "...", "...", "..."], "answer_index": 2, "explanation": "..."}
```

### `true_false` 是非題

```json
{"stem": "...", "answer": true, "explanation": "..."}
```

### `fill_blank` 填充題

```json
{"stem": "水的化學式為 ____，由 ____ 與氧組成。", "answers": ["H2O", "氫"]}
```

`stem` 內以 `____` 標記空格，`answers` 依空格順序對應。

### `short_answer` 問答題

```json
{"stem": "...", "model_answer": "...", "key_points": ["...", "..."]}
```

## 出題流程

1. 使用者選定範圍（文件／分類）、題型與數量，建立出題 job（`POST /api/v1/generate`）。
2. 素材選取（實作在 `backend/src/backend/questions/selection.py`）：
   - **比較題**：在**同科目**（分類階層的第一層；同主題反而配不出「相關但不相同」）內用 embedding 找相似度中段的 chunk 配對，區間由 `COMPARISON_SIMILARITY_MIN/MAX` 設定（預設 0.35–0.75），兩段一起餵給 `TEXT_MODEL`。
   - **類比題**：從單一 chunk 內的概念關係抽取。
   - 其他題型：單一 chunk 直接生成。
3. 生成一律 `response_format: json_schema` 強制輸出對應題型 schema，附 `source_chunk_ids`。
4. 生成結果全部以 `status = draft` 入庫。

## 審題流程

目的：LLM 出題必有爛題（答案錯誤、選項含糊、題幹引用不存在的上下文、重複題），必須人工把關後才能進入列印範圍。

1. 「待審題目」頁列出所有 `draft` 題目，可對照 `source_chunk_ids` 原文（`GET /api/v1/questions/{id}` 內含來源 chunk 全文）。
2. 使用者可直接編輯題幹／選項／答案（`PATCH`，經 discriminated union 驗證），然後「採用」（`approved`）或「丟棄」（`rejected`）。
3. 只有 `approved` 題目出現在題庫瀏覽與 Word 匯出的選題範圍。

### 狀態機

- `approve`：僅 `draft → approved`，其他狀態回 409。
- `reject`：任何狀態皆可按——`draft/approved → rejected`；對已是 `rejected` 的題目再按一次會回到 `draft`（復原誤丟棄）。
- 單題生成失敗不會使整個出題 job 失敗；job 結束時把失敗摘要記在 `jobs.error`，全部失敗才標 `failed`。

### 手動建題與複製

- `POST /api/v1/questions`：手動建題（同一份 union 驗證），預設 `approved`、可指定 `draft`，`source_chunk_ids` 為空。
- `POST /api/v1/questions/{id}/duplicate`：複製為 `draft` 改造變體。

### 相關 API

- `GET /api/v1/questions` 支援 `limit/offset`（回傳含 `total` 的分頁封包）與 `q` 全文搜尋（payload 文字 ILIKE）。
- `GET /api/v1/categories`：全部分類（flat，`id/name/parent_id`），供出題範圍選擇與分類路徑顯示；`PATCH .../{id}` 改名、`DELETE .../{id}`（有 chunk 引用或子分類時 409）。
- `GET /api/v1/documents*` 帶 `latest_job`（id/status/error），供前端顯示歷史失敗與重試。
