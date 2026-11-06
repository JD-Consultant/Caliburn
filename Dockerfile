# syntax=docker/dockerfile:1.7
FROM node:24.19.0-bookworm-slim@sha256:a9f5f7c91a432850b2a8a7797adf5eadb6c733ceed61167806cee7ea7fbc29df AS web-build
WORKDIR /build
RUN npm install --global pnpm@12.5.1
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/frontend/package.json apps/frontend/package.json
RUN --mount=type=cache,target=/root/.local/share/pnpm/store pnpm install --frozen-lockfile
COPY apps/frontend/ apps/frontend/
RUN pnpm --filter @caliburn/frontend build

FROM python:3.14.8-slim-trixie@sha256:89fb7d3da20043c370643435258bdd7ab755d326d359001d02988ed15ae5219e AS backend-build
COPY --from=ghcr.io/astral-sh/uv:0.12.20@sha256:100047e74f30778ab704942321a09750d6158739573ff58bf3924085cc6cd2d8 /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=0 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/caliburn/venv
WORKDIR /build/apps/backend
COPY packages/indexer-contract/ /build/packages/indexer-contract/
COPY packages/ocs-contract/ /build/packages/ocs-contract/
COPY apps/backend/pyproject.toml apps/backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --extra local-models --no-install-project --no-editable
COPY apps/backend/src/ src/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --extra local-models --no-editable

FROM python:3.14.8-slim-trixie@sha256:89fb7d3da20043c370643435258bdd7ab755d326d359001d02988ed15ae5219e AS runtime
ENV PATH="/opt/caliburn/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/caliburn/browsers \
    CALIBURN_REBUILD_WEB_DIST=/opt/caliburn/web \
    CALIBURN_REBUILD_REFERENCE_CONFIG=/opt/caliburn/reference.json \
    CALIBURN_REBUILD_PDF_FONT_PATH=/opt/caliburn/fonts/NotoSansCJKtc-Regular.otf \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HOME=/tmp
COPY --from=backend-build /opt/caliburn/venv/ /opt/caliburn/venv/
RUN python -m playwright install --with-deps chromium --only-shell \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin caliburn
ADD --checksum=sha256:dce08bd4fd91aa8aa76ed8fea4b694c2dfb8550f67871e326843212ddbeb88b4 \
    https://raw.githubusercontent.com/notofonts/noto-cjk/Sans2.004/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Regular.otf \
    /opt/caliburn/fonts/NotoSansCJKtc-Regular.otf
ADD --checksum=sha256:6a73f9541c2de74158c0e7cf6b0a58ef774f5a780bf191f2d7ec9cc53efe2bf2 \
    https://raw.githubusercontent.com/notofonts/noto-cjk/Sans2.004/LICENSE /opt/caliburn/fonts/LICENSE
RUN chmod 644 /opt/caliburn/fonts/*
COPY --from=web-build /build/apps/frontend/dist/ /opt/caliburn/web/
COPY docker/reference.json /opt/caliburn/reference.json
WORKDIR /opt/caliburn
USER caliburn
EXPOSE 8101
CMD ["python", "-m", "caliburn.server", "--host", "0.0.0.0"]
