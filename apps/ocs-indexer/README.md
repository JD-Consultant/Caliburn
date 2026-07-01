# jd-ocs-indexer

`jd-ocs-indexer` 是 **JD Authoring RAG 的 OCS 知識索引服務**。

它把 [jd-pdf-to-json](../jd-pdf-to-json/) 產出的 OCS（職能基準）JSON，轉成 **兩種 Qdrant 向量點（profile + task）**，並提供一個 **無狀態查詢 HTTP API** 給下游 `jobintel-ai`（JD 撰寫顧問產品）使用。本 repo 只負責「準備好結構化 + 可語意搜尋的候選池」與查詢；對話 / LLM / state / JD 生成都在 `jobintel-ai`。

```text
OCS JSON ─► normalize ─► build(profile + 每任務 task) ─► BGE-M3 embed ─► Qdrant(ocs_v3)
                                                                          │
                                          jobintel-ai ◄─ 無狀態查詢 API ◄─┘
```

> **狀態**：schema v3 索引管線 + 查詢 API 已完成，全測試綠；**全量 re-index 已完成**（`ocs_v3` = 904 profile + 8,549 task = 9,453 點，已 live 驗收 `/search`·`/task-pool`·`/pairs`）。

---

## 為什麼是 profile + task 兩種點

v3 從**使用者流程**倒推 embedding 單位——整個 JD 撰寫流程只有兩個動作需要語意搜尋：

| 動作 | 點類型 | embed 內容 |
|---|---|---|
| 使用者描述工作 → 找候選職務 | **profile**（每 OCS 一個） | 職稱 + 職務描述 + 工作內容（任務名）+ 活動 + 全部 K/S 技能名 |
| 改過 / 自訂的任務 → 找對應 K/S | **task**（每任務一個） | 任務名 + 活動內容 |

其餘（撈任務清單、撈 K/S/A 池）都是「已知 `ocs_code` → filter / scroll」，不需要向量。能力區塊（block）只在 index 時用來聚合每個 task 的 K/S 與活動句，**不單獨建點**。

**embed 是動作不是欄位**：embed 字串在 index 時組好餵模型、**不回存進 payload**；顯示用已存的結構化欄位（`job_description` / `activity_examples` / pairs）。K/S/A/output 一律存 `{code, name}` pair（綁定不漂；iCAP 代碼是 OCS-local）。

### Payload 摘要

**profile point**：`chunk_level`、`ocs_code`、`ocs_code_base`、`job_title`、`job_category`、`industry_codes/names`、`occupation_codes/names`、`version`、`version_seq`、`is_current`、`update_date`、`ocs_level`、`job_description`、`all_a_pairs`、`prerequisites`、`supplements`、`source_file`、`indexed_at`。

**task point**：`chunk_level`、`ocs_code`、`unit_id`、`unit_title`、`task_id`、`task_title`、`activity_examples`、`k_pairs`、`s_pairs`、`output_pairs`、`competency_level`、`source_file`。

**Payload 索引（9 個，全域可過濾才建）**：`chunk_level`、`ocs_code`、`ocs_code_base`、`job_title`(TEXT)、`is_current`、`version`、`ocs_level`、`industry_codes`、`occupation_codes`。

> point id = `uuid5(NAMESPACE, "ocs:{ocs_code}:profile")` 或 `uuid5(…, "ocs:{ocs_code}:unit:{unit_key}:task:{task_id}")`。查詢 API 會回傳 point id，供消費端日後 by-id 取回。

---

## 技術選型

| 層 | 決策 |
|---|---|
| Source of truth | `jd-pdf-to-json` 既有 JSON |
| Pipeline | 自訂：Reader → Normalizer → Builder → Embedder → QdrantWriter（無 markdown render、無 manifest） |
| Vector DB | Qdrant（named vectors：dense 1024d cosine + sparse lexical） |
| Collection | `ocs_v3` |
| Embedding | BGE-M3（dense + sparse，FlagEmbedding） |
| 查詢 | 無狀態 HTTP API（server 端 embed）+ CLI `query`/`smoke-query` |
| 套件管理 | uv |

換 embedding provider / 向量維度時建新 collection，不混用。

> 設計與決策的完整紀錄（schema v3 設計、決策 log、各階段計畫）保存在本地 `docs/superpowers/`（不納入 git）。

---

## 已知資料規模

依 `data/jd-json/`（908 份 OCS JSON）：

- 908 份 JSON、3,272 個 `ocu_unit`、~8,300 個 `task`、~8,689 個 `competency_block`
- v3 點數預估：~904 profile + ~8,300 task ≈ **~9,200 points**
- 129 份缺 version history、多數缺 `job_category`、53 個 task group 含多個 T-code

