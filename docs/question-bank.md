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

1. 使用者選定範圍（文件／分類），並組合**多個「題型 × 數量」項目**（如單選 10、是非 5、問答 2），一個 job 出完，建立出題 job（`POST /api/v1/generate`，body 帶 `items: [{question_type, count}]`）。progress 以全部題數合計顯示；單一項目全失敗不影響其他項目。
2. 素材選取（實作在 `backend/src/backend/questions/selection.py`）：
   - **比較題**：在**同科目**（分類階層的第一層；同主題反而配不出「相關但不相同」）內用 embedding 找相似度中段的 chunk 配對，區間由 `COMPARISON_SIMILARITY_MIN/MAX` 設定（預設 0.35–0.75），兩段一起餵給 `TEXT_MODEL`。
   - **類比題**：從單一 chunk 內的概念關係抽取。
   - 其他題型：單一 chunk 直接生成。
3. 生成一律 `response_format: json_schema` 強制輸出對應題型 schema，附 `source_chunk_ids`。
4. 生成結果全部以 `status = draft` 入庫。

### 題幹自足原則

- 題目必須**離開教材也能作答**：題幹要自帶必要脈絡（主題名稱、關鍵事實、引文或情境描述），不得依賴受測者看過來源文件。
- 禁止「根據教材內容」「根據上文／本文／課文」「文中提到」這類指涉來源的措辭；prompt 明文禁止，並在生成後做字串檢查，命中即該題重生（重生仍命中則該題記為失敗，不入庫）。
- 涉及教材特有名詞（如「Hands-on Lab 2」這種文件內部編號）時，題幹必須補足該名詞的內容描述，或改寫成不依賴內部編號的問法。

## 審題流程

目的：LLM 出題必有爛題（答案錯誤、選項含糊、題幹引用不存在的上下文、重複題），必須人工把關後才能進入列印範圍。

1. 「待審題目」頁列出所有 `draft` 題目，可對照 `source_chunk_ids` 原文（`GET /api/v1/questions/{id}` 內含來源 chunk 全文）。
2. 使用者可直接編輯題幹／選項／答案（`PATCH`，經 discriminated union 驗證），然後「採用」（`approved`）或「丟棄」（`rejected`）。
3. 只有 `approved` 題目出現在題庫瀏覽與 Word 匯出的選題範圍。

### 狀態機

- `approve`：僅 `draft → approved`，其他狀態回 409。
- `reject`：任何狀態皆可按——`draft/approved → rejected`；對已是 `rejected` 的題目再按一次會回到 `draft`（復原誤丟棄）。
- 單題生成失敗不會使整個出題 job 失敗；job 結束時把失敗摘要記在 `jobs.error`，全部失敗才標 `failed`。寫進 `jobs.error` 的是給使用者看的人話（題數、題型、原因類別），不得含 exception 類名、repr、payload dump、chunk id 清單。完整例外只寫後端 log。

### 手動建題與複製

- `POST /api/v1/questions`：手動建題（同一份 union 驗證），預設 `approved`、可指定 `draft`，`source_chunk_ids` 為空。
- `POST /api/v1/questions/{id}/duplicate`：複製為 `draft` 改造變體。

## 題目向量化與語意搜尋

決策見 `docs/decisions/2026-08-17-bank-agent-semantic-selection.md`。

- `questions.embedding` 為 `vector(EMBEDDING_DIM)`，nullable；`NULL` 代表尚未向量化。
- 向量化輸入文字由 payload 攤平而來（題幹、選項、答案、解析；比較題另含 A/B 主體與面向，類比題含四個槽位），實作在 `backend/src/backend/questions/embedding.py`，與 Word renderer 分離。
- 寫入時機：
  - `generate_questions` job 入庫時同步 embed（本來就在背景）。
  - `POST /api/v1/questions`、`PATCH /api/v1/questions/{id}`（有動到 payload 時）把 `embedding` 設為 NULL，並排一個只含該題 id 的 `embed_questions` job，不讓 embedding 延遲或失敗擋住編輯。
