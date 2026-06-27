# 欄位來源標記／鎖定等級／UUID 身分 — 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓文件每個葉項目（O/P/K/S、態度、所屬類別、基準代碼↔名稱）帶穩定 UUID 身分與「官方/自訂」來源標記，並在選單顯示候選來源；改官方內容即轉自訂；export 剝除前端欄位。

**Architecture:** 前端在 `CodeName`/`Indicator` 加 `_id`/`_src`/`_ref` 三個 `_` 前綴欄位（沿用既有 `_tid`/`_uid`/`_notes` 慣例），標記改「存值」而非「比對推導」；OPKS 顯示碼依陣列位置連號重編、身分靠 `_id`；選單來源資訊由 `OptionItem.srcs` 提供（Material 3 supporting text 版面 + avatar-group「+N」hover）。後端 `build()` 改為遞迴剝除任何 `_` 開頭 key，履行 export 契約純淨。

**Tech Stack:** Next.js 16 / React 19 / TypeScript / @tanstack/react-query / cmdk / @radix-ui/react-popover（前端）；FastAPI / Pydantic v2 / pytest（後端）。

## Global Constraints

- **三層 binding tier**（spec §4）：🔒鎖定配對（基準代碼↔名稱、所屬類別三類）官方唯讀、要不同走「＋加自訂」；✏️自由值（工作描述、基準級別）自由改、不標記；📋在地清單（O/P/K/S、態度、說明）改即自訂、可排序、顯示碼依位置連號重編。
- **狀態只有兩種**：官方（`_src==="official"`，不標）/ 自訂（`_src==="custom"`，標「自訂」）。**無「已改」、無「重設回官方」**。
- **持久化**：`_id`/`_src`/`_ref` 存進 draft（PATCH），finalize/export 一律剝除。
- **來源僅在選單顯示**（版面 A：名稱下方淡灰小字 `{occupation_name} · {ocs_code}`；多來源 `… +N`，`+N` = 隱藏數，hover 看全部）；自訂項不進選單故無來源行。
- **UI 不變**：只在下拉選單列加文字 + hover；文件/表格版型不動。🔒 類別官方列改唯讀屬「行為變更非版型」。
- **O/P 原始來源碼**：後端本期不提供，O/P 來源行不含原始碼後綴（延後）。
- **前端驗證 gate（無單元 runner）**：每個前端任務以 `cd frontend && npx tsc --noEmit`（無錯）+ `npm run lint`（無錯）+ 指定手動檢查為準。**後端**用 `cd backend && .venv/Scripts/python -m pytest -q`。
- **DRY / YAGNI / 頻繁 commit。**

---

## File Structure

- `backend/app/services/ocs_doc.py` — `build()` 的前端欄位剝除改遞迴 helper `_strip_underscore`。
- `backend/tests/` — 新增 build() 遞迴剝除測試。
- `frontend/src/types/index.ts` — `SourceRef`；`CodeName`/`Indicator` 加 `_id`/`_src`/`_ref`；`OptionItem.srcs`。
- `frontend/src/lib/ocsDoc.ts` — `ensureIds` 擴及葉項目；位置序碼 helper；`setOp`/`setKS`/`setAttitudes`/`setCategory` 保留 meta + 連號重編。
- `frontend/src/lib/headerMeta.ts` — option 帶 `srcs`（由 `sources` + `primary_options` 組）。
- `frontend/src/components/interview/v3/fields/FieldCombobox.tsx` — 選單來源行 + 「+N」hover；`_src` 取代 `statusOf`；toggle/add/edit 寫 `_id`/`_src`/`_ref`。
- `frontend/src/components/interview/v3/CellFillerPanel.tsx` — 把任務來源（unit.source）灌進 O/P/K/S option 的 `srcs`。
- `frontend/src/components/interview/v3/DocHeader.tsx` — 🔒 類別官方列唯讀 + 來源行 + 自訂標記；基準代碼↔名稱 官方名稱唯讀。

---

## Task 1: 後端 build() 遞迴剝除任何 `_` 欄位

**Files:**
- Modify: `backend/app/services/ocs_doc.py:248-261`
- Test: `backend/tests/test_ocs_doc_strip.py`（新增；若已有對應測試檔則加 case）

**Interfaces:**
- Produces: `build()` 回傳的 dict 在任意深度不含以 `_` 開頭的 key。

- [ ] **Step 1: 先確認測試指令可跑**

Run: `cd backend && .venv/Scripts/python -m pytest -q`
Expected: 既有測試全綠（作為基線）。

- [ ] **Step 2: 寫失敗測試**

Create `backend/tests/test_ocs_doc_strip.py`:

