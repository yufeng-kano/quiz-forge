# 文件索引

執行任何任務前先讀本文件。`docs/` 是專案唯一真實來源；文件異動必須同步更新本索引。

文件分兩類：

- `docs/decisions/`：決策文件，檔名 `YYYY-MM-DD-主題.md`，記錄當下的決策與理由，之後不回改；推翻舊決策時新增一份新的決策文件。
- `docs/` 頂層：系統即時文件，平放不分子資料夾，實作變更時必須同步更新。

## 專案根目錄

| 路徑 | 用途 |
|---|---|
| `README.md` | 公開 repo 首頁：部署步驟、架構摘要、費用說明 |
| `.rule` | 給 LLM 的專案規則主檔 |
| `CLAUDE.md`、`AGENTS.md` | 指向 `.rule` 的 symlink |
| `.env.example` | 環境變數範本（真正的 `.env` 不入 Git） |
| `docs/` | 專案文件（本目錄） |
| `data/` | 樣本資料與 container mount 掛載點，見 `docs/data-inventory.md` |
| `backend/` | Python FastAPI 服務（uv 管理、Alembic migration），見 `docs/architecture.md` |
| `frontend/` | Vue 3 前端專案，`frontend/Dockerfile` 建置 website container，見 `docs/frontend.md` |
| `proxy/` | 純反向代理（nginx 實作）設定與 Dockerfile |
| `db/` | PostgreSQL（pgvector）設定檔 |
| `docker-compose.yml` | 服務編排（backend / db / nginx / website） |

## 文件清單

| 文件 | 摘要 |
|---|---|
| `docs/index.md` | 本索引 |
| `docs/overview.md` | 系統定位、核心流程、範圍界定、使用模型 |
| `docs/architecture.md` | Docker Compose 拓撲、nginx 設定、pg-as-queue、後端技術、LLM 介接、`.env` 變數 |
| `docs/data-model.md` | 資料表邏輯定義與設計決定 |
| `docs/ingestion.md` | 文件輸入管線：vision 解析契約（Markdown + bbox）、圖表裁切、網頁抽取、chunk 與分類、文件刪除與分類 GC |
| `docs/question-bank.md` | 六題型 payload schema、出題流程、審題流程、題目向量化與語意搜尋、題庫選題助手（題庫右側欄） |
| `docs/export.md` | Word 匯出：題目卷／答案卷、紙張尺寸、render 設計 |
| `docs/frontend.md` | 前端技術（router/Pinia/i18n 規範）、頁面清單、視覺風格（白色簡潔）、設計節制原則、清單有界原則、互動原則 |
| `docs/data-inventory.md` | `data/` 內資料清單與用途 |

## 決策文件

| 文件 | 摘要 |
|---|---|
| `docs/decisions/2026-08-15-initial-system-design.md` | 初始系統設計：D1–D11 技術決策、待確認事項、開發順序 |
| `docs/decisions/2026-08-15-ux-overhaul-feature-expansion.md` | UX 大改與功能補強：手動建題、匯出卷面、搜尋分頁、分類管理、Dashboard/任務中心、rechunk、專業版面 |
| `docs/decisions/2026-08-16-separate-frontend-container.md` | 前端獨立常駐 container（website），反向代理改名 proxy（資料夾/service/container 皆改名），website 與 proxy 分離 |
| `docs/decisions/2026-08-17-bank-agent-semantic-selection.md` | 題庫選題助手與題目語意搜尋：`questions.embedding`、`embed_questions` job、`similar_to` 查詢、對話 agent 有界迴圈、agent 只提案不改選取；D7 已被 D8 推翻，D8 又被 D10 推翻 |
| `docs/decisions/2026-08-17-bank-agent-own-pages.md` | 推翻 D7：選題助手曾改為獨立 `/conversations` 兩頁；已被同日 D10 推翻 |
| `docs/decisions/2026-08-17-bank-on-questions-page.md` | 推翻 D8／D9：助手回到題庫右側欄；左欄可切已選；取消全選；D13 左右分開捲；D14 提案列跳到題目；D15 Esc 還原篩選與捲動 |
| `docs/decisions/2026-08-17-compact-headers-and-job-errors.md` | 頁首只留頁名＋計數、狀態改純文字、任務錯誤改人話摘要 |
| `docs/decisions/2026-08-17-documents-workspace-layout.md` | 文件頁改滿版工作區：側欄＋滿高表格，上傳改頁首 Modal；拿掉兩 tab 與浮動卡片 |
| `docs/decisions/2026-08-17-list-pages-workspace.md` | 任務中心比照文件庫滿高表格；文件詳情大綱去卡片框。選題助手歷史頁已由 D10 撤回，不再適用本決策 |
| `docs/decisions/2026-08-17-ui-design-restraint.md` | 全站設計節制通則 D16–D22：禁卡中卡、pill 只留封閉集合短詞、icon 優先、不重述外框、不寫多餘文字與灰色小字、獨立區域各自捲動 |
| `docs/decisions/2026-08-17-drop-page-titles-keep-stat-cards.md` | D23 頁首不再放頁名（推翻同日頁首精簡決策的「只留頁名」）、D24 總覽與用量的總計維持 `StatCard` 卡片（D16 的明確例外）；D23 頁名部分已被同日 D25 推翻 |
| `docs/decisions/2026-08-17-professional-form-pages.md` | 表單頁專業化 D25–D30：頁首恢復頁名（推翻 D23）、出題頁分欄工作區、表單分區小節標題、控制項樣式升級、匯出「題目與配分」合併 widget、逐題配分移入 store 修跨頁消失 bug |
| `docs/decisions/2026-08-18-generate-row-difficulty-percent-scoring.md` | D31–D35：出題逐題型難度（`items[].difficulty`）、出題頁首放送出鈕與 icon 化觸發鈕（調整 D28）、配分改「目標總分＋題型百分比＋平均分配」（廢 `typePoints` 偏好）、修 `parsePointsInput` 對 number 的 crash、出題頁三欄並排（範圍｜題目設定｜紀錄） |
| `docs/decisions/2026-08-17-documents-folder-delete-icon.md` | L5 文件庫資料夾列刪除改 trash icon；按下仍走 ConfirmDialog。D18 的明確例外，只限資料夾列 |
| `docs/decisions/2026-08-17-documents-workspace-flush.md` | L6 工作區貼齊外框不另加左右內距、L7 搜尋列與表格同一塊並加分隔線；左右緣已被同日 L8 推翻 |
| `docs/decisions/2026-08-17-documents-workspace-bleed.md` | L8 文件庫工作區左右出血，與頁首底線同寬；推翻 L6「停在 page gutter」 |
