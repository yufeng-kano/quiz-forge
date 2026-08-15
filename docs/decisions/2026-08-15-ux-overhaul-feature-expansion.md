# UX 大改與功能補強

初版（開發順序 1–5）完成後，使用者判定：介面是原型等級、功能深度不足（「玩具」）。本決策定義補強範圍。

## 決策

### F1. 題目手動建立與複製

- `POST /api/v1/questions`：手動建題，payload 走同一份 discriminated union 驗證；手動題預設 `approved`（老師自己寫的不需審），可指定 `draft`。`source_chunk_ids` 空陣列。
- `POST /api/v1/questions/{id}/duplicate`：複製為 `draft` 供改造變體。

### F2. 匯出強化——可直接拿去考試的卷子

- 匯出參數新增：考卷標題（印在卷首）、選擇性「每題型配分」。
- 卷首固定印學生資訊列（班級／座號／姓名）。
- 題目依題型分節（一、選擇題…節標題與題型順序固定），節內連續編號；有配分時節標題印「每題 X 分」，卷首印總分。
- `exports` 表加 `title` 欄位（migration）；其餘參數存 job payload。

### F3. 題庫可搜尋、可分頁

- `GET /api/v1/questions` 增加 `limit/offset` 與 `total` 回傳封包，及 `q` 全文搜尋（payload 文字 ILIKE）。

### F4. 分類管理

- `PATCH /api/v1/categories/{id}`：改名。
- `DELETE /api/v1/categories/{id}`：僅允許無 chunk 引用且無子分類時刪除，否則 409。
- 不做合併（需求不明，等實際使用再說）。

### F5. 全域任務視角與總覽

- `GET /api/v1/jobs`：任務列表（篩 status/kind、新到舊、limit）。
- `GET /api/v1/stats`：documents/questions 各狀態計數、chunk 數、分類數、近期失敗 job 數、累計 token。
- 前端新增 Dashboard（`/`）與任務中心（`/jobs`）；文件列表移到 `/documents`。

### F6. 補頁後可重新 chunk

- `POST /api/v1/documents/{id}/rechunk`：以 job 重跑整個 chunk 階段（刪舊 chunk 重建；頁面解析不動）。關閉 ingestion 已知限制。

### U1. 專業版面

- 側邊欄導覽 + 頁面標題列（主要動作靠右）取代頂欄置中單欄。
- 建立設計系統層：DataTable（可排序）、Toast、ConfirmDialog、Modal、Skeleton；所有操作有即時回饋。
- 維持白色簡潔風與單一淺色主題不變。

## 理由

- 補強項全部圍繞「老師實際出一份考卷」的完整路徑：可控題目來源（F1）、可用的卷面（F2）、找得到題（F3/F5）、管線可自癒（F6）。
- 不做的：題目相似度去重提示、分類合併、多使用者——價值不明或違反單人定位，等真實使用回饋。

## 影響

- `GET /v1/questions` 回傳格式改為分頁封包，前端型別同步改（breaking，一次到位）。
- 前端路由 `/` 改為 Dashboard，文件列表移 `/documents`。