```python
from app.services.ocs_doc import build


def _has_underscore_key(node) -> bool:
    if isinstance(node, dict):
        if any(k.startswith("_") for k in node):
            return True
        return any(_has_underscore_key(v) for v in node.values())
    if isinstance(node, list):
        return any(_has_underscore_key(v) for v in node)
    return False


def test_build_strips_underscore_keys_at_every_depth():
    doc = {
        "version_info": {"versions": []},
        "ocs_profile": {
            "ocs_code": "AAA-001",
            "ocs_name": {"occupation_name": "x"},
            "category": {
                "job_categories": [{"code": "J", "name": "n", "_id": "u1", "_src": "official"}],
                "occupations": [],
                "industries": [],
            },
        },
        "ocs_content": {
            "ocu_units": [
                {
                    "ocu_code": "T1",
                    "ocu_name": "u",
                    "_uid": "uu",
                    "tasks": [
                        {
                            "task_codes": [{"code": "T1.1", "name": "t"}],
                            "_tid": "tt",
                            "_notes": "raw",
                            "competency_blocks": [
                                {
                                    "competency_level": 1,
                                    "indicators": [{"code": "P1.1.1", "text": "p", "_id": "i1", "_src": "custom"}],
                                    "outputs": [{"code": "O1.1.1", "name": "o", "_id": "o1", "_ref": {"ocs_code": "X"}}],
                                    "knowledge": [{"code": "K01", "name": "k", "_id": "k1", "_src": "official"}],
                                    "skills": [],
                                }
                            ],
                        }
                    ],
                }
            ]
        },
        "ocs_attitude": {"attitudes": [{"code": "A01", "name": "a", "_id": "a1", "_src": "official"}]},
        "notes": {"prerequisites": [], "supplements": []},
        "_pool": {"junk": 1},
    }
    out = build(doc)
    assert not _has_underscore_key(out)
```

- [ ] **Step 3: 跑測試確認失敗**

Run: `cd backend && .venv/Scripts/python -m pytest backend/tests/test_ocs_doc_strip.py -q`
Expected: FAIL（`_id`/`_src`/`_ref` 仍殘留在葉層，`_has_underscore_key` 為 True）。

- [ ] **Step 4: 實作遞迴剝除**

在 `backend/app/services/ocs_doc.py` 把目前的逐一 pop 段落（約 248–259 行）：

```python
    doc.pop("_pool", None)
    for unit in units:
        if not isinstance(unit, dict):
            continue
        unit.pop("_uid", None)
        for task in unit.get("tasks") or []:
            if isinstance(task, dict):
                task.pop("_tid", None)
                task.pop("_notes", None)
```

替換為：

```python
    # Strip ALL front-end-only keys (any "_"-prefixed key, at any depth) →
    # contract-pure final JSON. Covers _pool/_uid/_tid/_notes (unit/task) and
    # _id/_src/_ref (leaf O/P/K/S, attitudes, categories) + any future _ field.
    _strip_underscore(doc)
```

並在模組層級（檔案靠近其他 helper 處）新增：

```python
def _strip_underscore(node) -> None:
    """Recursively remove any dict key starting with '_' (front-end-only fields)."""
    if isinstance(node, dict):
        for k in [k for k in node if k.startswith("_")]:
            node.pop(k, None)
        for v in node.values():
            _strip_underscore(v)
    elif isinstance(node, list):
        for v in node:
            _strip_underscore(v)
```

> 註：原本 `units` 區域變數若僅用於該段剝除可一併移除；若 `build()` 他處仍用到 `units` 則保留。

- [ ] **Step 5: 跑測試確認通過 + 全後端綠**

Run: `cd backend && .venv/Scripts/python -m pytest -q`
Expected: PASS（新測試通過，既有測試不回歸）。

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ocs_doc.py backend/tests/test_ocs_doc_strip.py
git commit -m "fix(be): build() recursively strips all _-prefixed front-end keys"
```

---

## Task 2: 型別 — SourceRef、葉項目 meta、OptionItem.srcs

**Files:**
- Modify: `frontend/src/types/index.ts:33-41`（`CodeName`/`Indicator`）、`219-223`（`OptionItem`）

**Interfaces:**
- Produces:
  - `SourceRef = { ocs_code: string; occupation_name: string; code: string }`
  - `CodeName`/`Indicator` 新增可選 `_id?: string; _src?: "official" | "custom"; _ref?: SourceRef`
  - `OptionItem` 新增可選 `srcs?: SourceRef[]`

- [ ] **Step 1: 加型別**

在 `frontend/src/types/index.ts` 把 `CodeName`/`Indicator` 改為：

```ts
export type ItemSource = "official" | "custom";

export interface SourceRef {
  ocs_code: string;        // 來源官方基準碼，如 INM3513-009v1
  occupation_name: string; // 來源職業名，如 AIoT應用工程師
  code: string;            // 該項在來源文件的原始碼（O1.1.1 / K01 / INM；O/P 暫為 ""）
}

export interface CodeName {
  code: string;
  name: string;
  _id?: string;            // 穩定 UUID：dnd/編輯 key + 排序錨點
  _src?: ItemSource;       // 來源；加入當下即定
  _ref?: SourceRef;        // 官方來源；改內容→清空（轉自訂）
}

