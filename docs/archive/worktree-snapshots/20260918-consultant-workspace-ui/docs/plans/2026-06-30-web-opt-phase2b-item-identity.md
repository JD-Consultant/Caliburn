# Web 優化 階段2b:官方項目穩定身分（provenance 比對 + draft-op 對稱化）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓官方 K/S/O/P 以**來源身分**（`ocs_code + 原始 code`）判定「已選」,而非顯示 name 或位置序碼;為此把 `draft-op` 端點對稱化（回 `code`,對齊 recommend-ks），並把 `FieldCombobox` 的比對改成「**有 code 用身分、否則用值**」——後者讓值物件（說明事項）維持文字比對。

**Architecture（DDD 依據）:** Evans 的實體 vs 值物件——K/S/O/P/態度/類別是**實體**（有來源身分,改名仍是同一項）→ 比身分;說明/補充事項是**值物件**（就是那段文字）→ 比值。`FieldCombobox` 共用於兩者,故用單一規則「選項有來源 code→比 `_ref.ocs_code+code`;無 code→比 name」自動分流。位置序碼（renumberCoded）依 React keys 原則**只用於顯示/排序,不當身分**。

**Tech Stack:** 後端 FastAPI + pytest（需測試 DB,設定見 `docs/runbook.md`「跑後端 DB 整合測試」）;前端 Next/React/TS（三道綠:`npx tsc --noEmit` + `npm run lint` + `npm run build`）。

## Global Constraints

- **命名一致性（Zalando「MUST use common field names」）**:O/P 新欄位沿用 `code`,不另創名;前端 `OutputSuggestion`/`IndicatorSuggestion` 加 `code: string`。
- **不動 indexer**:O/P 的 code 本就在 `CitableItem`,只是被 `draft-op` 丟掉。
- **行為保持**:說明/補充事項（DocNotes,無 code）維持 name 比對;此規則對它們是 no-op。
- 後端測試需測試 DB（`TEST_DATABASE_URL`);若未建,照 runbook 起 db + 建 `caliburn_test` + `alembic upgrade head`。
- 一 task 一 commit,綠了才 commit;**不要 push**。
- **不在本階段**:大面 API 審視（排在 2b 之後獨立一輪);2a。

## File Structure

- `apps/api/app/services/ai/draft_op.py` — catalog/AI 兩分支帶 `code`;簽名收 `list[dict]`。
- `apps/api/app/api/routes/ai.py` — `_catalog_op` 回 `[{code,name}],[{code,text}]`（不再丟 code）。
- `apps/api/tests/test_ai_draft_op.py` — 更新斷言到新形狀。
- `apps/web/src/types/index.ts` — `OutputSuggestion`/`IndicatorSuggestion` 加 `code`。
- `apps/web/src/hooks/useTaskCatalog.ts` — `fetchTaskCatalog`/`fromEntry` 的 O/P 保留 code。
- `apps/web/src/components/interview/fields/FieldCombobox.tsx` — 比對改「有 code 用身分、否則用值」。

---

### Task 1: 後端 `draft-op` 對稱化（回 `code`）

**Files:**
- Modify: `apps/api/app/services/ai/draft_op.py`
- Modify: `apps/api/app/api/routes/ai.py`（`_catalog_op`）
- Test: `apps/api/tests/test_ai_draft_op.py`

**Interfaces:**
- Produces:`POST /ai/draft-op` → `{"outputs":[{code,name,source}], "indicators":[{code,text,source}]}`;catalog 分支 code 來自池,AI 分支 code=""。

- [ ] **Step 1: 先更新測試到新形狀（紅）**

在 `apps/api/tests/test_ai_draft_op.py`:

`test_draft_op_no_note_returns_full_catalog` 的 assert 區加:
```python
    assert [o["code"] for o in body["outputs"]] == ["O01", "O02"]
    assert [i["code"] for i in body["indicators"]] == ["P01", "P02"]
```
`test_draft_op_with_note_returns_ai_drafts` 的 assert 區加（AI 產出無來源碼）:
```python
    assert all(o["code"] == "" for o in body["outputs"])
    assert all(i["code"] == "" for i in body["indicators"])
```
（`test_draft_op_indexer_down_returns_empty`、`test_draft_op_thin_task_returns_empty` 仍斷言 `{"outputs": [], "indicators": []}`,不變。）

- [ ] **Step 2: 跑測試確認紅**

Run（已起 db + 測試庫;見 runbook）:
```bash
cd apps/api && TEST_DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/caliburn_test" PYTHONUTF8=1 uv run pytest tests/test_ai_draft_op.py -q
```
Expected: FAIL（body 無 `code` 鍵 / KeyError 或值不符）。

