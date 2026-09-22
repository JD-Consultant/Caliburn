# ocs-indexer — OCS 知識索引與查詢服務

「檢索」bounded context。把 [`apps/pdf-to-json`](../pdf-to-json/) 產出的 OCS(職能基準)JSON
轉成 **兩種 Qdrant 向量點(profile + task)**,並提供**無狀態查詢 HTTP API**(:8000)。
本 app 只負責「結構化 + 可語意搜尋的候選池」；不保存對話、LLM 或使用者狀態。
它目前是隔離、明示啟動的 RAG bounded context，沒有正式 JD App consumer。

```text
OCS JSON ─► normalize ─► build(profile + 每任務 task) ─► embed(HTTP→apps/embedder GPU) ─► Qdrant(ocs_v4)
                                                                                            │
                                                查詢 client ◄── 無狀態 API(:8000) ◄──┘
```

- **嵌入不在本進程**:BGE-M3(dense 1024d + sparse)由 [`apps/embedder`](../embedder/)
  GPU 容器提供(`POST /embed`),indexer 只是 HTTP client(ADR 0012;**別把 torch 裝回來**,
  Windows 上會 segfault)。
- **Qdrant 屬本 app**:別的服務只經查詢 API 取資料,不直接碰 collection(資料主權)。

## 跑 / 測試

```bash
uv sync --all-extras                       # api extra = fastapi + uvicorn
docker compose up -d qdrant embedder       # 從 monorepo 根(:6333 + :8082 GPU)
uv run jd-ocs-indexer index ./data/jd-json # 建索引(空 Qdrant 首次必跑;不需本機 torch)
uv run jd-ocs-indexer serve --port 8000    # 查詢 API（或根目錄 pnpm rag:dev）
uv run --all-extras pytest -q
```

`.env`(見 `.env.example`):`QDRANT_URL`(預設 `http://localhost:6333`)、`QDRANT_COLLECTION`
(預設 **`ocs_v4`**)、`EMBEDDER_URL`(預設 `http://localhost:8082`)、`OCS_SOURCE_ROOT`、
`INDEX_BATCH_SIZE`。換 embedding provider / 維度 → **建新 collection,不混用**(ADR 0009)。

## 為什麼是 profile + task 兩種點

從使用者流程倒推 embedding 單位——整個著作流程只有兩個動作需要語意搜尋:

| 動作 | 點類型 | embed 內容 |
|---|---|---|
| 描述工作 → 找候選職類 | **profile**(每 OCS 一個) | 職稱 + 職務描述 + 任務名 + 活動樣本 + 全部 K/S 名 |
| 任務文字 → 找相近任務 | **task**(每 task_code 一個) | 任務名 + 該任務的能力區塊內容 |

其餘(撈任務清單、撈 K/S/O/P/A 池、表頭 metadata)都是「已知 `ocs_code` → filter/scroll」,
不需要向量。

**不變量:embed 是動作不是欄位** —— embed 字串在 index 時組好餵模型,**不回存 payload**;
顯示一律用已存的結構化欄位。K/S/O/A 一律存 `{code, name}` pair(iCAP 代碼是 OCS-local,
綁定不漂)。

## Payload(schema v4;權威 = `ingestion/payloads.py`,pydantic)

- **profile point**:`chunk_level="profile"`、`schema_version="v4"`、`ocs_code`、`ocs_code_base`、
  `is_current`、`ocs_name{job_category_name?, occupation_name?}`、`job_description`、`ocs_level`、
  `job_categories/occupations/industries/attitudes`(各為 `[{code,name}]`)、
  `prerequisites/supplements`(字串列表)、`indexed_at`、`source_file`。
- **task point**:`chunk_level="task"`、`ocs_code`、`ocs_name`(denormalized 顯示名)、
  `ocu_code`、`ocu_name`、`task_code`、`task_name`、
  `competency_blocks[]`(巢狀:`competency_level` + `indicators(P)/outputs(O)/knowledge(K)/skills(S)`)、
  `source_file`。
- **manifest point**(保留 id 一點):`chunk_level="_manifest"` + embedding 身分
  (provider/model/dim/revision)。查詢前 `assert_compatible` 驗證,不相容 → 409(ADR 0009)。
- point id = `uuid5(NAMESPACE, chunk_key)`;**URN**(`ocs:{code}`、`ocs:{code}:T:{task_code}`…)
  查詢時由 payload 組出、不落庫(`api/urn.py`)。

## 關鍵流程

### 1. Index(CLI `index`,全量重建)

```
reader(掃 *.json) → normalize(缺欄 fallback/版本推導) → build(profile + 每 task_code 一點,
embed 字串只放 ChunkRecord.text) → HTTP embed(batch) → QdrantWriter.upsert
→ 非空 run 收尾寫 manifest(嵌入身分戳記)
```

單檔失敗不中斷(記入 report.failures)。`pipeline.run_index` 是純編排,CLI/測試共用。

### 2. 查詢(語意)

`POST /occupations:search`、`/tasks:search`:server 端 embed(query → embedder)→ Qdrant
**hybrid RRF**(dense + sparse named vectors)+ `chunk_level` filter。查詢前先驗 manifest 相容。

### 3. 查詢(結構,無向量)

`GET /occupations/{code}`(profile payload 原樣)、`…/tasks`(task 點聚合成 unit→task 樹)、
`…/competencies`(掃該 code 全部 task 點,K/S/O/P 依 `item_urn` 去重聚合成 **CitableItem**:
每項帶 `sources[]`(哪些任務帶入、各自 level),A 從 profile 點取)。

### 4. 錯誤對應(app.py exception handlers)

