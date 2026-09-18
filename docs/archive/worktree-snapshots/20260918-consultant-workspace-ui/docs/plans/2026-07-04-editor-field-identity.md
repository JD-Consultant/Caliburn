# 編輯器全欄位身分統一 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 `docs/specs/2026-07-04-editor-field-identity-unification-spec.md`——每列三件套(UUID/顯示碼/_ref)、notes 影子欄+n 碼、改名斷鏈、主基準自動勾選、基準代碼可取消、TaskPickerMenu 身分判定。

**Architecture:** 先 api(`build_pack` 蓋 notes n 碼),再 web lib 層(types→ocsDoc→pack,全 TDD),最後 UI 元件逐個接線(FieldCombobox→DocNotes→態度→DocHeader→JobDocTable→TaskPickerMenu),收尾更 living 文檔。

**Tech Stack:** api:FastAPI 純函式 + pytest(`uv run pytest`)。web:Next 16/React 19/TS5;lib 層 vitest(`npm run test`),UI 層 gate=`npx tsc --noEmit`+`npm run lint`。

## Global Constraints

- **一 task 一 commit,綠了才 commit**;commit message 不含雙引號(PowerShell 5.1 傳參會壞)。
- spec 為權威:`docs/specs/2026-07-04-editor-field-identity-unification-spec.md`(§2 表、§9 決策)。
- 檔案內中文標點有全形/半形混用——**Edit 前先 Read 精確位置**,別憑記憶寫 old_string。
- 契約欄位形狀不可變:`notes.prerequisites/supplements` 對外恆為 `string[]`;UI-only 一律 `_` 前綴。
- n 碼**不補零**(`n1`、`n2`…,來源側與文件側一致)。
- 不 push、不動 main;工作分支 `feat/editor-field-identity`。
- web 跑指令都在 `S:\caliburn\apps\web`;api 在 `S:\caliburn\apps\api`。

---

### Task 1: api `build_pack` — notes 池 srcs 蓋來源位置碼 n{i}

**Files:**
- Modify: `apps/api/app/core/domain/knowledge_pack.py:56-61`
- Test: `apps/api/tests/test_knowledge_pack.py`

**Interfaces:**
- Produces: notes 池 `srcs[]` 每項多 `"code": "n{i}"`(1-based,照該來源 `prerequisites`/`supplements` 清單順序)。web 端(Task 2 起)靠它走「有碼比碼」。

- [ ] **Step 1: 寫失敗測試**(加在 `test_categories_dedup_by_code_and_notes_by_text` 之後)

```python
def test_notes_srcs_carry_positional_n_codes():
    """spec 2026-07-04 §3:notes 來源位置碼 n{i}(1-based、不補零、per-source 清單順序)。"""
    details = {
        "OC1": _detail("OC1", "甲職業", prereqs=["大學以上", "二年經驗"]),
        "OC2": _detail("OC2", "乙職業", prereqs=["大學以上"]),
    }
    p = kp.build_pack(["OC1", "OC2"], details, {}, {})
    srcs = p["pools"]["prerequisites"]["大學以上"]["srcs"]
    assert [(s["ocs_code"], s["code"]) for s in srcs] == [("OC1", "n1"), ("OC2", "n1")]
    srcs2 = p["pools"]["prerequisites"]["二年經驗"]["srcs"]
    assert [(s["ocs_code"], s["code"]) for s in srcs2] == [("OC1", "n2")]
```

- [ ] **Step 2: 跑測試確認 FAIL**

Run: `cd S:\caliburn\apps\api; uv run pytest tests/test_knowledge_pack.py -q`
Expected: 1 failed(KeyError `'code'` 或 assert 不等)。

- [ ] **Step 3: 最小實作**——`knowledge_pack.py` 把

```python
        for pool_name, texts in (("prerequisites", d.prerequisites),
                                 ("supplements", d.supplements)):
            for t in texts:
                if t.strip():
                    _row(pools[pool_name], t)["srcs"].append(
                        {"ocs_code": code, "ocs_name": name})
```

改成(位置碼=該來源清單 1-based 序,spec §3;跳過空白不佔號,與可見清單一致):

```python
        for pool_name, texts in (("prerequisites", d.prerequisites),
                                 ("supplements", d.supplements)):
            i = 0
            for t in texts:
                if t.strip():
                    i += 1
                    _row(pools[pool_name], t)["srcs"].append(
                        {"ocs_code": code, "ocs_name": name, "code": f"n{i}"})
```

- [ ] **Step 4: 跑測試確認全綠**

Run: `cd S:\caliburn\apps\api; uv run pytest -q`
Expected: 全 pass(既有 93+,新增 1)。

- [ ] **Step 5: Commit**

```powershell
cd S:\caliburn; git add apps/api/app/core/domain/knowledge_pack.py apps/api/tests/test_knowledge_pack.py
git commit -m 'feat(api): stamp positional n-codes on notes pool srcs (field-identity spec s3)'
```

---

### Task 2: web types — `SourceRef.ocu_code`、`NoteItem`、notes 影子欄、`ocs_profile._levelSrc`

**Files:**
- Modify: `apps/web/src/types/index.ts`(SourceRef、OcsProfile、OcsDocument.notes)
- Modify: `apps/web/src/lib/pack.ts`(`packSrcToRef` 帶 `ocu_code`)
- Test: `apps/web/src/lib/pack.test.ts`(新檔)

**Interfaces:**
- Produces:
  - `SourceRef` 多 `ocu_code?: string`(職責身分對位用)。
  - `export type NoteItem = { code: string; text: string; _id?: string; _src?: ItemSource; _ref?: SourceRef }`。
  - `OcsDocument["notes"]` 變 `{ prerequisites: string[]; supplements: string[]; _prerequisites?: NoteItem[]; _supplements?: NoteItem[] }`。
  - `OcsProfile` 多 `_levelSrc?: SourceRef & { level: number }`。
  - `packSrcToRef` 回傳含 `ocu_code`。

