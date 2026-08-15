# 前端

## 技術

- Vue 3 + Vite，用 `npm create vue@latest` 建立於 `frontend/`。
- 路由 vue-router、狀態 Pinia、API 呼叫統一走 `/api/v1`（同源，經 nginx 反代，不需 CORS）。
- vue-router 與 Pinia 已隨 scaffold 安裝；實作功能頁時必須真正落地：頁面清單全部走 router 定義，跨頁狀態（job 輪詢、篩選條件等）放 Pinia store，不散落元件內。
- i18n 用 vue-i18n：介面文案全部進 locale 檔，但只做繁體中文（`zh-Hant-TW`）一種語言，不做語言切換功能。目的為文案集中管理，不是多語系。
- 禁止在元件內硬編碼中文文案（一律走 locale 檔），也禁止把假資料寫死在 view 裡。
- build 產物交由 nginx serve，不做常駐 container。

## 基礎架構（已實作）

- i18n：`src/i18n/`＋`src/locales/zh-Hant-TW.json`；`useAppI18n()`/`translate()` 是型別化包裝，key 型別由 locale JSON 推導，打錯 key 直接編譯錯誤。
- API client：`src/api/`（`config.ts` 的 `API_BASE_PATH`、`client.ts` fetch 包裝與 `ApiError`、`types.ts` 集中型別、各資源模組）。錯誤統一轉 `ApiError` 並抽出 FastAPI `detail`。
- Job 輪詢：`src/stores/jobs.ts`（Pinia，訂閱計數共用計時器、遞迴 setTimeout 防重疊、done/failed 停止）＋`src/composables/useJobPolling.ts`。
- 共用元件：`StatusBadge`（同時涵蓋 job 與 document/page 狀態字彙）、`ProgressText`（`3/12 pages`、`chunks 3/10` 本地化為「3 / 12 頁（25%）」）、`AppButton`、`EmptyState`、`MarkdownContent`（markdown-it + DOMPurify，表格橫向捲動、圖片限寬、連結開新分頁）。
- 文件頁已實作：兩 tab（見下）與詳情（逐頁狀態與單頁重試、markdown 圖文渲染、chunk 分類與標籤）。狀態輪詢規則：有 job id 就輪 job，否則輪 document 本身直到終態。
- locale key 群組：`status.*`、`documents.*`、`documentDetail.*`、`questions.*`、`editor.*`、`review.*`、`bank.*`、`generate.*`、`job.progress.*`、`errors.*` 等，全部經型別化 t()。
- 題目元件：`src/components/questions/` 六題型各一個顯示元件與編輯器，`QuestionDisplay` 依 type 派發，審題與題庫共用；類比題題幹由槽位組出，比較題答案以面向×A×B 表格呈現。
- 審題編輯 UX：答案用結構選取（單選以 radio 標正解、刪選項自動平移 index）、填充題即時檢查 `____` 數與答案數、空白解析正規化為 null；422 錯誤可讀化呈現。
- 出題頁：範圍選擇為兩個獨立 picker widget——「選擇文件」「選擇分類」按鈕開 Modal（搜尋框＋有界捲動清單；文件顯示標題/來源/頁數且僅 ready 可選；分類為科目分組樹、勾科目展開為主題 id），已選項目以可移除 chips 呈現（單行 ellipsis、過多折疊「+N」）。**題型×數量組合列**（可增減列、同題型不重複、合計題數與預估 LLM 呼叫數顯示）、難度、job 進度與本 session 歷史（右欄有界捲動）。
- 題庫頁：debounce 搜尋（`q`）＋篩選（題型/難度/科目/主題）＋真分頁（`AppPagination`，頁量對齊後端 default limit）；「新增題目」modal 重用六題型編輯器（`QuestionPayloadFields`）、可存草稿；每題可「複製」成草稿改造；「管理分類」modal 支援改名/刪除（409 原因直出）。勾選存 `exportSelection` Pinia store 跨頁保留，供匯出頁消費。
- 審題頁：伺服器端篩選與分頁、批次採用/丟棄（ConfirmDialog、逐題進度、單題失敗不中斷、總結 toast）。
- 匯出頁：必填考卷標題、僅對選取中存在的題型顯示配分輸入；歷史為可排序 DataTable。
- 用量頁：總計 StatCard ＋ 兩張可排序 DataTable。
- 難度字彙統一「簡單/中等/困難」（與後端分類 prompt 同組值，見 `src/questions/labels.ts`）。
- 匯出頁：消費 `exportSelection`（顯示已選題、單筆移除）、紙張選擇（尺寸常數鏡射自 `backend/export/paper.py`，JIS B）、job 進度、歷史紀錄與題目卷/答案卷下載（純 `<a>` 連結、由後端 Content-Disposition 決定檔名）；job 失敗保留選取並顯示違規 id。
- 用量頁：總計卡片 + 依 model/依用途兩表，purpose 未知值顯示原字串不隱藏。
- 七頁全部實作完成；尚未加 vitest（純函式模組 `usage/rows.ts` 等暫無單元測試，屬待補項目）。
- 佈局：側邊欄導覽（8 項：總覽/文件/出題/審題/題庫/匯出/任務/用量，inline SVG icon，窄幅自動縮為 icon-only）＋每頁 `PageHeader`（標題左、動作右）＋全寬內容區。
- 設計系統 `src/components/ui/`：`DataTable`（泛型欄位定義、排序、sticky header、skeleton/empty）、`AppModal`/`ConfirmDialog`（`useConfirm` promise 式）、`ToastHost`＋toasts store、`AppSkeleton`、`StatCard`、`AppIcon`、`AppTabs`（底線式 tab，ARIA tabs pattern、隱藏面板不掛載內容故不觸發輪詢）。
- Dashboard（`/`）吃 `GET /v1/stats`；任務中心（`/jobs`）吃 `GET /v1/jobs`，僅在有進行中 job 時輪詢。
- 文件區為兩 tab：「上傳」（拖放上傳、網址匯入、進行中/失敗文件的有界清單）與「文件庫」（預設；DataTable 含標題搜尋與欄位排序）。tab 記在路由 query（`?tab=upload`，預設不帶）；上傳/匯入完成自動切回「上傳」tab。詳情改雙欄（左 sticky 頁面導覽、右內容），header 提供重試解析/重新分段（rechunk，ConfirmDialog 註明會花 LLM 費用）/刪除。
- 尚無前端單元測試（scaffold 未含 vitest）；功能頁落地時再補 vitest。