缺漏欄位不阻斷索引；由 schema 層以 nullable / 空陣列處理。

---

## 快速開始

### 1. 安裝

```bash
uv sync                 # 核心（index 管線）
uv sync --extra api     # 額外裝 fastapi + uvicorn（查詢 API）
```

首次 `index` 會下載 BGE-M3（約 2.3GB）到 `~/.cache/huggingface/`，之後不再重抓。

> **GPU（選用）**：Windows 上 `uv sync` 會自動從 PyTorch 官方 index 裝 CUDA 版 torch（`pyproject.toml` 已設定；非 Windows 平台走 PyPI 的 CPU 版）。要用 GPU 把 `.env` 設 `BGE_M3_DEVICE=cuda` + `BGE_M3_USE_FP16=true`；CPU 也能跑，只是 embed 慢很多。BGE-M3 在 GPU 約佔 ~1.1GB VRAM。

### 2. 設定 `.env`

複製 `.env.example` 為 `.env`：

```bash
QDRANT_URL=https://your-qdrant-host   # 或 http://localhost:6333（只寫 host，不需 port）
QDRANT_API_KEY=<your-api-key>
QDRANT_TIMEOUT=300
QDRANT_COLLECTION=ocs_v3

OCS_SOURCE_ROOT=./data

BGE_M3_MODEL=BAAI/bge-m3
BGE_M3_DEVICE=cpu          # GPU 改 cuda
BGE_M3_USE_FP16=false       # GPU 建議 true
BGE_M3_BATCH_SIZE=8

INDEX_BATCH_SIZE=32
```

### 3. CLI

每個命令可用 `uv run jd-ocs-indexer <cmd>` 或 `uv run python -m jd_ocs_indexer.cli <cmd>`，加 `--help` 看完整選項。

> Windows 終端機中文亂碼：PowerShell 先 `$env:PYTHONIOENCODING="utf-8"`。

#### `index` — 建索引（write to Qdrant）

reader → normalize → build(profile + task) → embed → upsert。全量重建（無增量 manifest）。

```bash
uv run jd-ocs-indexer index <SCAN_DIR> [--limit N]
```

| 參數 | 必填 | 預設 | 說明 |
|---|---|---|---|
| `SCAN_DIR` | ✓ | — | 要 index 的目錄（吃裡面所有 `*.json`） |
| `--limit N` |  | `0` | 只處理前 N 個檔（0 = 不限制） |

```bash
uv run jd-ocs-indexer index data/jd-json --limit 5    # 小量驗收
uv run jd-ocs-indexer index data/jd-json              # 全量
```

> `index` 寫入 `settings.qdrant_collection`（預設 `ocs_v3`）。若 `.env` 指向別的 collection，可臨時覆寫：`QDRANT_COLLECTION=ocs_v3 uv run jd-ocs-indexer index …`。

#### `stats` — 統計

```bash
uv run jd-ocs-indexer stats [SCAN_DIR] [--collection NAME]
```

`SCAN_DIR` → source 端統計（檔數 / units / tasks / blocks / 缺漏）；`--collection` → Qdrant 端 `total_points` + by `chunk_level`（profile / task）。

#### `doctor` — 資料健康檢查

```bash
uv run jd-ocs-indexer doctor <SCAN_DIR> [--show-files N]
```

掃 parse 失敗 / 缺 version / 缺 job_category / zero-block unit / multi-task group（不阻斷索引）。

#### `query` — 自然語言查詢（人類可讀）

```bash
uv run jd-ocs-indexer query "<TEXT>" [OPTIONS]
```

| 參數 | 預設 | 說明 |
|---|---|---|
| `TEXT` | — | 自然語言查詢（引號括起） |
| `--collection NAME` | `.env` 的值 | 覆寫 collection |
| `-l, --level` | 不限 | `profile` / `task` |
| `--ocs-code CODE` | 不限 | 鎖定特定職務 |
| `-k, --top-k N` | `10` | 顯示前 N 筆 |
| `-H, --hybrid` | `false` | dense + sparse RRF 融合 |

```bash
uv run jd-ocs-indexer query "資料分析 Python SQL" --level profile --top-k 5
uv run jd-ocs-indexer query "清洗資料" --level task --hybrid
```

#### `smoke-query` — 索引驗證（原始輸出，格式不保證穩定）

```bash
uv run jd-ocs-indexer smoke-query --collection ocs_v3 [--ocs-code CODE] [--probe-vector "<text>"] [--limit N]
```

