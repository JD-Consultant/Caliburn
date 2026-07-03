# 知識包 P3:多池選單(web 三面逐切 pack)+ A4 文件級 K/S 重編 + 舊端點退役

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** web 所有選單改吃知識包(ADR 0021 唯一同步點落地):填格 O/P/K/S/L 五選單、職責/任務遞迴兩選單(前端寫入取代 buildTasks)、表頭(類別/態度/notes/主基準/描述/基準級別)——全部大池+借用+預勾+自動勾選+序號顯示+每列引用行;A4 文件級 K/S 重編(ocs-schema 同名共碼);切完退役三個舊投影端點 + buildTasks。

**Architecture:** 資料只從 `useKnowledge`(`["knowledge", id]`,P2 已上)讀;選項組裝住 **`web/src/lib/pack.ts` 純函式**(池 → OptionItem,srcs → `_ref`,own-first 重排);寫入一律走既有「前端文件編輯 + autosave PATCH」單一路徑(spec 資料流決策①)。api 端只刪不加。設計全文=spec [`2026-07-03-editor-provenance-knowledge-pack-decisions.md`](../specs/2026-07-03-editor-provenance-knowledge-pack-decisions.md) §2/§4(A4)/§5 + ADR 0021。

**Tech Stack:** web:Next.js 16 + TanStack Query v5 + cmdk/shadcn(三道 gate:`npx tsc --noEmit` / `npm run lint` / `npm run build`)。api:FastAPI + pytest(`TEST_DATABASE_URL`)。

## Global Constraints

- 繁體中文回應;commit 用英文 conventional commits。**一 task 一 commit、綠了才 commit、不要 push**。green-before == green-after(api 現 175 passed;web 三道綠)。
- **文檔同 commit 更新**:動哪面 → 同 commit 修 `apps/web/README.md` 對應行;動端點 → `apps/api/README.md`。
- **選單顯示(W1 定稿)**:池選項**無碼 → 顯序號 `1. 2. 3.`**;類別選單例外顯真實國家分類碼;每列必有引用行(SourceLine);**無搜尋、無排序**(池 append 序原樣)。
- **預勾統一規則**:預設=該實體「自己的」官方集合(填格=任務 o/p/k/s_refs 聯集;職責=主基準(順序1)來源的職責列 + 其任務);初次(空格開面板)自動套用 + 「**自動勾選**」按鈕重套(「帶官方」改名);之後以使用者動過的為準(文件是真相)。
- **`_ref` 選取規則**:池列 srcs 依 append 序;開「任務 X 的選單」時,X 自己的來源**穩定重排到首位**(選用/預勾的 `_ref` 與引用行首行都對到 X);借用列 `_ref` = srcs[0]。
- **A4(ocs-schema)**:K/S 碼=文件層級,name 為 key、首現給號、**同名共碼**;O/P 維持任務範圍、A 維持全域。代碼共用、身分(`_id`/`_ref`)各自。
- 名字不做正規化(key=原始字串);防呆去重先不做;`meta.partial` UI 提示不做(維護者:不用過度設計)。
- **不在本 plan**(→ Plan UX):素材庫模式(工作描述/NOTE 點一下即加,A3)、表頭 ✕/toggle-off/清空手打、級別再點取消。
- api 退役**只刪殼不刪共用**:`task_detail.task_competencies` 為 ai.py + authoring 共用,**必留**;刪任何 symbol 前先 grep 零引用。

## File Structure

- `apps/web/src/lib/pack.ts` — 新:池 → 選單選項純函式層(唯一 pack 讀取邏輯集中點)。
- `apps/web/src/lib/ocsDoc.ts` — A4 `renumberDocKS` + 批次入文件 `addFromPool`。
- `apps/web/src/lib/urn.ts` — 補 `taskUrns`(多來源任務)。
- `apps/web/src/types/index.ts` — `OcsTask._refs` / `OcuUnit._refs`(UI-only 多來源)。
- `apps/web/src/components/interview/fields/FieldCombobox.tsx` — 序號、any-src 勾選判定、自動勾選(defaults)。
- `apps/web/src/components/interview/CellFillerPanel.tsx`、`JobDocTable.tsx`(TaskRow L 選單+AttitudeBlock)、`TaskCuratePanel.tsx`(重寫)、`DocHeader.tsx`、`DocNotes.tsx`、`app/documents/[id]/page.tsx` — 消費面。
- 退役:web `hooks/useTaskCatalog.ts`(整檔)、`hooks/useDocument.ts`(useHeaderMeta/useTaskCandidates/useBuildTasks)、`lib/headerMeta.ts`(整檔)、`lib/api.ts`/`types/index.ts` 對應項、`Providers.tsx`(buster);api `routes/documents.py` 4 路由、`core/domain/header_meta.py`(整檔)、`ocs_doc.build_from_picked`、對應測試。

---

### Task 1: A4 — 文件級 K/S 重編(同名共碼)

**Files:** Modify `apps/web/src/lib/ocsDoc.ts`

**Interfaces:**
- Produces:`renumberDocKS(doc): void`(module-private,由 `renumber()` 與 `setKS()` 呼叫);`setKS` 簽名不變。

- [ ] **Step 1: 實作 `renumberDocKS` 並接線**

在 `renumberCoded` 之後加(`renumberCoded` 仍供 O/P/A 用):

```typescript
// A4(ocs-schema「文件層級去重」):K/S 碼以 name 為 key 全文件共用——首現給號、
// 同名共碼、空名各給新號;身分仍看 _id/_ref(碼共用、身分各自)。O/P 維持任務範圍、
// A 維持全域(renumberCoded)。任何 K/S 內容變動與結構變動(renumber)都要重跑。
function renumberDocKS(doc: OcsDocument): void {
  for (const [field, prefix] of [["knowledge", "K"], ["skills", "S"]] as const) {
    const codeByName = new Map<string, string>();
    let n = 0;
    for (const u of doc.ocs_content?.ocu_units ?? []) {
      for (const t of u.tasks ?? []) {
        for (const it of t.competency_blocks?.[0]?.[field] ?? []) {
          let code = it.name ? codeByName.get(it.name) : undefined;
          if (!code) {
            code = positionalCode(prefix, n++);
            if (it.name) codeByName.set(it.name, code);
          }
          it.code = code;
        }
      }
    }
  }
}
```

