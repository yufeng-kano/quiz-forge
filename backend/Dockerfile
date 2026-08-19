FROM python:3.13-slim

# 官方 uv 靜態執行檔，不用系統 pip 安裝
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:${PATH}"

# 先只複製 lockfile 相關檔案，讓依賴安裝可以被 layer cache 命中
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .
RUN uv sync --frozen --no-dev

# Windows checkout 可能帶 CRLF，去掉 CR 避免 shebang 失效
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
