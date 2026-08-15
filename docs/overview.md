# 系統總覽

## 定位

QuizForge 是單一使用者自架的題庫生成系統。使用者把教材文件丟進系統，系統將內容文字化、分類，再用 LLM 生成題目，經人工審題後匯出成可列印的 Word 考卷。

- 部署形態：Docker Compose，本機執行，瀏覽器操作。
- 發佈形態：公開 GitHub repo，使用者 clone 後自行啟動。
- 成本模式：LLM 走 OpenRouter，使用者自備 API key，費用自付。

## 核心流程

1. **文件輸入**：上傳掃描件（PDF/圖片）、電子文件（PDF/Word），或輸入網址抓取網頁內容。
2. **文字化**：PDF 與圖片一律走 vision model 解析成 Markdown（含圖表裁切）；網頁走本地正文抽取。詳見 `ingestion.md`。
3. **分類**：內容切 chunk，由 LLM 依分類 schema 標註（科目／主題／難度／標籤），同時計算 embedding 存 pgvector。
4. **出題**：依題型從 chunk 生成題目，structured output 強制 JSON。詳見 `question-bank.md`。
5. **審題**：生成題目先進 `draft`，使用者在網頁上編輯、採用或丟棄；只有 `approved` 進題庫。
6. **匯出**：從題庫選題，生成題目卷與答案卷兩份 Word 檔，支援 A4／B4／B3 紙張。詳見 `export.md`。

## 範圍界定

- 不整合掃描器硬體；實體文件由使用者自行掃描成檔案後上傳。
- 不做帳號系統與登入驗證（單人本機使用）。
- 有文字層的 PDF 也走 vision 管線，換取管線一致性，代價是每頁都消耗 token（已與需求方確認接受使用者付費模式）。

## 使用模型（皆為 `.env` 設定，不寫死）

| 用途 | 預設 model | 說明 |
|---|---|---|
| vision 解析 | `google/gemini-3.6-flash` | PDF/圖片 → Markdown + 圖表 bbox |
| 摘要／分類／出題 | `openai/gpt-5.6-luna` | 文字任務統一一組設定 |
| embedding | `openai/text-embedding-3-small` | 1536 維，供比較題配對 |
