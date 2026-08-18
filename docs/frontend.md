# 前端

## 技術

- Vue 3 + Vite，用 `npm create vue@latest` 建立於 `frontend/`。
- 路由 vue-router、狀態 Pinia、API 呼叫統一走 `/api/v1`（同源，經 proxy 反代，不需 CORS）。
- vue-router 與 Pinia 已隨 scaffold 安裝；實作功能頁時必須真正落地：頁面清單全部走 router 定義，跨頁狀態（job 輪詢、篩選條件等）放 Pinia store，不散落元件內。
- i18n 用 vue-i18n：介面文案全部進 locale 檔，但只做繁體中文（`zh-Hant-TW`）一種語言，不做語言切換功能。目的為文案集中管理，不是多語系。
- 禁止在元件內硬編碼中文文案（一律走 locale 檔），也禁止把假資料寫死在 view 裡。
- build 產物由獨立常駐 container `website`（`quiz-forge-website`）serve：`frontend/Dockerfile` multi-stage build（node build → nginx 靜態 serve，含 SPA `try_files` fallback），website 與 proxy 分離（見 `docs/decisions/2026-08-16-separate-frontend-container.md`）。

## 基礎架構（已實作）

- i18n：`src/i18n/`＋`src/locales/zh-Hant-TW.json`；`useAppI18n()`/`translate()` 是型別化包裝，key 型別由 locale JSON 推導，打錯 key 直接編譯錯誤。
- API client：`src/api/`（`config.ts` 的 `API_BASE_PATH`、`client.ts` fetch 包裝與 `ApiError`、`types.ts` 集中型別、各資源模組）。錯誤統一轉 `ApiError` 並抽出 FastAPI `detail`。
- Job 輪詢：`src/stores/jobs.ts`（Pinia，訂閱計數共用計時器、遞迴 setTimeout 防重疊、done/failed 停止）＋`src/composables/useJobPolling.ts`。
- 共用元件：`StatusBadge`（同時涵蓋 job 與 document/page 狀態字彙，純文字加語意色）、`ProgressText`（`3/12 pages`、`chunks 3/10` 本地化為「3 / 12 頁（25%）」）、`AppButton`（`icon` prop 提供方形 icon-only 尺寸，caller 必須給 `aria-label` 與 `title`）、`EmptyState`（一行置中淡字＋選用動作，沒有虛線框與底色）、`MarkdownContent`（markdown-it + DOMPurify，表格橫向捲動、圖片限寬、連結開新分頁）。
- 文件頁已實作：滿版工作區（見下）與詳情（逐頁狀態與單頁重試、markdown 圖文渲染、chunk 分類與標籤）。狀態輪詢規則：有 job id 就輪 job，否則輪 document 本身直到終態。
- locale key 群組：`status.*`、`documents.*`、`documentDetail.*`、`questions.*`、`editor.*`、`review.*`、`bank.*`、`generate.*`、`job.progress.*`、`errors.*` 等，全部經型別化 t()。
- 題目元件：`src/components/questions/` 六題型各一個顯示元件與編輯器，`QuestionDisplay` 依 type 派發，審題與題庫共用；類比題題幹由槽位組出，比較題答案以面向×A×B 表格呈現（面向是純文字不是膠囊）。`QuestionCard` 只有一種樣式：上下留白加一條底線分隔，沒有邊框卡片變體；題號留在標頭列、不顯示建立時間；狀態詞只在偏離該頁預期狀態時才出現（`expectedStatus` prop：審題 `draft`、題庫 `approved`）。`QuestionEditor` 以左側線標示編輯區，不是套在題列裡的面板；答案區同樣只用左側線，不加底色。
- 審題編輯 UX：答案用結構選取（單選以 radio 標正解、刪選項自動平移 index）、填充題即時檢查 `____` 數與答案數、空白解析正規化為 null；422 錯誤可讀化呈現。
- 出題頁（`docs/decisions/2026-08-17-professional-form-pages.md` D26）：三欄工作區（`page--workspace`，D35）——「出題範圍」「題目設定」「出題紀錄」各佔一欄，欄間分割線、各欄自體捲動；表單以 `display: contents` 橫跨前兩欄；出題紀錄 rail 有欄頭（標題＋筆數），空狀態置中在 rail 內；窄幅退回單欄堆疊。範圍選擇為兩個獨立 picker widget——欄位 label（文件／分類）右側的 plus icon 按鈕開 Modal（搜尋框＋有界捲動清單；文件顯示標題/來源/頁數且僅 ready 可選；分類為科目分組樹、勾科目展開為主題 id），已選項目以可移除 chips 呈現（單行 ellipsis、過多折疊「+N」）。**題型×數量×難度三欄列**（可增減列、同題型不重複、每列可獨立設難度，`docs/decisions/2026-08-18-generate-row-difficulty-percent-scoring.md` D31）；「新增題型」是「題目設定」小節標題右側的 plus icon 按鈕（D32）。「建立出題任務」是頁首右側主動作（native `form` 屬性連回表單），表單不再有底部送出列與合計文字。表單不套卡片；題型／題數／難度的可見 label 只出現在第一列（其餘列走 `aria-label`），列內移除是 icon 按鈕；出題紀錄每筆用分隔線不用邊框，逐項顯示「{題型} {N} 題（{難度}）」。
- 題庫頁（`docs/decisions/2026-08-17-bank-on-questions-page.md`）：左欄兩個檢視——「題庫」（debounce `q`＋語意 `similar_to`＋題型/難度/科目/主題＋真分頁）與「已選」（`exportSelection` 勾選順序，同一套題卡）。沒有「全選目前結果」。選取列只留題數（可切到已選）、前往匯出、清除選取。「新增題目」modal 重用六題型編輯器、可存草稿；每題「複製」「丟棄」用 icon 按鈕（`aria-label` 走 locale）；「管理分類」modal 支援改名/刪除。未向量化提示與「補向量」仍在左欄。題與題用分隔排，不是一疊獨立漂浮白卡。
- 選題助手是題庫右側可收合欄，不是獨立導覽頁。欄是固定高度的獨立捲動框：吃滿頁首以下剩餘視窗；只有訊息區捲動，欄頭與輸入框釘在欄內，不跟左欄清單共用 overflow（`docs/decisions/2026-08-17-bank-on-questions-page.md` D13）。欄內：目前對話訊息、輸入框、切換／新增／刪除對話。收合記 localStorage；窄幅預設收合。同一時間一個回合（`isBusy`）。題庫頁訂閱 `pendingTurn.jobId`（不限本則），沒有進行中回合時才訂閱本則 `failedTurn.jobId` 供重試；終態 `finishTurn`。離開 `/questions` 才停輪詢。訊息是時間軸文字，不是每則一張 bordered card；助手回覆用既有 `MarkdownContent`（markdown-it + DOMPurify）渲染。提案是扁平列，點列跳到左欄該題（只顯示這一題），沒有「加入選取」。Esc（或再按「題庫」）還原跳題前的篩選、頁碼與左欄捲動位置。套用查詢條件只寫篩選 store，不換頁。舊路由 `/conversations`、`/conversations/:id` `replace` 到 `/questions`（有 id 則打開該則）。實作：`src/views/QuestionBankView.vue`、`src/components/bank-agent/`（含右側欄殼）、`src/stores/bankAgent.ts`（active 對話由欄內狀態決定，可被舊網址 id 初始化）、`src/questions/agentSteps.ts`、`src/api/conversations.ts`、收合偏好 `src/questions/bankAgentPrefs.ts`。已刪獨立的 `ConversationListView`／`ConversationView`。
- 審題頁：伺服器端篩選與分頁、批次採用/丟棄（ConfirmDialog、逐題進度、單題失敗不中斷、總結 toast）。篩選列與批次列直接貼在工作面上、不是卡片；題目是分隔列不是漂浮卡；來源原文用左側線標示引用，不是套在題卡裡的面板；選取題數只在批次列出現一次。
- 匯出頁（`docs/decisions/2026-08-17-professional-form-pages.md` D29／D30）：必填考卷標題；已選題目與配分合併為一個「題目與配分」widget（`ExportQuestionsField`＋`ExportQuestionsModal`）——頁面上只留觸發按鈕與一行摘要（已選題數、合計配分），Modal 內為配分工具（目標總分＋「全部平均」＋各題型佔總分百分比＋「依比例分配」，最大餘數法整數化，兩者都寫成逐題配分，見 `docs/decisions/2026-08-18-generate-row-difficulty-percent-scoring.md` D33）＋逐題列表（題號、題型、預覽、逐題配分輸入、移除），已選清單不再攤平在頁面上。request 只送 `question_points`，不再送每題型預設 `points`。「已不在已採用題庫」警示仍顯示在頁面（會讓匯出失敗）。表頭欄位勾選群（班級／座號／姓名／總分欄）。紙張、表頭勾選、目標總分與題型百分比（`typePercents`／`targetTotal`）等偏好經 Pinia store 持久化到 localStorage，重開瀏覽器記住；題目選取與逐題配分放 `exportSelection` store，維持 session 內、跨頁保留（取消選取即刪該題配分）。歷史為可排序 DataTable，考卷標題單行 ellipsis＋tooltip，且自己有界捲動。頁面本體不套卡片；「依目標總分平均分配」的限制只在輸入的目標分數無法分配時才提示。
- 用量頁：總計四個數字（總 token／輸入 token／輸出 token／呼叫次數）用 `StatCard` 卡片呈現（D24）＋兩張可排序 DataTable，每張各自有界捲動；model 與 purpose 為開放字串，單行 ellipsis＋`title` tooltip。
- 難度字彙統一「簡單/中等/困難」（與後端分類 prompt 同組值，見 `src/questions/labels.ts`）。
- 匯出頁：消費 `exportSelection`（顯示已選題、單筆移除）、紙張選擇（尺寸常數鏡射自 `backend/export/paper.py`，JIS B）、job 進度、歷史紀錄與題目卷/答案卷下載（純 `<a>` 連結、由後端 Content-Disposition 決定檔名）；job 失敗保留選取並顯示違規 id。
- 用量頁：總計卡片 + 依 model/依用途兩表，purpose 未知值顯示原字串不隱藏。
- 八個導覽項對應的功能頁全部實作完成；尚未加 vitest（純函式模組 `usage/rows.ts` 等暫無單元測試，屬待補項目）。
- 佈局：側邊欄導覽（8 項：總覽/文件/出題/審題/題庫/匯出/任務/用量，inline SVG icon，窄幅自動縮為 icon-only）＋每頁 `PageHeader`（頁名＋計數在左、動作在右，D25）＋全寬內容區。選題助手掛在題庫右側，不是第九個導覽項。
- 頁首文案（D23 的頁名部分已被 `docs/decisions/2026-08-17-professional-form-pages.md` D25 推翻）：`PageHeader` 顯示可見頁名 `<h1>`（`pageName` prop，文案取自側邊欄的 `nav.*` key）作為每頁的版面錨點，左側接計數（「共 7 題」「待審 3 題」）、右側該頁動作。文件詳情以 `heading` prop（文件標題，是資料不是頁名，仍可 inline 改名）取代頁名。D23 其餘不變：不得寫說明頁面用途的導覽句（例如「瀏覽已採用的題目，依分類、題型與難度篩選並勾選送匯出。」）。
- 狀態呈現：表格、頁首與出題紀錄的狀態／題型標籤用純文字加語意色（已完成／處理中／失敗），不用圓角 pill／chip／tag。`StatusBadge` 不得再做成膠囊底色框。已選文件／分類的可移除 chips 仍保留（那是控制項，不是狀態裝飾）。
- 任務錯誤：任務中心「錯誤」欄只顯示給人看的一句摘要（例如「1 題出題失敗」），單行 ellipsis，完整說明放 `title` tooltip。不得在表格展開 exception 類名、`type='single_choice'`、chunk id、payload dump 等程式碼級細節。完整失敗紀錄留在後端 log。
- 設計系統 `src/components/ui/`：`DataTable`（泛型欄位定義、排序、sticky header、skeleton/empty；清單工作區傳 `fillHeight` 撐滿父層且不加邊框圓角，與篩選列同一塊工作面，其餘頁維持內容高度並保留邊框；欄位可設 `ellipsis` 讓開放字串單行截斷＋tooltip；表頭是可讀字級的標題色，不是灰色小字）、`StatCard`（label＋數字的卡片，只用於總覽與用量的總計；`hint` 只放畫面別處沒有的數字）、`AppModal`/`ConfirmDialog`（`useConfirm` promise 式）、`AppMenu`/`AppMenuItem`（列 overflow 選單）、`ToastHost`＋toasts store、`AppSkeleton`、`AppIcon`、`AppTabs`（底線式 tab，ARIA tabs pattern、隱藏面板不掛載內容故不觸發輪詢；文件頁已不再使用，同日 F1 的左欄 3 tab 已被 G1 推翻）。
- Dashboard（`/`）吃 `GET /v1/stats`；任務中心（`/jobs`）吃 `GET /v1/jobs`，僅在有進行中 job 時輪詢。
- 文件區是滿版工作區（`docs/decisions/2026-08-17-documents-workspace-layout.md`，視覺落地見 `docs/decisions/2026-08-17-documents-workspace-flush.md` L6／L7、`docs/decisions/2026-08-17-documents-workspace-bleed.md` L8）：頁首以下剩餘高度由左側資料夾欄＋右側表格吃滿，兩者中間一條分割線，都不是獨立圓角卡片。工作區左右出血與頁首底線同寬（負 margin 吃掉 `.page` gutter），分割線兩側不再加空白帶。左欄（`docs/decisions/2026-08-18-documents-library-single-filelist.md` G1–G3，推翻同日 F1 的 3 tab）：單一清單「全部／未分類／各資料夾」，選定項目持久化 localStorage；項目滿欄寬、無邊框（無左邊線與圓角底色，active 只靠字重與顏色）、純文字計數；點項目讓右側表格顯示全部／未分類／該資料夾內容；未分類與第一個資料夾之間一條分隔線（沒有資料夾時不顯示）。新增資料夾 band（plus icon 置中、整行可點、無分隔線、高度與清單列一致）常駐在分隔線與第一個資料夾之間。資料夾列上改名／刪除（刪除是 trash icon，按下開 ConfirmDialog，見 L5；刪除後文件變未分類）。文件列可拖放到資料夾項目或未分類項目（拖上去＝取消分類；HTML5 drag & drop，拖曳中目標高亮），drop 目標常駐可見故不需切檢視，全部不是 drop 目標；列選單「移至資料夾」維持當備援。表格 `table-layout: fixed`，標題欄吃剩餘寬度並單行 ellipsis；來源／狀態／頁數／時間固定窄欄；列動作收進 overflow 選單。搜尋列是表格欄頭：無獨立圓角邊框、左右與表頭對齊，與表頭之間一條分隔線，不是插在表上方的獨立輸入框。頁首主按鈕打開上傳 Modal（拖放檔案＋網址匯入）；網址顯示一律為解碼後的可讀文字（percent-encoded 中文顯示為中文）：輸入框在輸入時自動正規化（移除換行與空白、折行網址拼接成一行，並 `decodeURI` 顯示可讀文字），送出給後端的值才 percent-encode；文件庫標題、文件詳情來源連結等同理，顯示解碼文字、`href` 維持 encode 原值。實作在 `src/utils/url.ts`；成功後留在文件庫，新列自己顯示解析進度。`?tab=upload` 進入時打開該 Modal，關掉後 `replace` 拿掉 query。進行中或失敗份數可在搜尋與表之間用一行摘要提示，不再做第二個 tab、也不再掛 `DocumentActiveList` 卡片清單。文件改名於列選單與詳情頁 header 提供（inline 編輯，PATCH title）。詳情改雙欄（左 sticky 頁面導覽、右內容），header 左側有返回鈕（回文件庫），並提供重試解析/重新分段（rechunk，ConfirmDialog 註明會花 LLM 費用）/刪除。詳情頁的逐頁內容與 chunk 都不是卡片：上下留白加一條底線分隔；chunk 標籤是純文字串接不是 chips，只標示「未建立向量」的例外狀態；左欄分隔線吃滿整欄高度，只有頁面清單捲動。
- 尚無前端單元測試（scaffold 未含 vitest）；功能頁落地時再補 vitest。