- [ ] **Step 1: 寫失敗測試** `apps/web/src/lib/pack.test.ts`

```ts
import { describe, expect, it } from "vitest";
import { packSrcToRef } from "./pack";

describe("packSrcToRef", () => {
  it("帶上 ocu_code(職責身分對位;spec §6)", () => {
    const ref = packSrcToRef({
      ocs_code: "OC1", ocs_name: "甲職業", ocu_code: "T2", ocu_name: "維護",
      task_code: "T2.3", task_name: "保養", code: "K07", competency_level: 4,
    });
    expect(ref).toEqual({
      ocs_code: "OC1", occupation_name: "甲職業", code: "K07",
      ocu_code: "T2", task_code: "T2.3", task_name: "保養",
    });
  });
  it("缺欄位時 ocu_code/task_code 為 undefined、code 為空字串", () => {
    const ref = packSrcToRef({ ocs_code: "OC1", ocs_name: "甲職業" });
    expect(ref.code).toBe("");
    expect(ref.ocu_code).toBeUndefined();
  });
});
```

- [ ] **Step 2: 跑測試確認 FAIL**

Run: `cd S:\caliburn\apps\web; npm run test`
Expected: FAIL(回傳物少 `ocu_code`)。

- [ ] **Step 3: 改 types** `src/types/index.ts`:

`SourceRef` 加一行(放在 `code` 之後):

```ts
  ocu_code?: string;       // 來源職責碼(職責身分對位用,如 T2;spec 2026-07-04 §6)
```

`ItemSource` 附近(`CodeName` 之前)加:

```ts
// notes 影子列(spec 2026-07-04 §3):契約欄恆 string[],物件列存 notes._prerequisites/_supplements。
export type NoteItem = { code: string; text: string; _id?: string; _src?: ItemSource; _ref?: SourceRef };
```

`OcsDocument` 的 `notes` 行改成:

```ts
  notes: {
    prerequisites: string[]; supplements: string[];
    _prerequisites?: NoteItem[]; _supplements?: NoteItem[]; // 唯一真相;setter 同步導出 string[]
  };
```

`OcsProfile` 型別(搜 `ocs_level: number | null` 那個 type)加:

```ts
  _levelSrc?: SourceRef & { level: number }; // 基準級別官方來源(值==官方值時寫;spec §2)
```

- [ ] **Step 4: 改 `pack.ts` 的 `packSrcToRef`**

```ts
export function packSrcToRef(s: PackSrc): SourceRef {
  return {
    ocs_code: s.ocs_code,
    occupation_name: s.ocs_name,
    code: s.code ?? "",
    ocu_code: s.ocu_code ?? undefined,
    task_code: s.task_code ?? undefined,
    task_name: s.task_name ?? undefined,
  };
}
```

- [ ] **Step 5: 跑測試+gate 確認綠**

Run: `cd S:\caliburn\apps\web; npm run test; npx tsc --noEmit; npm run lint`
Expected: 全綠。

- [ ] **Step 6: Commit**

```powershell
cd S:\caliburn; git add apps/web/src/types/index.ts apps/web/src/lib/pack.ts apps/web/src/lib/pack.test.ts
git commit -m 'feat(web): SourceRef.ocu_code + NoteItem + notes shadow fields + profile _levelSrc types'
```

---

### Task 3: `ocsDoc.ts` — notes 影子列 setter + `renumber()` 給 n 碼

**Files:**
- Modify: `apps/web/src/lib/ocsDoc.ts`(notes 區段重寫 + renumber)
- Test: `apps/web/src/lib/ocsDoc.test.ts`

**Interfaces:**
- Consumes: `NoteItem`(Task 2)。
- Produces:
  - `setNoteItems(doc, field: NoteField, items: NoteItem[]): OcsDocument`——寫 `notes._<field>`(逐項淺拷貝)+ 導出 `notes[field] = rows.map(r=>r.text).filter(Boolean)`,收尾走 `renumber`。
  - `renumber()` 對 `notes._prerequisites`/`_supplements` 依位置給 `n{i}`(不補零)。
  - 既有 `setNotes`/`addNote`/`updateNote`/`deleteNote` **刪除**(先 `Grep` 確認只有 `DocNotes.tsx` 用 `setNotes`;Task 7 會改走 `setNoteItems`,本 task 一併刪四個舊 setter 並讓 `DocNotes.tsx` 暫時改用 `setNoteItems` 的最小接法以保 tsc 綠——見 Step 4)。

- [ ] **Step 1: 寫失敗測試**(加到 `ocsDoc.test.ts`)

