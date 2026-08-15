# 文件輸入與解析管線

## 兩條輸入線

| 來源 | 處理方式 |
|---|---|
| 上傳檔案（PDF、圖片、Word） | PDF/圖片走 vision 管線；Word 用 `python-docx`/`mammoth` 直接抽文字 |
| 網址 | `trafilatura` 本地抽正文轉 Markdown（免費），再用 `TEXT_MODEL` 產摘要 |

原始檔一律保留在 `DATA_DIR` 下，`documents.raw_file_path` 記錄位置。

## Vision 管線（PDF 與圖片統一路徑）

設計原則：**簡單且一致**。不判斷 PDF 有無文字層，全部走同一條路。

1. `PyMuPDF` 將 PDF 逐頁 render 成 PNG（DPI 由 `OCR_DPI` 設定，預設 200）；圖片檔視為單頁。
2. 每頁一個 vision 呼叫（`VISION_MODEL`），一頁一筆 `pages` 記錄，單頁失敗單頁重試。
3. 呼叫用 `response_format: json_schema` 強制輸出：

```json
{
  "markdown": "頁面內容，圖表位置放佔位符 ![fig-1]",
  "figures": [
    {"id": "fig-1", "bbox": [ymin, xmin, ymax, xmax], "caption": "圖表說明"}
  ]
}
```

- `bbox` 為 0–1000 正規化座標（Gemini 慣例，順序 ymin, xmin, ymax, xmax）。

## 圖表裁切

1. bbox 換算回原始頁面 pixel 座標。
2. 用 Pillow 從**原始高解析頁面圖**裁切（不得從送模型的縮圖裁，品質不足）。
3. 裁切圖存為 `assets`，Markdown 佔位符改寫成 `/api/v1/assets/{id}` 圖片連結。
4. 文件詳情頁直接渲染 Markdown 即圖文並茂；出題可引用圖片。

## 網頁線的摘要用途界定

- 摘要（`TEXT_MODEL` 產生）只用於**分類與列表顯示**。
- **出題一律用全文**，不得用摘要出題（摘要會丟失細節）。

## Chunk 與分類

1. 解析完成的 Markdown 依標題結構 + 長度上限切 chunk。
2. 每個 chunk 由 `TEXT_MODEL` 依分類 schema 標註：科目／主題／難度／標籤（`categories` 支援階層）。
3. 每個 chunk 呼叫 `EMBEDDING_MODEL` 計算 embedding，存 pgvector（維度 `EMBEDDING_DIM`）。
4. embedding 用途：比較題的相關 chunk 配對（見 `question-bank.md`）。
