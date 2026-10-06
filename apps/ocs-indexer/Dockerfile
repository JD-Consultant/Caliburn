# syntax=docker/dockerfile:1.7
FROM python:3.14.8-slim-trixie@sha256:89fb7d3da20043c370643435258bdd7ab755d326d359001d02988ed15ae5219e AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.20@sha256:100047e74f30778ab704942321a09750d6158739573ff58bf3924085cc6cd2d8 /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=0 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/caliburn/venv
WORKDIR /build/apps/ocs-indexer
COPY packages/ocs-contract/pyproject.toml /build/packages/ocs-contract/pyproject.toml
COPY packages/ocs-contract/src/ /build/packages/ocs-contract/src/
COPY packages/indexer-contract/pyproject.toml /build/packages/indexer-contract/pyproject.toml
COPY packages/indexer-contract/src/ /build/packages/indexer-contract/src/
COPY apps/ocs-indexer/pyproject.toml apps/ocs-indexer/uv.lock apps/ocs-indexer/README.md ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --extra api --no-dev --no-install-project --no-editable
COPY apps/ocs-indexer/src/ src/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --extra api --no-dev --no-editable

FROM python:3.14.8-slim-trixie@sha256:89fb7d3da20043c370643435258bdd7ab755d326d359001d02988ed15ae5219e AS runtime
ENV PATH=/opt/caliburn/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=build /opt/caliburn/venv /opt/caliburn/venv
RUN groupadd --gid 10001 caliburn && useradd --uid 10001 --gid caliburn --create-home caliburn
WORKDIR /home/caliburn
USER caliburn
EXPOSE 8000
CMD ["jd-ocs-indexer", "serve", "--host", "0.0.0.0", "--port", "8000"]