```ts
import { setNoteItems } from "./ocsDoc"; // 併入既有 import

describe("setNoteItems(notes 影子列,spec 2026-07-04 §3)", () => {
  const base = () => docWith([{ name: "U1", tasks: [] }]);
  it("寫影子列+同步導出契約 string[],顯示碼 n1,n2(不補零)", () => {
    const next = setNoteItems(base(), "prerequisites", [
      { code: "", text: "大學以上", _id: "a", _src: "official",
        _ref: { ocs_code: "OC1", occupation_name: "甲", code: "n1" } },
      { code: "", text: "二年經驗", _id: "b", _src: "custom" },
    ]);
    expect(next.notes.prerequisites).toEqual(["大學以上", "二年經驗"]);
    expect(next.notes._prerequisites!.map((r) => r.code)).toEqual(["n1", "n2"]);
    expect(next.notes._prerequisites![0]._ref!.code).toBe("n1"); // 身分不隨顯示碼動
  });
  it("拖動換序:顯示碼重編、_ref 凍結", () => {
    const d1 = setNoteItems(base(), "supplements", [
      { code: "", text: "甲", _id: "a", _src: "official",
        _ref: { ocs_code: "OC1", occupation_name: "甲", code: "n1" } },
      { code: "", text: "乙", _id: "b", _src: "official",
        _ref: { ocs_code: "OC1", occupation_name: "甲", code: "n2" } },
    ]);
    const rows = d1.notes._supplements!;
    const d2 = setNoteItems(d1, "supplements", [rows[1], rows[0]]);
    expect(d2.notes._supplements!.map((r) => [r.code, r._ref!.code])).toEqual(
      [["n1", "n2"], ["n2", "n1"]]);
    expect(d2.notes.supplements).toEqual(["乙", "甲"]);
  });
  it("純函式:不污染呼叫端 items;空白 text 不進契約欄", () => {
    const items = [{ code: "", text: "", _id: "x" }, { code: "", text: "有值", _id: "y" }];
    const next = setNoteItems(base(), "prerequisites", items);
    expect(items[0].code).toBe("");
    expect(next.notes.prerequisites).toEqual(["有值"]);
    expect(next.notes._prerequisites!.length).toBe(2); // 影子列保留空白列(就地編輯中)
  });
});
```

註:`docWith` fixture 目前沒鋪 `notes`——在 fixture 的回傳物加 `notes: { prerequisites: [], supplements: [] },`。

- [ ] **Step 2: 跑測試確認 FAIL**(`setNoteItems` 不存在)

Run: `cd S:\caliburn\apps\web; npm run test`

- [ ] **Step 3: 實作**——`ocsDoc.ts` notes 區段整段替換(刪 `setNotes`/`addNote`/`updateNote`/`deleteNote` 與 `ensureNotes`):

```ts
// ── 說明與補充事項(notes)編輯──影子列為唯一真相(spec 2026-07-04 §3):
// notes._<field> 存 NoteItem 物件列,契約欄 string[] 由此導出;finalize/export 剝 `_` 後契約乾淨。
export type NoteField = "prerequisites" | "supplements";

export function setNoteItems(doc: OcsDocument, field: NoteField, items: NoteItem[]): OcsDocument {
  const next = clone(doc);
  if (!next.notes) next.notes = { prerequisites: [], supplements: [] };
  next.notes[`_${field}`] = items.map((it) => ({ ...it }));
  return renumber(next); // n 碼重編 + 契約欄導出都在 renumber(單一重編點)
}
```

`renumber()` 裡(態度那行之後、`renumberDocKS` 之前)加:

```ts
  for (const f of ["prerequisites", "supplements"] as const) {
    const rows = doc.notes?.[`_${f}`];
    if (rows) {
      rows.forEach((r, i) => { r.code = `n${i + 1}`; }); // n 碼不補零(spec 全域約束)
      doc.notes[f] = rows.map((r) => r.text).filter(Boolean); // 契約欄=影子列投影
    }
  }
```

import 補 `NoteItem`。

- [ ] **Step 4: `DocNotes.tsx` 最小改接**(只為 tsc 綠;完整 UI 在 Task 7):`setNotes` 呼叫改

```ts
        onCommit={(items) => onChange(setNoteItems(doc, field,
          items.map((i) => ({ code: i.code, text: i.name, _id: i._id, _src: i._src, _ref: i._ref }))))}
```

import 改 `setNoteItems`。

- [ ] **Step 5: 跑測試+gate 確認綠**

Run: `cd S:\caliburn\apps\web; npm run test; npx tsc --noEmit; npm run lint`

- [ ] **Step 6: Commit**

```powershell
cd S:\caliburn; git add apps/web/src/lib/ocsDoc.ts apps/web/src/lib/ocsDoc.test.ts apps/web/src/components/interview/DocNotes.tsx
git commit -m 'feat(web): notes shadow rows as source of truth + n display codes in renumber'
```

---

### Task 4: `ocsDoc.ts` — 改名斷鏈、`clearPrimaryBasis`、級別來源清理

**Files:**
- Modify: `apps/web/src/lib/ocsDoc.ts`(`renameUnit`/`renameTask`/`setTaskLevel`/`setOcsLevel`;新增 `clearPrimaryBasis`/`setOcsLevelSrc` 邏輯)
- Test: `apps/web/src/lib/ocsDoc.test.ts`

**Interfaces:**
- Produces:
  - `renameUnit(doc, ui, name)`:名字有變 → 同時 `delete unit._refs`、`unit.source = { ocs_code: "", occupation_name: "" }`。
  - `renameTask(doc, ui, ti, name)`:名字有變 → `task.provenance = { ocs_code: "", task_code: "" }`、`delete task._refs`、`delete task._levelSrc`。
  - `clearPrimaryBasis(doc)`:清 `ocs_code`、`ocs_name.occupation_name`、`ocs_name.job_category_name`(級別/描述/類別不動;`_levelSrc` 保留=歷史來源)。
  - `setTaskLevel(..., src?)`:`src` 未給 → **`delete _levelSrc`**(修殘留)。
  - `setOcsLevel(doc, value, src?)`:簽名加第三參數 `src?: SourceRef & { level: number }`;給→寫 `ocs_profile._levelSrc`,未給→`delete`。

- [ ] **Step 1: 寫失敗測試**

