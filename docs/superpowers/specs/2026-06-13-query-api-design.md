# Query API 設計 — jd-ocs-indexer HTTP 接口

> 狀態：設計定稿，待實作。
> 目標讀者：實作者（writing-plans → implementation）、jobintel-ai consumer 端。
> 關聯文件：[USER_FLOW.md](../../USER_FLOW.md)（下游契約）、[DESIGN_DECISIONS.md](../../DESIGN_DECISIONS.md)。

---

## 1. 背景與目標

`jd-ocs-indexer` 目前只有 CLI（`render / index / stats / doctor / smoke-query / query`）。
下游 `jobintel-ai` 顧問服務與 UI 需要以 HTTP 取用已建好的 Qdrant 索引，
而不應該 import 本 Python library、也不該直接打 raw Qdrant REST。

本設計新增一層**無狀態 read API**，把既有的 retrieval primitives
（`validation/search.py`、`validation/smoke_query.py`）包成 HTTP endpoint，
並在 server 端內建 BGE-M3 embedding，讓 caller 只送純文字即可查詢。

### 責任界線（沿用 USER_FLOW §4.2）

| API 做 | API 不做 |
|---|---|
| 無狀態 read：向量搜尋 / scroll / payload 取用 | LLM 對話、JD 文字生成 |
| server 端 text → embedding | 多輪對話 state machine |
| 把 chunk payload 整形成 caller 友善的 response | 使用者編輯狀態管理 |
| profile/unit/block 三層的取用入口 | 候選 OCS 的最終排序呈現（UI 決定） |

---

## 2. 關鍵決策（三個架構分岔）

1. **Embedding 邊界 = server 端內建 BGE-M3。**
   API 收純文字 query，內部跑 BGE-M3 產 dense+sparse 再查 Qdrant。
   Caller 最簡單（text in → hits out），與 CLI `query` 行為一致。
   代價：服務需載入 ~2GB 模型、CPU embedding 每次 query 偏慢。

2. **Endpoint 風格 = 混合。**
   核心 `POST /search` 泛用向量搜尋，
   加上語意化 helper（`/task-pool`、`/pairs`）包裝 scroll 型操作。

3. **部署 / 認證 = localhost / 私網，先不做 auth。**
   不放 middleware；但 `create_app()` factory 留為擴充點，
   日後要加 `X-API-Key` 或 CORS 是一行的事。多 worker 擴充見 §7。

---

## 3. 程式結構

採方案 A：在本 repo 新增 `api/` subpackage，複用既有模組，不另開 service。

```
src/jd_ocs_indexer/api/
  __init__.py
  app.py       # create_app() + lifespan：載 embedder + qdrant client 進 app.state
  schemas.py   # Pydantic request/response models
  service.py   # 編排層：複用 validation/search + 新增 task-pool 的 block→unit→task shaping
  routes.py    # endpoint handlers（依賴 app.state 的 embedder/client/settings）
```

- 複用：`embeddings/bge_m3.py`、`store/qdrant_client.py`、
  `validation/search.py`、`validation/smoke_query.py`、`validation/stats.py`、`config.py`。
- `[project.optional-dependencies]` 新增 `api = ["fastapi>=0.115", "uvicorn[standard]>=0.30"]`，
  純 indexer 安裝不受影響。
- CLI 新增 `serve` 子命令：`uvicorn.run("jd_ocs_indexer.api.app:create_app", factory=True, host, port, workers=1)`。

---

## 4. Endpoint 契約

| Verb | Path | USER_FLOW Round | 用途 |
|---|---|---|---|
| POST | `/search` | 0-1, 2-custom | 泛用向量搜尋，server 端 embed |
| POST | `/task-pool` | 2 | 合併多 OCS 的 unit→task 選單 |
| GET | `/profile/{ocs_code}/pairs` | 4, gap | 取該 OCS 的 K/S/A/output 完整詞彙池 |
| GET | `/healthz` | ops | 模型載入 + Qdrant 連線狀態 |
| GET | `/stats` | ops | collection 統計 |

### 4.1 共用 Hit 投影

回傳的 `hit` 是 payload 的**精選投影**（非完整 payload；要全量 caller 自行打 Qdrant）。
固定帶導覽 + 出處欄位，body 內文 opt-in：

