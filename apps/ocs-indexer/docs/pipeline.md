---
title: ocs-indexer 管線內部 — ingest + 查詢
audience: agent-primary(也給人)
scope: apps/ocs-indexer 內部(reader→normalizer→builder→embed→Qdrant;查詢 semantic + structural)
updated: 2026-07-04
---

# ocs-indexer 管線內部 — ingest + 查詢(深文檔)

> **主讀者 = agent。** [`../README.md`](../README.md) 是「面」(端點 / codemap / payload schema);
> 這份是「**內部怎麼跑 + 為什麼**」——動 `normalizer` / `builder` / payload / 查詢邏輯前先讀。
> **living**:改管線的碼,同 commit 更新本檔。payload 欄位權威在 `ingestion/payloads.py`(pydantic)。

## 1. 一句話

- **離線 index**:每個 OCS JSON → `normalize`(對齊 / 補缺 / 版本)→ `build`(**1 profile 點 + 每 task_code 1 task 點**)→ `embed`(HTTP → `apps/embedder`)→ Qdrant `upsert`;非空 run 收尾寫 **manifest**(嵌入身分)。
- **線上 query**:**semantic**(embed query → RRF hybrid)+ **structural**(scroll + filter,**無向量**)。

## 2. 資料模型:兩種點 + 一個 manifest

| 點 | `chunk_level` | chunk_key(→ uuid5 id) | 幹嘛 |
|---|---|---|---|
| profile | `profile` | `ocs:{code}:profile` | 每 OCS 一點;職類搜尋 + 表頭池原料 |
| task | `task` | `ocs:{code}:task:{task_code}` | 每 task_code 一點;任務搜尋 + 能力池原料 |
| manifest | `_manifest` | 固定 sentinel id | 嵌入身分(provider/model/dim/revision);**不參與搜尋** |

- **named vectors**:每點存 `dense`(1024d)+ `sparse`;查詢照名字選(`using="dense"/"sparse"`)。
- **point id = `uuid5(NAMESPACE, chunk_key)`**(`store/ids.py`)→ 同 key 重跑冪等覆蓋。
- payload schema(profile / task 欄位)不在此複製 → 見 [`../README.md`](../README.md) 的「Payload」節(權威 = `ingestion/payloads.py`)。

## 3. Ingest 端到端(`pipeline.run_index`)

```
reader.iter_loaded(scan_dir)                       # 逐檔 yield (loaded | fail)
  └ 單檔 parse 失敗 → report.failures,continue     # 不中斷整批
normalize(doc)  → NormalizedOCS                    # 對齊 / 補缺 / 版本
build(norm, ctx) → [ChunkRecord]                   # 1 profile + N task;text=embed 字串
embedder.embed_texts([r.text …])                   # HTTP batch → dense+sparse
writer.upsert(EmbeddedChunk…)                      # batched;先 ensure_collection + ensure_payload_indexes
非空 run 收尾:write_manifest(embedder.signature)   # 蓋上「誰建的索引」
```

### 3.1 `normalizer`:lockstep pairs(**防 code↔name 漂移**,最重要)

`normalize` 把 tolerant 的來源模型攤平成 builder 不必再判空的 `NormalizedOCS`。關鍵手法:
**所有 code+name 對(K/S/O/P/態度/三分類/task)先組成 `Pair`(**兩邊都非空才收**),再從 pair 派生平行陣列**——
所以 `k_codes[i]` 與 `k_terms[i]` **永遠對齊**。三分類另按 `code|name` 去重。

> **為什麼**:曾把多值的 `category.job_categories`(AIoT = MPM/INM/ISD/SET)只抓 code、丟了 name,
> 平行陣列錯位。修法就是這個「先綁對、再拆」。改 normalizer **絕不可**回到「分別收 code 陣列、name 陣列」。

其餘:`is_current`(version_info 有對到 `ocs_code` 的列且 status 含「最新」;**無 version_info → 視為 current**)、
`version_seq` / `ocs_code_base`(從 `ocs_code` 尾巴 `vN` 推)、order 索引(unit/task/block,1-based)。

### 3.2 `builder`:embed 字串 vs payload(**embed 是動作,不是欄位**)

- **profile 點**:payload = 結構化欄位;**embed text** = `job_title` + `job_description` + `工作內容：`任務名 + `活動：`前 20 條指標文字 + `技能：`全部 K/S 名。
- **task 點**:payload = 該 task_group 的 `competency_blocks`(巢狀:level + P/O/K/S);**embed text** = `task_name` + 去重指標文字。
- **鐵則:embed 字串只塞 `ChunkRecord.text` 餵模型,永不寫回 payload**;顯示一律用結構化欄位。
- 「同格多 T code」→ builder 對 `group.tasks` 每個 task_code 各出一個 task 點,**共用同一組 blocks**。