```ts
import { clearPrimaryBasis, renameUnit, setOcsLevel, setTaskLevel } from "./ocsDoc"; // 併入既有 import
import { renameTask } from "./ocsDoc";

describe("改名斷鏈 + 級別來源(spec 2026-07-04 §2/§5)", () => {
  it("renameTask:清 provenance/_refs/_levelSrc → 變自訂", () => {
    const doc = docWith([{ name: "U1", tasks: [task("T1.1", "甲")] }]);
    doc.ocs_content.ocu_units[0].tasks[0]._refs = [{ ocs_code: "OC1", occupation_name: "甲職", code: "" }];
    doc.ocs_content.ocu_units[0].tasks[0]._levelSrc = { ocs_code: "OC1", occupation_name: "甲職", code: "", level: 3 };
    const next = renameTask(doc, 0, 0, "改過的名字");
    const t = next.ocs_content.ocu_units[0].tasks[0];
    expect(t.provenance).toEqual({ ocs_code: "", task_code: "" });
    expect(t._refs).toBeUndefined();
    expect(t._levelSrc).toBeUndefined();
    expect(t.task_codes![0].name).toBe("改過的名字");
  });
  it("renameUnit:清 source/_refs", () => {
    const doc = docWith([{ name: "U1", tasks: [] }]);
    doc.ocs_content.ocu_units[0]._refs = [{ ocs_code: "OC1", occupation_name: "甲職", code: "", ocu_code: "T1" }];
    const next = renameUnit(doc, 0, "新名");
    expect(next.ocs_content.ocu_units[0]._refs).toBeUndefined();
    expect(next.ocs_content.ocu_units[0].source).toEqual({ ocs_code: "", occupation_name: "" });
  });
  it("setTaskLevel 無 src → 清舊 _levelSrc(修殘留)", () => {
    const doc = docWith([{ name: "U1", tasks: [task("T1.1", "甲")] }]);
    const d1 = setTaskLevel(doc, 0, 0, 3, { ocs_code: "OC1", occupation_name: "甲職", code: "", level: 3 });
    expect(d1.ocs_content.ocu_units[0].tasks[0]._levelSrc?.level).toBe(3);
    const d2 = setTaskLevel(d1, 0, 0, 5);
    expect(d2.ocs_content.ocu_units[0].tasks[0]._levelSrc).toBeUndefined();
  });
  it("setOcsLevel:src 給→寫 ocs_profile._levelSrc,未給→清", () => {
    const doc = docWith([{ name: "U1", tasks: [] }]);
    const d1 = setOcsLevel(doc, "4", { ocs_code: "OC1", occupation_name: "甲職", code: "", level: 4 });
    expect(d1.ocs_profile._levelSrc?.level).toBe(4);
    const d2 = setOcsLevel(d1, "5");
    expect(d2.ocs_profile._levelSrc).toBeUndefined();
  });
  it("clearPrimaryBasis:整組清 code+兩名,其他欄不動", () => {
    const doc = docWith([{ name: "U1", tasks: [] }]);
    doc.ocs_profile.ocs_name = { job_category_name: "職類名", occupation_name: "職業名" };
    doc.ocs_profile.job_description = "描述留著";
    const next = clearPrimaryBasis(doc);
    expect(next.ocs_profile.ocs_code).toBe("");
    expect(next.ocs_profile.ocs_name.occupation_name).toBe("");
    expect(next.ocs_profile.ocs_name.job_category_name).toBe("");
    expect(next.ocs_profile.job_description).toBe("描述留著");
  });
});
```

- [ ] **Step 2: 跑測試確認 FAIL**

- [ ] **Step 3: 實作**

`renameUnit` 改:

```ts
export function renameUnit(doc: OcsDocument, ui: number, name: string): OcsDocument {
  const next = clone(doc);
  const unit = next.ocs_content.ocu_units[ui];
  if (unit.ocu_name === name) return next;
  unit.ocu_name = name;
  // 改名=斷鏈變自訂(spec §5;與 OPKS「改內容→自訂」一致;底下任務身分不受影響)
  delete unit._refs;
  unit.source = { ocs_code: "", occupation_name: "" };
  return next;
}
```

`renameTask` 改(原本改 `tc.name` 的邏輯保留,後面加斷鏈):

```ts
export function renameTask(doc: OcsDocument, ui: number, ti: number, name: string): OcsDocument {
  const next = clone(doc);
  const t = next.ocs_content.ocu_units[ui].tasks[ti];
  const tc = t.task_codes?.[0] ?? { code: "", name: "" };
  if (tc.name === name) return next;
  tc.name = name;
  t.task_codes = [tc];
  delete t._refs;          // 改名=斷鏈變自訂(spec §5;own-refs 自動帶入/官方級別隨之失效)
  delete t._levelSrc;
  t.provenance = { ocs_code: "", task_code: "" };
  return next;
}
```

`setTaskLevel` 的 `_levelSrc` 行改:

```ts
  const t = next.ocs_content.ocu_units[unitIdx].tasks[taskIdx];
  if (src) t._levelSrc = src;
  else delete t._levelSrc; // 值≠官方 → 來源清掉(spec §2:不留殘留)
```

`setOcsLevel` 改:

```ts
export function setOcsLevel(
  doc: OcsDocument,
  value: string,
  src?: SourceRef & { level: number },
): OcsDocument {
  const next = clone(doc);
  const n = parseInt(value, 10);
  next.ocs_profile.ocs_level = Number.isFinite(n) ? n : null;
  if (src) next.ocs_profile._levelSrc = src;
  else delete next.ocs_profile._levelSrc;
  return next;
}
```

新增(放 `setPrimaryBasis` 旁):

```ts
// 再點已選基準=整組清空(spec §9 決策 4):代碼↔名稱綁定一起進出;級別/描述/類別不動。
export function clearPrimaryBasis(doc: OcsDocument): OcsDocument {
  const next = clone(doc);
  next.ocs_profile.ocs_code = "";
  next.ocs_profile.ocs_name.occupation_name = "";
  next.ocs_profile.ocs_name.job_category_name = "";
  return next;
}
```

import 補 `SourceRef`(若未含)。

