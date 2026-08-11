# Caliburn embedder — BGE-M3 (dense+sparse) on Linux + CUDA. ADR 0012.
# torch runs here (stable Linux build), NOT in the app processes → no Windows
# OMP/_dynamo bugs. Pinned stable torch (not the bleeding-edge 2.12 that broke).
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/root/.cache/huggingface

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Stable Linux torch from the CUDA 12.4 wheel index (matches the cuda base).
RUN pip3 install --no-cache-dir torch==2.6.0 --index-url https://download.pytorch.org/whl/cu124

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 80
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80"]