`renumber()` 尾端(`return doc;` 前)加一行:`renumberDocKS(doc);`

`setKS()` 把 `renumberCoded(block[field], field === "knowledge" ? "K" : "S");` 換成:`renumberDocKS(next);`

- [ ] **Step 2: 三道綠**:`cd apps/web && npx tsc --noEmit && npm run lint && npm run build`。
- [ ] **Step 3: 手動驗證**(dev):兩個任務各加同名 K「統計」→ 兩處顯示同一個碼(如 K01);刪掉首現那筆 → 另一筆遞補為首現、全文件重編不斷號。
- [ ] **Step 4: Commit**

```bash
git add apps/web/src/lib/ocsDoc.ts
git commit -m "fix(web): document-level K/S renumbering - same name shares code per ocs-schema [A4]"
```

---

### Task 2: `lib/pack.ts` 選項層 + `taskUrns` + `_refs` 型別

**Files:** Create `apps/web/src/lib/pack.ts`;Modify `apps/web/src/lib/urn.ts`、`apps/web/src/types/index.ts`

**Interfaces(後續全部 task 依賴,名稱照抄):**
- `packSrcToRef(s: PackSrc): SourceRef`
- `valuePoolOptions(pool, ownPairs?): OptionItem[]`(K/S/O/P/態度/notes;code=""→ 選單顯序號)
- `codedPoolOptions(pool): OptionItem[]`(三類;code=分類碼)
- `toItems(options): CodeName[]`(選項 → 官方文件項,`_ref`=srcs[0])
- `taskUrns(task: OcsTask): string[]`(urn.ts;`_refs` 全列,fallback 單 provenance)
- `ownTaskRefs(pack, urns): { k, s, o, p: string[]; level: number | null; levelSrc: SourceRef | null; pairs: {ocs_code, task_code}[] }`
- `unitRows(pack): UnitRowVM[]`、`taskRows(pack): TaskRowVM[]`、`primaryBasisOptions(pack): BasisOption[]`

- [ ] **Step 1: 型別**(`types/index.ts`)

`OcsTask` 加一欄(`_levelSrc` 下方):
```typescript
  _refs?: SourceRef[]; // 多來源(合併列選入):全部來源;provenance 取首個(相容單來源讀者)
```
`OcuUnit` 加一欄(`_uid` 上方):
```typescript
  _refs?: SourceRef[]; // 多來源(合併職責列選入)
```

- [ ] **Step 2: `urn.ts` 加 `taskUrns`**

```typescript
// 任務的全部身分 URN:合併列選入的任務 _refs 多筆;舊資料/單來源 fallback provenance。
export function taskUrns(task: {
  provenance?: { ocs_code?: string; task_code?: string };
  _refs?: { ocs_code: string; task_code?: string }[];
}): string[] {
  const refs = task._refs?.length ? task._refs : task.provenance ? [task.provenance] : [];
  const out: string[] = [];
  for (const r of refs) {
    const u = taskUrn({ ocs_code: r.ocs_code, task_code: r.task_code });
    if (u && !out.includes(u)) out.push(u);
  }
  return out;
}
```

- [ ] **Step 3: `lib/pack.ts`**(整檔新建)