- [ ] **Step 4: 跑測試+gate 確認綠**

Run: `cd S:\caliburn\apps\web; npm run test; npx tsc --noEmit; npm run lint`

- [ ] **Step 5: Commit**

```powershell
cd S:\caliburn; git add apps/web/src/lib/ocsDoc.ts apps/web/src/lib/ocsDoc.test.ts
git commit -m 'feat(web): rename breaks identity; clearPrimaryBasis; level source hygiene'
```

---

### Task 5: `pack.ts` — `primaryDefaults` / `isOfficialBasis` / `noteRowsFromStrings`

**Files:**
- Modify: `apps/web/src/lib/pack.ts`
- Test: `apps/web/src/lib/pack.test.ts`

**Interfaces:**
- Consumes: `NoteItem`(Task 2)、`packSrcToRef`。
- Produces:
  - `isOfficialBasis(pack, ocsCode: string): boolean`——`occupation_details` 含該 code。
  - `primaryDefaults(options: OptionItem[], primaryCode: string): OptionItem[]`——srcs 含主基準碼者。
  - `noteRowsFromStrings(texts: string[], pool: Record<string, PoolRow>): NoteItem[]`——舊 draft 遷移:文字對池命中→official+`_ref`(該池列 srcs 首個),否則 custom;顯示碼照序 `n{i}`。

- [ ] **Step 1: 寫失敗測試**(加到 `pack.test.ts`)

```ts
import { isOfficialBasis, noteRowsFromStrings, primaryDefaults } from "./pack";
import type { KnowledgePack } from "@/types";

describe("primaryDefaults / isOfficialBasis(spec 2026-07-04 §4)", () => {
  const opts = [
    { code: "", name: "甲", srcs: [{ ocs_code: "OC1", occupation_name: "甲職", code: "n1" }] },
    { code: "", name: "乙", srcs: [{ ocs_code: "OC2", occupation_name: "乙職", code: "n1" }] },
    { code: "", name: "丙", srcs: [
      { ocs_code: "OC2", occupation_name: "乙職", code: "n2" },
      { ocs_code: "OC1", occupation_name: "甲職", code: "n2" },
    ] },
  ];
  it("篩出 srcs 含主基準碼的選項(不重排)", () => {
    expect(primaryDefaults(opts, "OC1").map((o) => o.name)).toEqual(["甲", "丙"]);
  });
  it("isOfficialBasis:只認 occupation_details 裡的 code", () => {
    const pack = { occupation_details: [{ ocs_code: "OC1" }] } as unknown as KnowledgePack;
    expect(isOfficialBasis(pack, "OC1")).toBe(true);
    expect(isOfficialBasis(pack, "自訂碼")).toBe(false);
    expect(isOfficialBasis(pack, "")).toBe(false);
  });
});

describe("noteRowsFromStrings(舊 draft 遷移,spec §3)", () => {
  it("命中池→official+_ref(首來源);未命中→custom;顯示碼照序", () => {
    const pool = { 大學以上: { srcs: [{ ocs_code: "OC1", ocs_name: "甲職", code: "n1" }] } };
    const rows = noteRowsFromStrings(["大學以上", "自己打的"], pool);
    expect(rows[0]).toMatchObject({ code: "n1", text: "大學以上", _src: "official" });
    expect(rows[0]._ref).toMatchObject({ ocs_code: "OC1", code: "n1" });
    expect(rows[1]).toMatchObject({ code: "n2", text: "自己打的", _src: "custom" });
    expect(rows[0]._id).toBeTruthy();
  });
});
```

- [ ] **Step 2: 跑測試確認 FAIL**

- [ ] **Step 3: 實作**(加在 `valuePoolOptions` 附近;import `NoteItem`)

```ts
// 主基準是否官方(spec §4:主基準空白/自訂 → 自動勾選不套)。
export function isOfficialBasis(pack: KnowledgePack, ocsCode: string): boolean {
  return !!ocsCode && pack.occupation_details.some((d) => d.ocs_code === ocsCode);
}

// 表頭層自動勾選 defaults:srcs 含主基準碼的選項(順序照池序,不重排)。
export function primaryDefaults(options: OptionItem[], primaryCode: string): OptionItem[] {
  return options.filter((o) => (o.srcs ?? []).some((s) => s.ocs_code === primaryCode));
}

// 舊 draft notes 遷移(spec §3):string[] → 影子列;文字對池命中=official(來源凍結為池列首來源)。
export function noteRowsFromStrings(texts: string[], pool: Record<string, PoolRow>): NoteItem[] {
  return texts.map((t, i) => {
    const src = pool[t]?.srcs?.[0];
    return src
      ? { code: `n${i + 1}`, text: t, _id: newId(), _src: "official" as const, _ref: packSrcToRef(src) }
      : { code: `n${i + 1}`, text: t, _id: newId(), _src: "custom" as const };
  });
}
```

- [ ] **Step 4: 跑測試+gate 確認綠**

Run: `cd S:\caliburn\apps\web; npm run test; npx tsc --noEmit; npm run lint`

- [ ] **Step 5: Commit**

```powershell
cd S:\caliburn; git add apps/web/src/lib/pack.ts apps/web/src/lib/pack.test.ts
git commit -m 'feat(web): primaryDefaults/isOfficialBasis/noteRowsFromStrings pack helpers'
```

---

### Task 6: `FieldCombobox` — 自動勾選鈕移入選單 + 首開自動套

**Files:**
- Modify: `apps/web/src/components/interview/fields/FieldCombobox.tsx`