```jsonc
{
  "chunk_key": "ocs:SMS2512-002v1:profile",
  "chunk_level": "profile",            // profile|unit|block
  "ocs_code": "SMS2512-002v1",
  "job_title": "AI 應用規劃師",
  "score": 0.83,                       // null 表示非向量結果（scroll）
  "version": "v1",
  "is_current": true,
  "ocs_level": 5,
  "competency_level": null,
  "unit_id": null, "unit_title": null, "unit_order": null,
  "task_ids": [], "task_titles": [],
  "block_order": null,
  "k_pairs": [], "s_pairs": [],        // [{code,name}]
  "industry_names": ["..."], "occupation_names": ["..."],
  "source_file": "jd-ocs/.../SMS2512-002v1.json",
  "snippet": null                       // 僅 include_text=true 時填
}
```

> profile 的 `job_description` 全文落在 chunk `text` body（renderer 產出），
> 經 `include_text=true` 取 `snippet` 即可瀏覽；payload 本身無獨立 `job_description` 欄位。

### 4.2 POST /search

```jsonc
// request
{
  "query": "我在金融科技做資料分析，會 Python SQL",
  "level": "profile",                  // optional: profile|unit|block
  "hybrid": true,                      // dense+sparse RRF；false=dense-only
  "top_k": 5,                          // 1..50
  "filters": {                         // 全 optional
    "ocs_code": null,                  // 精確比對單一 OCS
    "is_current": true,
    "k_codes": null,                   // MatchAny
    "s_codes": null,                   // MatchAny
    "attitude_codes": null             // MatchAny
  },
  "include_text": false,
  "text_lines": 6                      // include_text 時 body 取幾行
}
// response
{ "mode": "hybrid", "level": "profile", "hits": [ /* §4.1 */ ] }
```

- `level=profile` → Round 0-1 找候選 OCS；`level=block` → Round 2 自訂項目掛點。
- 既有 `_level_filter(level, ocs_code)` 擴成 `build_filter(...)`，
  支援 `is_current`(bool)、`k_codes/s_codes/attitude_codes`(MatchAny)。
- **filter 無隱藏預設**：未給的欄位一律不套用。
  USER_FLOW §Round1「預設只回 `is_current=true`」是 jobintel-ai 端策略，
  由 caller 明確帶 `filters.is_current=true`，API 不自動注入，保持泛用 endpoint 可預期。
- hybrid 走既有 `hybrid_search`（RRF），dense 走 `dense_search`。

### 4.3 POST /task-pool

```jsonc
// request
{ "ocs_codes": ["SMS2512-002v1", "INM3513-009v1"], "activity_examples": 1 }
// response — 從 block chunks scroll 後分組
{
  "groups": [
    {
      "ocs_code": "SMS2512-002v1",
      "job_title": "AI 應用規劃師",
      "units": [
        {
          "unit_id": "U1", "unit_title": "評估與分析AI技術", "unit_order": 1,
          "tasks": [
            { "task_id": "T1.2", "task_title": "掌握目標並確立需求",
              "activity_examples": ["跟業務確認 AI 應用發展需求…"] }
          ]
        }
      ]
    }
  ]
}
```