```typescript
// 知識包 → 選單選項(ADR 0021;spec §5)。唯一的 pack 讀取邏輯集中點,全部純函式。
// 池序=append 序(職位優先序),選單不排序不搜尋;選項無碼 → FieldCombobox 顯序號。
import type {
  CodeName, KnowledgePack, OptionItem, PackSrc, PoolRow, SourceRef,
} from "@/types";

const newId = () => (globalThis.crypto?.randomUUID?.() ?? `id-${Math.random().toString(36).slice(2)}`);

export function packSrcToRef(s: PackSrc): SourceRef {
  return {
    ocs_code: s.ocs_code,
    occupation_name: s.ocs_name,
    code: s.code ?? "",
    task_code: s.task_code ?? undefined,
    task_name: s.task_name ?? undefined,
  };
}

// 值池(K/S/O/P/態度/notes)→ 選項。ownPairs 給了 → 該列若含「自己的來源」
// (ocs_code+task_code 命中),把它穩定重排到 srcs 首位:_ref 與引用行首行都對到本任務。
export function valuePoolOptions(
  pool: Record<string, PoolRow>,
  ownPairs?: { ocs_code: string; task_code: string }[],
): OptionItem[] {
  return Object.entries(pool).map(([name, row]) => {
    let srcs = row.srcs.map(packSrcToRef);
    if (ownPairs?.length) {
      const i = row.srcs.findIndex((s) =>
        ownPairs.some((p) => p.ocs_code === s.ocs_code && p.task_code === (s.task_code ?? "")));
      if (i > 0) srcs = [srcs[i], ...srcs.slice(0, i), ...srcs.slice(i + 1)];
    }
    return { code: "", name, srcs };
  });
}

// 三類池(職類別/職業別/行業別):key=國家分類碼(選單例外顯真實碼)。
export function codedPoolOptions(
  pool: Record<string, { name: string; srcs: PackSrc[] }>,
): OptionItem[] {
  return Object.entries(pool).map(([code, row]) => ({
    code,
    name: row.name,
    srcs: row.srcs.map((s) => ({ ...packSrcToRef(s), code })),
  }));
}

// 選項 → 官方文件項(勾選/預勾共用形狀;_ref = srcs[0],即 own-first 重排後的本任務來源)。
export function toItems(options: OptionItem[]): CodeName[] {
  return options.map((o) => ({
    code: o.code, name: o.name, _id: newId(), _src: "official" as const,
    _ref: o.srcs?.[0] ?? { ocs_code: "", occupation_name: "", code: o.code },
  }));
}

// 任務自己的官方配套(聯集,照 urns 順序;level 衝突取第一個非空 = 順序 1 優先)。
export function ownTaskRefs(pack: KnowledgePack, urns: string[]): {
  k: string[]; s: string[]; o: string[]; p: string[];
  level: number | null; levelSrc: SourceRef | null;
  pairs: { ocs_code: string; task_code: string }[];
} {
  const acc = { k: [] as string[], s: [] as string[], o: [] as string[], p: [] as string[] };
  let level: number | null = null;
  let levelSrc: SourceRef | null = null;
  const pairs: { ocs_code: string; task_code: string }[] = [];
  for (const urn of urns) {
    const st = pack.source_tasks[urn];
    if (!st) continue;
    pairs.push({ ocs_code: st.ocs_code, task_code: st.task_code });
    for (const [field, refs] of [["k", st.k_refs], ["s", st.s_refs], ["o", st.o_refs], ["p", st.p_refs]] as const) {
      for (const key of refs) if (!acc[field].includes(key)) acc[field].push(key);
    }
    if (level === null && st.competency_level !== null) {
      level = st.competency_level;
      levelSrc = {
        ocs_code: st.ocs_code, occupation_name: st.ocs_name, code: "",
        task_code: st.task_code, task_name: st.task_name,
      };
    }
  }
  return { ...acc, level, levelSrc, pairs };
}

// ── 職責/任務兩選單(TaskCuratePanel)──────────────────────────────────────────
export interface UnitRowVM {
  name: string;                 // units 池 key
  srcs: SourceRef[];            // 來源職責(每來源含 ocu_code)
  ownTaskKeys: string[];        // 該職責官方帶的任務(合併列=聯集;值=tasks 池 key)
}
export interface TaskRowVM {
  name: string;                 // tasks 池 key
  urns: string[];               // 池列 srcs(source_tasks 的 URN)
  srcs: SourceRef[];            // 顯示用(URN → source_tasks 解出)
}

export function unitRows(pack: KnowledgePack): UnitRowVM[] {
  return Object.entries(pack.pools.units).map(([name, row]) => {
    const pairSet = new Set(row.srcs.map((s) => `${s.ocs_code}__${s.ocu_code ?? ""}`));
    const ownTaskKeys: string[] = [];
    for (const st of Object.values(pack.source_tasks)) {
      if (!pairSet.has(`${st.ocs_code}__${st.ocu_code ?? ""}`)) continue;
      if (st.task_name && !ownTaskKeys.includes(st.task_name)) ownTaskKeys.push(st.task_name);
    }
    return { name, srcs: row.srcs.map(packSrcToRef), ownTaskKeys };
  });
}

export function taskRows(pack: KnowledgePack): TaskRowVM[] {
  return Object.entries(pack.pools.tasks).map(([name, row]) => ({
    name,
    urns: row.srcs,
    srcs: row.srcs.flatMap((urn) => {
      const st = pack.source_tasks[urn];
      return st ? [{
        ocs_code: st.ocs_code, occupation_name: st.ocs_name, code: st.task_code,
        task_code: st.task_code, task_name: st.task_name,
      }] : [];
    }),
  }));
}

// ── 表頭(DocHeader)────────────────────────────────────────────────────────────
export interface BasisOption {
  ocs_code: string;
  occupation_name: string;
  job_category_name: string;
  job_description: string;
  ocs_level: number | null;
}

export function primaryBasisOptions(pack: KnowledgePack): BasisOption[] {
  return pack.occupation_details.map((d) => ({
    ocs_code: d.ocs_code,
    occupation_name: d.ocs_name.occupation_name ?? "",
    job_category_name: d.ocs_name.job_category_name ?? "",
    job_description: d.job_description,
    ocs_level: d.ocs_level,
  }));
}
```

- [ ] **Step 4: 三道綠**(pure 新增,無消費者也要過 lint 的 no-unused?——`lib/` export 不觸發;過就好)。
- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/pack.ts apps/web/src/lib/urn.ts apps/web/src/types/index.ts
git commit -m "feat(web): pack option layer - pool->menu options, own-first srcs, task urns [ADR 0021]"
```

---

### Task 3: FieldCombobox — 序號顯示 + any-src 勾選判定 + 「自動勾選」

**Files:** Modify `apps/web/src/components/interview/fields/FieldCombobox.tsx`

**Interfaces:**
- Produces:new prop `defaults?: OptionItem[]`(自動勾選的目標集;未給 = 全部 options,即既有「帶官方」行為);按鈕文案「帶官方」→「自動勾選」。

- [ ] **Step 1: 勾選判定改 any-src**(取代現 `officialMatch`;池的合併列 srcs 多筆、own-first 重排後 srcs[0] 未必是 `_ref` 那筆,必須掃全部)

```typescript
  // 勾選判定(DDD 實體 vs 值物件):選項帶來源身分(srcs 任一 {ocs_code, code} 命中 _ref)
  // → 官方同物;無 code 來源(值物件,如說明事項)→ 比 name。改過內容 _src=custom → 未勾選。
  const officialMatch = (v: Item, o: OptionItem) => {
    const coded = (o.srcs ?? []).filter((s) => s.code);
    if (coded.length > 0 || o.code) {
      if (v._ref && coded.some((s) => s.code === v._ref!.code && s.ocs_code === v._ref!.ocs_code)) return true;
      if (!coded.length && o.code) return v._ref?.code === o.code; // 無 srcs 的舊路徑(自訂候選)
      return false;
    }
    return v.name === o.name;
  };
```

- [ ] **Step 2: 序號顯示**(`toggleList` 的 map 加 index;碼空 → `i+1.`)

```typescript
      {options.map((o, i) => {
        const k = keyOf(o) || `name:${o.name}`;
        return (
          <CommandItem key={k} value={`${o.code} ${o.name}`} onSelect={() => toggle(o)} className="items-start">
            <Check className={"mt-0.5 h-3.5 w-3.5 " + (isOfficialSelected(o) ? "opacity-100" : "opacity-0")} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1">
                <span className="font-mono text-xs text-muted-foreground">{o.code || `${i + 1}.`}</span>
                <span className="flex-1">{o.name}</span>
              </div>
              <SourceLine srcs={o.srcs} />
            </div>
          </CommandItem>
        );
      })}
```

- [ ] **Step 3: `selectAllOfficial` → `applyDefaults` + prop**

props 加 `defaults`(型別 `OptionItem[]`,optional,JSDoc:「自動勾選的目標集(該實體自己的官方配套);未給=全部 options」);實作:

```typescript
  const applyDefaults = () => {
    const next = [...value];
    for (const o of defaults ?? options) {
      if (next.some((v) => v._src === "official" && officialMatch(v, o))) continue;
      const ref: SourceRef = o.srcs?.[0] ?? { ocs_code: "", occupation_name: "", code: o.code };
      next.push({ code: o.code, name: o.name, _id: newId(), _src: "official", _ref: ref });
    }
    onCommit(next);
  };