export interface Indicator {
  code: string;
  text: string;
  _id?: string;
  _src?: ItemSource;
  _ref?: SourceRef;
}
```

並把 `OptionItem` 改為：

```ts
export interface OptionItem {
  code: string;
  name: string;
  sources?: string[];      // 既有：ocs_code 清單（向後相容）
  srcs?: SourceRef[];      // 新：完整來源（選單顯示用；首個 + 其餘）
}
```

- [ ] **Step 2: 型別檢查 + lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 無錯（新欄位皆可選，不破壞既有用法）。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(fe): add SourceRef + item provenance fields (_id/_src/_ref) + OptionItem.srcs"
```

---

## Task 3: ocsDoc — ensureIds 擴及葉項目 + 位置序碼 helper

**Files:**
- Modify: `frontend/src/lib/ocsDoc.ts:14-38`（`uid`/`ensureIds`）；於檔案 setter 區前新增 helper。

**Interfaces:**
- Consumes: `uid()`（既有）。
- Produces:
  - `ensureIds` 另外為 outputs/indicators/knowledge/skills、attitudes、category 三類缺 `_id` 者補 `_id`。
  - `positionalCode(prefix: string, idx: number): string` — 純字母前綴補零 2 位（`A`→`A01`）；含點/數字前綴不補零（`O1.1.`→`O1.1.1`）。
  - `renumberCoded(items: { code: string }[], prefix: string): void` — 依索引就地重寫 `code`。

- [ ] **Step 1: 加位置序碼 helper**

在 `frontend/src/lib/ocsDoc.ts`（`emptyTask` 之後、`ensureIds` 之前）新增：

```ts
// 位置序碼：字母前綴補零 2 位（A→A01）；含點/數字前綴不補零（O1.1.→O1.1.1）。
export function positionalCode(prefix: string, idx: number): string {
  const pad = /^[A-Za-z]+$/.test(prefix) ? 2 : 0;
  return `${prefix}${String(idx + 1).padStart(pad, "0")}`;
}

// 依陣列位置就地重寫每筆 code（身分由 _id 維持，故重編不影響來源/自訂判定）。
function renumberCoded<T extends { code: string }>(items: T[], prefix: string): void {
  items.forEach((it, i) => { it.code = positionalCode(prefix, i); });
}
```

- [ ] **Step 2: 擴充 ensureIds 到葉項目**

把 `ensureIds`（約 28–38 行）改為：

```ts
export function ensureIds(doc: OcsDocument | undefined): OcsDocument | undefined {
  if (!doc) return doc;
  const next = clone(doc);
  for (const u of next.ocs_content?.ocu_units ?? []) {
    if (!u._uid) u._uid = uid();
    for (const t of u.tasks ?? []) {
      if (!t._tid) t._tid = uid();
      const b = t.competency_blocks?.[0];
      if (b) {
        for (const arr of [b.outputs, b.indicators, b.knowledge, b.skills]) {
          for (const it of arr ?? []) if (!it._id) it._id = uid();
        }
      }
    }
  }
  for (const a of next.ocs_attitude?.attitudes ?? []) if (!a._id) a._id = uid();
  for (const kind of ["job_categories", "occupations", "industries"] as const) {
    for (const c of next.ocs_profile?.category?.[kind] ?? []) if (!c._id) c._id = uid();
  }
  return next;
}
```

- [ ] **Step 3: 型別檢查 + lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 無錯。

- [ ] **Step 4: 手動驗證 ensureIds**

