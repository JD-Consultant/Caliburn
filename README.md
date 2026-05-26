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

```bash
# 只把 JSON render 成 Markdown（不連 Qdrant），人工檢查 chunk 文字
uv run python -m jd_ocs_indexer.cli render tests/fixtures -o output/md

# 來源端統計：files / units / tasks / blocks / 缺漏欄位數
uv run python -m jd_ocs_indexer.cli stats tests/fixtures

# 已知資料缺漏的健康報告（不阻斷索引）
uv run python -m jd_ocs_indexer.cli doctor tests/fixtures --show-files 10

# 完整 pipeline：reader -> normalizer -> builder -> renderer -> embed -> upsert
uv run python -m jd_ocs_indexer.cli index tests/fixtures

# 重跑會依 source_json_hash 自動 skip 未變檔案
uv run python -m jd_ocs_indexer.cli index tests/fixtures   # 全部 skipped
uv run python -m jd_ocs_indexer.cli index tests/fixtures --rebuild   # 忽略 manifest

# Qdrant 端統計：total points + by chunk_level
uv run python -m jd_ocs_indexer.cli stats --collection ocs_bgem3_v1

# smoke-query：驗證 payload filter / 向量檢索（原始輸出，不格式化）
uv run python -m jd_ocs_indexer.cli smoke-query --collection ocs_bgem3_v1 --ocs-code SMS2512-002v1
uv run python -m jd_ocs_indexer.cli smoke-query --collection ocs_bgem3_v1 -k K01 -s S01
uv run python -m jd_ocs_indexer.cli smoke-query --collection ocs_bgem3_v1 --probe-vector "AI 應用開發 部署 系統整合"

# query：自然語言查詢（人類可讀輸出 + 工作路徑 + 程式碼摘要）
uv run python -m jd_ocs_indexer.cli query "我想做AI應用部署與系統整合"
uv run python -m jd_ocs_indexer.cli query "資料處理 ETL" --hybrid --level block --top-k 5
uv run python -m jd_ocs_indexer.cli query "資料蒐集分析" --ocs-code SMS2512-002v1 --level unit
```

`query` 與 `smoke-query` 的差別：
- `smoke-query` 為驗證工具，輸出 raw（chunk_key、score、level、ocs_code），用來確認索引有沒有寫好。
- `query` 為人類可讀的探索工具，顯示職務 / 單元 / 任務 / 區塊 breadcrumb、K/S codes、source 檔名、Markdown 摘要。預設純 dense 檢索；加 `--hybrid` 啟用 BGE-M3 dense + sparse 經 Qdrant RRF 融合。

> Windows 終端機若有中文亂碼，先 `$env:PYTHONIOENCODING="utf-8"`（PowerShell）。VSCode 終端機預設就是 UTF-8。

### 4. 全量索引

```bash
uv run python -m jd_ocs_indexer.cli index S:/jd-pdf-to-json/output/0518
```

預估 ~12,869 chunks。CPU 上 BGE-M3 一個 batch (8 chunks) 約 2-3 秒，總時間估 60-90 分鐘。跑到一半中斷不會壞 — 已 upsert 的檔會寫進 `.data/manifest.json`，下次重跑自動 skip。

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