```

兩處按鈕(`title` 模式與預設模式)`onClick={selectAllOfficial}` → `onClick={applyDefaults}`,文案「帶官方」→「**自動勾選**」。

- [ ] **Step 4: 三道綠 + 手動確認既有面未壞**(表頭類別選單仍顯分類碼、態度選單可勾)。
- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/interview/fields/FieldCombobox.tsx
git commit -m "feat(web): combobox ordinal display, any-src official match, auto-check defaults [W1]"
```

---

### Task 4: 填格五選單(O/P/K/S/L)→ pack(含 B4 `_levelSrc` 接線)

**Files:** Modify `apps/web/src/components/interview/CellFillerPanel.tsx`、`apps/web/src/components/interview/JobDocTable.tsx`、`apps/web/src/app/documents/[id]/page.tsx`、`apps/web/README.md`

**Interfaces:**
- Consumes:`useKnowledge(profileId, enabled)`、`taskUrns`、`ownTaskRefs`、`valuePoolOptions`、`toItems`、FieldCombobox `defaults`。
- Produces:CellFillerPanel props 不變;TaskRow 增 `pack?: KnowledgePack` prop(JobDocTable 傳入)。

- [ ] **Step 1: CellFillerPanel 改讀 pack**

整段替換資料來源(移除 `useTaskCatalog`/`withSrc`/`taskKey`;`urn` 改 `taskUrns`):

```typescript
"use client";

// D13 CellFiller:per-cell FieldCombobox。選項=知識包大池(全部,可借用;ADR 0021),
// 預勾=任務自己的官方配套(o/p/k/s_refs 聯集):空格開面板自動套用、「自動勾選」鈕重套。
// 每格點選即 onSave(nextDoc),無存檔鈕。
import { useEffect, useRef } from "react";
import type { OcsDocument } from "@/types";
import { getBlock, setKS, setOp } from "@/lib/ocsDoc";
import { taskUrns } from "@/lib/urn";
import { ownTaskRefs, toItems, valuePoolOptions } from "@/lib/pack";
import { useKnowledge } from "@/hooks/useKnowledge";
import { FieldCombobox } from "./fields/FieldCombobox";
import type { CellTarget } from "./JobDocTable";
import { X } from "lucide-react";
```

主體(`unitIdx/taskIdx/block/tn/title/taskNum` 邏輯保留,其餘換):

```typescript
  const task = document.ocs_content?.ocu_units?.[unitIdx]?.tasks?.[taskIdx];
  const urns = taskUrns(task ?? {});
  const { data: pack, isLoading } = useKnowledge(profileId, true);
  const own = pack ? ownTaskRefs(pack, urns) : null;

  // 各池選項(own-first 重排:_ref 與引用行對到本任務);預設集=own refs 命中的列。
  const pools = pack?.pools;
  const optionsFor = (kind: CellTarget["kind"]) => {
    if (!pools || !own) return { options: [], defaults: [] };
    const pool = { o: pools.outputs, p: pools.indicators, k: pools.knowledge, s: pools.skills }[kind];
    const ownKeys = new Set({ o: own.o, p: own.p, k: own.k, s: own.s }[kind]);
    const options = valuePoolOptions(pool, own.pairs);
    return { options, defaults: options.filter((op) => ownKeys.has(op.name)) };
  };
```

初次預勾(spec:「初次/按自動勾選時套用,之後以使用者動過的為準」——空格開面板即套用一次;
`applied` ref 防 StrictMode 雙跑):

```typescript
  const applied = useRef(false);
  useEffect(() => {
    if (applied.current || !pack || !block) return;
    const { defaults } = optionsFor(target.kind);
    if (defaults.length === 0) return;
    const empty = {
      o: (block.outputs?.length ?? 0) === 0, p: (block.indicators?.length ?? 0) === 0,
      k: (block.knowledge?.length ?? 0) === 0, s: (block.skills?.length ?? 0) === 0,
    }[target.kind];
    if (!empty) { applied.current = true; return; }
    applied.current = true;
    const items = toItems(defaults);
    if (target.kind === "k") onSave(setKS(document, unitIdx, taskIdx, "knowledge", items));
    else if (target.kind === "s") onSave(setKS(document, unitIdx, taskIdx, "skills", items));
    else if (target.kind === "o") onSave(setOp(document, unitIdx, taskIdx, items, block.indicators ?? []));
    else onSave(setOp(document, unitIdx, taskIdx, block.outputs ?? [],
      items.map((i) => ({ code: i.code, text: i.name, _id: i._id, _src: i._src, _ref: i._ref }))));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pack]);
```

四個分支的 `options={withSrc(...)}` 換 `options={optionsFor("k").options}`、加 `defaults={optionsFor("k").defaults}`(o/p/s 同理;P 分支 options 已是 {code:"",name,srcs} 形狀,原本的 `cat.indicators.map` 轉換刪除);`cat.isLoading` → `isLoading`。

- [ ] **Step 2: TaskRow 級別選單 → pack + B4**

JobDocTable:刪 `useTaskLevel`/`taskUrn`/`useHeaderMeta` 的 level 相關 import(`useHeaderMeta` 本 task 只動 TaskRow,AttitudeBlock 留給 Task 6);`JobDocTable` 主體加 `const { data: pack } = useKnowledge(profileId, true);` 並把 `pack` 傳給每個 `UnitRow → TaskRow`。TaskRow 內:

```typescript
  // 級別:官方值來自知識包 source_tasks(聯集取第一個非空=順序1);選中官方值 → 存 _levelSrc(B4)。
  const own = pack ? ownTaskRefs(pack, taskUrns(task)) : null;
  const officialLevel = own?.level ?? task._levelSrc?.level ?? null;
  const levelSrc = own?.levelSrc ?? null;
```

(刪 `levelOpen` state 與 `onOpenChange`、刪原 `fetchedLevel`/手組 `levelSrc`。)OfficialMenu:

