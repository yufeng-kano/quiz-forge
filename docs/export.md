# Word 匯出

## 輸出內容

每次匯出產生兩份 `.docx`：

1. **題目卷**：題目本體，供列印作答。
2. **答案卷**：題目 + 答案 + 解析；比較題的答案 render 成異同表格。

紀錄存 `exports` 表，檔案放 `DATA_DIR` 下，可重複下載。

## 技術

- `python-docx` 生成；頁面尺寸以 mm 直接設定（實作在 `backend/src/backend/export/`）。
- 支援紙張：A4、B4、B3，採 JIS B 系列尺寸（台灣考卷慣例的 B4=257×364mm，非 ISO B）；常數在 `export/paper.py`。
- 每個題型一個 render 函式，輸入為該題型的 Pydantic model（與 `question-bank.md` 同一份定義，`questions/schemas.py`）。
- 全題自動連續編號；選擇/是非題附「配分：______分」手填欄（schema 無配分資料，留白由老師填）。
- 版面樣式集中在 `export/style.py`；CJK 字型設定「微軟正黑體」——docx 只存字型名稱，由開啟檔案的電腦提供字型，container 不需安裝。

## API

- `POST /api/v1/exports`（question_ids + paper_size + 配分與表頭選項，全部必須 `approved`，否則 job 失敗並列出違規 id）→ export job。
- 配分參數：每題型預設配分 `points`（API 保留、Word render 邏輯不變）＋ `question_points`（`{question_id: 分數}`，逐題覆寫，優先於題型預設）。前端自 `docs/decisions/2026-08-18-generate-row-difficulty-percent-scoring.md` D33 起只送 `question_points`（配分工具以「目標總分＋題型百分比＋平均分配」產生逐題配分）。
- 表頭選項 `header_fields`：`class`／`seat`／`name`／`score`（總分欄）四個布林，預設全開；控制卷首學生資訊列與總分顯示。
- `GET /api/v1/exports` 歷次紀錄；`GET /api/v1/exports/{id}/questions.docx`、`.../answers.docx` 下載。
- 檔案落在 `DATA_DIR/exports/{id}-questions.docx` 與 `{id}-answers.docx`。

## 選題流程

1. 使用者從題庫（僅 `approved`）勾選題目或按分類/題型/難度篩選。
2. 設定考卷標題、紙張尺寸與（選擇性）每題型配分，建立匯出 job。
3. 完成後提供題目卷與答案卷下載連結。

## 卷面結構

- 卷首：考卷標題（`exports.title`）、學生資訊列（僅列 `header_fields` 勾選的欄位；全不勾則整列省略）；任一題有配分且 `score` 開啟時印總分（= 全卷配分合計）。
- 題目依題型分節（一、選擇題…固定順序），節內連續編號。
- 配分印法：節內每題分數一致時節標題印「每題 X 分」；不一致時各題題號後印「（X 分）」。有配分資料的題目不再印「配分：______分」手填欄；完全沒設配分維持現行手填欄行為。
- 配分等其餘匯出參數存 job payload，不落 exports 資料欄。

## 待確認

- 客戶提出「B3」尺寸較少見（台灣考卷慣用 B4），交付前向客戶再確認一次。