啟動 `cd frontend && npm run dev`，開既有有任務的文件；在瀏覽器 console 不需操作，只需確認頁面照常載入、無 runtime error（`ensureIds` 在 `page.tsx` 已被呼叫，會在載入時補 `_id`）。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/ocsDoc.ts
git commit -m "feat(fe): ensureIds assigns _id to leaf items; add positional code helpers"
```

---

## Task 4: ocsDoc — setOp/setKS/setAttitudes/setCategory 保留 meta + 連號重編

**Files:**
- Modify: `frontend/src/lib/ocsDoc.ts`：`setCategory`（118-122）、`setOp`（291-303）、`setKS`（305-316）、`setAttitudes`（338-349）。

**Interfaces:**
- Consumes: `renumberCoded`、`positionalCode`（Task 3）。
- Produces：
  - `setCategory` 保留每筆的 `_id`/`_src`/`_ref`（不再只挑 code/name）。
  - `setOp` 對 outputs 重編 `O{task}.` 序、indicators 重編 `P{task}.` 序（task = 該任務 `task_codes[0].code` 去掉開頭 `T`）。
  - `setKS` 對 knowledge 重編 `K`、skills 重編 `S`。
  - `setAttitudes` 依陣列位置重編 `A`（移除原 code 排序，因位置序碼本身即遞增）。

- [ ] **Step 1: setCategory 保留 meta**

把 `setCategory`（118-122）改為：

```ts
export function setCategory(doc: OcsDocument, kind: CatKind, items: CodeName[]): OcsDocument {
  const next = clone(doc);
  next.ocs_profile.category[kind] = items.map((it) => ({
    code: it.code, name: it.name, _id: it._id, _src: it._src, _ref: it._ref,
  }));
  return next;
}
```

- [ ] **Step 2: setOp 連號重編**

把 `setOp`（291-303）改為：

```ts
export function setOp(
  doc: OcsDocument,
  unitIdx: number,
  taskIdx: number,
  outputs: CodeName[],
  indicators: Indicator[],
): OcsDocument {
  const next = clone(doc);
  const block = ensureBlock(next, unitIdx, taskIdx);
  const taskNum = (next.ocs_content.ocu_units[unitIdx].tasks[taskIdx].task_codes?.[0]?.code ?? "").replace(/^T/i, "");
  block.outputs = [...outputs];
  block.indicators = [...indicators];
  renumberCoded(block.outputs, `O${taskNum}.`);
  renumberCoded(block.indicators, `P${taskNum}.`);
  return next;
}
```

- [ ] **Step 3: setKS 連號重編**

把 `setKS`（305-316）改為：

```ts
export function setKS(
  doc: OcsDocument,
  unitIdx: number,
  taskIdx: number,
  field: "knowledge" | "skills",
  items: CodeName[],
): OcsDocument {
  const next = clone(doc);
  const block = ensureBlock(next, unitIdx, taskIdx);
  block[field] = [...items];
  renumberCoded(block[field], field === "knowledge" ? "K" : "S");
  return next;
}
```

- [ ] **Step 4: setAttitudes 連號重編（移除原排序）**

把 `setAttitudes`（338-349）改為：

```ts
export function setAttitudes(doc: OcsDocument, items: CodeName[]): OcsDocument {
  const next = clone(doc);
  const list = [...items];
  renumberCoded(list, "A"); // 位置序碼即遞增（A01、A02…）；身分由 _id 維持。
  next.ocs_attitude = { attitudes: list };
  return next;
}
```

- [ ] **Step 5: 型別檢查 + lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 無錯。

- [ ] **Step 6: 手動驗證連號**

`npm run dev`，進一個任務的 K：用選單選 2 筆官方 → 文件顯示 `K01`、`K02`；刪掉第一筆 → 剩的變 `K01`（連號重編生效）。態度同理顯示 `A01…`。

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/ocsDoc.ts
git commit -m "feat(fe): setters preserve item meta + renumber positional codes by array position"
```

---

## Task 5: headerMeta — option 帶 srcs（類別/態度）

**Files:**
- Modify: `frontend/src/lib/headerMeta.ts:3-12`

**Interfaces:**
- Consumes: `HeaderMeta`（`job_categories/occupations/industries/attitudes` 每筆有 `sources: string[]`；`primary_options` 有 `ocs_code`/`occupation_name`）。
- Produces: `categoryOptions`/`attitudeOptions` 回傳的 `OptionItem` 帶 `srcs: SourceRef[]`（每個 source ocs_code 解析出 occupation_name；`code` 用候選自身 code）。

- [ ] **Step 1: 加來源組裝**

把 `frontend/src/lib/headerMeta.ts` 開頭改為：

```ts
import type { HeaderMeta, HeaderMetaPrimaryOption, OptionItem, SourceRef } from "@/types";

function srcRefs(meta: HeaderMeta, sources: string[] | undefined, code: string): SourceRef[] {
  const nameByCode = new Map((meta.primary_options ?? []).map((o) => [o.ocs_code, o.occupation_name]));
  return (sources ?? []).map((oc) => ({ ocs_code: oc, occupation_name: nameByCode.get(oc) ?? "", code }));
}

export function categoryOptions(
  meta: HeaderMeta,
  kind: "job_categories" | "occupations" | "industries",
): OptionItem[] {
  return (meta[kind] ?? []).map((c) => ({
    code: c.code, name: c.name, sources: c.sources, srcs: srcRefs(meta, c.sources, c.code),
  }));
}

export function attitudeOptions(meta: HeaderMeta): OptionItem[] {
  return (meta.attitudes ?? []).map((a) => ({
    code: a.code, name: a.name, sources: a.sources, srcs: srcRefs(meta, a.sources, a.code),
  }));
}
```

（`noteOptions`/`primaryOptions` 不動。）

- [ ] **Step 2: 型別檢查 + lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 無錯。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/headerMeta.ts
git commit -m "feat(fe): headerMeta options carry SourceRef[] (occupation_name + ocs_code)"
```

---

## Task 6a: FieldCombobox — 選單來源行（版面 A）+「+N」hover

**Files:**
- Modify: `frontend/src/components/interview/v3/fields/FieldCombobox.tsx:79-96`（`toggleList`）

**Interfaces:**
- Consumes: `OptionItem.srcs`（Task 2/5）。
- Produces: 選單每列在名稱下方多一行來源；多來源顯示「首個 + +N」，`title` 屬性列出全部（hover native tooltip）。

- [ ] **Step 1: 加來源渲染 helper + 改 toggleList**

在 `FieldCombobox` 元件內、`toggleList` 定義前新增：

```tsx
  const srcLine = (o: OptionItem) => {
    const s = o.srcs ?? [];
    if (s.length === 0) return null;
    const first = s[0];
    const more = s.length - 1;
    const full = s.map((r) => `${r.occupation_name} ${r.ocs_code}`).join("\n");
    return (
      <div className="mt-0.5 text-[10px] text-muted-foreground" title={more > 0 ? full : undefined}>
        來源:{first.occupation_name} · {first.ocs_code}
        {more > 0 ? <span className="ml-1 rounded bg-muted px-1">+{more}</span> : null}
      </div>
    );
  };
