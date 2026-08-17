# 出題逐題型難度（三欄列）、頁首送出、配分改百分比工具

- 日期：2026-08-18
- 狀態：已決定
- 背景：使用者回饋三件事——(1) 匯出配分輸入時 crash（`TypeError: e.trim is not a function`）；(2) 配分應該改成「各題型佔總分多少 %，並可平均分配」；(3) 出題頁的題型列要改 3 欄（每個題型可單獨設難度）、選擇文件／選擇分類／新增題型改成文字右側的 icon、送出鈕移到頁首、移除「共 N 題約 N 次 LLM 呼叫」文字。

## D31：出題難度改為逐題型（題型 × 數量 × 難度 三欄列）

- `POST /api/v1/generate` 的 `items[]` 每項新增選填 `difficulty`；request 層級的共用 `difficulty` 從 `GenerateIn` 移除（pydantic 對多餘欄位預設忽略，舊 client 不會 422）。
- worker（`generate_questions`）以 item 的 `difficulty` 為準；item 沒帶時回退 job payload 的 job-level `difficulty`，讓改版前已排入佇列的 job 重試時行為不變。
- 前端出題列改為「題型｜題數｜難度」三欄＋移除鈕；獨立的整份難度欄位取消。
- 出題紀錄逐項顯示「{題型} {N} 題（{難度}）」，meta 行不再有整份難度。

## D32：出題頁首放主動作、icon 化觸發鈕（調整 D28）

- 「建立出題任務」移到 `PageHeader` 右側動作區（native `form` 屬性連回表單），表單底部的送出列與「共 N 題，約 N 次 LLM 呼叫」文字移除。
- 「選擇文件」「選擇分類」文字按鈕改為欄位 label 右側的 plus icon 按鈕；「新增題型」改為「題目設定」小節標題右側的 plus icon 按鈕（`aria-label`／`title` 保留全名）。D28 的「表單內新增動作帶文字」在此被使用者回饋推翻：icon 緊貼在它作用的標題／label 右側時位置本身就說明了用途。

## D33：配分改「目標總分＋題型百分比＋平均分配」

- 移除「每題型預設配分（每題 X 分）」概念的 UI 與偏好：`exportPrefs` 的 `typePoints` 廢棄，改存 `typePercents`（各題型佔總分的百分比）與 `targetTotal`（目標總分，預設 100）；storage key 沿用 v1，舊值中的 `typePoints` 讀取時直接忽略（parser 逐欄容錯）。
- 配分 Modal 的工具列：目標總分輸入＋「全部平均」（全部題目均分）＋各題型百分比輸入（顯示該型題數與比例合計）＋「依比例分配」（各型分得 `目標×%`，型內均分；最大餘數法保證整數且合計等於目標）。兩種分配都寫成逐題配分，逐題輸入仍可微調。
- 送出 request 不再帶 `points`（每題型預設配分）；後端該參數保留不動（`ExportIn.points` 仍有效，Word render 邏輯不變），只是前端一律以 `question_points` 表達。
- 合計、已配分題數等摘要全部改為只看逐題配分。

## D35：出題頁改三欄並排（細化 D26 的分欄）

- 「出題範圍」「題目設定」不再是左欄內上下疊的兩個區塊，而是各佔一欄：頁面固定三欄——出題範圍｜題目設定｜出題紀錄，欄間以分割線隔開，各欄自體捲動。
- 表單元素以 `display: contents` 橫跨前兩欄（submit 行為不受 layout 影響，頁首送出鈕靠 native `form` 屬性）。
- 窄幅（≤960px）退回單欄堆疊，分割線轉為水平。

## D34：配分輸入 crash 修正（bug）

- 原因：`<input type="number">` 搭配 `v-model` 時 Vue 會自動把值轉成 number，`parsePointsInput` 對著 number 呼叫 `.trim()` 直接 TypeError。
- 修正：`parsePointsInput`（與新的百分比 parser）接受 `string | number`，先正規化成字串再驗證；配分相關輸入一律改走 `:value`＋`@input` 讀 `element.value`。