## 4. Query 端到端(`api/service.py`,純同步;route 包 threadpool)

### 4.1 semantic(`search_occupations` / `search_tasks`)

```
assert_compatible(read_manifest, embedder.signature)   # 不相容 → 409(ADR 0009)
embedder.embed_query(q) → dense + sparse
hybrid_search(level="profile"|"task", limit=top_k)
```

**RRF hybrid**(`validation/search.py`)= Qdrant **內建融合**:兩個 `Prefetch`(dense、sparse 各取 `prefetch_limit=50`、都套 `build_filter`)→ `FusionQuery(RRF)` → 取 `top_k`。sparse 缺就退純 dense。
`build_filter` 是 CLI `query` 與 API **共用**的唯一 filter 構造器(`chunk_level` / `ocs_code` / `is_current`)。

### 4.2 structural(**無向量**,scroll + filter)

| 端點函式 | 做法 |
|---|---|
| `get_occupation` | scroll 該 code 的 profile 點 → 原樣投影(表頭池原料) |
| `get_occupation_tasks` | scroll task 點 → 聚成 `units{ocu_code → {ocu_name, urn, tasks[]}}` 樹,排序 |
| `get_competencies` | scroll task 點 → 每 block 的 K/S/O/P 項**按 `item_urn(code,type,code)` 去重**成 bucket;每項 `sources[]` **累積**(哪個 unit/task 帶入、各自 level);A 從 profile 點取 |
| `batch_get_tasks` | `client.retrieve(ids)` → 投影;**缺失 id 靜默略過**(刻意,ADR 0019) |
| `matching.service.match_items` | 相似比對(ADR 0022,`POST /items:match`):不碰 Qdrant,吃呼叫端送來的池 → 清洗/NFKC 收斂 → embedder 嵌入 → 跨來源 numpy cosine → FS 分帶 → 星型分群(舊 `tasks:findSimilar` 已退役,零消費者、功能被涵蓋) |

> `get_competencies` 的 **CitableItem** 就是 api `/knowledge` 能力池的原料:同一 K/S 跨多任務出現時,
> 去重成一項、`sources[]` 記全部出處(api 據此堆 `srcs`,web 選單顯示引用行)。

### 4.3 manifest 相容(查詢前必驗)

`_manifest` 點存嵌入身分;**每個 semantic 查詢前 `assert_compatible`**——索引端與查詢端 embedder 不一致就 **409**,不會拿錯維度的向量硬查(ADR 0009)。換 provider/維度 = **建新 collection,不混用**。

## 5. 不變量(code 讀不出的規則)

1. **embed 是動作、不是欄位**:embed 字串 index 時組好餵模型,**不回存 payload**(§3.2)。
2. **lockstep pairs**:normalizer 一律「先綁 code+name pair、再拆平行陣列」,禁止分別收(§3.1)。
3. **Qdrant 資料主權**:別的服務只經查詢 API 取資料,不直接碰 collection。
4. **K/S 的 `code` 是 OCS-local**(跨不同 OCS 會撞名),不是全域鍵;跨 OCS 的身分用 URN(`api/urn.py` 現組、不落庫)。
5. **換嵌入 = 換 collection**:manifest 綁一組維度/模型;查詢前驗,不相容 409。
6. **管線純編排**:`run_index` 不碰 Typer/console(CLI/批次/測試共用);`api/service` 不 import FastAPI(可 fake 測)。

## 6. 指路

- 面 / 端點 / payload schema:[`../README.md`](../README.md)。
- ADR:[0003](../../../docs/adr/0003-indexer-stays-separate-service.md)(獨立服務)·[0009](../../../docs/adr/0009-embedding-version-manifest.md)(manifest / 相容)·[0010](../../../docs/adr/0010-indexer-contract-shared-package.md)(契約 #2)·[0012](../../../docs/adr/0012-embedding-as-a-service.md)(embedder 服務化)。
- 來源 JSON 契約:[`apps/pdf-to-json/README.md`](../../pdf-to-json/README.md) §6.3;取用注意事項 [`docs/ocs-source-json.md`](../../../docs/ocs-source-json.md)。
- 下游消費(哪個端點餵哪個池):[`apps/api/README.md`](../../api/README.md) + [`docs/design/editor-knowledge-pack.md`](../../../docs/design/editor-knowledge-pack.md)。
- 文檔怎麼寫:[`docs/README.md`](../../../docs/README.md)、[`docs/design/README.md`](../../../docs/design/README.md)。