```

把 `toggleList`（79-96）的每個 `CommandItem` 內容改成「名稱 + 來源行」兩行版（用 flex-col 容納次要行）：

```tsx
  const toggleList = (
    <CommandGroup>
      {options.map((o) => {
        const k = keyOf(o);
        return (
          <CommandItem key={k} value={`${o.code} ${o.name}`} onSelect={() => toggle(o)} className="items-start">
            <Check className={"mt-0.5 h-3.5 w-3.5 " + (sel.has(k) ? "opacity-100" : "opacity-0")} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1">
                {o.code ? <span className="font-mono text-xs text-muted-foreground">{o.code}</span> : null}
                <span className="flex-1">{o.name}</span>
              </div>
              {srcLine(o)}
            </div>
          </CommandItem>
        );
      })}
    </CommandGroup>
  );
```

> 移除原本的「已改」`<span>`（72-74 對應邏輯在此 toggleList，本步驟一併移除）與 `pillSources` 的「共N」分支（改由 `srcLine` 的「+N」取代）。

- [ ] **Step 2: 型別檢查 + lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 無錯。

- [ ] **Step 3: 手動驗證來源行**

`npm run dev`，開類別選單：每個官方候選名稱下出現「來源:職業名 · ocs_code」；若該候選來自多個職業，顯示「+N」且 hover 跳完整清單。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/interview/v3/fields/FieldCombobox.tsx
git commit -m "feat(fe): combobox dropdown shows source supporting line + +N hover (layout A)"
```

---

## Task 6b: FieldCombobox — `_src` 取代推導；toggle/add/edit 寫 `_id`/`_src`/`_ref`

**Files:**
- Modify: `frontend/src/components/interview/v3/fields/FieldCombobox.tsx`：`toggle`（42-46）、`addCustomFromQuery`（48-53）、`confirmFooterAdd`（66-72）、`statusOf`（140-144）、`selectedView` 的 list 編輯（147-167）。

**Interfaces:**
- Consumes: `crypto.randomUUID`、`OptionItem.srcs`。
- Produces: 加入官方 → item 帶 `_id`/`_src:"official"`/`_ref`（取 `srcs[0]` 或以 `{code,name}` fallback）；加自訂 → `_id`/`_src:"custom"`；就地改名 → `_src:"custom"`、清 `_ref`；`statusOf` 改讀 `_src`。

- [ ] **Step 1: 加 uid + 改 toggle/add 建構 meta**

在 `FieldCombobox.tsx` 檔案頂部 import 後新增：

```tsx
const newId = () => (globalThis.crypto?.randomUUID?.() ?? `id-${Math.random().toString(36).slice(2)}`);
```

把 `toggle`（42-46）改為：

```tsx
  const toggle = (opt: OptionItem) => {
    const k = keyOf(opt);
    if (sel.has(k)) { onCommit(value.filter((v) => keyOf(v) !== k)); return; }
    const ref = opt.srcs?.[0] ?? { ocs_code: "", occupation_name: "", code: opt.code };
    onCommit([...value, { code: opt.code, name: opt.name, _id: newId(), _src: "official", _ref: ref }]);
  };
```

把 `addCustomFromQuery`（48-53）改為（search 模式自訂）：

```tsx
  const addCustomFromQuery = () => {
    const n = query.trim();
    if (!n || value.some((v) => v.name === n)) { setQuery(""); return; }
    onCommit([...value, { code: "", name: n, _id: newId(), _src: "custom" }]);
    setQuery("");
  };
```

把 `confirmFooterAdd`（66-72）改為（footer 模式自訂）：

```tsx
  const confirmFooterAdd = () => {
    const n = cName.trim();
    if (!n) return;
    const code = autoCode ? nextCode(autoCode) : footerWithCode ? cCode.trim() : "";
    onCommit([...value, { code, name: n, _id: newId(), _src: "custom" }]);
    setCCode(""); setCName(""); setAdding(false);
  };
```

> `selectAllOfficial`（73-77）同步補 meta：把 push 物件改為 `{ code: o.code, name: o.name, _id: newId(), _src: "official", _ref: o.srcs?.[0] ?? { ocs_code: "", occupation_name: "", code: o.code } }`。

- [ ] **Step 2: statusOf 改讀 _src；list 編輯改名→轉自訂**

把 `statusOf`（140-144）改為：

```tsx
  const statusOf = (item: Item): "official" | "custom" => (item._src === "custom" ? "custom" : item._src === "official" ? "official" : "custom");
```

把 `selectedView` 的 list 分支（147-167）的 `FieldText onCommit` 改為「改名即轉自訂」：

