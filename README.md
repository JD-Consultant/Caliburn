# jd-ocs-indexer

`jd-ocs-indexer` 是 **JD Authoring RAG 的 OCS 索引建置器**。

它把 [jd-pdf-to-json](../jd-pdf-to-json/) 已產出的 OCS（職能基準）JSON 轉成 schema-aware Markdown chunks，產生 embeddings，並寫入 Qdrant。未來的 MCP server / HTTP API / JD 產生器會讀取這個 collection，但不放在本 repo。

```text
OCS JSON -> profile/unit/block Markdown chunks -> embeddings -> Qdrant storage
```

v1 **不提供正式查詢 API / MCP server tool / RAG answer engine**。本 repo 只保留 CLI smoke query，用來驗證 Qdrant 寫入、payload filter、point retrieve 正常。

> **目前狀態：v1 骨架已實作，3 份 fixture 端到端通過**。可對 `S:\jd-pdf-to-json\output\0518\` 全量 908 份跑 `index`。詳見下方 [快速開始](#快速開始)。

---

## 產品定位

未來 RAG 的目標不是單純查詢 OCS，而是幫使用者撰寫自己的職務說明書：

```text
使用者描述自己的工作內容
  -> 找相似 OCS 職務 / 工作任務 / K/S
  -> 提示可能遺漏的工作內容
  -> 讓使用者確認或補充
  -> 產生專屬職務說明書
```

因此本 repo 要產出的不是一般文件索引，而是可以支援下列能力的 OCS knowledge index：

- 使用自然語言工作描述找候選職務。
- 從長段工作描述拆出多個活動後，分別命中相關 unit/block。
- 聚合 `ocs_code`、unit、K/S codes，供未來服務產生提示。
- 透過 `source_file` 回到完整 JSON，補足 JD 生成需要的背景資料。

---

## v1 目標

1. 讀取 `S:\jd-pdf-to-json\output\0518\*.json` 作為 source of truth。
2. 將每份 JSON 轉成三層 chunk：`profile`、`unit`、`block`。
3. 將每個 chunk render 成 Markdown，作為 embedding/text 投影；Markdown 不作切分來源。
4. 使用 embedding adapter 產生向量，預設 BGE-M3 dense + sparse。
5. 使用 direct Qdrant writer upsert points 與 payload indexes。
6. 提供 CLI smoke query 驗證：count、依 `ocs_code` retrieve、依 K/S code filter、dev-only vector probe。

---

## 非 v1 範圍

- 不開 HTTP API。
- 不開 MCP server。
- 不提供正式 Python 查詢 SDK。
- 不在 indexer 內產生 LLM 答案。
- 不處理使用者互動、遺漏提示、JD 草稿生成。
- 不處理 PDF 解析；PDF -> JSON 完全由 `jd-pdf-to-json` 負責。
- 不把 LlamaIndex `IngestionPipeline` 當 v1 主線。

正式 serving layer 建議另開 repo，例如 `jd-ocs-rag-service` 或 `jd-ocs-mcp`。該 repo 使用 `qdrant-client` 讀取本 repo 建好的 collection，並負責 query orchestration、完整 JSON context assembly、LLM prompt、MCP/API contract。

LlamaIndex 不列為必要依賴。若未來服務只是 deterministic tool/API，`qdrant-client` + 自訂 context assembler 會更可控；只有需要內建 chat engine、agent workflow、RAG evaluation 時才重新評估。

---

## 技術選型

| 層 | v1 決策 |
|---|---|
| Source of truth | `jd-pdf-to-json` 既有 JSON |
| Pipeline | 自訂 pipeline：Reader -> Builder -> Renderer -> Embedder -> QdrantWriter |
| Vector DB | Qdrant（本機 Docker 或後續 Cloud） |
| Collection | `ocs_bgem3_v1` |
| Embedding（主） | BGE-M3（dense 1024d + sparse lexical weights） |
| Embedding（備） | OpenAI dense-only、FastEmbed/BM25 adapter |
| Chunk 策略 | 三層：profile / unit / block（約 12,869 chunks） |
| 查詢 | v1 僅 CLI smoke query；正式 MCP/API/JD RAG 另 repo |
| 套件管理 | uv |

不同 embedding provider 不混用同一個 collection；換 provider 或向量維度時建立新 collection。

---

## 設計文件

| 文件 | 內容 |
|---|---|
| [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) | v1 決策總報告、模組架構、CLI、驗收標準 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 系統資料流、repo 邊界、未來 JD Authoring RAG 契約 |
| [docs/CHUNKING.md](docs/CHUNKING.md) | 三層 chunk 策略、Markdown 模板、邊界情況 |
| [docs/SCHEMA.md](docs/SCHEMA.md) | Qdrant collection、named vectors、payload 欄位與索引 |
| [docs/INGESTION.md](docs/INGESTION.md) | 自訂 ingestion pipeline、增量更新、CLI 規劃 |
| [docs/RETRIEVAL.md](docs/RETRIEVAL.md) | 未來 JD Authoring RAG service 的查詢契約與 v1 smoke query |

---

## 已知資料規模

依 `S:\jd-pdf-to-json\output\0518\` 實測：

- 908 份 JSON
- 3,272 個 `ocu_unit`
- 8,347 個 `task`
- 8,689 個 `competency_block`
- 預估 v1 chunks：908 profile + 3,272 unit + 8,689 block = 12,869 points
- 129 份 JSON 缺 version history
- 903 份 JSON 缺 `job_category`
- 53 個 task group 含多個 T-code

缺漏欄位不阻斷索引；由 schema 層以 nullable 或空陣列處理。

---

## 快速開始

### 1. 安裝相依

```bash
uv sync
```

uv 會建立 `.venv` 並依 `pyproject.toml` / `uv.lock` 安裝（含 `FlagEmbedding` + `torch` + `qdrant-client`）。首次 `index` 會自動下載 BGE-M3 模型（約 2.3GB）到 `~/.cache/huggingface/`，第二次起不會重抓。

### 2. 設定 `.env`

複製 `.env.example` 為 `.env`，按你的環境填：

```bash
QDRANT_URL=https://qdrant.yokosama.com   # 或 http://localhost:6333
QDRANT_API_KEY=<your-api-key>
QDRANT_COLLECTION=ocs_bgem3_v1