```typescript
          options={[1, 2, 3, 4, 5, 6].map((n) => ({
            value: String(n),
            label: `級別 ${n}`,
            srcs: officialLevel === n && levelSrc ? [levelSrc] : [],
          }))}
          selected={level != null ? String(level) : ""}
          onPick={(v) => onChange(setTaskLevel(doc, unitIdx, taskIdx, v,
            officialLevel != null && Number(v) === officialLevel && levelSrc
              ? { ...levelSrc, level: officialLevel } : undefined))}
```

- [ ] **Step 3: 拆掉批次 seeding 掛載**:`app/documents/[id]/page.tsx` 移除 `useTaskCatalogs` import 與 `useTaskCatalogs(id, taskCount > 0);` 呼叫(hook 本體 Task 7 刪)。
- [ ] **Step 4: 三道綠。**
- [ ] **Step 5: 手動驗證**(dev,選過職類的文件):開任一任務 K 格 → 選單=全 K 池(跨職類可借用)、序號 1.2.3.、每列引用行;空格首開自動帶入該任務官方 K;「自動勾選」鈕只補自己的;級別下拉官方值帶引用行,選官方值後 PATCH 的 doc 內任務含 `_levelSrc`。
- [ ] **Step 6: 同 commit 更新 `apps/web/README.md`**:「關鍵流程 4. 填格」改寫(useTaskCatalog → 知識包大池+預勾+借用);query 表 task-catalogs 列註「填格已改吃 knowledge(Task 7 退役)」。
- [ ] **Step 7: Commit**

```bash
git add apps/web/src/components/interview/CellFillerPanel.tsx apps/web/src/components/interview/JobDocTable.tsx apps/web/src/app/documents/[id]/page.tsx apps/web/README.md
git commit -m "feat(web): cell filler + task level menus read knowledge pack - big pools, borrow, pre-check, _levelSrc [ADR 0021, B4]"
```

---

### Task 5: TaskCuratePanel → 職責/任務遞迴兩選單 + 前端寫入(buildTasks 退場準備)

**Files:** Modify `apps/web/src/components/interview/TaskCuratePanel.tsx`(重寫)、`apps/web/src/lib/ocsDoc.ts`(`addFromPool`)、`apps/web/src/app/documents/[id]/page.tsx`(props 接線)、`apps/web/README.md`

**Interfaces:**
- Consumes:`unitRows`/`taskRows`/`packSrcToRef`(Task 2)、`useKnowledge`。
- Produces:`addFromPool(doc, picks: PoolPick[]): OcsDocument`(ocsDoc);TaskCuratePanel props:`{ profileId, currentDoc, intake?, autoExtract?, onApply: (d: OcsDocument) => void, onClose, onError }`(**`onApply` 新增**,取代內部 `useBuildTasks`)。

- [ ] **Step 1: `ocsDoc.ts` 加 `addFromPool`**

```typescript
// ── 批次入文件(P3 前端寫入路徑;spec 資料流決策①:單一寫入路徑=前端編輯+PATCH)──
// 職責以 ocu_name 併入既有列(同 key 不重建),任務 append;provenance=首個來源、
// _refs=全部來源(合併列雙來源引用);最後 renumber(位置碼 + A4 文件級 K/S)。
export interface PoolPick {
  unit: { name: string; srcs: SourceRef[] };
  tasks: { name: string; srcs: SourceRef[]; provenance: { ocs_code: string; task_code: string } }[];
}

export function addFromPool(doc: OcsDocument, picks: PoolPick[]): OcsDocument {
  const next = clone(doc);
  for (const pick of picks) {
    let unit = next.ocs_content.ocu_units.find((u) => u.ocu_name === pick.unit.name);
    if (!unit) {
      const first = pick.unit.srcs[0];
      unit = {
        ocu_code: "",
        ocu_name: pick.unit.name,
        source: { ocs_code: first?.ocs_code ?? "", occupation_name: first?.occupation_name ?? "" },
        tasks: [],
        _uid: uid(),
      } as OcuUnit;
      if (pick.unit.srcs.length) unit._refs = pick.unit.srcs;
      next.ocs_content.ocu_units.push(unit);
    }
    for (const t of pick.tasks) {
      const task: OcsTask = {
        task_codes: [{ code: "", name: t.name }],
        competency_blocks: [emptyBlock()],
        provenance: { ocs_code: t.provenance.ocs_code, task_code: t.provenance.task_code },
        _tid: uid(),
      };
      if (t.srcs.length) task._refs = t.srcs;
      unit.tasks.push(task);
    }
  }
  return renumber(next);
}
```

- [ ] **Step 2: TaskCuratePanel 重寫**(遞迴選單:職責清單=units 池全部;每職責展開任務選單=tasks 池**全部**(借用);皆序號+引用行;無搜尋)

保留:Modal 外殼、AI 預勾(extract-tasks)、CIT 自訂(structure-task)區塊與 `aiCustoms/customPicks/citDesc/citBusy/citProposal` 狀態。替換資料與勾選模型:

```typescript
  const { data: pack, isLoading, isError } = useKnowledge(profileId, true);
  const units = useMemo(() => (pack ? unitRows(pack) : []), [pack]);
  const tasks = useMemo(() => (pack ? taskRows(pack) : []), [pack]);
  const taskByKey = useMemo(() => new Map(tasks.map((t) => [t.name, t])), [tasks]);
  const primary = pack?.occupation_details[0]?.ocs_code ?? "";
  const ocsCodes = useMemo(
    () => (pack?.occupation_details ?? []).map((d) => d.ocs_code), [pack]);

  // 已在文件(任何職責下)的任務:provenance URN 命中池列 → 標「已加入」不可再勾。
  const alreadyIn = useMemo(() => {
    const s = new Set<string>();
    for (const u of currentDoc?.ocs_content?.ocu_units ?? [])
      for (const t of u.tasks ?? []) for (const urn of taskUrns(t)) s.add(urn);
    return s;
  }, [currentDoc]);
  const rowInDoc = (row: TaskRowVM) => row.urns.some((u) => alreadyIn.has(u));

  // 暫存勾選:職責 key → 該職責底下勾的任務 key(同一任務列勾在別職責 → 他處 disabled)。
  const [staged, setStaged] = useState<Map<string, Set<string>>>(new Map());
  const stagedUnitOf = (taskKey: string): string | null => {
    for (const [uk, set] of staged) if (set.has(taskKey)) return uk;
    return null;
  };

  // 預勾(spec:主基準(順序1)來源的職責列 + 其官方任務聯集);「自動勾選」鈕重套。
  const defaults = useMemo(() => {
    const m = new Map<string, Set<string>>();
    if (!primary) return m;
    for (const u of units) {
      if (!u.srcs.some((s) => s.ocs_code === primary)) continue;
      const picks = new Set(u.ownTaskKeys.filter((k) => {
        const row = taskByKey.get(k);
        return row && !rowInDoc(row);
      }));
      if (picks.size) m.set(u.name, picks);
    }
    return m;
  }, [units, taskByKey, primary, alreadyIn]);
  const [seeded, setSeeded] = useState(false);
  useEffect(() => {
    if (seeded || !pack) return;
    setSeeded(true);
    setStaged(new Map([...defaults].map(([k, v]) => [k, new Set(v)])));
  }, [pack, defaults, seeded]);
```

