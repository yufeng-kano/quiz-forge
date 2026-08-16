# 2026-08-16 前端獨立 container（website 與 proxy 分離）

## 決策

推翻 `2026-08-15-initial-system-design.md` D3 中「前端不做常駐 container、由 nginx 同時 serve 靜態檔與反代」的決定。

新拓撲：

- `website`（container name `quiz-forge-website`）：前端專屬常駐 container，serve Vue build 靜態檔（含 SPA `try_files` fallback）。Dockerfile 在 `frontend/Dockerfile`（multi-stage：node build → nginx 靜態 serve）。
- `proxy`（container name `quiz-forge-proxy`，nginx 實作）：純反向代理，不再 serve 任何靜態檔。`/` proxy 到 `website`，`/api/v1` proxy 到 `backend`。舊的 `nginx/` 資料夾與 `quiz-forge-nginx` container 一併改名為 `proxy/`、`quiz-forge-proxy`。

## 理由

- 單一職責：website（serve 前端）與 proxy（反向代理）不混在同一個 container，各自獨立重建與擴充。
- 前端更新不需重build proxy image；proxy 設定變更也不牽動前端 build。
- 使用者明確要求 website 與 proxy 分離。

## 影響

- container 總數由 3 變 4：`quiz-forge-website`、`quiz-forge-proxy`、`quiz-forge-backend`、`quiz-forge-db`。
- `website` 不對 host 暴露 port，只走 compose 內部 network。
- 對外 port 仍只有 `NGINX_HTTP_PORT`（proxy）。