## 頁面清單

| 路由 | 頁面 | 說明 |
|---|---|---|
| `/` | Dashboard | 總覽：文件/題目各狀態計數、待審 CTA、最近任務、累計 token |
| `/documents` | 文件區 | 滿版文件庫（左欄 filelist 全部／未分類／各資料夾＋滿高 DataTable，含搜尋與排序；列可拖入資料夾；列選單可改名／移動／刪除）。頁首打開上傳 Modal（拖放與網址匯入）；`?tab=upload` 會打開該 Modal |
| `/documents/:id` | 文件詳情 | 左欄頁面大綱（滿高側欄，不是卡片）＋右欄逐頁 Markdown（含裁切圖表）、chunk 與分類結果、失敗頁重試、重新 chunk |
| `/jobs` | 任務中心 | 滿版工作區：篩選列貼表格上方（不是獨立卡片），DataTable 吃滿剩餘高度；失敗重試；錯誤欄為人話摘要，狀態為純文字不是 tag |
| `/review` | 審題 | `draft` 題目列表，對照來源 chunk 原文，可編輯後採用／丟棄 |
| `/questions` | 題庫 | `approved` 題目瀏覽或已選檢視；右側可展開選題助手。依分類／題型／難度／語意搜尋篩選，逐題勾選送匯出 |
| `/conversations`、`/conversations/:id` | （舊網址） | `replace` 到 `/questions`；有 `:id` 時打開該則對話 |
| `/generate` | 出題 | 選範圍（文件／分類）、題型、數量，建立出題 job |
| `/exports` | 匯出 | 選紙張尺寸、歷次匯出紀錄、下載題目卷／答案卷 |
| `/usage` | 用量 | `llm_usage` 累計統計（依 model／用途） |