勾選操作:

```typescript
  const toggleUnit = (u: UnitRowVM, on: boolean) =>
    setStaged((prev) => {
      const next = new Map(prev);
      if (!on) { next.delete(u.name); return next; }
      const set = new Set(next.get(u.name) ?? []);
      for (const k of u.ownTaskKeys) {
        const row = taskByKey.get(k);
        if (row && !rowInDoc(row) && stagedUnitOf(k) === null) set.add(k);
      }
      next.set(u.name, set);
      return next;
    });

  const toggleTask = (unitName: string, taskKey: string) =>
    setStaged((prev) => {
      const next = new Map(prev);
      const set = new Set(next.get(unitName) ?? []);
      if (set.has(taskKey)) set.delete(taskKey);
      else set.add(taskKey);           // 勾任務=職責自動採用(選單開在誰底下就進誰)
      if (set.size === 0) next.delete(unitName);
      else next.set(unitName, set);
      return next;
    });
```

AI 預勾(取代原 byCode 對映;suggested id=task_code per OCS → URN → 池列 → 放回**它自己的職責**):

```typescript
      for (const id of res.suggested_task_ids) {
        for (const oc of ocsCodes) {
          const st = pack?.source_tasks[`ocs:${oc}:T:${id}`];
          if (!st?.task_name || !st.ocu_name) continue;
          const row = taskByKey.get(st.task_name);
          if (!row || rowInDoc(row) || stagedUnitOf(st.task_name)) continue;
          setStaged((prev) => {
            const next = new Map(prev);
            const set = new Set(next.get(st.ocu_name!) ?? []);
            set.add(st.task_name);
            next.set(st.ocu_name!, set);
            return next;
          });
        }
      }
```

確認(前端寫入;provenance 優先取「與本職責同職業」的來源):

```typescript
  const confirm = () => {
    const picks: PoolPick[] = [];
    for (const u of units) {
      const set = staged.get(u.name);
      if (!set?.size) continue;
      const unitCodes = new Set(u.srcs.map((s) => s.ocs_code));
      const pickTasks = [];
      for (const t of tasks) {                       // 池序原樣
        if (!set.has(t.name)) continue;
        const pref = t.srcs.find((s) => unitCodes.has(s.ocs_code)) ?? t.srcs[0];
        pickTasks.push({
          name: t.name, srcs: t.srcs,
          provenance: { ocs_code: pref?.ocs_code ?? "", task_code: pref?.task_code ?? "" },
        });
      }
      picks.push({ unit: { name: u.name, srcs: u.srcs }, tasks: pickTasks });
    }
    for (const c of customPicks) {                   // CIT 自訂:自訂職責(名)+ 空 provenance
      picks.push({
        unit: { name: c.ocu_name || "自訂任務", srcs: [] },
        tasks: [{ name: c.task_name, srcs: [], provenance: { ocs_code: "", task_code: "" } }],
      });
    }
    if (picks.length === 0) { onClose(); return; }
    if (!currentDoc) { onError("文件尚未載入"); return; }
    onApply(addFromPool(currentDoc, picks));
    onClose();
  };
```

渲染(職責一層 + 展開任務選單;皆序號+SourceLine;「自動勾選」鈕在頂部):

```tsx
      <div className="mb-2 flex items-center justify-end">
        <Button size="sm" variant="outline" onClick={() => setStaged(new Map([...defaults].map(([k, v]) => [k, new Set(v)])))}>
          自動勾選
        </Button>
      </div>
      <div className="max-h-[60vh] space-y-2 overflow-y-auto">
        {units.map((u, ui) => {
          const set = staged.get(u.name);
          const isOpen = openUnit === u.name;
          return (
            <div key={u.name} className="rounded-md border">
              <div className="flex items-start gap-2 border-b bg-muted/40 px-2 py-1.5 text-sm font-medium">
                <input type="checkbox" className="mt-1" checked={!!set?.size}
                  onChange={(e) => toggleUnit(u, e.target.checked)} />
                <button type="button" className="min-w-0 flex-1 text-left" onClick={() => setOpenUnit(isOpen ? null : u.name)}>
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono text-xs text-muted-foreground">{ui + 1}.</span>
                    <span>{u.name}</span>
                    {set?.size ? <Badge variant="secondary" className="ml-1 text-[10px]">已勾 {set.size}</Badge> : null}
                    <ChevronDown className={"ml-auto h-3.5 w-3.5 transition-transform " + (isOpen ? "rotate-180" : "")} />
                  </div>
                  <SourceLine srcs={u.srcs} />
                </button>
              </div>
              {isOpen ? (
                <div className="space-y-0.5 p-1.5">
                  {tasks.map((t, ti) => {
                    const inDoc = rowInDoc(t);
                    const elsewhere = stagedUnitOf(t.name);
                    const here = !!set?.has(t.name);
                    const disabled = inDoc || (!!elsewhere && elsewhere !== u.name);
                    const isOwn = u.ownTaskKeys.includes(t.name);
                    return (
                      <label key={t.name}
                        className={"flex items-start gap-2 rounded px-2 py-1 text-sm " +
                          (disabled ? "opacity-50" : "cursor-pointer hover:bg-muted/50")}>
                        <input type="checkbox" className="mt-1" disabled={disabled}
                          checked={inDoc || here} onChange={() => toggleTask(u.name, t.name)} />
                        <span className="mt-0.5 font-mono text-xs text-muted-foreground">{ti + 1}.</span>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            <span>{t.name}</span>
                            {isOwn ? null : <Badge variant="outline" className="text-[10px]">借用</Badge>}
                            {inDoc ? <span className="ml-auto text-[10px] text-muted-foreground">已加入</span> : null}
                            {elsewhere && elsewhere !== u.name ? <span className="ml-auto text-[10px] text-muted-foreground">已勾於「{elsewhere}」</span> : null}
                          </div>
                          <SourceLine srcs={t.srcs} />
                        </div>
                      </label>
                    );
                  })}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
```

