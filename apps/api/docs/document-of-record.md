---
title: api 文件 of-record — skeleton / assemble_final / validate
audience: agent-primary(也給人)
scope: apps/api/app/core/domain/ocs_doc.py(OCS 文件契約純函式,dict-only)
updated: 2026-07-04
---

# api 文件 of-record — `ocs_doc`(深文檔)

> **主讀者 = agent。** OCS「著作產出文件」契約的 **3 個純函式 + 完成度**;**finalize 的 gate 在這**。
> 權威契約 = [`apps/pdf-to-json/README.md`](../../pdf-to-json/README.md) §6(**純 dict**,不用 pydantic、
> 不用 legacy `app/schemas/ocs.py`)。文件生命週期(draft PATCH → finalize → INSERT final)見 [`../README.md`](../README.md) §1。
> web 鏡像 = [`apps/web/src/lib/ocsDoc.ts`](../../web/src/lib/ocsDoc.ts)(完成度公式兩邊對齊)。
> living:改 [`ocs_doc.py`](../../app/core/domain/ocs_doc.py) 同 commit 更本檔。

## 1. 四個函式

| 函式 | 幹嘛 | 何時 |
|---|---|---|
| `skeleton(profile, units_tasks)` | 產**空殼**(profile/units/tasks 在、格子空) | 無文件時 GET 回空殼、選職類建 draft |
| `assemble_final(draft)` | 回**契約完整**的 deep copy(過 `validate`) | `finalize` / `export` |
| `validate(doc)` | 回**人類可讀錯誤字串列**(`[]` = valid) | `finalize`(非空 → 422) |
| `compute_completion(content)` | 填充率 ∈ [0,1] | list 端點 / dashboard |

## 2. `skeleton` — 空殼 + 分組 / 重編 / provenance

- **依 `(ocs_code, unit_id)` 分組**:不同職類即使都把職責編成「T1」也**不會合併**(key 含 ocs_code)。
- **全文件重編**:職責 `T1, T2…`、任務 `T{u}.{t}`;來源留在 `unit["source"]` / `task["provenance"]`(顯示 + recurate 合併)。
- **`occupation_name` 絕不退回 `job_title`**:未選職類時留空,待〔選職類〕帶入官方名(與 route `_refresh_header` 一致)。

> `build_from_picked` / `_renumber` **已隨 `document:buildTasks` 端點退役(P3,ADR 0021)**:
> 任務選用改由 web 前端文件編輯(`addFromPool`)+ PATCH,**單一寫入路徑**。別把它們加回來。

## 3. `assemble_final` — finalize 的 gate

```
deep copy(draft)
→ 補齊 5 大頂層鍵 + 各自 defaults(version_info/ocs_profile/ocs_content/ocs_attitude/notes)
→ 若無 version 紀錄 → 補一筆(v1 / 最新版本)
→ _strip_underscore(doc)          ← 遞迴剝除所有 "_" 開頭鍵
→ 契約純淨 dict
```

**`_strip_underscore`**:遞迴走 dict/list,`pop` 掉任何 `_` 開頭的鍵——涵蓋 unit/task 的 `_uid/_tid/_notes`、
葉節點 O/P/K/S/態度/類別的 `_id/_src/_ref/_levelSrc`,以及**任何未來新增的 `_` 欄**。draft 存進 DB **會**帶 `_` 欄
(前端 UI 用),但 finalize / export 後**契約 JSON 純淨**。

## 4. `validate` — 嚴格檢查(回字串,不丟例外)

逐層檢查並蒐集人類可讀錯誤:5 大頂層鍵 → `ocs_profile`(`ocs_code` 為 str、`ocs_name` 含
`job_category_name`+`occupation_name`)→ `ocs_content.ocu_units` 逐個(`ocu_code`/`ocu_name` 為 str、
`tasks` 為 list)→ 每 task(`task_codes` **非空**且每筆有 `code`+`name`、`competency_blocks` **非空**)→
每 block(`indicators`/`outputs`/`knowledge`/`skills` 為 list、`competency_level` 為 **int 或 None**)→
`ocs_attitude.attitudes` 為 list → `notes` 含 `prerequisites`+`supplements`。回 `[]` 即合法。

## 5. `compute_completion`

`filled = 1(header) + (1 if 有態度) + Σ_task 已填格數(O/P/K/S 各 1)`;
`total = 4 × 任務數 + 1(A) + 1(header)`。回 `filled / total`。**web `completion()` 用相同公式**(別讓兩邊漂)。

## 6. 不變量(code 讀不出的規則)

1. **純 dict**:不用 pydantic、不用 legacy `app/schemas/ocs.py`(那是 LLM 時代、defaults 不同)。
2. **draft 寬鬆、final 嚴格**:PATCH **不驗 schema**;`finalize` 才 `assemble_final` + `validate`(錯 → 422)。
3. **`_` 前綴一律 UI-only**:draft 存 DB、finalize/export **一律剝**(§3)。
4. **`occupation_name` 絕不退回 `job_title`**(§2)。
5. **分組 key 含 `ocs_code`**:多職類 cherry-pick 不會誤併(§2)。
6. **完成度公式與 web 對齊**(§5);retired 的 `build_from_picked` 別復活(§2)。

## 7. 指路

- 生命週期 / 端點 / 樂觀鎖:[`../README.md`](../README.md) §1;ADR [0015](../../../docs/adr/0015-document-save-optimistic-concurrency.md)(樂觀並發)。
- 契約 schema 權威:[`apps/pdf-to-json/README.md`](../../pdf-to-json/README.md) §6 · [`docs/ocs-schema.md`](../../../docs/ocs-schema.md) · [`packages/ocs-contract`](../../../packages/ocs-contract/)。
- web 鏡像(前端編輯 + 完成度):[`apps/web/src/lib/ocsDoc.ts`](../../web/src/lib/ocsDoc.ts) · [`docs/design/editor-knowledge-pack.md`](../../../docs/design/editor-knowledge-pack.md)。
