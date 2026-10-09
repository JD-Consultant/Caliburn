# syntax=docker/dockerfile:1.7
# ADR 0012 isolates Torch from Windows app processes. CUDA/Python/package inputs
# are independently fixed; updating them requires a new lock and runtime checks.
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04@sha256:2fcc4280646484290cc50dce5e65f388dd04352b07cbe89a635703bd1f9aedb6
COPY --from=ghcr.io/astral-sh/uv:0.12.20@sha256:100047e74f30778ab704942321a09750d6158739573ff58bf3924085cc6cd2d8 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/root/.cache/huggingface \
    UV_PYTHON_INSTALL_DIR=/opt/python \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH"

# The pinned uv release carries the download URL and checksum for this Python.
RUN uv python install 3.11.16

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-build --python 3.11.16 --no-python-downloads

COPY app.py .
COPY reranking.py .

EXPOSE 80
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80"]