```tsx
              <FieldText value={v.name} multiline={editMultiline}
                onCommit={(name) => onCommit(value.map((x, i) => (i === idx ? { ...x, name, _src: "custom", _ref: undefined } : x)))} />
```

並把該分支的標記改為只剩「自訂」（移除「已改」與 `officialNameOf` tooltip）：

```tsx
            {status === "custom" ? (
              <span className="mt-2 shrink-0 rounded bg-amber-100 px-1 text-[10px] text-amber-700" title="自訂項目">自訂</span>
            ) : null}
```

> 移除已不再使用的 `officialNameOf`（145）。

- [ ] **Step 3: 型別檢查 + lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 無錯（若 lint 報未使用變數，刪除對應 dead code）。

- [ ] **Step 4: 手動驗證「改即自訂」**

`npm run dev`，進一個任務的 K：選一筆官方（無標記）→ 在已選清單就地改它的名字 → 標記變「自訂」，且重開選單該官方項變回未勾選、可再選（再選後又出現一筆官方）。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/interview/v3/fields/FieldCombobox.tsx
git commit -m "feat(fe): combobox stores _id/_src/_ref; edit-official forks to custom; drop derived 已改"
```

---

## Task 7: CellFillerPanel — 把任務來源灌進 O/P/K/S option.srcs

**Files:**
- Modify: `frontend/src/components/interview/v3/CellFillerPanel.tsx`

**Interfaces:**
- Consumes: `useTaskCatalog`（既有）、`document.ocs_content.ocu_units[unitIdx].source`（`{ocs_code, occupation_name}`）。
- Produces: 傳給每個 `FieldCombobox` 的 `options` 帶 `srcs: [taskSource]`（單一來源＝該任務的來源職業；O/P 的 `code` 為 ""，K/S 用候選自身 code）。

- [ ] **Step 1: 組任務來源並附到 options**

在 `CellFillerPanel`（`const cat = useTaskCatalog(...)` 之後）新增：

```tsx
  const unitSrc = document.ocs_content?.ocu_units?.[unitIdx]?.source;
  const withSrc = (items: { code: string; name: string }[]) =>
    items.map((it) => ({
      ...it,
      srcs: [{ ocs_code: unitSrc?.ocs_code ?? "", occupation_name: unitSrc?.occupation_name ?? "", code: it.code }],
    }));
```

把四個 `FieldCombobox` 的 `options=` 包一層 `withSrc(...)`：
- K：`options={withSrc(cat.knowledge)}`
- S：`options={withSrc(cat.skills)}`
- O：`options={withSrc(cat.outputs)}`
- P：`options={withSrc(cat.indicators.map((i) => ({ code: i.code, name: i.text })))}`（P 原本已 map，包進 withSrc）

- [ ] **Step 2: 型別檢查 + lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 無錯。

- [ ] **Step 3: 手動驗證**

`npm run dev`，由「選任務」帶入一個官方任務後，點該任務的 K 格 → 選單候選名稱下出現「來源:該任務職業 · ocs_code」。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/interview/v3/CellFillerPanel.tsx
git commit -m "feat(fe): CellFiller attaches task source occupation to O/P/K/S options"
```

---

## Task 8: DocHeader — 🔒 類別官方列唯讀 + 來源行 + 自訂標記

**Files:**
- Modify: `frontend/src/components/interview/v3/DocHeader.tsx`：`CategoryPicker`（38-98）來源行；`catStatus`（152-158）改讀 `_src`；`Marker`（100-112）只剩自訂；類別列渲染（248-273）官方唯讀；`toggleOfficial`/`addCustom`（161-173）寫 meta。

**Interfaces:**
- Consumes: `OptionItem.srcs`、項目 `_src`/`_ref`。
- Produces: 官方類別列 name/code 顯示為唯讀文字（非輸入框）；自訂列維持可編輯 + 刪除 + 「自訂」標記；CategoryPicker 候選顯示來源行。

- [ ] **Step 1: catStatus 改讀 _src**

把 `catStatus`（152-158）改為：

```tsx
  const catStatus = (e: { _src?: "official" | "custom" }): "official" | "custom" =>
    e._src === "custom" ? "custom" : e._src === "official" ? "official" : "custom";
```

- [ ] **Step 2: Marker 只剩自訂**

把 `Marker`（100-112）改為：

```tsx
function Marker({ status }: { status: "official" | "custom" }) {
  if (status === "official") return null;
  return (
    <span className="shrink-0 rounded bg-amber-100 px-1 py-0.5 text-[10px] text-amber-700" title="自訂項目">自訂</span>
  );
}
```

- [ ] **Step 3: toggleOfficial/addCustom 寫 meta**

把 `toggleOfficial`/`addCustom`（161-173）改為：