## 視覺風格

- 白色簡潔風：白底、留白充足、低彩度點綴色，不用深色主題。
- 移除 scaffold 預設的示範樣式與深色 media query，全站以淺色為唯一主題。
- 專業商業佈局：側邊欄導覽 + 每頁頁首列（頁名＋計數在左、主要動作在右），內容區依頁面性質用全寬 data table 或分欄，不再是置中單欄。
- 表單頁（出題、匯出）以區塊分組並加小節標題（`main.css` 的 `.form-section`／`.form-section__title`，hairline 分隔）；控制項統一樣式（一致高度、自訂 select 箭頭、`--focus-ring`、hover 邊框色、數字欄 `tabular-nums`），且寬度必須符合預期內容——數字欄固定窄寬、select 有上限寬度，不拉滿整欄（`docs/decisions/2026-08-17-professional-form-pages.md` D27／D28）。
- 清單工作區（文件庫、任務中心）必須吃滿頁首以下剩餘視窗高度。篩選列與表格是同一塊工作面，不是另掛一張圓角卡片。列少時表格表面仍拉到底，空白留在表內，不留在卡片下方。高度靠 flex 鏈傳下去：`.app-shell`（grid、`min-height: 100vh`）→ `.app-main`（flex column、撐滿格子）→ `.page.page--workspace`（`flex: 1; min-height: 0`）→ `.workspace` → `DataTable` 的 `fillHeight`。非工作區頁維持自然高度，不套 `page--workspace`。見 `docs/decisions/2026-08-17-list-pages-workspace.md`。題庫是分欄工作區（左清單＋右對話），不是 DataTable 頁。
- 文件詳情左側頁面大綱與文件庫資料夾欄同一語彙：滿高側欄加分割線，不是獨立圓角卡片。題庫右側對話欄同一語彙。出題表單、匯出表單不套卡片框。**唯一的卡片例外是總覽與用量的總計數字（`StatCard`）**，見 `docs/decisions/2026-08-17-drop-page-titles-keep-stat-cards.md` D24。題庫／審題的題目不要做成一疊各自帶完整邊框的漂浮卡。
- 頁首保持單行緊湊：標題＋計數即可，不放教學句。狀態是文字不是標籤。表格錯誤欄是人話，不是 stack trace。畫面上不常駐操作說明句。空狀態一律一行文字（＋必要時一個動作連結），沒有虛線框。重新整理／重試／移除／新增／改名／展開收合一律 icon-only（`AppButton` 的 `icon` prop），名稱走 `aria-label` 與 `title`；刪除與其他誤點會掉資料的動作保留文字。例外：文件庫資料夾列刪除用 trash icon，按下仍開 ConfirmDialog（L5）。選題助手空狀態只留一行置中淡字「開始對話找出題目」，不要虛線卡片框。輸入框固定列高、不可拉大，沒有「送出」鈕（Enter 送出、Shift+Enter 換行）。送出成功不跳 toast，訊息進時間軸、欄底顯示處理中就夠。
- 設計系統層：DataTable（可排序、hover、sticky header；清單工作區用父層撐滿高度的模式，其他頁維持內容高度）、Toast（操作回饋）、ConfirmDialog、Modal、列 overflow 選單、Skeleton loading；所有寫入操作必有成功/失敗回饋。浮層才用陰影，資料列與側欄不加陰影。