**為什麼從 block shaping 而非讀 unit payload**：
unit payload 的 `task_ids` 與 `task_titles` 是兩條各自 dedup 的陣列
（[builder.py:207-211](../../../src/jd_ocs_indexer/ingestion/builder.py#L207-L211)），
不能安全 zip 對齊（與 v2 修掉的 parallel-array 對齊 bug 同類），
且 per-task 的代表性 activity 例句在 unit 層不存在。
block payload 則同時帶對齊的 per-group `task_ids/task_titles` 與
`work_activity_terms`（= indicator texts），是正確來源。**不需重建索引。**

**Shaping 演算法**（`service.build_task_pool`）：

1. Filter：`chunk_level == "block"` AND `ocs_code` ∈ `ocs_codes`（MatchAny）。
2. Scroll 所有命中 block point（`with_payload=True, with_vectors=False`），分頁直到 exhausted。
3. 分組 `ocs_code → unit(依 unit_order) → task(依 task_orders/task_id)`：
   - 每個 block 內 `zip(task_ids, task_titles)` 是對齊的；逐 task 收集 title。
   - `activity_examples`：自 block `work_activity_terms` 取前 N 句、truncate、去重。
   - `job_title` 取該 ocs_code 任一 block payload。
4. 多 task 的 group（罕見的 multi_task_groups）：該 block 的 activities 掛到它列出的每個 task_id。

### 4.4 GET /profile/{ocs_code}/pairs

```jsonc
// response
{
  "ocs_code": "SMS2512-002v1",
  "job_title": "AI 應用規劃師",
  "all_k_pairs": [{"code": "K01", "name": "AI 技術基本原理"}],
  "all_s_pairs": [], "all_a_pairs": [], "all_output_pairs": []
}
```

- 來源：profile chunk payload 的 `all_*_pairs`
  （[builder.py:158-161](../../../src/jd_ocs_indexer/ingestion/builder.py#L158-L161)）。
- 找該 ocs_code 的 `chunk_level == "profile"` chunk（scroll, limit 1）。
- 查無 → **404**。

### 4.5 GET /healthz、GET /stats

```jsonc
// GET /healthz  → 200 ok / 503 not-ready
{ "status": "ok", "model_loaded": true, "qdrant": "reachable", "collection": "ocs_bgem3_v2" }
// GET /stats   → 包 validation/stats.collection_stats
{ "collection": "ocs_bgem3_v2", "total_points": 12810,
  "by_level": { "profile": 908, "unit": 3272, "block": 8689 } }
```

---

## 5. 模型生命週期 / 併發

- BGE-M3 用 FastAPI **lifespan 啟動時載入一次**進 `app.state.embedder`；冷啟動數秒。
- Qdrant client（帶 `settings.qdrant_timeout`）同樣於 lifespan 建一次進 `app.state.client`。
- **單一 uvicorn worker**：每個 worker 各自載 ~2GB 模型，故預設 `workers=1`。
- Embedding 為 blocking CPU → 丟 `fastapi.concurrency.run_in_threadpool`，
  並以一把 lock 序列化（FlagEmbedding 不保證 thread-safe），
  使 scroll 型 endpoint 不被 embedding 卡住 event loop。
- 同步 Qdrant client 呼叫亦走 threadpool。

---

## 6. 錯誤處理

| 情境 | HTTP | body |
|---|---|---|
| schema 違規（FastAPI 內建） | 422 | `{detail: [...]}` |
| 空 query / 未知 level / top_k 超界 | 400 | `{detail: "..."}` |
| `/pairs` 未知 ocs_code | 404 | `{detail: "ocs_code not found"}` |
| Qdrant 不通 / upstream 錯（map `ResponseHandlingException`/`UnexpectedResponse`） | 502/503 | `{detail: "..."}` |
| `/healthz` 模型未就緒或 Qdrant 不通 | 503 | `{status: "degraded", ...}` |

統一錯誤 envelope：`{"detail": "..."}`。

---

## 7. 測試策略（TDD）

- **不載 2GB 模型**：以 stub embedder（回固定 dense + 空/固定 sparse）取代 BGEM3Embedder。
- **不連真 Qdrant**：以 fake/Mock `QdrantClient` 回 canned `query_points` / `scroll` 結果。
- 用 FastAPI `TestClient` 對每個 endpoint 驗：
  - `/search`：request validation、`build_filter` 組裝（level + is_current + k_codes/s_codes）、
    dense vs hybrid 分支、`include_text` 開關下 `snippet` 有無。
  - `/task-pool`：給 canned block points → 驗 unit 依 `unit_order` 排序、
    task 依 `task_id` 對齊、`activity_examples` 取樣數、multi-task group 掛載。
  - `/pairs`：抽 `all_*_pairs` 正確、未知 ocs_code 回 404。
  - `/healthz`：model_loaded / qdrant 兩種狀態組合。
- 真 Qdrant 的整合測試以 env flag gate，預設 skip。

---

## 8. 範圍外 / 未來

- **Auth**：`X-API-Key` middleware / CORS — `create_app()` 已留擴充點，要外曝再加。
- **吞吐擴充**：多 uvicorn process 擺 openresty 後面（同 Qdrant 架構），或 embedding 抽成獨立服務。
- **`task_pairs` 索引欄位**：若日後想讓 `/task-pool` 改讀 unit payload，
  需在 builder 加對齊的 `tasks: [{id,title,activity}]` 並重建索引（本設計不需要）。
- **JD 生成 / 對話 state**：屬 jobintel-ai，不在本 API。