OCS_SOURCE_ROOT=S:/jd-pdf-to-json
OCS_SOURCE_ROOT_ALIAS=jd-pdf-to-json

EMBEDDING_PROVIDER=bge-m3
BGE_M3_MODEL=BAAI/bge-m3
BGE_M3_DEVICE=cpu          # 或 cuda
BGE_M3_USE_FP16=false
BGE_M3_BATCH_SIZE=8

INDEX_BATCH_SIZE=64
MANIFEST_PATH=.data/manifest.json
```

`QDRANT_URL` 只寫 host（不需要 port），factory 會依 scheme 自動判 443/6333。

### 3. CLI

所有命令共用前綴 `uv run python -m jd_ocs_indexer.cli`。也可以 `uv run jd-ocs-indexer ...`（pyproject 已註冊 entry-point）。任何命令加 `--help` 看完整選項。

> Windows 終端機若有中文亂碼，先 `$env:PYTHONIOENCODING="utf-8"`（PowerShell）。VSCode 內建終端機預設就是 UTF-8。

---

#### `render` — JSON → Markdown chunks（不連 Qdrant）

用途：人工檢查 chunk 文字、debug normalizer / renderer。

```bash
uv run python -m jd_ocs_indexer.cli render <SCAN_DIR> [OPTIONS]
```

| 參數 / Flag | 必填 | 預設 | 說明 |
|---|---|---|---|
| `SCAN_DIR` | ✓ | — | 要掃描的目錄，會吃裡面所有 `*.json`。例：`tests/fixtures` 或 `S:/jd-pdf-to-json/output/0518` |
| `-o, --output PATH` |  | `output/md` | Markdown 輸出根目錄；每份 OCS 一個子資料夾 `<ocs_code>/<chunk_key>.md` |
| `--limit N` |  | `0` | 只處理前 N 個檔案（0 = 不限制） |

範例：
```bash
uv run python -m jd_ocs_indexer.cli render tests/fixtures -o output/md
uv run python -m jd_ocs_indexer.cli render S:/jd-pdf-to-json/output/0518 --limit 5
```

---

#### `stats` — 統計

兩種模式：source 端（掃 JSON）或 Qdrant 端（查 collection）。可同時帶兩種。

```bash
uv run python -m jd_ocs_indexer.cli stats [SCAN_DIR] [--collection NAME]
```

| 參數 / Flag | 必填 | 預設 | 說明 |
|---|---|---|---|
| `SCAN_DIR` |  | — | 給了就統計 source 端：檔數 / units / tasks / blocks / 缺漏欄位數 |
| `--collection NAME` |  | — | 給了就統計 Qdrant collection：total points + by chunk_level |

範例：
```bash
uv run python -m jd_ocs_indexer.cli stats tests/fixtures
uv run python -m jd_ocs_indexer.cli stats --collection ocs_bgem3_v1
uv run python -m jd_ocs_indexer.cli stats S:/jd-pdf-to-json/output/0518 --collection ocs_bgem3_v1
```

---

#### `doctor` — 健康檢查

掃描已知資料缺漏（不阻斷索引）：parse 失敗 / 缺 version / 缺 job_category / zero-block unit / multi-task group。

```bash
uv run python -m jd_ocs_indexer.cli doctor <SCAN_DIR> [--show-files N]
```

| 參數 / Flag | 必填 | 預設 | 說明 |
|---|---|---|---|
| `SCAN_DIR` | ✓ | — | 要掃描的目錄 |
| `--show-files N` |  | `10` | 每類問題顯示前 N 個檔名 |

範例：
```bash
uv run python -m jd_ocs_indexer.cli doctor S:/jd-pdf-to-json/output/0518 --show-files 20
```

---

#### `index` — 完整 pipeline（write to Qdrant）

reader → normalizer → builder → renderer → embed → upsert。依 `source_json_hash` 自動 skip 未變檔案。

```bash
uv run python -m jd_ocs_indexer.cli index <SCAN_DIR> [--limit N] [--rebuild]
```

| 參數 / Flag | 必填 | 預設 | 說明 |
|---|---|---|---|
| `SCAN_DIR` | ✓ | — | 要 index 的目錄 |
| `--limit N` |  | `0` | 只處理前 N 個檔（0 = 不限制） |
| `--rebuild` |  | `false` | 忽略 manifest，所有檔重新 embed + upsert |

範例：
```bash
# fixture 端到端測試
uv run python -m jd_ocs_indexer.cli index tests/fixtures

