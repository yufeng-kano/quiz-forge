# 資料清單

`data/` 內資料異動時必須同步更新本文件。

| 路徑 | 用途 | 入 Git |
|---|---|---|
| `data/samples/` | 測試用樣本文件（範例 PDF、掃描件、Word），保留原始檔名與格式 | 是 |
| `data/container-mounts/` | Docker bind mount 掛載點 | 只保留資料夾結構（各子目錄 `.gitkeep`），runtime 內容由 `.gitignore` 排除 |
| `data/container-mounts/db/` | PostgreSQL 資料目錄（實際資料在 `pgdata/` 子目錄） | 否 |
| `data/container-mounts/uploads/` | 使用者上傳原檔 | 否 |
| `data/container-mounts/assets/` | 頁面裁切圖表 | 否 |
| `data/container-mounts/exports/` | Word 匯出檔 | 否 |

目前 `data/samples/` 為空（僅 `.gitkeep`）；`data/container-mounts/` 已依上表建立子目錄結構。