(`openUnit` 為新 state `useState<string | null>(null)`;import 增 `SourceLine`、`unitRows/taskRows` 型別、`taskUrns`、`addFromPool` 與 `PoolPick`;刪 `useBuildTasks/useTaskCandidates` import 與 `tkey/ukey/adopted/picked`;`customPicks` 型別改 `{ ocu_name: string; task_name: string }[]`,`addCustom(name, unit)` 對應改存這兩欄;底部按鈕 `build.isPending` 邏輯刪除——`onApply` 走 autosave,即點即回。「將新增 N 個任務」計數改 `[...staged.values()].reduce((a, s) => a + s.size, 0) + customPicks.length`。)

- [ ] **Step 3: page.tsx 接線**:`<TaskCuratePanel …>` 移除舊 props 不變者外,加 `onApply={(d) => autosave.commit(d)}`(用該頁既有的 commit/onChange 函式;執行時以頁面實際變數名為準)。
- [ ] **Step 4: 三道綠。**
- [ ] **Step 5: 手動驗證**(dev):選任務面板=職責清單(序號+引用行+主基準預勾);展開職責→任務選單=**全池**(他職責任務標「借用」);勾借用任務→該任務入此職責;確認→表格出現、Network 走 **PATCH**(非 buildTasks);合併職責(兩職類同名)引用行顯雙來源;「自動勾選」重套主基準集。
- [ ] **Step 6: 同 commit 更新 `apps/web/README.md`**:「關鍵流程 3. 選任務」改寫(兩選單遞迴+借用+預勾+前端寫入,buildTasks 不再使用)。
- [ ] **Step 7: Commit**

```bash
git add apps/web/src/components/interview/TaskCuratePanel.tsx apps/web/src/lib/ocsDoc.ts apps/web/src/app/documents/[id]/page.tsx apps/web/README.md
git commit -m "feat(web): task curation via unit/task pool menus with borrow + client-side doc write [ADR 0021]"
```

---

### Task 6: 表頭三消費者(DocHeader / AttitudeBlock / DocNotes)→ pack

**Files:** Modify `apps/web/src/components/interview/DocHeader.tsx`、`JobDocTable.tsx`(AttitudeBlock)、`DocNotes.tsx`;Delete `apps/web/src/lib/headerMeta.ts`;Modify `apps/web/README.md`

**Interfaces:**
- Consumes:`useKnowledge`、`primaryBasisOptions`/`codedPoolOptions`/`valuePoolOptions`(Task 2)。

- [ ] **Step 1: DocHeader**:`useHeaderMeta` → `useKnowledge(profileId, !!p.ocs_code)`;`primaryOptions(meta)` → `pack ? primaryBasisOptions(pack) : []`(`BasisOption` 欄位名與原 `HeaderMetaPrimaryOption` 相同,`opts` 下游零改);`catOptions` → `(kind) => (pack ? codedPoolOptions(pack.pools[kind]) : [])`;import 改 `@/lib/pack`。
- [ ] **Step 2: AttitudeBlock**(JobDocTable 內):`useHeaderMeta`+`attitudeOptions(meta)` → `useKnowledge`+`pack ? valuePoolOptions(pack.pools.attitudes) : []`。
- [ ] **Step 3: DocNotes**:`noteOptions(meta, field)` → `pack ? valuePoolOptions(pack.pools[field]) : []`(直接就是 `{code:"", name, srcs}` 形狀,原 `.map((t) => ({code:"",name:t}))` 刪;NOTE 選單因此**升級出引用行**——素材庫互動改版仍屬 Plan UX)。
- [ ] **Step 4: 刪 `lib/headerMeta.ts`**(先 `grep -r "lib/headerMeta" apps/web/src` 確認零引用)。
- [ ] **Step 5: 三道綠。**
- [ ] **Step 6: 手動驗證**(dev):表頭「職能基準代碼」下拉=已選職類清單;所屬類別選單顯真實分類碼+引用行、勾選帶入;態度/NOTE 選單序號+引用行;基準級別官方值帶引用;工作描述「加入官方描述」可用。
- [ ] **Step 7: 同 commit 更新 `apps/web/README.md`**:codemap `headerMeta.ts` 改 `pack.ts`;「關鍵流程 2. 選職類」invalidate 對象敘述改(header-meta 不再使用)。
- [ ] **Step 8: Commit**

```bash
git add apps/web/src/components/interview/DocHeader.tsx apps/web/src/components/interview/JobDocTable.tsx apps/web/src/components/interview/DocNotes.tsx apps/web/README.md
git rm apps/web/src/lib/headerMeta.ts
git commit -m "feat(web): header, attitudes, notes menus read knowledge pack [ADR 0021]"
```

---

### Task 7: 退役 — web 舊 query/api fn/型別 + api 四路由 + 文檔收斂

**Files:** Modify `apps/web/src/hooks/useDocument.ts`、`src/lib/api.ts`、`src/types/index.ts`、`src/components/layout/Providers.tsx`;Delete `apps/web/src/hooks/useTaskCatalog.ts`;Modify `apps/api/app/api/routes/documents.py`、`apps/api/README.md`、`apps/web/README.md`;Delete `apps/api/app/core/domain/header_meta.py` + 對應測試(執行時以 grep 定位確切檔名)