## 頁面清單

| 路由 | 頁面 | 說明 |
|---|---|---|
| `/` | Dashboard | 總覽：文件/題目各狀態計數、待審 CTA、最近任務、累計 token |
| `/documents` | 文件區 | 兩個 tab：「上傳」（拖放上傳、網址匯入、進行中的解析任務）與「文件庫」（list 模式 DataTable，含搜尋與排序） |
| `/documents/:id` | 文件詳情 | 逐頁渲染 Markdown（含裁切圖表）、chunk 與分類結果、失敗頁重試、重新 chunk |
| `/jobs` | 任務中心 | 全域 job 列表（篩狀態/種類）、失敗重試 |
| `/review` | 審題 | `draft` 題目列表，對照來源 chunk 原文，可編輯後採用／丟棄 |
| `/questions` | 題庫 | `approved` 題目瀏覽，依分類／題型／難度篩選，勾選送匯出 |
| `/generate` | 出題 | 選範圍（文件／分類）、題型、數量，建立出題 job |
| `/exports` | 匯出 | 選紙張尺寸、歷次匯出紀錄、下載題目卷／答案卷 |
| `/usage` | 用量 | `llm_usage` 累計統計（依 model／用途） |

## 視覺風格

- 白色簡潔風：白底、留白充足、低彩度點綴色，不用深色主題。
- 移除 scaffold 預設的示範樣式與深色 media query，全站以淺色為唯一主題。
- 專業商業佈局：側邊欄導覽 + 每頁標題列（標題左、主要動作右），內容區依頁面性質用全寬 data table 或分欄，不再是置中單欄。
- 設計系統層：DataTable（可排序、hover、sticky header）、Toast（操作回饋）、ConfirmDialog、Modal、Skeleton loading；所有寫入操作必有成功/失敗回饋。

## 清單有界原則

- 任何會隨資料增長的清單都不得讓頁面無限變長：必須用「有界高度＋內部捲動」、分頁、tab 或搜尋其中之一收束。
- 長標題（尤其 URL 型文件）一律單行 ellipsis 截斷，完整內容放 tooltip（`title` 屬性）；不允許多行折行撐版面。
- 選擇型控制項（挑文件、挑分類）不得把整份清單攤平在表單裡；一律用「觸發按鈕＋Modal picker（內含搜尋、有界捲動）＋已選 chips」的獨立 widget 形式。

## 互動原則

- 長任務（解析、出題、匯出）建立 job 後輪詢 `GET /api/v1/jobs/{id}` 顯示進度；多頁文件顯示逐頁進度（如「12/40 頁」）。
- 失敗以最小單位重試（單頁、單題），介面提供對應按鈕。
- 題目渲染元件依題型分開實作，與 `question-bank.md` 的 payload schema 一一對應。
