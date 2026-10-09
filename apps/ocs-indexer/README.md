# ocs-indexer — OCS 知識索引與查詢服務

將 [`apps/pdf-to-json`](../pdf-to-json/) 產出的 OCS（職能基準）JSON 建成 Qdrant 索引，
透過 **無狀態查詢 HTTP API**（:8000）提供公版候選資料。職位整體參考使用獨立的
document／task 索引；既有 profile／task 索引與介面保留原語意。

本 app 是「檢索」bounded context，負責結構化候選池及語意搜尋，不保存對話、LLM 或使用者狀態。
RAG 服務須明示啟動；JD App 可依 [ADR0080](../../docs/adr/0080-opt-in-public-reference-agent-tools.md)配置 HTTP consumer，不成為 App 預設啟動依賴。

下圖為既有 profile／task 索引的資料流；新公版參考索引的使用方式見[職位整體參考 API](#職位整體參考-api)。

```text
OCS JSON ─► normalize ─► build(profile + 每任務 task) ─► embed(HTTP→apps/embedder GPU) ─► Qdrant(ocs_v4)
                                                                                            │
                                                查詢 client ◄── 無狀態 API(:8000) ◄──┘
```

- **模型在獨立 GPU 容器：**BGE-M3（dense 1024d + sparse）由 [`apps/embedder`](../embedder/)
  提供（`POST /embed`），indexer 只作 HTTP client。依 ADR 0012，不在 indexer 安裝 torch；
  原 Windows 行程內執行曾有 segfault。
- **Qdrant 由本 app 管理：**其他服務經查詢 API 取資料，不直接存取 collection。

## 跑 / 測試

### 與 JD App 一起用 Docker 啟動

使用根目錄的 `compose.jd-app.yaml` 加 `compose.jd-app.rag.yaml`，首次選版與建索引後可用 `pnpm docker:rag:up` 一起啟動 App、PostgreSQL、查詢 API、Qdrant 與 GPU 模型。停止用 `pnpm docker:rag:stop`。完整設定、來源唯讀掛載與搜尋檢查見[操作手冊](../../docs/runbook.md#含公版參考的-docker-模式)。

RAG 仍是獨立服務，不移入 App。查詢 API 映像依本目錄的 lockfile 安裝 API extra 與兩個契約套件，不安裝 torch，也不包含 `.env`、測試或來源 JSON。容器只走內網，不接收 App 的金鑰。`Dockerfile.dockerignore` 限制可進入建置的檔案；服務以非 root 使用者執行，套件採非 editable 安裝，不依賴開發原始碼路徑。

完整模式使用 `caliburn-jd-app` project 的專用索引與模型快取 volume，不自動載入獨立開發 Compose 的資料。下方原生／獨立開發方式仍可用，兩種方式不要同時掛同一份 Qdrant 儲存。

### 職位整體參考 API

2026-10-05 已實作；JD App 可選 consumer 依 [ADR0080](../../docs/adr/0080-opt-in-public-reference-agent-tools.md) 明示啟用，獨立服務權責不變。

輸入員工實際工作文字，取得最多五份去重公版及**完整已解析任務目錄**。
顧問自行判斷是否適用；本服務不保存員工確認進度，也不判定 JD 完成。
JSON 目錄完整不等於原 PDF 抽取完整。

| Method | Path | 用途 |
|---|---|---|
| POST | `/occupation-references:search` | `{query, limit?}` → 公版概述、任務目錄、搜尋證據及實際檢索設定 |
| GET | `/occupation-references/{reference_id}` | 固定來源的概述與完整已解析目錄 |
| GET | `/occupation-references/{reference_id}/tasks/{task_id}` | 任務群組 O/P/K/S，保留無碼項目及多 T 共用區塊 |

查詢預設 `limit=5`，可選 1–5；未知欄位拒絕。模型只提供工作正文，不提供檢索參數。
BGE-M3 1024 維向量用 exact cosine 搜整份 D／任務與概述 T，兩路各取 20 份不同父公版；
**完整聯集全部 rerank 後才取最終五份**。`rerank_logit` 是排序值，cosine 是搜尋證據，
都不是符合率或適用門檻。職位名稱供顯示，不嵌入；K/S 保存在來源，按需讀取。

以下從 repo 根目錄執行，選版目錄每個 OCS code 僅放一份明示選用的 JSON：

```powershell
docker compose --profile rag up -d --build qdrant embedder
uv run --project apps/ocs-indexer --extra api jd-ocs-indexer index-references ./data/selected-ocs --collection ocs_references_20261005
$env:REFERENCE_COLLECTION = 'ocs_references_20261005'
$env:REFERENCE_CANDIDATE_LIMIT = '20'
uv run --project apps/ocs-indexer --extra api jd-ocs-indexer serve --port 8000
```

`index-references` 只建立新 collection，拒絕覆寫及重複 OCS code；全部寫入後才發布 ready
manifest。原始 UTF-8 JSON 與 hash 綁定 `reference_id`，讀取不代換成新版。失敗的 collection
保持未 ready；修正後請改用新名稱，不會自動刪資料。

`REFERENCE_COLLECTION` 未設定時新 API 回 503。`RERANKER_URL` 預設沿用 `EMBEDDER_URL`。
20 是原話控制初值，尚未證明為通用最佳參數；可由服務端設定 40。`GET /healthz` 是既有
基礎檢查，不代替新索引／模型的實際搜尋驗證。body 格式錯誤 422、來源不存在 404、索引
未 ready／不相容 409、無效模型回覆 502、連線失敗 503，不將故障當空結果。

契約權威：[`indexer_contract/references.py`](../../packages/indexer-contract/src/indexer_contract/references.py)。
設計及證據：[`API 設計`](../../docs/specs/2026-10-05-occupation-reference-api-design.md)、
施工及驗證。

### 既有 profile／task API

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

既有 profile／task 索引依兩種查詢用途選擇 embedding 單位。這組介面與上面的職位整體參考 API 分開，不能將下表當作新 API 的向量內容：

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
| GET | `/healthz`、`/stats` | 基礎連線檢查（含可取得的 `index_model`）、點數統計；不代表公版索引 ready |

這組 profile／task API 的歷史消費端設計保留在 Git 與研究文件。若要新增它的正式 JD App 用途，須另經現行決策流程，不能直接復活舊 `apps/api` 接點；ADR0080 已接入的是上方獨立的職位整體參考 API。

## Codemap

```text
src/jd_ocs_indexer/
  cli.py                  # index-references / index / stats / query / serve(瘦 CLI)
  config.py               # .env → Settings(QDRANT_*, EMBEDDER_URL, OCS_SOURCE_ROOT)
  pipeline.py             # run_index 純編排(CLI/批次/測試共用)
  models/                 # ocs.py(來源 JSON tolerant models)、chunk.py(ChunkRecord/EmbeddedChunk)
  ingestion/              # reader(掃檔) → normalizer(補缺/版本) → builder(v4 兩種點)
                          #   payloads.py = 落庫 payload 的 pydantic 權威(schema_version)
  embeddings/             # base.py(port + 相容驗證)、http_embedder.py(→ apps/embedder)、factory.py
  references/             # source(固定來源)／service(檢索用例)／store(Qdrant adapter)
  reranking/              # HTTP adapter：批次配對、模型身分／分數驗證
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
| `index-references <SCAN_DIR> --collection <NEW_NAME>` | 選定來源版本 → 獨立公版參考索引；拒絕覆寫 |
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
[來源 JSON 欄位契約](../pdf-to-json/README.md#6-field-contract)與 [OCS JSON Schema](../../packages/ocs-contract/schema/ocs-document.schema.json)·
embedder 細節:當時的內部紀錄。