# 重跑 → 全部 skipped
uv run python -m jd_ocs_indexer.cli index tests/fixtures

# 強制重建（換 embedding model / 改 chunk 格式時用）
uv run python -m jd_ocs_indexer.cli index tests/fixtures --rebuild

# 全量
uv run python -m jd_ocs_indexer.cli index S:/jd-pdf-to-json/output/0518
```

---

#### `smoke-query` — 索引驗證（原始輸出）

只用來確認寫入是否正確，輸出格式不保證穩定。**人類查詢請用 `query`**。

```bash
uv run python -m jd_ocs_indexer.cli smoke-query --collection NAME [QUERY_OPTIONS]
```

| 參數 / Flag | 必填 | 預設 | 說明 |
|---|---|---|---|
| `--collection NAME` | ✓ | — | Qdrant collection 名稱 |
| `--ocs-code CODE` |  | — | 用 payload filter 撈出該 OCS 的所有 chunk |
| `-k, --knowledge CODE` |  | — | K-code filter（可重複）：`-k K01 -k K02` |
| `-s, --skill CODE` |  | — | S-code filter（可重複） |
| `--probe-vector "<text>"` |  | — | 把 text 用 BGE-M3 embed 後做 dense + sparse 雙路驗證 |
| `--limit N` |  | `10` | 顯示前 N 筆 |

範例：
```bash
# 撈出某個職務的所有 chunk（profile + unit + block）
uv run python -m jd_ocs_indexer.cli smoke-query --collection ocs_bgem3_v1 --ocs-code SMS2512-002v1