- [ ] **Step 1: web 刪**(每項先 grep 零引用再刪):
  - `hooks/useTaskCatalog.ts` 整檔(消費者已在 Task 4 拔掉)。
  - `useDocument.ts`:`useHeaderMeta`、`useTaskCandidates`、`useBuildTasks` 三個 hook;`useSetOccupations.onSuccess` 移除 `task-candidates`/`header-meta` 兩行 invalidate(knowledge 的留);頂部對應 import 清理。
  - `lib/api.ts`:`getHeaderMeta`、`getTaskCandidates`、`getTaskCatalogs`、`buildTasks`;`recommendKS`/`draftOP` 若 grep 零引用一併刪(server `/ai/*` 端點**保留**——訪談引擎/agent 主線用,ADR 0020)。
  - `types/index.ts`:`HeaderMeta*` 五個 interface、`TaskCandidates`/`CandidateGroup`/`CandidateUnit`/`CandidateTask`、`TaskCatalogs`/`TaskCatalogEntry`、`PickedTask`;`RecommendKsResult`/`KsSuggestion`/`DraftOpResult`/`OutputSuggestion`/`IndicatorSuggestion` 同樣 grep 零引用才刪(`ExtractTasksResult`/`StructureTaskResult` 仍在用,留)。
  - `Providers.tsx`:`PERSIST_BUSTER` `"ocs-v4-2"` → `"ocs-v4-3"`(task-catalogs 持久化條目作廢)。
- [ ] **Step 2: web 三道綠。**
- [ ] **Step 3: api 刪**(`routes/documents.py`):`task_candidates`、buildTasks 路由(`document:buildTasks`)、`get_header_meta`、`task_catalogs` 四個 handler + 頂部 `header_meta` import;`core/domain/header_meta.py` 整檔;`ocs_doc.build_from_picked`(grep 確認僅 buildTasks 路由引用);對應測試檔/測試函式(`grep -rl "header-meta\|task-candidates\|task-catalogs\|buildTasks\|build_from_picked\|header_meta" apps/api/tests` 定位後整檔或逐函式刪)。**留**:`GET /document` 空殼 seeding、`task_detail.task_competencies`(ai.py + authoring 共用)、`/knowledge`、`/occupations`、`/ai/*`。
- [ ] **Step 4: api 綠**:`cd apps/api && uv run pytest -q`(數量=175 − 刪掉的測試數,全 passed)。
- [ ] **Step 5: 手動 smoke**(dev 重啟 api 後):選職類→表頭/態度/NOTE/選任務/填格全部可用;Network 僅見 `/knowledge`(+`/ai/*` 特殊功能),舊三端點 404。
- [ ] **Step 6: 同 commit 文檔收斂**:
  - `apps/api/README.md`:端點表刪 4 列;`§3½` 之外提及 header-meta/task-candidates/task-catalogs/buildTasks 的段落改為「已由 /knowledge 取代(ADR 0021)」一句。
  - `apps/web/README.md`:query 表收斂為 `document`/`knowledge`/`task-catalog(刪)`…(僅剩 document、knowledge、profiles);「資料層」「重載還原」「API 消費面」段同步;不變量段補 A4 一條(K/S 文件級同名共碼)。
- [ ] **Step 7: Commit**

```bash
git add -A apps/web/src apps/api/app apps/api/tests apps/api/README.md apps/web/README.md
git commit -m "refactor: retire header-meta/task-candidates/task-catalogs/buildTasks - knowledge pack is the single source [ADR 0021]"
```

---

### Task 8: UI 修訂——選任務 modal 拆掉,改「選職責下拉 + 職責列選任務」(2026-07-03 維護者驗收回饋)

**決策(維護者)**:不要大 modal;**表格為中心**:工具列「選職責 ▾」下拉 → 勾=空職責立即入
表格、再點取消=移除空職責、含任務鎖定(表格刪);每職責列「選任務 ▾」→ 任務大池選單
(語意照舊:全池、預勾自己的、借用、已在他職責 disabled;空職責首開自動帶官方任務、
「自動勾選」重套;取消勾選=移除**空**任務,有內容鎖定)。**AI 預勾(extract-tasks)與 CIT
自訂助手(structure-task)先拿掉**(等訪談引擎 ADR 0020;server `/ai/*` 保留)。

**Files:** Create `components/interview/UnitPickerMenu.tsx`、`TaskPickerMenu.tsx`;Modify
`lib/ocsDoc.ts`(`addTasksToUnit`/`taskHasContent`/`taskFromPool` 抽共用)、`JobDocTable.tsx`
(UnitRow 掛選單+空狀態文案)、`app/documents/[id]/page.tsx`(工具列換下拉、掛 useKnowledge);
Delete `TaskCuratePanel.tsx`;Modify `lib/api.ts`+`types/index.ts`(退 extractTasks/structureTask);
`apps/web/README.md` 同 commit。

- [ ] 三道綠 + commit(一個 commit:同一個 UI 切換)。

## Self-Review

- **Spec coverage:** §5 遞迴選單流程(職責→任務→五選單,全池+預勾+借用)=Task 4/5;預勾統一規則(初次+自動勾選鈕)=Task 3/4/5;W1 序號+引用行(類別例外)=Task 3/6;§5.1 預勾欄(級別衝突取順序1)=Task 4;聯集語意(職責/任務 srcs、`_refs` 多筆 provenance)=Task 2/5;資料流決策①(buildTasks 退役、前端寫入)=Task 5/7、③(逐面切、切完才退)=任務順序本身;A4=Task 1;B4 `_levelSrc`=Task 4;A5 已在 P1 修(態度池 name key,Task 6 只消費)。
- **Type consistency:** `OptionItem{code,name,srcs}` 全線共用;`toItems→CodeName{_src:"official",_ref:srcs[0]}` 與 FieldCombobox `toggle` 同構;`BasisOption` 欄位名=原 `HeaderMetaPrimaryOption`(下游零改);`PoolPick.tasks[].provenance` 與既有 `OcsTask.provenance` 同形。
- **Placeholder scan:** 各步驟含完整代碼;退役步驟以 grep 指令定位、非「適當清理」。
- **風險:** (a) 初次預勾寫文件=行為變更,以「空格才套用+applied ref」限制爆炸半徑;(b) A4 重編改既有 draft 的 K/S 碼——正是修 bug 的目的(匯出才合 ocs-schema);(c) FieldCombobox any-src 判定對舊 `_ref`(單來源 code)向後相容(池列 srcs 含該來源)。
- **不過度設計檢查:** 無搜尋、無排序、無虛擬滾動(池量級 ~百列);staged 用 Map/Set 本地 state,不進 store;pack.ts 無 memo 層(呼叫端 useMemo 即可)。
