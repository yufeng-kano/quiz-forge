# 前端

## 技術

- Vue 3 + Vite，用 `npm create vue@latest` 建立於 `frontend/`。
- 路由 vue-router、狀態 Pinia、API 呼叫統一走 `/api/v1`（同源，經 nginx 反代，不需 CORS）。
- vue-router 與 Pinia 已隨 scaffold 安裝；實作功能頁時必須真正落地：頁面清單全部走 router 定義，跨頁狀態（job 輪詢、篩選條件等）放 Pinia store，不散落元件內。
- i18n 用 vue-i18n：介面文案全部進 locale 檔，但只做繁體中文（`zh-Hant-TW`）一種語言，不做語言切換功能。目的為文案集中管理，不是多語系。
- 禁止在元件內硬編碼中文文案（一律走 locale 檔），也禁止把假資料寫死在 view 裡。
- build 產物交由 nginx serve，不做常駐 container。

## 頁面清單

| 路由 | 頁面 | 說明 |
|---|---|---|
| `/` | 文件列表 | 所有 documents 與處理狀態；入口含上傳與網址匯入 |
| `/documents/:id` | 文件詳情 | 逐頁渲染 Markdown（含裁切圖表）、chunk 與分類結果、失敗頁重試 |
| `/review` | 審題 | `draft` 題目列表，對照來源 chunk 原文，可編輯後採用／丟棄 |
| `/questions` | 題庫 | `approved` 題目瀏覽，依分類／題型／難度篩選，勾選送匯出 |
| `/generate` | 出題 | 選範圍（文件／分類）、題型、數量，建立出題 job |
| `/exports` | 匯出 | 選紙張尺寸、歷次匯出紀錄、下載題目卷／答案卷 |
| `/usage` | 用量 | `llm_usage` 累計統計（依 model／用途） |

## 視覺風格

- 白色簡潔風：白底、留白充足、低彩度點綴色，不用深色主題。
- 移除 scaffold 預設的示範樣式與深色 media query，全站以淺色為唯一主題。

## 互動原則

- 長任務（解析、出題、匯出）建立 job 後輪詢 `GET /api/v1/jobs/{id}` 顯示進度；多頁文件顯示逐頁進度（如「12/40 頁」）。
- 失敗以最小單位重試（單頁、單題），介面提供對應按鈕。
- 題目渲染元件依題型分開實作，與 `question-bank.md` 的 payload schema 一一對應。