**Interfaces:**
- Produces: 新 prop `autoApplyOnFirstOpen?: boolean`(預設 false)。行為:
  - 選單(Popover)內容頂列 = 說明文字(既有 label 情境自帶)+「自動勾選」鈕(呼叫既有 `applyDefaults`);**外部按鈕列的「自動勾選」鈕移除**(兩個版型都是)。
  - `onMenuOpenChange(true)` 且 `autoApplyOnFirstOpen` 且未套過且 `value.length === 0` 且 `(defaults ?? []).length > 0` → `applyDefaults()`,一次為限(`useRef`)。
- Consumes: 無新依賴。呼叫端(Task 7/8/9)靠 `defaults` + `autoApplyOnFirstOpen` 組合。

- [ ] **Step 1: 實作**

(a) 元件內加:

```ts
  const autoApplied = useRef(false);
```

(import `useRef`)。`onMenuOpenChange` 改:

```ts
  const onMenuOpenChange = (o: boolean) => {
    setOpen(o);
    if (o && autoApplyOnFirstOpen && !autoApplied.current) {
      autoApplied.current = true;
      if (value.length === 0 && (defaults ?? []).length > 0) applyDefaults(); // 首開且空才套(spec §4)
    }
  };
```

props 解構加 `autoApplyOnFirstOpen = false`,型別註記:

```ts
  // 首次打開選單且欄位為空 → 自動套 defaults(spec 2026-07-04 §4;之後以使用者為準)
  autoApplyOnFirstOpen?: boolean;
```

(b) `menu` 的兩個分支都包一層,選單頂列加鈕(放 `<Command>` 之前、共用):

```tsx
  const menuHeader = (
    <div className="mb-1 flex items-center justify-end px-1">
      <button type="button" className="shrink-0 text-xs text-muted-foreground hover:text-foreground"
        title="套用官方預設(勾上還沒選的)" onClick={applyDefaults}>
        自動勾選
      </button>
    </div>
  );
```

兩個 `PopoverContent` 內容改為 `<>{menuHeader}{menu}</>`(或把 `menuHeader` 放進 `menu` 兩分支開頭,擇一,總之**選單內恰一顆**)。

(c) 移除兩個版型外部的 `自動勾選` `<button>`/`<Button>`(title 模式那顆與預設模式那顆)。

- [ ] **Step 2: gate**

Run: `cd S:\caliburn\apps\web; npm run test; npx tsc --noEmit; npm run lint`
Expected: 全綠(此元件無單測,靠 tsc/lint + Task 7-9 的手測)。

- [ ] **Step 3: Commit**

```powershell
cd S:\caliburn; git add apps/web/src/components/interview/fields/FieldCombobox.tsx
git commit -m 'feat(web): FieldCombobox auto-check button inside menu + first-open auto-apply'
```

---

### Task 7: `DocNotes` — 影子列接線 + 遷移 + 主基準自動勾選

**Files:**
- Modify: `apps/web/src/components/interview/DocNotes.tsx`

**Interfaces:**
- Consumes: `setNoteItems`(Task 3)、`noteRowsFromStrings`/`primaryDefaults`/`isOfficialBasis`(Task 5)、`autoApplyOnFirstOpen`(Task 6)。

- [ ] **Step 1: 實作**——`NoteCombo` 重寫:

```tsx
function NoteCombo({ doc, profileId, field, title, onChange }: {
  doc: OcsDocument; profileId: string; field: NoteField; title: string; onChange: (d: OcsDocument) => void;
}) {
  const { data: pack } = useKnowledge(profileId, !!doc.ocs_profile.ocs_code);
  const options = pack ? valuePoolOptions(pack.pools[field]) : [];
  const primary = doc.ocs_profile.ocs_code;
  const defaults = pack && isOfficialBasis(pack, primary) ? primaryDefaults(options, primary) : [];
  // 影子列=真相;舊 draft(只有 string[])→ 由文字對池重建(display 用,下次 commit 落庫)。
  const rows = useMemo<NoteItem[]>(() => {
    const shadow = doc.notes?.[`_${field}`];
    if (shadow) return shadow;
    return pack ? noteRowsFromStrings(doc.notes?.[field] ?? [], pack.pools[field])
                : (doc.notes?.[field] ?? []).map((t, i) => ({ code: `n${i + 1}`, text: t }));
  }, [doc.notes, field, pack]);
  const value = rows.map((r) => ({ code: r.code, name: r.text, _id: r._id, _src: r._src, _ref: r._ref }));
  return (
    <div>
      <FieldCombobox label="選/輸入" title={title} layout="list" customMode="footer" editMultiline
        autoCode="n" autoApplyOnFirstOpen
        value={value} options={options} defaults={defaults}
        onCommit={(items) => onChange(setNoteItems(doc, field,
          items.map((i) => ({ code: i.code, text: i.name, _id: i._id, _src: i._src, _ref: i._ref }))))} />
    </div>
  );
}
```

import 對齊:`useMemo`、`NoteItem`、`isOfficialBasis`/`noteRowsFromStrings`/`primaryDefaults`。
注意 `autoCode="n"`:`positionalCode`/`nextCode` 對純字母前綴會補零(n01)——暫定碼無妨,
`setNoteItems` 收尾 `renumber` 會重編成 `n1` 樣式(與 O/P 的「暫定碼→setter 重編」同模式)。

- [ ] **Step 2: gate**

Run: `cd S:\caliburn\apps\web; npm run test; npx tsc --noEmit; npm run lint`

- [ ] **Step 3: 手測**(dev server + api + indexer 起著;`docs/runbook.md`):
選過職類的文件 → 說明事項選單:官方項可勾/取消勾(不再全標自訂)、首開空欄自動帶主基準項、
改字後該列變「自訂」且選單取消勾選、拖不了的(notes 無拖拉)略過、重載後狀態不變。

- [ ] **Step 4: Commit**

