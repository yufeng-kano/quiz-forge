# 資料清單

`data/` 內資料異動時必須同步更新本文件。

| 路徑 | 用途 | 入 Git |
|---|---|---|
| `data/samples/` | 測試用樣本文件（範例 PDF、掃描件、Word），保留原始檔名與格式 | 是 |
| `data/container-mounts/` | Docker bind mount 掛載點（DB 資料、上傳原檔、裁切圖、匯出檔） | 只保留資料夾結構，runtime 內容由 `.gitignore` 排除 |

目前 `data/samples/` 與 `data/container-mounts/` 皆為空（僅 `.gitkeep`）。