#### `serve` — 啟動查詢 API

```bash
uv run jd-ocs-indexer serve --host 127.0.0.1 --port 8000
```

---

## Query API（給 jobintel-ai）

Qdrant 之上的 **無狀態 HTTP read 層**。查詢文字在 **server 端 embed**（走 `apps/embedder` GPU 容器，ADR 0012），caller 只送純文字。不做對話 / LLM / state。

- 預設綁 `127.0.0.1`（loopback、**無 auth**；對外請加反向代理 / middleware，`create_app()` 是擴充點）。
- 互動式 OpenAPI：`http://127.0.0.1:8000/docs`。
- **request/response schema 的權威 = [`packages/indexer-contract`](../../packages/indexer-contract/)**（共用 pydantic，ADR 0010）；本表只列面。
- 自訂方法用 **AIP-136 `:verb`**（ADR 0019）；資源讀取用資源式 GET。

| Method | Path | 用途 |
|---|---|---|
| POST | `/occupations:search` | 自然語言 → 職類 hits（`{query, top_k}` → `{hits:[OccupationHit]}`） |
| POST | `/tasks:search` | 自然語言 → 任務 hits（只回身分 + score） |
| POST | `/tasks:batchGet` | point id 批次取回任務細節（`{ids}` → `{tasks:[TaskDetail]}`;缺失 id 靜默略過 — 刻意偏離 AIP-231，見 ADR 0019） |
| POST | `/tasks:findSimilar` | 去重候選對（`{ocs_codes, score_threshold}`;producer 流程用） |
| GET | `/occupations/{ocs_code}` | 職類官方 metadata（名稱/行業/態度/建議條件…） |
| GET | `/occupations/{ocs_code}/tasks` | 該職類 unit→task 結構 |
| GET | `/occupations/{ocs_code}/competencies` | 該職類 K/S/O/P/A 能力池（多來源 CitableItem） |
| GET | `/healthz` | 就緒狀態（degraded 回 503;含 `index_model`） |
| GET | `/stats` | collection 點數統計 |

```bash
curl -s localhost:8000/occupations:search -H 'content-type: application/json' \
  -d '{"query":"資料分析 機器學習","top_k":5}'
curl -s localhost:8000/healthz
# {"status":"ok","model_loaded":true,"qdrant":"reachable","collection":"ocs_v4","index_model":"bge-m3/BAAI/bge-m3/1024"}
```

### 錯誤碼

| 情境 | HTTP |
|---|---|
| request schema 違規（空 `query` / `top_k` 超界 / 空 `ids`） | 422 |
| `/occupations/{ocs_code}` 未知 code | 404 |
| 索引 embedding 版本與查詢端不相容（ADR 0009） | 409 |
| Qdrant / embedder upstream 回錯、連不上 | 502 / 503 |

---

## 模組結構

```text
src/jd_ocs_indexer/
  cli.py                  # index / stats / doctor / smoke-query / query / serve
  config.py               # .env -> Settings
  models/
    ocs.py                # OCS JSON Pydantic models（tolerant）
    chunk.py              # ChunkRecord / Pair / EmbeddedChunk / SparseVector
  ingestion/
    reader.py             # 掃 JSON / 算 hash / LoadedFile
    normalizer.py         # 缺欄位 fallback / version 推導 / 對齊 task pairs
    builder.py            # 產 profile + 每任務 task records（embed 不回存）
  embeddings/
    base.py               # EmbeddingService Protocol
    bge_m3.py             # FlagEmbedding BGEM3 adapter（dense + sparse）
  store/
    ids.py                # uuid5(NAMESPACE, chunk_key) point id
    schema.py             # vectors + 9 payload indexes
    qdrant_client.py      # URL parser
    writer.py             # ensure collection / batch upsert
  validation/
    stats.py              # source + collection 統計
    smoke_query.py        # by ocs_code / dense+sparse probe
    search.py             # build_filter + dense / hybrid(RRF)（CLI query + API 共用）
  api/                    # 查詢 API（optional extra：uv sync --extra api）
    schemas.py            # Pydantic request / response
    service.py            # 無狀態編排：search / batch_get / find_similar / detail / stats / health
    routes.py             # FastAPI router（threadpool + embed lock + 502/503）
    app.py                # create_app() factory + lifespan
```

---

## 參考

- Qdrant hybrid queries: https://qdrant.tech/documentation/search/hybrid-queries/
- BGE-M3 / FlagEmbedding: https://github.com/FlagOpen/FlagEmbedding