# 找同時涵蓋 K01 + S01 的 block（K 與 S 之間是 AND，同欄多個是 OR）
uv run python -m jd_ocs_indexer.cli smoke-query --collection ocs_bgem3_v1 -k K01 -s S01

# 驗證 dense + sparse 都寫進去了
uv run python -m jd_ocs_indexer.cli smoke-query --collection ocs_bgem3_v1 --probe-vector "AI 應用開發 部署 系統整合"
```

---

#### `query` — 自然語言查詢（人類可讀）

包裝 BGE-M3 + Qdrant 給人探索用。輸出含分數、chunk level、能力等級、職務→單元→任務→區塊 breadcrumb、K/S codes、source 檔名、Markdown 摘要。

```bash
uv run python -m jd_ocs_indexer.cli query "<TEXT>" [OPTIONS]
```

| 參數 / Flag | 必填 | 預設 | 說明 |
|---|---|---|---|
| `TEXT` | ✓ | — | 自然語言查詢文字（用引號括起來） |
| `--collection NAME` |  | `.env` 的 `QDRANT_COLLECTION` | 指定 collection 覆寫預設 |
| `-l, --level LEVEL` |  | 不限 | `profile` / `unit` / `block`；只看某一層 |
| `--ocs-code CODE` |  | 不限 | 鎖定特定職務（找它底下的 unit / block） |
| `-k, --top-k N` |  | `10` | 顯示前 N 筆 |
| `-H, --hybrid` |  | `false` | 啟用 dense + sparse RRF 融合（適合精確術語混語意的查詢） |
| `--text-lines N` |  | `4` | 每筆顯示幾行 Markdown 摘要（0 = 只顯示 metadata 不顯示 body） |

策略建議：
- **找候選職務**：`--level profile --top-k 5`
- **找具體能力 / 工作活動**：`--level block --hybrid`
- **查特定職務的標準任務**：`--ocs-code XXX --level unit`
- **長段工作描述**：拆成多個短查詢分別跑，再交集 / 排序（v1 indexer 不做這件事，由未來 service 負責）

範例：
```bash
# 從職務描述找最相關的具體能力
uv run python -m jd_ocs_indexer.cli query "我會用 SQL 清理資料並做 Power BI 報表" --level block --hybrid --top-k 5

# 找候選職務
uv run python -m jd_ocs_indexer.cli query "AI 導入規劃" --level profile --top-k 3

# 鎖定一個職務看它的工作任務
uv run python -m jd_ocs_indexer.cli query "資料蒐集分析" --ocs-code SMS2512-002v1 --level unit

