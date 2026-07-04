---
title: api 知識包伺服器組裝 — build_pack
audience: agent-primary(也給人)
scope: apps/api/app/core/domain/knowledge_pack.py(indexer DTO → GET /knowledge 的 pack dict)
updated: 2026-07-04
---

# api 知識包組裝 — `build_pack`(深文檔)

> **主讀者 = agent。** 這是 **`GET …/knowledge` 的心臟**:把 indexer 三資源組成 **web 所有選單吃的那一包**。
> 上游 = [`ocs-indexer/docs/pipeline.md`](../../ocs-indexer/docs/pipeline.md)(`competencies` 等 DTO);
> 下游消費 = [`docs/design/editor-knowledge-pack.md`](../../../docs/design/editor-knowledge-pack.md)(web `pack.ts` → 選單)。
> 權威決策見 [`docs/specs/2026-07-03-editor-provenance-knowledge-pack-decisions.md`](../../../docs/specs/2026-07-03-editor-provenance-knowledge-pack-decisions.md) §5。
> living:改 [`knowledge_pack.py`](../../app/core/domain/knowledge_pack.py) 同 commit 更本檔。

## 1. 一句話

`build_pack(order, details, tasks_by_code, pools_by_code)` **純函式**:照**職位優先序**把每個 OCS 的
indexer 回應攤成 **12 個池(key 去重 + `srcs` 累積)+ `source_tasks`(任務 URN byId,反掛 o/p/k/s_refs)**。
不碰 IO、不排序、不正規化名字。

## 2. 輸入 / 輸出

| | 形狀 | 來源 |
|---|---|---|
| `order` | `list[str]`(成功抓到的 ocs_code,**優先序**) | route:per-code 並行抓,掛的略過 |
| `details[code]` | `OccupationDetail`(表頭 + 三類 + 態度 + notes) | indexer `GET /occupations/{code}` |
| `tasks_by_code[code]` | `OccupationTasks`(unit→task 樹) | indexer `…/tasks` |
| `pools_by_code[code]` | `CompetencyPool`(K/S/O/P 的 CitableItem,帶 `sources[]`) | indexer `…/competencies` |
| **回傳** | `{occupation_details[], pools{12 池}, source_tasks{}}` | route 再補 `meta.partial` |

> DTO 權威 = [`packages/indexer-contract`](../../../packages/indexer-contract/)(ADR 0010);
> route 端的並行抓取 / partial / 502 見 [`../README.md`](../README.md) §3。

## 3. 12 池 + 去重 key(§5.1;**key = 原始字串精確比對,不正規化**)

| 池 | key | `srcs[]` 每筆帶 |
|---|---|---|
| `knowledge` / `skills` / `outputs` | **name** | ocs_code, ocs_name, code, ocu/task_code+name, competency_level |
| `indicators`(P) | **text** | 同上 |
| `units` | **ocu_name** | ocs_code, ocs_name, ocu_code, ocu_name |
| `tasks` | **task_name** | **URN 字串**(指向 `source_tasks`,非完整 srcs) |
| `attitudes` | **name** | ocs_code, ocs_name, code |
| `job_categories` / `occupations` / `industries` | **分類 code** | ocs_code, ocs_name(row 另存 `name`) |
| `prerequisites` / `supplements` | **text** | ocs_code, ocs_name, **code=`n{i}`(來源清單 1-based 位置碼,不補零;跳過空白不佔號。web 端 notes 官方判定/`_ref` 綁定靠它——spec [2026-07-04 field-identity](../../../docs/specs/2026-07-04-editor-field-identity-unification-spec.md) §3)** |

> **為什麼態度 / K / S 用 name 當 key(A5)**:那些 code 是**文件自編**(A01、K01…),跨不同職類**必撞**;
> name 才是穩定身分。三類池反而用**國家分類碼**(全國唯一)。

## 4. 組裝規則(逐段,對照 `build_pack`)

依 `order` 逐 code(**append 序 = 職位優先序**;A 的值先進、B 後進,選單就照這個順序不再排):

1. **`occupation_details`**:`append(d.model_dump())`——保序,給表頭主基準選單。
2. **表頭池**:態度(name key)、三類(code key,row 存 `{name, srcs}`)、notes(text key)。
3. **結構池**:
   - `units`:ocu_name key。
   - `tasks`:task_name key,`srcs` **append URN**(`ocs:{code}:T:{task_code}`),去重。
   - 同時建 `source_tasks[urn]` 骨架:`{ocs/ocu/task 身分, competency_level:None, o/p/k/s_refs:[]}`。
4. **能力池 + 反掛**(K/S/O/P):對每個 CitableItem 的每個 `source`——
   - 正向:`pools[池][key].srcs.append({…含 task 出處 + level})`;
   - **反向**:`source_tasks[該 source 的 URN][x_refs].append(key)`,並在 `competency_level is None` 時**補上** source 的 level。
   → 於是 `source_tasks[urn]` 成為「**這個任務自己配套哪些 O/P/K/S**」的反向索引。

## 5. 不變量(code 讀不出的規則)

1. **名字不正規化**:池 key = 原始字串**精確比對**(維護者拍板);別偷加 trim/lower/全半形轉換。
2. **append 序 = 職位優先序**:池不排序(web 選單也不排,顯序號)。
3. **`tasks` 池 `srcs` 是 URN**(指 `source_tasks`),**不是**完整 srcs——與其他池不同,別統一。
4. **`source_tasks` = 任務→自己配套的反向索引**:web `ownTaskRefs(pack, urns)` 靠它做「預勾自己的官方 O/P/K/S」。
5. **A5**:態度 / K / S 用 **name** key(code 文件自編會撞);三類用**分類 code**。
6. **partial 由 route 標**,不在此:單 code 抓失敗 → route 略過該 code + `meta.partial=true`;`build_pack` 只組收到的。
7. **純函式**:不 IO、不 import 外圈(core/domain;ADR 0008)。

## 6. 指路

- 上游 DTO 怎麼來:[`ocs-indexer/docs/pipeline.md`](../../ocs-indexer/docs/pipeline.md)(§4.2 `get_competencies` 的 CitableItem)。
- 下游怎麼吃:[`docs/design/editor-knowledge-pack.md`](../../../docs/design/editor-knowledge-pack.md)(web `pack.ts` / 選單 / `_ref`·URN 三分)。
- 決策(去重 key / 三分 / A4 / A5):[`docs/specs/2026-07-03-editor-provenance-knowledge-pack-decisions.md`](../../../docs/specs/2026-07-03-editor-provenance-knowledge-pack-decisions.md)。
- ADR [0021](../../../docs/adr/0021-knowledge-pack-single-sync-point.md)(知識包=唯一同步點)· app 面 [`../README.md`](../README.md)。