```tsx
  const toggleOfficial = (kind: CatKind, o: OptionItem) => {
    const existing = p.category?.[kind] ?? [];
    if (existing.some((e) => ekey(e) === ekey(o)))
      onChange(setCategory(doc, kind, existing.filter((e) => ekey(e) !== ekey(o))));
    else {
      const ref = o.srcs?.[0] ?? { ocs_code: "", occupation_name: "", code: o.code };
      onChange(setCategory(doc, kind, [...existing, { code: o.code, name: o.name, _id: newId(), _src: "official", _ref: ref }]));
    }
  };
  const addCustom = (kind: CatKind, code: string, name: string) => {
    const existing = p.category?.[kind] ?? [];
    if (existing.some((e) => e.name === name && e.code === code)) return;
    onChange(setCategory(doc, kind, [...existing, { code, name, _id: newId(), _src: "custom" }]));
  };
```

在檔案頂部 import 後新增 `newId`：

```tsx
const newId = () => (globalThis.crypto?.randomUUID?.() ?? `id-${Math.random().toString(36).slice(2)}`);
```

- [ ] **Step 4: CategoryPicker 候選加來源行**

在 `CategoryPicker` 的 `CommandItem`（67-75）把內容改為兩行版（移除原「已改」span 72-74），並在名稱下加來源：

```tsx
                <CommandItem key={ekey(o)} value={`${o.code} ${o.name}`} onSelect={() => onToggle(o)} className="items-start">
                  <Check className={"mt-0.5 h-3.5 w-3.5 " + (has(o) ? "opacity-100" : "opacity-0")} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1">
                      {o.code ? <span className="font-mono text-xs text-muted-foreground">{o.code}</span> : null}
                      <span className="flex-1">{o.name}</span>
                    </div>
                    {(o.srcs?.length ?? 0) > 0 ? (
                      <div className="mt-0.5 text-[10px] text-muted-foreground"
                        title={o.srcs!.length > 1 ? o.srcs!.map((r) => `${r.occupation_name} ${r.ocs_code}`).join("\n") : undefined}>
                        來源:{o.srcs![0].occupation_name} · {o.srcs![0].ocs_code}
                        {o.srcs!.length > 1 ? <span className="ml-1 rounded bg-muted px-1">+{o.srcs!.length - 1}</span> : null}
                      </div>
                    ) : null}
                  </div>
                </CommandItem>
```

- [ ] **Step 5: 官方類別列改唯讀**

把類別列的名稱格（248-259）與代碼格（261-273）改為：官方列（`r.src === "official"`）顯示唯讀文字、自訂列維持 `FieldText` + 刪除。先讓 `catRows`（176-183）帶上 `_src`：

```tsx
    return rows.map((e, i) => ({
      ...k, idx: i, name: e.name, code: e.code, src: (e as CodeName)._src,
      real: i < entries.length, firstOfKind: i === 0, kindCount: rows.length,
    }));
```

名稱格（248-259）：

```tsx
            <td className={TD}>
              <div className="flex items-center gap-1.5">
                <div className="min-w-0 flex-1">
                  {r.real && r.src === "official" ? (
                    <span className="block px-1.5 py-1">{r.name}</span>
                  ) : (
                    <FieldText value={r.name} placeholder="名稱（可自訂）"
                      onCommit={(v) => onChange(upsertCategory(doc, r.key, r.idx, "name", v))} />
                  )}
                </div>
                {r.real ? <Marker status={catStatus({ _src: r.src })} /> : null}
              </div>
            </td>
```

代碼格（261-273）：

```tsx
            <td className={TD}>
              <div className="flex items-center gap-1">
                <div className="flex-1">
                  {r.real && r.src === "official" ? (
                    <span className="block px-1.5 py-1 font-mono">{r.code}</span>
                  ) : (
                    <FieldText value={r.code} placeholder="代碼"
                      onCommit={(v) => onChange(upsertCategory(doc, r.key, r.idx, "code", v))} />
                  )}
                </div>
                {r.real ? (
                  <button type="button" className="shrink-0 text-muted-foreground hover:text-destructive" title="刪除此列" onClick={() => onChange(deleteCategory(doc, r.key, r.idx))}>
                    <X className="h-3.5 w-3.5" />
                  </button>
                ) : null}
              </div>
            </td>
```

> `upsertCategory`（lib）會丟失 meta；但官方列已唯讀不會走 upsert，自訂列本就 `_src:"custom"`、`_ref` 不存在，故 upsert 後維持自訂（`catStatus` 視無 `_src` 為 custom）。為穩健，於 Task 4 之外不需改 upsertCategory。確認 import 仍含 `CodeName` 型別（檔頭 `import type { OcsDocument, OptionItem } ...` 需補 `CodeName`）。

- [ ] **Step 6: 型別檢查 + lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 無錯（移除任何未使用 import，如 `Marker` 原 `official` prop）。

- [ ] **Step 7: 手動驗證**