| 情境 | HTTP |
|---|---|
| request schema 違規 | 422 |
| 未知 `ocs_code` | 404 |
| 索引 embedding 與查詢端不相容(ADR 0009) | 409 |
| Qdrant 回錯 / 連不上 | 502 / 503 |
| `GET /healthz` degraded(模型/Qdrant 任一不可用) | 503 |

## Query API reference(:8000)

**request/response schema 權威 = [`packages/indexer-contract`](../../packages/indexer-contract/)**
(共用 pydantic,ADR 0010);自訂方法用 AIP-136 `:verb`(ADR 0019)。互動式 OpenAPI:`/docs`。
預設綁 `127.0.0.1`、無 auth(對外請加反向代理;`create_app()` 是擴充點)。

| Method | Path | 用途 |
|---|---|---|
| POST | `/occupations:search` | 自然語言 → 職類 hits(`{query, top_k}`) |
| POST | `/tasks:search` | 自然語言 → 任務 hits |
| POST | `/tasks:batchGet` | point id 批次取回(缺失 id 靜默略過——刻意偏離 AIP-231,ADR 0019) |
| POST | `/items:match` | **相似比對**(ADR 0022):池進(`{kind, items:[{id,text,sources}]}`)→ `{groups, possible_matches, config}` 出。六步確定性管線(清洗→NFKC 收斂→嵌入→跨來源 cosine→FS 三區分帶→星型分群);per-kind 門檻在 [`matching/core.py`](src/jd_ocs_indexer/matching/core.py) `THRESHOLDS`(改門檻=跑 [`scripts/calibrate_match.py`](scripts/calibrate_match.py) 留紀錄)。錯誤:>500 項→413、kind 不認得→422、embedder 掛→503(body 含 `code`) |
| GET | `/occupations/{ocs_code}` | 職類官方 metadata(表頭池原料) |
| GET | `/occupations/{ocs_code}/tasks` | unit→task 結構(任務候選原料) |
| GET | `/occupations/{ocs_code}/competencies` | K/S/O/P/A 能力池(多來源 CitableItem) |
| GET | `/healthz`、`/stats` | 就緒(含 `index_model`)、點數統計 |

歷史消費端設計保留在 Git 與研究文件；未來若要接入正式 JD App，須另經現行決策流程，不能直接復活舊 `apps/api` 接點。

## Codemap

```text
src/jd_ocs_indexer/
  cli.py                  # index / stats / doctor / smoke-query / query / serve(瘦 CLI,ADR 0009)
  config.py               # .env → Settings(QDRANT_*, EMBEDDER_URL, OCS_SOURCE_ROOT)
  pipeline.py             # run_index 純編排(CLI/批次/測試共用)
  models/                 # ocs.py(來源 JSON tolerant models)、chunk.py(ChunkRecord/EmbeddedChunk)
  ingestion/              # reader(掃檔) → normalizer(補缺/版本) → builder(v4 兩種點)
                          #   payloads.py = 落庫 payload 的 pydantic 權威(schema_version)
  embeddings/             # base.py(port + 相容驗證)、http_embedder.py(→ apps/embedder)、factory.py
  store/                  # ids(uuid5)、schema(vectors+payload indexes)、writer(upsert)、
                          #   manifest(嵌入身分)、qdrant_client
  validation/             # stats、smoke_query、search(build_filter + dense/hybrid RRF,CLI+API 共用)
  api/                    # 查詢 API(extra):schemas、service(無狀態編排,可 fake 測)、
                          #   routes(threadpool + embed lock)、app(create_app factory)、urn.py
  matching/               # 相似比對(ADR 0022):core.py(純規則:門檻/清洗/分帶/星型)、
                          #   service.py(管線:collapse→embed→score→組回應;不碰 Qdrant)
```

另有 `scripts/calibrate_match.py`(app 根):門檻校準,與生產共用 `matching` 的
collapse/score_pairs(校準即生產);輸出留 `docs/specs/` 當校準紀錄。

## CLI reference

皆可 `uv run jd-ocs-indexer <cmd> --help`。中文亂碼:`$env:PYTHONIOENCODING="utf-8"`。

| 命令 | 用途 |
|---|---|
| `index <SCAN_DIR> [--limit N]` | 建索引(全量;寫 `QDRANT_COLLECTION`) |
| `stats [SCAN_DIR] [--collection]` | source 端 / Qdrant 端統計 |
| `doctor <SCAN_DIR>` | 資料健康檢查(parse 失敗/缺欄;不阻斷索引) |
| `query "<TEXT>" [-l profile\|task] [--ocs-code] [-H]` | 人類可讀查詢(`-H` = hybrid) |
| `smoke-query` | 索引驗證(原始輸出,格式不保證穩定) |
| `serve [--host] [--port]` | 起查詢 API |

## 指路

**內部管線深文檔(改 ingest / 查詢邏輯前先讀):[`docs/pipeline.md`](docs/pipeline.md)** —— normalizer lockstep、
builder embed 字串、RRF hybrid、competencies 去重、manifest 相容的「內部怎麼跑 + 為什麼」。

ADR [0003](../../docs/adr/0003-indexer-stays-separate-service.md)(獨立服務)·
[0009](../../docs/adr/0009-embedding-version-manifest.md)(manifest)·
[0010](../../docs/adr/0010-indexer-contract-shared-package.md)(契約 #2)·
[0012](../../docs/adr/0012-embedding-as-a-service.md)(embedder 服務化)·
[0019](../../docs/adr/0019-api-naming-alignment.md)(命名)·
[`docs/ocs-source-json.md`](../../docs/ocs-source-json.md)(來源 JSON 契約)·
embedder 細節:[`docs/specs/2026-06-29-embedder-service-bge-m3-research.md`](../../docs/specs/2026-06-29-embedder-service-bge-m3-research.md)。
