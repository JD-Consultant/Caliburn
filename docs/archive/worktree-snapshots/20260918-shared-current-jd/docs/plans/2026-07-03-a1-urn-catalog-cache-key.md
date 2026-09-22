# A1:per-task catalog 快取鍵改 URN(位置碼→身分)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修正 review finding A1——per-task catalog 的快取鍵從**文件位置碼**(T1.2,結構性編輯會重編 → 快取錯位、填格面板顯示別的任務的官方候選)改為**身分 URN**(`ocs:{ocs_code}:T:{task_code}`,由 provenance 組出,永不重編)。api 批次回應鍵與 web 快取鍵同步改,持久化 buster bump。

**Architecture:** 位置碼的病根=它的意義依賴 server 端文件當下狀態,而 client 永遠比 server 新(autosave debounce 500ms)——任何靠 invalidate/refetch 的修法都有 race。URN 由任務的 `provenance`(ocs_code+task_code)現組,不依賴文件排法與存檔狀態,零 race。格式沿用 indexer `api/urn.py` 的 scheme(spec §2 三分:身分存 provenance、顯示用位置碼、**鍵用 URN 現組**)。此鍵即 pack v2(ADR 0021)任務節點的原生鍵,非白工。決策:`docs/specs/2026-07-03-editor-provenance-knowledge-pack-decisions.md` §4 A1。

**Tech Stack:** 後端 FastAPI + pytest(`uv run pytest`,DB 測試需 `TEST_DATABASE_URL`);前端 Next 16 / TanStack Query v5(三道綠:`npx tsc --noEmit` + `npm run lint` + `npm run build`)。

## Global Constraints

- 維護者用**繁體中文**;commit 用英文 conventional commits。
- 一 task 一 commit,綠了才 commit;**不要 push**。green-before == green-after。
- `/ai/recommend-ks`、`/ai/draft-op` 的 `task_key` 參數**維持位置碼**(即時定位語意,server 收到立即 resolve、不快取)——只有「快取的鍵」改身分。
- 自訂任務(無 provenance)本來就不在批次內;改後 per-task query 直接 `enabled:false`(現況 fallback 對自訂任務也只回空,行為等價、少打兩發 API)。

## File Structure

- `apps/api/app/api/routes/documents.py` — `task_catalogs` 回應鍵改 URN。
- `apps/api/tests/test_task_catalogs_api.py` — 斷言鍵改 URN。
- `apps/web/src/lib/urn.ts` — 新增:`taskUrn(provenance)` 組字串(web 端唯一組 URN 點)。
- `apps/web/src/hooks/useTaskCatalog.ts` — `catalogKey` 吃 URN;`useTaskCatalog`/`useTaskLevel` 簽名加 urn。
- `apps/web/src/components/interview/CellFillerPanel.tsx`、`JobDocTable.tsx` — 呼叫端由 task.provenance 組 URN 傳入。
- `apps/web/src/components/layout/Providers.tsx` — `PERSIST_BUSTER` `ocs-v4-1` → `ocs-v4-2`(持久化的 task-catalogs 鍵形狀變了)。

---

### Task 1: api — 批次回應鍵改 URN

**Files:**
- Modify: `apps/api/app/api/routes/documents.py`(`task_catalogs`)
- Modify: `apps/api/tests/test_task_catalogs_api.py`

- [ ] **Step 1: 改測試斷言(紅)**

`test_task_catalogs_batches_pool_once_per_ocs_code`:
```python
    cats = r.json()["catalogs"]
    assert set(cats) == {"ocs:OC1:T:T1.1", "ocs:OC1:T:T1.2"}
    assert [k["code"] for k in cats["ocs:OC1:T:T1.1"]["knowledge"]] == ["K01"]
    # …其餘 T1.1/T1.2 取值同步改 URN 鍵
```
`test_task_catalogs_skips_custom_tasks`:`assert not any("T1.3" in k for k in r.json()["catalogs"])`(自訂無 provenance,本來就不在)。

- [ ] **Step 2: 跑測試確認紅**

```bash
cd apps/api && uv run pytest tests/test_task_catalogs_api.py -q
```
Expected: FAIL(鍵仍為位置碼)。

- [ ] **Step 3: 實作**

`documents.py::task_catalogs`——triples 收集處位置碼 `tk` 不再當鍵,鍵改 provenance URN
(格式對齊 indexer `api/urn.py` 的 `task_urn`;api 端不 import indexer,inline 組):

```python
    triples: list[tuple[str, str]] = []  # (ocs_code, task_code) — 鍵由 provenance 組,不用位置碼
    for unit in (content.get("ocs_content") or {}).get("ocu_units") or []:
        for task in unit.get("tasks") or []:
            ref = ai_tasks.catalog_ref(task)
            if ref["ocs_code"] and ref["task_code"]:
                triples.append((ref["ocs_code"], ref["task_code"]))
    ...
    for ocs_code, task_code in triples:
        pool = pools.get(ocs_code)
        if pool is None:
            continue
        # 鍵 = 身分 URN(scheme 同 indexer api/urn.py):結構性編輯重編位置碼不影響此鍵(A1)
        catalogs[f"ocs:{ocs_code}:T:{task_code}"] = task_competencies(pool, task_code)
```
(docstring 補一句:鍵=任務身分 URN,非文件位置碼。)