# 只看 metadata 不顯示 Markdown 摘要
uv run python -m jd_ocs_indexer.cli query "AI 部署" --text-lines 0
```

#### `query` 與 `smoke-query` 差別

| | `smoke-query` | `query` |
|---|---|---|
| 用途 | 索引驗證 | 人類探索 |
| 輸入 | code filter / probe text | 自然語言 |
| 輸出 | raw（chunk_key、score） | breadcrumb + K/S + 摘要 |
| 融合 | dense / sparse 各跑一次 | 預設 dense；`--hybrid` 走 Qdrant RRF |
| 穩定性 | 不保證輸出格式穩定 | 主要使用介面，會盡量穩 |

### 4. 全量索引時間估計

`index S:/jd-pdf-to-json/output/0518` 預估 ~12,869 chunks。CPU 上 BGE-M3 一個 `INDEX_BATCH_SIZE=64` 約 28-40 秒，總時間估 **80-100 分鐘**。GPU 上會快 10-20 倍。

跑到一半中斷不會壞 — 每一 batch upsert 成功會更新 `.data/manifest.json`，下次重跑自動 skip 已完成的檔案。

### 5. v1 fixture acceptance（已驗證）

| 驗證 | 結果 |
|---|---|
| `render` 產出 profile/unit/block Markdown | ✓ 3 fixtures = 66 chunks |
| `index` 建 collection + payload indexes + upsert dense+sparse | ✓ 66 points (3 profile + 15 unit + 48 block) |
| 重跑 `index` 依 hash skip 未變檔 | ✓ skipped=3 |
| `smoke-query --ocs-code` payload filter | ✓ 16 hits across 三層 |
| `smoke-query -k -s` K/S code filter | ✓ 3 block hits |
| `smoke-query --probe-vector` dense+sparse | ✓ top hit T3.3「確保AI應用部署與系統整合」(dense 0.70 / sparse 0.25) |

---

## Query API (for jobintel-ai)

Stateless HTTP read layer over the Qdrant index. Embeds query text server-side
(BGE-M3), so callers send plain text. No conversation state / LLM here.

Install + run:

```bash
uv sync --extra api
jd-ocs-indexer serve --host 127.0.0.1 --port 8000
```

| Method | Path | Use |
|---|---|---|
| POST | `/search` | NL query → hits (server-side embed; `level`/`filters`/`hybrid`/`top_k`) |
| POST | `/task-pool` | merge `ocs_codes` → unit→task menu with activity examples |
| GET | `/profile/{ocs_code}/pairs` | OCS-wide K/S/A/output vocabulary pools |
| GET | `/healthz` | model + Qdrant readiness (200 ok / 503 degraded) |
| GET | `/stats` | collection point counts by level |

Interactive OpenAPI docs at `/docs`. Example:

```bash
curl -s localhost:8000/search -H 'content-type: application/json' \
  -d '{"query":"資料分析 Python SQL","level":"profile","top_k":5}'
```

---

## 模組結構

```text
src/jd_ocs_indexer/
  cli.py                  # render / index / stats / doctor / smoke-query
  config.py               # .env -> Settings dataclass
  models/
    ocs.py                # OCS JSON Pydantic models（tolerant，未知欄位忽略）
    chunk.py              # ChunkRecord / EmbeddedChunk / SparseVector
  ingestion/
    reader.py             # 掃 JSON / 算 source_json_hash / 產 LoadedFile
    normalizer.py         # 缺欄位 fallback / version 推導 / order 編號
    builder.py            # 三層 chunk 與 payload
    renderer.py           # Markdown + chunk_content_hash
    manifest.py           # .data/manifest.json 增量狀態
  embeddings/
    base.py               # EmbeddingService Protocol
    bge_m3.py             # FlagEmbedding BGEM3FlagModel adapter（dense+sparse）
  store/
    ids.py                # uuid5(NAMESPACE, chunk_key) point id
    schema.py             # vectors + payload index spec
    qdrant_client.py      # URL parser（host/port/https/prefix 拆解）
    writer.py             # ensure collection / batch upsert / delete by chunk_keys
  validation/
    stats.py              # source 與 collection 統計
    smoke_query.py        # by ocs_code / K/S filter / dense probe / sparse probe
    search.py             # dense + hybrid(RRF) helpers for the `query` CLI
```

---

## 參考文件

- Qdrant overview: https://qdrant.tech/documentation/overview/
- Qdrant hybrid queries: https://qdrant.tech/documentation/search/hybrid-queries/
- BGE-M3 / FlagEmbedding: https://github.com/FlagOpen/FlagEmbedding
