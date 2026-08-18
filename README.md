# Quiz Forge

把教材變成考卷的自架系統。

把掃描件、PDF、Word、圖片或網頁丟進去，系統會自動文字化、分類、出題。

你在瀏覽器上審題，再匯出可列印的 Word 考卷。

單人本機使用，瀏覽器操作。LLM 走 OpenRouter，模型與費用都由你決定。

## 它能做什麼

- **文件輸入**：掃描件（PDF／圖片）、電子文件（PDF／Word）、網頁網址，都走同一條管線。
- **文字化**：PDF 與圖片由 vision model 讀取成文字，圖表裁切保留。
- **自動分類**：內容自動標註科目、主題、難度與標籤，之後可以語意搜尋。
- **出題**：支援比較、類比、單選、是非、填充、問答 6 種題型，可以依題型設定難度與配分。
- **審題**：生成的題目先放草稿，逐題編輯、採用或丟棄。只有採用的題目進題庫。
- **題庫與選題助手**：題庫支援語意搜尋，也可以請助手從整庫幫你挑題。
- **Word 匯出**：選題後生成題目卷與答案卷 2 份，支援 A4／B4／B3（JIS）紙張。
- **用量追蹤**：每次 LLM 呼叫都記錄 model 與 token 用量，累計統計隨時可查。

## 部署

**需求**：Docker 與 Docker Compose、OpenRouter API key。

```bash
git clone https://github.com/yufeng-kano/quiz-forge
cd quiz-forge
cp .env.example .env
# 編輯 .env，至少填入 LLM_API_KEY，並更換 POSTGRES_PASSWORD
docker compose up -d --build
```

瀏覽器開 `http://localhost:8080`（port 可用 `.env` 的 `NGINX_HTTP_PORT` 調整）。

## 安全

- 單人本機系統，沒有帳號與登入。不要把 nginx port 暴露到公網。
- `.env`（含 API key 與 DB 密碼）已被 `.gitignore` 排除，不會進版本紀錄。