- [ ] **Step 4: 綠 + 全套**

```bash
cd apps/api && uv run pytest tests/test_task_catalogs_api.py -q && uv run pytest -q
```
Expected: 全綠(無 DB 的照常 skip)。

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/api/routes/documents.py apps/api/tests/test_task_catalogs_api.py
git commit -m "fix(api): key task-catalogs by provenance URN, not positional task code [A1]"
```

---

### Task 2: web — 快取鍵/呼叫端改 URN + buster bump

**Files:**
- Create: `apps/web/src/lib/urn.ts`
- Modify: `apps/web/src/hooks/useTaskCatalog.ts`、`CellFillerPanel.tsx`、`JobDocTable.tsx`、`Providers.tsx`

- [ ] **Step 1: 新增 `lib/urn.ts`**

```typescript
// 任務身分 URN(scheme 同 indexer api/urn.py):由 provenance 現組、不落庫(spec §2 三分)。
// 自訂任務(無 provenance)回 ""(呼叫端據此停用 catalog query)。
export function taskUrn(p?: { ocs_code?: string; task_code?: string }): string {
  return p?.ocs_code && p?.task_code ? `ocs:${p.ocs_code}:T:${p.task_code}` : "";
}
```

- [ ] **Step 2: `useTaskCatalog.ts` — 鍵改 URN,fallback 仍用位置碼**

```typescript
const catalogKey = (profileId: string, urn: string) => ["task-catalog", profileId, urn];
```
`useTaskCatalogs` 的 seeding 迴圈不變(批次回應的鍵已是 URN,直接灌)。
`useTaskCatalog(profileId, urn, taskKey, enabled)`、`useTaskLevel(profileId, urn, taskKey, enabled)`:
queryKey 用 `urn`;`queryFn: () => fetchTaskCatalog(profileId, taskKey)`(`/ai/*` 維持位置碼);
`enabled: enabled && !!urn && !!taskKey`。

- [ ] **Step 3: 呼叫端傳 URN**

`CellFillerPanel.tsx`:任務物件在手,`const urn = taskUrn(doc…tasks[taskIdx]?.provenance)`;
`useTaskCatalog(profileId, urn, tk, true)`。
`JobDocTable.tsx` `TaskRow`:`useTaskLevel(profileId, taskUrn(task.provenance), tc?.code ?? "", levelOpen)`。

- [ ] **Step 4: buster bump**

`Providers.tsx`:`const PERSIST_BUSTER = "ocs-v4-2";`(舊持久化的位置碼鍵作廢)。

- [ ] **Step 5: 三道綠**

```bash
cd apps/web && npx tsc --noEmit && npm run lint && npm run build
```

- [ ] **Step 6: 手動驗證(A1 復現場景)**

`npm run up` + turbo dev,開一份 ≥3 任務的文件:
1. 開 T1.2 的 K 格記下候選 → 關閉 → **刪除 T1.1**(T1.2 變 T1.1、T1.3 變 T1.2)→ 開「新 T1.2」(原 T1.3)的 K 格。
   Expected: 顯示**原 T1.3 任務**的官方候選(改前:顯示原 T1.2 的,錯)。
2. 拖拉任務跨職責 → 開格,候選仍正確。
3. Network:整程無多餘 `recommend-ks`/`draft-op`(seeding 命中,URN 不因重編失效)。

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/lib/urn.ts apps/web/src/hooks/useTaskCatalog.ts apps/web/src/components/interview/CellFillerPanel.tsx apps/web/src/components/interview/JobDocTable.tsx apps/web/src/components/layout/Providers.tsx
git commit -m "fix(web): key per-task catalog cache by provenance URN; bump persist buster [A1]"
```

---

## Self-Review

- **Spec coverage:** spec §4 A1(鍵=URN、buster bump)+ §2 三分(身分/顯示/鍵)。`/ai/*` 位置碼語意維持(Global Constraints 載明)。
- **Type consistency:** api 回應鍵 URN ⇄ web seeding 直灌(鍵透傳)⇄ `catalogKey(urn)` ⇄ 呼叫端 `taskUrn(provenance)`;fallback `fetchTaskCatalog(profileId, taskKey)` 簽名不動。
- **行為保持:** 官方任務路徑功能等價(僅鍵形狀);自訂任務由「fallback 打兩發回空」變「query 停用」——等價且省請求。
- **風險:** 舊 localStorage 快取靠 buster 作廢;pack v2 落地時本段(批次端點+per-task query)整體退役,URN 鍵直接沿用於任務節點——非白工。
- **殘餘已知縫(不在本 plan):** fallback 以位置碼打 `/ai/*` 在「未 seed + 剛結構編輯 + 500ms 內」的極窄窗口仍可能取回舊切片——pack v2(client 端零 server 依賴)根治;已記 spec §5。