```powershell
cd S:\caliburn; git add apps/web/src/components/interview/DocNotes.tsx
git commit -m 'feat(web): DocNotes shadow rows + migration + primary-basis auto-check (fixes custom-tag bug)'
```

---

### Task 8: 態度(AttitudeBlock)— 主基準 defaults + 首開自動套

**Files:**
- Modify: `apps/web/src/components/interview/JobDocTable.tsx`(`AttitudeBlock`)

- [ ] **Step 1: 實作**——`AttitudeBlock` 的 `FieldCombobox` 加:

```tsx
  const primary = doc.ocs_profile?.ocs_code ?? "";
  const options = pack ? valuePoolOptions(pack.pools.attitudes) : [];
  const defaults = pack && isOfficialBasis(pack, primary) ? primaryDefaults(options, primary) : [];
```

JSX:`options={options} defaults={defaults} autoApplyOnFirstOpen`。import `isOfficialBasis, primaryDefaults`。

- [ ] **Step 2: gate + Commit**

Run: `cd S:\caliburn\apps\web; npm run test; npx tsc --noEmit; npm run lint`

```powershell
cd S:\caliburn; git add apps/web/src/components/interview/JobDocTable.tsx
git commit -m 'feat(web): attitudes auto-check from primary basis'
```

---

### Task 9: `DocHeader` — 三類自動勾選、級別綁 `_levelSrc`+自動帶、基準代碼點選取消

**Files:**
- Modify: `apps/web/src/components/interview/DocHeader.tsx`
- Modify: `apps/web/src/components/interview/fields/OfficialMenu.tsx`(頂列自動勾選鈕 prop)

**Interfaces:**
- Consumes: `clearPrimaryBasis`/`setOcsLevel(src)`(Task 4)、`primaryDefaults`/`isOfficialBasis`(Task 5)。
- Produces: `OfficialMenu` 新 prop `onAutoApply?: () => void`(給了→選單頂列顯「自動勾選」鈕,點了呼叫並關選單)。

- [ ] **Step 1: `OfficialMenu` 加 prop**——`PopoverContent` 開頭(Command 前):

```tsx
        {onAutoApply ? (
          <div className="mb-1 flex items-center justify-end px-1">
            <button type="button" className="shrink-0 text-xs text-muted-foreground hover:text-foreground"
              onClick={() => { onAutoApply(); setOpenAnd(false); }}>
              自動勾選
            </button>
          </div>
        ) : null}
```

- [ ] **Step 2: `DocHeader` 基準代碼 onPick 支援取消**:

```tsx
                onPick={(code) => {
                  if (code === p.ocs_code) { onChange(clearPrimaryBasis(doc)); return; } // 再點=整組清空
                  const o = opts.find((x) => x.ocs_code === code);
                  if (o) onChange(setPrimaryBasis(doc, { ocs_code: o.ocs_code, occupation_name: o.occupation_name, job_category_name: o.job_category_name || "" }));
                }}
```

- [ ] **Step 3: 三類 `CategoryPicker` 自動勾選**——`CategoryPicker` 加 props `onAutoApply?: () => void` 與 `autoApplyOnFirstOpen?: boolean`,`Popover` `onOpenChange` 首開時(`useRef` 一次為限)且 `existing` 無 real 項目 → `onAutoApply?.()`;選單頂列加「自動勾選」鈕(同 Step 1 樣式)。`DocHeader` 端:

```tsx
  const primaryOfficial = !!pack && isOfficialBasis(pack, p.ocs_code);
  const applyCatDefaults = (kind: CatKind) => {
    if (!primaryOfficial) return; // 主基準空白/自訂 → 不套(spec §4)
    const existing = p.category?.[kind] ?? [];
    const picks = primaryDefaults(catOptions(kind), p.ocs_code)
      .filter((o) => !existing.some((e) => ekey(e) === ekey(o)))
      .map((o) => ({ code: o.code, name: o.name, _id: newId(), _src: "official" as const,
                     _ref: o.srcs?.[0] ?? { ocs_code: "", occupation_name: "", code: o.code } }));
    if (picks.length) onChange(setCategory(doc, kind, [...existing, ...picks]));
  };
```

`CategoryPicker` 呼叫處傳 `onAutoApply={() => applyCatDefaults(r.key)} autoApplyOnFirstOpen`。

- [ ] **Step 4: 基準級別**——`OfficialMenu`(基準級別那顆)改:

```tsx
              <OfficialMenu
                trigger={…既有…}
                options={[1, 2, 3, 4, 5, 6].map((n) => ({ … 既有 …}))}
                selected={p.ocs_level != null ? String(p.ocs_level) : ""}
                onAutoApply={() => { const b = primaryBasis(); if (b?.ocs_level != null)
                  onChange(setOcsLevel(doc, String(b.ocs_level), levelSrcOf(b))); }}
                onOpenChange={(o) => { if (o && !levelAuto.current) { levelAuto.current = true;
                  const b = primaryBasis();
                  if (p.ocs_level == null && b?.ocs_level != null)
                    onChange(setOcsLevel(doc, String(b.ocs_level), levelSrcOf(b))); } }}
                onPick={(v) => { const b = primaryBasis();
                  const official = b?.ocs_level != null && Number(v) === b.ocs_level;
                  onChange(setOcsLevel(doc, v, official ? levelSrcOf(b!) : undefined)); }}
              />
```

輔助(元件內):

```tsx
  const levelAuto = useRef(false);
  const primaryBasis = () => (primaryOfficial ? opts.find((o) => o.ocs_code === p.ocs_code) : undefined);
  const levelSrcOf = (b: BasisOption) => ({
    ocs_code: b.ocs_code, occupation_name: b.occupation_name, code: "", level: b.ocs_level as number });
```

