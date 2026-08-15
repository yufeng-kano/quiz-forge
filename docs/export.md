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

- `POST /api/v1/exports`（question_ids + paper_size，全部必須 `approved`，否則 job 失敗並列出違規 id）→ export job。
- `GET /api/v1/exports` 歷次紀錄；`GET /api/v1/exports/{id}/questions.docx`、`.../answers.docx` 下載。
- 檔案落在 `DATA_DIR/exports/{id}-questions.docx` 與 `{id}-answers.docx`。

## 選題流程

1. 使用者從題庫（僅 `approved`）勾選題目或按分類/題型/難度篩選。
2. 選擇紙張尺寸，建立匯出 job。
3. 完成後提供題目卷與答案卷下載連結。

## 待確認

- 客戶提出「B3」尺寸較少見（台灣考卷慣用 B4），交付前向客戶再確認一次。
