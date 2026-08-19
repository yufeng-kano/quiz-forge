# frontend

Quiz Forge 的 Vue 3 前端專案。技術棧：Vite、Pinia、vue-router、vue-i18n（zh-Hant-TW）。

## 開發

```bash
npm install
npm run dev        # Vite dev server
npm run build      # type-check + 產出 dist/
npm run lint       # oxlint + eslint
npm run format     # prettier
```

## 部署

`Dockerfile` 是兩階段建置：先用 Node 把 `dist/` build 出來，再 COPY 進 `nginx:alpine` 常駐伺服。

- `nginx.conf` 是 **website container** 的靜態 serve 設定（含 SPA fallback），不是 proxy 的。
- 靜態檔的對外轉發由 `proxy/` 的 nginx 負責，見根目錄 `README.md` 與 `docs/architecture.md`。