(import `useRef`、`BasisOption`、`clearPrimaryBasis`、`isOfficialBasis`、`primaryDefaults`。)
級別官方判定顯示(選項 srcs)既有邏輯不動;**值==官方即官方、不區分怎麼選的**(spec §9 決策 6)。

- [ ] **Step 5: gate + 手測 + Commit**

Run: `cd S:\caliburn\apps\web; npm run test; npx tsc --noEmit; npm run lint`
手測:基準代碼再點=清空(名稱一起清、描述留);三類首開自動帶主基準、自動勾選鈕補勾;
級別首開空→帶主基準級別;改選非官方值→(dev tools 看 doc)`_levelSrc` 消失。

```powershell
cd S:\caliburn; git add apps/web/src/components/interview/DocHeader.tsx apps/web/src/components/interview/fields/OfficialMenu.tsx
git commit -m 'feat(web): header auto-check (categories/level), level source binding, basis click-to-clear'
```

---

### Task 10: `JobDocTable` — 職責/任務「自訂」tag + 任務級別自動勾選鈕

**Files:**
- Modify: `apps/web/src/components/interview/JobDocTable.tsx`

- [ ] **Step 1: 任務列 tag**——`TaskRow` 內(`tc` 之後):

```tsx
  const isCustomTask = taskUrns(task).length === 0; // 無官方身分=自訂(含手動新增/改過名)
```

名稱 `EditableText` 之後加:

```tsx
        {isCustomTask ? <span className="shrink-0 rounded bg-amber-100 px-1 text-[10px] text-amber-700" title="自訂任務(無官方來源)">自訂</span> : null}
```

- [ ] **Step 2: 職責列 tag**——`UnitRow` 內:

```tsx
  const isCustomUnit = !(unit._refs?.length) && !unit.source?.ocs_code;
```

`EditableText` 之後、來源字樣之前加同樣式 `自訂` span(title「自訂職責(無官方來源)」)。

- [ ] **Step 3: 任務級別選單自動勾選**——`TaskRow` 的 `OfficialMenu` 加:

```tsx
          onAutoApply={() => { if (officialLevel != null && levelSrc)
            onChange(setTaskLevel(doc, unitIdx, taskIdx, officialLevel, { ...levelSrc, level: officialLevel })); }}
```

(首開自動帶**維持既有 CellFiller/整表規則**:任務級別本來就顯示在列上、無「空格首開」概念,只加鈕。)

- [ ] **Step 4: gate + Commit**

Run: `cd S:\caliburn\apps\web; npm run test; npx tsc --noEmit; npm run lint`

```powershell
cd S:\caliburn; git add apps/web/src/components/interview/JobDocTable.tsx
git commit -m 'feat(web): custom tags on renamed/manual units+tasks; task-level auto-check button'
```

---

### Task 11: `TaskPickerMenu` — own 任務改 `_refs` 身分對位

**Files:**
- Modify: `apps/web/src/components/interview/TaskPickerMenu.tsx`

**Interfaces:**
- Consumes: `SourceRef.ocu_code`(Task 2 起 `addFromPool` 存的 `unit._refs` 已含)。

- [ ] **Step 1: 實作**——`ownKeys` 計算整段替換:

```tsx
  // 本職責的官方任務集:以 unit._refs 的 (ocs_code, ocu_code) 對回 units 池列(身分對位,
  // spec 2026-07-04 §6;改過名的職責 _refs 已清 → 無 own=全借用,行為由身分導出)。
  const unitPairs = new Set((unit?._refs ?? [])
    .filter((r) => r.ocu_code)
    .map((r) => `${r.ocs_code}__${r.ocu_code}`));
  const ownKeys = pack && unit && unitPairs.size
    ? unitRows(pack)
        .filter((u) => u.srcs.some((s) => s.ocu_code && unitPairs.has(`${s.ocs_code}__${s.ocu_code}`)))
        .flatMap((u) => u.ownTaskKeys)
    : [];
```

(刪原本 `unitRows(pack).find((u) => u.name === unit.ocu_name)` 名字對位。)

- [ ] **Step 2: gate + 手測 + Commit**

Run: `cd S:\caliburn\apps\web; npm run test; npx tsc --noEmit; npm run lint`
手測:池職責入表 → 選任務有預設 own;**改職責名** → tag 出現、選任務全變借用、原 own 預勾消失。

```powershell
cd S:\caliburn; git add apps/web/src/components/interview/TaskPickerMenu.tsx
git commit -m 'feat(web): TaskPickerMenu own-task matching by unit _refs identity'
```

---

### Task 12: living 文檔更新 + 全 repo 驗證 + tag

**Files:**
- Modify: `docs/design/editor-knowledge-pack.md`(§2 三分表補 n 碼/notes 列;不變量補「改名斷鏈」「自動勾選規則」)
- Modify: `apps/web/README.md`(不變量:notes 影子欄、改名斷鏈、自動勾選規則一行各)
- Modify: `apps/api/docs/knowledge-pack-assembly.md`(notes 池 srcs 蓋 n 碼一行)
- Modify: `docs/specs/2026-07-04-editor-field-identity-unification-spec.md`(頂部補 plan 連結)

- [ ] **Step 1: 逐檔更新**(寫法照 `docs/design/README.md` dual-audience 清單:動作→請求、真名、不變量)。
- [ ] **Step 2: 全 repo 驗證**

Run: `cd S:\caliburn; npx turbo test`(5/5 綠)
Run: `cd S:\caliburn\apps\web; npx tsc --noEmit; npm run lint; npm run build`(三道綠)

- [ ] **Step 3: Commit + tag**

```powershell
cd S:\caliburn; git add -A; git commit -m 'docs: update living docs for field-identity unification'
git tag editor-field-identity
```

(合併回 main 由維護者拍板,照 finishing-a-development-branch 流程。)
