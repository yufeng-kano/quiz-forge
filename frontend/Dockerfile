# 建置 context 是 repo 根目錄（Docker 不讀 .gitignore，靠根目錄 .dockerignore 排除多餘檔案）。

# ---- 1. build 前端 ----
FROM node:24-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ---- 2. serve ----
FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html