`npm run dev`：選官方類別 → 該列 name/code 為唯讀文字、無標記；按「＋加自訂」加一列 → 可編輯、標「自訂」、可刪；CategoryPicker 候選顯示來源行。

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/interview/v3/DocHeader.tsx
git commit -m "feat(fe): header categories lock official rows read-only + source line + custom marker"
```

---

## Task 9: DocHeader — 基準代碼↔名稱 官方名稱唯讀

**Files:**
- Modify: `frontend/src/components/interview/v3/DocHeader.tsx`：職類/職業名稱列（211-229）。

**Interfaces:**
- Consumes: `p.ocs_code`、`primaryOptions(meta)`。
- Produces: 當目前主基準 `ocs_code` 命中官方 `primary_options` 時，職類/職業名稱顯示唯讀（官方鎖定）；否則維持 `FieldText` 可編輯（自訂）。

- [ ] **Step 1: 加 isOfficialBasis 並條件唯讀**

在 `DocHeader` 內（`opts` 定義後）新增：

```tsx
  const isOfficialBasis = !!p.ocs_code && opts.some((o) => o.ocs_code === p.ocs_code);
```

把職類名稱格（218-221）改為：

```tsx
          <td className={TD} colSpan={3}>
            {isOfficialBasis ? (
              <span className="block px-1.5 py-1">{p.ocs_name?.job_category_name || "—"}</span>
            ) : (
              <FieldText value={p.ocs_name?.job_category_name ?? ""} placeholder="職類名稱"
                onCommit={(v) => onChange(setOcsName(doc, "job_category_name", v))} />
            )}
          </td>
```

把職業名稱格（225-228）改為：

```tsx
          <td className={TD} colSpan={3}>
            {isOfficialBasis ? (
              <span className="block px-1.5 py-1">{p.ocs_name?.occupation_name || "—"}</span>
            ) : (
              <FieldText value={p.ocs_name?.occupation_name ?? ""} placeholder="職業名稱"
                onCommit={(v) => onChange(setOcsName(doc, "occupation_name", v))} />
            )}
          </td>
```

- [ ] **Step 2: 型別檢查 + lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 無錯。

- [ ] **Step 3: 手動驗證**

`npm run dev`：用「職能基準代碼 ▾」選官方基準 → 職類/職業名稱變唯讀；若手動把 `ocs_code` 改成非官方（或無命中）→ 名稱恢復可編輯。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/interview/v3/DocHeader.tsx
git commit -m "feat(fe): lock 基準代碼↔名稱 occupation/category name read-only when official basis"
```

---

## Task 10: 整合驗證（draft 往返 + export 剝除）

**Files:**
- 無新增；端到端驗證 + 全 gate。

- [ ] **Step 1: 全前端 gate**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: 無錯。

- [ ] **Step 2: 全後端 gate**

Run: `cd backend && .venv/Scripts/python -m pytest -q`
Expected: 全綠。

- [ ] **Step 3: 端到端手動流程**

`npm run dev` + 後端啟動，開一份文件：
1. 選官方類別/態度/O/P/K/S → 皆無標記、選單顯示來源行。
2. 就地改一筆官方 K 名稱 → 標「自訂」、選單該官方變未勾選、可重選。
3. K 連號（K01、K02…）、刪除後重編。
4. **重載頁面** → 上述 `_src`/自訂狀態、`_id` 維持（draft 持久化）。
5. 「匯出 JSON」→ 下載檔**不含任何 `_id`/`_src`/`_ref`/`_tid` 等 `_` 欄位**。
6. 「產生正式版本」→ finalize 成功、正式版同樣無 `_` 欄位。

- [ ] **Step 4: Commit（若有收尾微調）**

```bash
git add -A
git commit -m "chore(fe): provenance/lock-tiers integration polish"
```

---

## Self-Review（對照 spec）

- **§3 資料模型** → Task 2（型別）、Task 3（`_id` 補齊）、Task 6b/8（建構 `_src`/`_ref`）。✓
- **§4 三層 tier** → 🔒 Task 8（類別唯讀）+ Task 9（基準名稱唯讀）；✏️ 自由值（工作描述/級別）本就 `FieldText` 不標記、無需改；📋 Task 4（連號）+ Task 6b（改即自訂）。✓
- **§5 兩態標記** → Task 6b（statusOf 讀 _src）、Task 8（Marker 只剩自訂）。✓
- **§6 OPKS 流程/兩套碼** → Task 4（文件位置碼）、Task 6a（選單來源原始碼顯示）、Task 6b（改即自訂、官方可重選）。✓
- **§7 來源顯示版面 A + +N hover** → Task 5（資料）、Task 6a（FieldCombobox）、Task 7（CellFiller 來源）、Task 8（CategoryPicker）。✓
- **§8 持久化 + export 剝除** → Task 1（後端遞迴剝除）、Task 10（往返驗證）。✓
- **§9 UI 不變 / 行為變更** → 僅選單加文字 + 類別/名稱唯讀；無版型改動。✓
- **延後項（O/P 原始碼後綴）** → 未納入（Task 7 的 O/P `code` 為 ""，來源行不含原始碼，符合 spec）。✓

> 備註（與 spec §3 的小精化）：多來源清單放在 `OptionItem.srcs`（選單用），文件項 `_ref` 為單一 `SourceRef`（選中當下的首要來源）。spec 原將多來源寫成 `SourceRef.sources?`，實作改置於 `OptionItem.srcs` 較不自我遞迴，語意等價。