- [ ] **Step 3: 改 `_catalog_op`（ai.py）不再丟 code**

把 `apps/api/app/api/routes/ai.py` 的 `_catalog_op` 結尾:
```python
    detail = task_competencies(pool, ref["task_code"])
    return [o["name"] for o in detail["outputs"]], [p["text"] for p in detail["indicators"]]
```
改為:
```python
    detail = task_competencies(pool, ref["task_code"])
    return detail["outputs"], detail["indicators"]
```
並把其型別註解 `-> tuple[list[str], list[str]]` 改為 `-> tuple[list[dict], list[dict]]`。

- [ ] **Step 4: 改 `draft_op` service 帶 code（draft_op.py）**

把 `_catalog_all` 與 `draft_op` 改為:
```python
def _catalog_all(outputs_catalog: list[dict], indicators_catalog: list[dict]) -> dict:
    return {
        "outputs": [{"code": o.get("code", ""), "name": o.get("name", ""), "source": "catalog"}
                    for o in outputs_catalog],
        "indicators": [{"code": p.get("code", ""), "text": p.get("text", ""), "source": "catalog"}
                       for p in indicators_catalog],
    }


async def draft_op(
    *,
    task_name: str,
    note: str | None,
    outputs_catalog: list[dict],
    indicators_catalog: list[dict],
    llm: LlmPort | None,
) -> dict:
    if not (note and note.strip()) or llm is None:
        return _catalog_all(outputs_catalog, indicators_catalog)

    prompt = prompts.DRAFT_OP.format(
        task_name=task_name or "（未命名任務）",
        note=note.strip(),
        outputs_ref="\n".join(f"- {o.get('name', '')}" for o in outputs_catalog) or "（無）",
        indicators_ref="\n".join(f"- {p.get('text', '')}" for p in indicators_catalog) or "（無）",
    )
    parsed = await llm.complete_json(prompt, role="cheap", default=None)
    if not isinstance(parsed, dict):
        return _catalog_all(outputs_catalog, indicators_catalog)

    outputs = _strs(parsed.get("outputs"))
    indicators = _strs(parsed.get("indicators"))
    if not outputs and not indicators:
        return _catalog_all(outputs_catalog, indicators_catalog)
    return {
        "outputs": [{"code": "", "name": n, "source": "ai"} for n in outputs],
        "indicators": [{"code": "", "text": t, "source": "ai"} for t in indicators],
    }
```
（`_strs` 不變;docstring 可同步更新形狀。）

- [ ] **Step 5: 跑 draft-op 測試 + 全套（綠）**

Run:
```bash
cd apps/api && TEST_DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/caliburn_test" PYTHONUTF8=1 uv run pytest tests/test_ai_draft_op.py -q
TEST_DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/caliburn_test" PYTHONUTF8=1 uv run pytest -q
```
Expected: draft-op 測試全綠;全套全綠（green-before==green-after）。

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/services/ai/draft_op.py apps/api/app/api/routes/ai.py apps/api/tests/test_ai_draft_op.py
git commit -m "feat(api): symmetric draft-op — return O/P codes like recommend-ks [2b]"
```

---

### Task 2: 前端型別 + O/P 保留 code

**Files:**
- Modify: `apps/web/src/types/index.ts`（`OutputSuggestion`/`IndicatorSuggestion`）
- Modify: `apps/web/src/hooks/useTaskCatalog.ts`（`fetchTaskCatalog`、`fromEntry`）

**Interfaces:**
- Consumes:Task 1 的 `draft-op` 回 `code`;批次 `task-catalogs` 本就回 O/P code。
- Produces:`TaskCatalogData.outputs/indicators` 帶真實來源 code（非 `""`）。

- [ ] **Step 1: 型別加 code**

在 `apps/web/src/types/index.ts`:
```typescript
export interface OutputSuggestion {
  code: string;
  name: string;
  source: AiSource;
}
export interface IndicatorSuggestion {
  code: string;
  text: string;
  source: AiSource;
}
```

- [ ] **Step 2: `useTaskCatalog.ts` 兩處保留 O/P code**

`fetchTaskCatalog` 內:
```typescript
    outputs: op.outputs.map((o) => ({ code: o.code, name: o.name })),
    indicators: op.indicators.map((i) => ({ code: i.code, text: i.text })),
```
`fromEntry` 內:
```typescript
    outputs: e.outputs.map((o) => ({ code: o.code, name: o.name })),
    indicators: e.indicators.map((i) => ({ code: i.code, text: i.text })),
