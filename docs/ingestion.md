# 文件輸入與解析管線

## 兩條輸入線

| 來源 | 處理方式 |
|---|---|
| 上傳檔案（PDF、圖片、Word） | PDF/圖片走 vision 管線；Word 用 `python-docx`/`mammoth` 直接抽文字 |
| 網址（網頁） | `trafilatura` 本地抽正文轉 Markdown（免費），再用 `TEXT_MODEL` 產摘要 |
| 網址（檔案） | 依 content-type／副檔名判斷指向 PDF/Word/圖片時，下載檔案後進上傳檔案同一條管線；下載大小上限由 `URL_FETCH_MAX_BYTES` 設定 |

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

1. 解析完成的 Markdown 依標題結構 + 長度上限（`CHUNK_MAX_CHARS`，預設 4000）切 chunk。
2. 每個 chunk 由 `TEXT_MODEL` 依分類 schema 標註：科目／主題／難度／標籤（`categories` 支援階層，主題的 parent 為科目，get-or-create 跨文件去重）。難度不設獨立欄位，以 `難度:{值}` 併入 `tags[]`。分類 prompt 必須帶入**既有科目清單**（與該科目下既有主題），引導模型優先重用既有分類、避免同義科目碎裂（如「資訊工程／資訊科技」並存）；只有真的不合適才建新分類。
3. 每個 chunk 呼叫 `EMBEDDING_MODEL` 計算 embedding，存 pgvector（維度 `EMBEDDING_DIM`）。
4. embedding 用途：比較題的相關 chunk 配對（見 `question-bank.md`）。

## 實作備註與已知限制

- 實作在 `backend/src/backend/ingestion/`；所有 LLM prompt 集中在 `prompts.py`。
- 頁面圖存 `DATA_DIR/uploads/{doc_id}/pages/`，裁切圖存 `DATA_DIR/assets/`。
- 單頁重試（`POST /api/v1/pages/{id}/retry`）重用已存的頁面 PNG，不重新 render PDF。
- chunk 階段失敗重試時整段 chunk 階段重跑（頁面解析不重跑）；不做 chunk 中斷點續跑。
- 單頁重試成功後不會自動重跑 chunk；補頁後用 `POST /api/v1/documents/{id}/rechunk` 手動重建（以 job 刪舊 chunk 重跑整個 chunk 階段，頁面解析不動）。