## 設計節制原則

全站合規基準，見 `docs/decisions/2026-08-17-ui-design-restraint.md`（D16–D22）。實作與檢視都以本節為準：

- **卡片不是骨架**：版面靠 grid/flex、間距、分割線、標題階層。卡片只用來框「有界捲動區」或「真正獨立的資料集」，最多一層，禁止卡中卡。需要卡中卡就是外層選錯了。
- **pill 只留封閉集合短詞**：狀態、題型、計數這種單行放得下的值才可以。開放內容（標題、分類名、任何會變長的字串）用純文字加語意色；pill 不能折行，在窄欄會被邊框切過文字。已選文件／分類的可移除 chips 是控制項，不受此限。
- **icon 優先於文字**：refresh／copy／close／add／edit／search／expand 等慣用動作一律 icon-only，名稱進 `aria-label` 與 tooltip（文案仍走 locale 檔）。只有「沒有公認 glyph」或「罕見且誤點會掉資料」的動作留文字。例外：文件庫資料夾列刪除用 trash icon，按下仍開 ConfirmDialog（`docs/decisions/2026-08-17-documents-folder-delete-icon.md` L5）；文件列刪除與批次丟棄仍留文字。
- **不重述外框已說的事**：側邊欄已標示所在頁，頁面不再重複頁名意義、不寫用途說明句；內容自明的區塊不加標題，欄位有 label 就不加下方註解。無障礙名稱例外（可視覺隱藏）。
- **不寫多餘輔助文字**：不配副標、不配提示、不配說明。文案要能講出畫面還沒說的事才留。
- **禁止灰色小字當折衷**：重要就給可讀字級與字重，不重要就刪；不用「縮小＋轉灰」處理拿不定主意的文字。
- **獨立區域各自捲動**：每個邏輯區域自訂高度、自持捲軸，不共用一條 overflow（題庫左右欄 D13、清單工作區同理）。
- **先用最樸素的手段**：weight／顏色優先於 chip，分割線優先於面板，間距優先於邊框。

## 清單有界原則

- 任何會隨資料增長的清單都不得讓頁面無限變長：必須用「有界高度＋內部捲動」、分頁、tab 或搜尋其中之一收束。
- 長標題（尤其 URL 型文件）一律單行 ellipsis 截斷，完整內容放 tooltip（`title` 屬性）；不允許多行折行撐版面。
- 選擇型控制項（挑文件、挑分類）不得把整份清單攤平在表單裡；一律用「觸發按鈕＋Modal picker（內含搜尋、有界捲動）＋已選 chips」的獨立 widget 形式。

## 互動原則

- 長任務（解析、出題、匯出）建立 job 後輪詢 `GET /api/v1/jobs/{id}` 顯示進度；多頁文件顯示逐頁進度（如「12/40 頁」）。
- 失敗以最小單位重試（單頁、單題），介面提供對應按鈕。
- 題目渲染元件依題型分開實作，與 `question-bank.md` 的 payload schema 一一對應。