```

- [ ] **Step 3: 型別檢查綠**

Run:
```bash
cd apps/web && npx tsc --noEmit
```
Expected: 無輸出。

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/types/index.ts apps/web/src/hooks/useTaskCatalog.ts
git commit -m "feat(web): carry O/P source codes through catalog data [2b]"
```

---

### Task 3: `FieldCombobox` 比對改「有 code 用身分、否則用值」

**Files:**
- Modify: `apps/web/src/components/interview/fields/FieldCombobox.tsx`

**Interfaces:**
- Consumes:Task 2 後 O/P 選項/選中項都帶來源 code（`_ref.code`/`srcs[0].code`）。
- Produces:官方「已選」判定 = 實體比身分、值物件比值;同名不同項不再誤判。

- [ ] **Step 1: 改比對邏輯**

在 `apps/web/src/components/interview/fields/FieldCombobox.tsx`,把現有:
```typescript
  const isOfficialSelected = (o: { name: string }) =>
    value.some((v) => v._src === "official" && v.name === o.name);
```
改為（並新增 `officialMatch` 輔助）:
```typescript
  // DDD：選項有來源身分(code)→ 比 provenance(ocs_code+code)；無 code(值物件，如說明事項)→ 比 name。
  const officialMatch = (v: Item, o: { code: string; name: string; srcs?: SourceRef[] }) => {
    const srcCode = o.srcs?.[0]?.code ?? o.code ?? "";
    if (srcCode) {
      return v._ref?.code === srcCode && (v._ref?.ocs_code ?? "") === (o.srcs?.[0]?.ocs_code ?? "");
    }
    return v.name === o.name;
  };
  const isOfficialSelected = (o: OptionItem) =>
    value.some((v) => v._src === "official" && officialMatch(v, o));
```
把 `toggle` 內取消勾選的 filter:
```typescript
    if (isOfficialSelected(opt)) {
      onCommit(value.filter((v) => !(v._src === "official" && officialMatch(v, opt))));
      return;
    }
```
把 `selectAllOfficial` 內「已選官方→跳過」:
```typescript
      if (next.some((v) => v._src === "official" && officialMatch(v, o))) continue;
```

- [ ] **Step 2: 三道綠**

Run:
```bash
cd apps/web && npx tsc --noEmit && npm run lint && npm run build
```
Expected: 全綠。

- [ ] **Step 3: 手動驗證（行為）**

`npm run up` + `turbo dev`,開一份有任務的文件:
1. **K/S/O/P**:點某格,選一個官方項 → 該項打勾;若該任務候選有**同名不同碼**兩項,只勾中的那個打勾（改前會兩個都勾）。
2. **說明/補充事項（DocNotes）**:選/取消官方候選仍正常打勾（值物件比對未受影響）。
3. **態度**:官方態度選取/打勾正常。
Expected: 上述成立。

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/components/interview/fields/FieldCombobox.tsx
git commit -m "feat(web): match official items by provenance identity, fall back to value [2b, DDD]"
```

---

## Self-Review

- **Spec coverage:** 對應研究紀錄 §3 D-2b-1（provenance 比對,Task 3）、D-2b-2（O/P code 接回,Task 1+2）。修正點「值物件用值比對」由 Task 3 的 `officialMatch` 規則涵蓋。
- **Placeholder scan:** 無 TBD/TODO;每步具實際碼與指令。
- **Type consistency:** 後端回 `{code,name,source}`/`{code,text,source}` ⇄ 前端 `OutputSuggestion`/`IndicatorSuggestion`（加 `code`）⇄ `fetchTaskCatalog`/`fromEntry` 讀 `o.code`/`i.code`;`officialMatch` 讀 `_ref.code`/`srcs[0].code`（Task 2 後皆有值）。
- **行為保持:** DocNotes（無 code）→ `officialMatch` 走 name 分支 = 原行為;態度/類別（有 code）→ 升級身分比對。
- **命名:** 沿用 `code`（Zalando 共用欄位名）;新輔助 `officialMatch` 自我描述 + 註解引 DDD。
- **風險:** 後端為內部端點、無外部消費者,形狀變更安全;前端 `officialMatch` 對無 code 者退回原 name 比對,最壞情況等同改前。
- **優化觀察（提出、未納入本階段）:** `fetchTaskCatalog`（per-task 後備）在批次 seeding + 持久化後已少觸發,可保留;未見其他需在這些檔案順手處理的命名/結構問題。