- `embed_questions` job：payload `{"question_ids": null | [int]}`，`null` 代表補齊全部 `embedding IS NULL` 的題；progress 逐題更新，單題失敗記入 `jobs.error` 不中斷其他題。`jobs.error` 同樣只寫人話摘要。
- `GET /api/v1/questions` 的 `similar_to` 參數做語意搜尋：把文字 embed 一次（purpose `question_search`），以 cosine 距離排序，過濾相似度低於 `QUESTION_SIMILARITY_MIN` 的題。既有篩選全部照常生效——語意是排序加門檻，不取代篩選；`q` 與 `similar_to` 併用時 `q` 是硬條件、`similar_to` 決定順序。未向量化的題不會出現在 `similar_to` 查詢結果，回應封包的 `unembedded_total` 供前端提示補向量。

## 題庫選題助手（對話 agent）

掛在題庫頁（`/questions`）右側可收合欄（`docs/decisions/2026-08-17-bank-on-questions-page.md` D10、D13）。側邊欄沒有獨立「選題助手」項。舊網址 `/conversations`、`/conversations/:id` 導向題庫（有 id 則打開該則對話）。右欄固定高度、只捲訊息；輸入框釘在欄底，不跟左欄清單共用捲動框。

題庫左欄兩個檢視：題庫（篩選＋分頁）與已選（`exportSelection` 勾選順序）。沒有「全選目前結果」。語意搜尋與補向量仍留在題庫篩選列。

- 一個回合＝一個 `bank_agent_turn` job；題庫頁訂閱 `pendingTurn.jobId` 並輪詢 `GET /api/v1/jobs/{id}`，完成後清掉 `pendingTurn` 並重讀該則訊息。同一時間只跑一個回合；失敗重試出現在送出該回合的那則對話。離開 `/questions` 才停止輪詢。
- 後端跑有界迴圈（上限 `BANK_AGENT_MAX_STEPS`），每一步用 `response_format: json_schema` 取得一個 `BankAgentStep`：
  - `action`：`search`／`propose`／`reply`
  - `search`：`similar_to`／`q`／`type`／`difficulty`／`category_id`／`limit`
  - `question_ids`：`propose` 時選出的題目
  - `reply`：給使用者看的話
- agent 的搜尋固定 `status = approved`，這不是模型可控欄位：agent 只提案給匯出用，未採用的題目提了也沒用。
- `search` 步驟與 `GET /v1/questions` 共用同一個查詢函式（`backend/src/backend/questions/search.py`），兩邊行為不會漂移。
- `action = search` 時後端執行上節的查詢，把命中題目的精簡摘要（id、題型、難度、分類路徑、題幹前 N 字，上限 `BANK_AGENT_SEARCH_LIMIT`）回餵模型；`propose`／`reply` 結束回合，達步數上限則強制結束並在回覆說明。
- prompt 帶入題庫 schema、六題型、難度字彙、分類樹摘要、最近 `BANK_AGENT_HISTORY_LIMIT` 則訊息，以及前端傳來的目前已選題目 id。
- **agent 只提案不改選取**：`question_ids` 存進該則 assistant 訊息的 `proposed_question_ids`。點提案列跳到左欄該題（只顯示這一題），使用者看過再用 checkbox 勾選。Esc 還原跳題前的篩選與捲動。助手不寫入匯出選取。助手回覆的 `content` 以 Markdown 渲染（與文件頁同一套 sanitizer）。
- 該回合跑過的搜尋條件與命中數存進 `steps`，右側欄以可展開的「查詢過程」呈現；「套用到篩選」只寫入題庫篩選，人已在題庫頁不換頁。

### 相關 API

- `GET /api/v1/questions` 支援 `limit/offset`（回傳含 `total` 的分頁封包）與 `q` 全文搜尋（payload 文字 ILIKE）；`similar_to` 做語意排序，回應另含 `unembedded_total`。
- `POST /api/v1/questions/embed`：建立 `embed_questions` job（body `{"question_ids": null | [int]}`），回 job id。
- `GET /api/v1/conversations`、`POST /api/v1/conversations`、`GET /api/v1/conversations/{id}`（含訊息）、`DELETE /api/v1/conversations/{id}`。
- `POST /api/v1/conversations/{id}/messages`：body 帶 `content` 與目前 `selected_question_ids`，建立 `bank_agent_turn` job，回 `{job_id, message_id}`。
- `GET /api/v1/categories`：全部分類（flat，`id/name/parent_id`），供出題範圍選擇與分類路徑顯示；`PATCH .../{id}` 改名、`DELETE .../{id}`（有 chunk 引用或子分類時 409）。
- `GET /api/v1/documents*` 帶 `latest_job`（id/status/error），供前端顯示歷史失敗與重試。
