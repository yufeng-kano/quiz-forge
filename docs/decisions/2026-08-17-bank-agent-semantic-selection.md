# 題庫選題助手與題目語意搜尋

日期：2026-08-17

## 背景

題庫頁（`/questions`）目前只能用題型／難度／科目／主題四個 select 加上 `q`（`payload::text` 的 ILIKE）找題。實際使用時：

- `q` 只做字面比對，搜「三角函數應用」找不到題幹寫「已知 sin θ …，求塔高」的題。
- 要湊一份考卷，得自己想好條件、逐頁翻、逐題勾，題庫一大就不可行。
- 分類只到「科目／主題」兩層，粒度不足以表達「這一章偏應用的中等題」這種需求。

使用者明確要求：題庫頁加右側對話欄，用描述讓 agent 選題；並且一併補上題目層級的語意搜尋。

## 決策

### D1 `questions` 新增 embedding 欄位

`questions` 加 `embedding vector(EMBEDDING_DIM)`，nullable。

- 維度沿用既有 `EMBEDDING_DIM`，不新增第二個維度設定，也不換 embedding model。
- 向量化的輸入文字由 payload 攤平而來（題幹、選項、答案、解析、比較題的面向與 A/B 主體、類比題的四個槽位），實作在 `backend/src/backend/questions/embedding.py`，與 renderer 分離。
- `embedding IS NULL` 就是「尚未向量化」，不另外開狀態欄位。

理由：題目是選題的檢索單位，拿 chunk 的 embedding 代替會錯——一個 chunk 可以生出十題難度題型都不同的題，chunk 相似度無法區分它們。

### D2 既有題目用背景 job 補向量，不在請求路徑上同步 embed

新增 job kind `embed_questions`，payload `{"question_ids": null | [int]}`，`null` 代表補齊所有 `embedding IS NULL` 的題。

- progress 逐題更新（`12/40`），單題失敗只記進 `jobs.error` 不中斷其他題，符合「最小單位可重試」。
- `POST /v1/questions`（手動建題）與 `PATCH /v1/questions/{id}`（改到 payload 時）在寫入後把該題 `embedding` 設為 NULL，並排一個只含該題 id 的 `embed_questions` job。編輯不被 embedding API 的延遲或失敗擋住。
- 出題 job（`generate_questions`）在題目入庫時直接同步 embed，因為它本來就在背景執行。

### D3 語意搜尋接在既有 `GET /v1/questions` 上，不開新 endpoint

新增查詢參數 `similar_to`（自由文字）：

- 有 `similar_to` 時，後端先把它 embed 一次（purpose `question_search`），再以 cosine 距離排序，並過濾掉相似度低於 `QUESTION_SIMILARITY_MIN` 的題。
- 其餘既有參數（`status`／`type`／`difficulty`／`category_id`／`q`／`limit`／`offset`）全部照舊生效，語意搜尋是排序＋門檻，不是取代篩選。
- `similar_to` 與 `q` 可同時給：`q` 當硬條件（字面必須命中），`similar_to` 決定排序。
- `embedding IS NULL` 的題在 `similar_to` 查詢下不會出現；回應封包加 `unembedded_total` 讓前端提示「有 N 題尚未向量化」。

理由：選題助手和使用者手動篩選要走同一條查詢路徑，否則兩邊行為會漂移。

### D4 對話 agent 用「結構化輸出 + 後端有界迴圈」，不用 tool calling

新增 job kind `bank_agent_turn`。一個回合的流程：

1. 帶入系統 prompt（題庫 schema、可用篩選值、六種題型、難度字彙、分類樹摘要）、最近 `BANK_AGENT_HISTORY_LIMIT` 則訊息、使用者這次的輸入、以及前端傳來的目前已選題目 id。
2. LLM 以 `response_format: json_schema` 輸出一個 `BankAgentStep`：
   - `action: "search" | "propose" | "reply"`
   - `search`：`similar_to`／`q`／`type`／`difficulty`／`category_id`／`limit`
   - `question_ids`：`propose` 時要選的題目 id
   - `reply`：給使用者看的話
3. `action = "search"` 時後端執行 D3 的查詢，把命中題目的精簡摘要（id、題型、難度、分類路徑、題幹前 N 字）回餵給模型，進下一步。
4. `action = "propose"` 或 `"reply"` 結束回合。步數上限 `BANK_AGENT_MAX_STEPS`，達上限強制結束並在回覆中說明。

不用 OpenAI tool calling：`.rule` 要求結構化輸出一律走 `response_format: json_schema`，且 OpenRouter 各家 model 的 tool calling 支援程度不一，structured output 是共同分母。

### D5 agent 只「提案」，不直接改動匯出選取

agent 產出的 `question_ids` 存在該則 assistant 訊息的 `proposed_question_ids`，前端渲染成題目卡片，使用者按「加入選取」才寫進 `exportSelection` store。

理由與審題流程一致——LLM 的產出一律先進待確認狀態，由人決定是否採用。直接改選取會讓使用者不知道自己的勾選被誰動過。

### D6 對話持久化，但不做多使用者概念

新增 `conversations` 與 `conversation_messages` 兩張表。單人系統不做擁有者欄位；對話可多條、可刪除、標題由第一則使用者訊息截斷產生。

`conversation_messages.steps` 用 jsonb 記錄該回合 agent 實際跑過的搜尋條件與命中數，在 UI 上以可展開的「查詢過程」呈現。目的是讓選題不是黑箱：使用者看得到 agent 用什麼條件找到這些題，並能把同一組條件手動套進頁面篩選。

### D7 右側欄可收合，不動既有版面結構

題庫頁改為「主內容 + 右側面板」兩欄，面板寬度固定、內部自捲動，收合狀態持久化到 localStorage。窄視窗自動收合為浮動按鈕。既有的 `QuestionFilters`／`ExportSelectionBar`／分頁全部保留原位置與行為。

## 代價與風險

- **費用**：既有題目 re-embed 會產生一次性 embedding API 費用；此後每次語意搜尋一次 embed、每個 agent 回合 1～`BANK_AGENT_MAX_STEPS` 次 chat 呼叫。全部照舊記進 `llm_usage`，在用量頁看得到。
- **換 embedding model 的代價變大**：現在有 `chunks` 與 `questions` 兩處向量要一起 re-embed。
- **未建向量索引**：延續既有決定，資料量小先全表掃 cosine，不建 HNSW。
- **agent 選題品質不保證**：D5 的提案機制是防線，使用者仍須確認。

## 被否決的選項

- **只做結構化查詢、不做對話**：投入最小，但使用者明確要對話介面，且結構化查詢無法處理「這章比較難的那幾題再多找幾題像的」這種需要看到中間結果的需求。
- **拿 chunk embedding 代替題目 embedding**：不用 migration，但無法區分同一 chunk 生出的不同題，見 D1。
- **agent 直接寫入匯出選取**：少一次點擊，但違反「LLM 產出先進待確認」的專案原則，見 D5。
