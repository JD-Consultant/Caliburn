// D27 OCS 文件的就地（immutable）更新與完成度計算。每任務一個 competency_block
// → 都讀寫 competency_blocks[0]。完成度公式對齊後端 compute_completion：
// filled = 1(表頭) + (A?1:0) + Σ_task[(O>0)+(P>0)+(K>0)+(S>0)]；total = 4*任務數 + 2。
import type { CodeName, CompetencyBlock, Indicator, OcsDocument, OcsTask, OcuUnit } from "@/types";

function clone(doc: OcsDocument): OcsDocument {
  return structuredClone(doc);
}

function emptyBlock(): CompetencyBlock {
  return { competency_level: null, indicators: [], outputs: [], knowledge: [], skills: [] };
}

function uid(): string {
  return (globalThis.crypto?.randomUUID?.() ?? `id-${Math.random().toString(36).slice(2)}`);
}

function emptyTask(): OcsTask {
  return {
    task_codes: [{ code: "", name: "" }],
    competency_blocks: [emptyBlock()],
    provenance: { ocs_code: "", task_code: "" },
    _tid: uid(),
  };
}

// 位置序碼：字母前綴補零 2 位（A→A01）；含點/數字前綴不補零（O1.1.→O1.1.1）。
export function positionalCode(prefix: string, idx: number): string {
  const pad = /^[A-Za-z]+$/.test(prefix) ? 2 : 0;
  return `${prefix}${String(idx + 1).padStart(pad, "0")}`;
}

// 依陣列位置就地重寫每筆 code（身分由 _id 維持，故重編不影響來源/自訂判定）。
function renumberCoded<T extends { code: string }>(items: T[], prefix: string): void {
  items.forEach((it, i) => { it.code = positionalCode(prefix, i); });
}

// 補上缺少的穩定 id（dnd 用）。新載入的文件（seed/build 來的）沒有 id → 在此補。
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

// 結構變動後重新遞進編號：職責 T1,T2…；任務 T{u}.{t}。名稱/區塊/provenance 不動。
function renumber(doc: OcsDocument): OcsDocument {
  const units = doc.ocs_content?.ocu_units ?? [];
  units.forEach((u, ui) => {
    u.ocu_code = `T${ui + 1}`;
    (u.tasks ?? []).forEach((t, ti) => {
      const tc = t.task_codes?.[0] ?? { code: "", name: "" };
      tc.code = `T${ui + 1}.${ti + 1}`;
      t.task_codes = [tc, ...(t.task_codes ?? []).slice(1)];
    });
  });
  return doc;
}

function move<T>(arr: T[], idx: number, dir: -1 | 1): void {
  const j = idx + dir;
  if (j < 0 || j >= arr.length) return;
  [arr[idx], arr[j]] = [arr[j], arr[idx]];
}

// ── 表頭(ocs_profile) 編輯 ────────────────────────────────────────────────────
export type CatKind = "job_categories" | "occupations" | "industries";

export function setProfileField(
  doc: OcsDocument,
  key: "ocs_code" | "job_description",
  value: string,
): OcsDocument {
  const next = clone(doc);
  next.ocs_profile[key] = value;
  return next;
}

export function setOcsLevel(doc: OcsDocument, value: string): OcsDocument {
  const next = clone(doc);
  const n = parseInt(value, 10);
  next.ocs_profile.ocs_level = Number.isFinite(n) ? n : null;
  return next;
}

export function setOcsName(
  doc: OcsDocument,
  key: "job_category_name" | "occupation_name",
  value: string,
): OcsDocument {
  const next = clone(doc);
  next.ocs_profile.ocs_name[key] = value;
  return next;
}

export function updateCategory(
  doc: OcsDocument,
  kind: CatKind,
  idx: number,
  field: "name" | "code",
  value: string,
): OcsDocument {
  const next = clone(doc);
  next.ocs_profile.category[kind][idx][field] = value;
  return next;
}

// 就地更新；若該 idx 還不存在（空白虛擬列）則補到該長度再寫。
export function upsertCategory(
  doc: OcsDocument,
  kind: CatKind,
  idx: number,
  field: "name" | "code",
  value: string,
): OcsDocument {
  const next = clone(doc);
  const arr = next.ocs_profile.category[kind];
  while (arr.length <= idx) arr.push({ name: "", code: "" });
  arr[idx][field] = value;
  return next;
}

// 整類取代（D29 表頭選單套用）：把某類的清單換成勾選結果。
export function setCategory(doc: OcsDocument, kind: CatKind, items: CodeName[]): OcsDocument {
  const next = clone(doc);
  next.ocs_profile.category[kind] = items.map((it) => ({
    code: it.code, name: it.name, _id: it._id, _src: it._src, _ref: it._ref,
  }));
  return next;
}

// 切換主基準（D29）：代碼↔名稱綁定一起換（含職類名）；不動工作描述/級別等使用者欄位。
export function setPrimaryBasis(
  doc: OcsDocument,
  basis: { ocs_code: string; occupation_name: string; job_category_name: string },
): OcsDocument {
  const next = clone(doc);
  next.ocs_profile.ocs_code = basis.ocs_code;
  next.ocs_profile.ocs_name.occupation_name = basis.occupation_name;
  next.ocs_profile.ocs_name.job_category_name = basis.job_category_name;
  return next;
}

export function addCategory(doc: OcsDocument, kind: CatKind): OcsDocument {
  const next = clone(doc);
  next.ocs_profile.category[kind].push({ name: "", code: "" });
  return next;
}

export function deleteCategory(doc: OcsDocument, kind: CatKind, idx: number): OcsDocument {
  const next = clone(doc);
  next.ocs_profile.category[kind].splice(idx, 1);
  return next;
}

// ── 說明與補充事項（notes）編輯 ──────────────────────────────────────────────
export type NoteField = "prerequisites" | "supplements";

function ensureNotes(doc: OcsDocument) {
  if (!doc.notes) doc.notes = { prerequisites: [], supplements: [] };
  if (!doc.notes.prerequisites) doc.notes.prerequisites = [];
  if (!doc.notes.supplements) doc.notes.supplements = [];
}

// 整欄取代（D29 表頭選單套用 prerequisites/supplements）。
export function setNotes(doc: OcsDocument, field: NoteField, items: string[]): OcsDocument {
  const next = clone(doc);
  ensureNotes(next);
  next.notes[field] = [...items];
  return next;
}

export function addNote(doc: OcsDocument, field: NoteField): OcsDocument {
  const next = clone(doc);
  ensureNotes(next);
  next.notes[field].push("");
  return next;
}

export function updateNote(doc: OcsDocument, field: NoteField, idx: number, value: string): OcsDocument {
  const next = clone(doc);
  ensureNotes(next);
  next.notes[field][idx] = value;
  return next;
}

export function deleteNote(doc: OcsDocument, field: NoteField, idx: number): OcsDocument {
  const next = clone(doc);
  ensureNotes(next);
  next.notes[field].splice(idx, 1);
  return next;
}

// ── 職責(unit) 層編輯 ─────────────────────────────────────────────────────────
export function addUnit(doc: OcsDocument): OcsDocument {
  const next = clone(doc);
  next.ocs_content.ocu_units.push({
    ocu_code: "",
    ocu_name: "",
    source: { ocs_code: "", occupation_name: "" },
    tasks: [],
    _uid: uid(),
  } as OcuUnit);
  return renumber(next);
}

export function deleteUnit(doc: OcsDocument, ui: number): OcsDocument {
  const next = clone(doc);
  next.ocs_content.ocu_units.splice(ui, 1);
  return renumber(next);
}

export function renameUnit(doc: OcsDocument, ui: number, name: string): OcsDocument {
  const next = clone(doc);
  next.ocs_content.ocu_units[ui].ocu_name = name;
  return next;
}

export function moveUnit(doc: OcsDocument, ui: number, dir: -1 | 1): OcsDocument {
  const next = clone(doc);
  move(next.ocs_content.ocu_units, ui, dir);
  return renumber(next);
}

// ── 任務(task) 層編輯 ─────────────────────────────────────────────────────────
export function addTask(doc: OcsDocument, ui: number): OcsDocument {
  const next = clone(doc);
  next.ocs_content.ocu_units[ui].tasks.push(emptyTask());
  return renumber(next);
}

export function deleteTask(doc: OcsDocument, ui: number, ti: number): OcsDocument {
  const next = clone(doc);
  next.ocs_content.ocu_units[ui].tasks.splice(ti, 1);
  return renumber(next);
}

export function renameTask(doc: OcsDocument, ui: number, ti: number, name: string): OcsDocument {
  const next = clone(doc);
  const tc = next.ocs_content.ocu_units[ui].tasks[ti].task_codes?.[0] ?? { code: "", name: "" };
  tc.name = name;
  next.ocs_content.ocu_units[ui].tasks[ti].task_codes = [tc];
  return next;
}

export function moveTask(doc: OcsDocument, ui: number, ti: number, dir: -1 | 1): OcsDocument {
  const next = clone(doc);
  move(next.ocs_content.ocu_units[ui].tasks, ti, dir);
  return renumber(next);
}

// ── 拖拉用：任意位置搬移 ──────────────────────────────────────────────────────
export function reorderUnits(doc: OcsDocument, from: number, to: number): OcsDocument {
  const next = clone(doc);
  const units = next.ocs_content.ocu_units;
  if (from < 0 || from >= units.length || to < 0 || to >= units.length || from === to) return next;
  const [u] = units.splice(from, 1);
  units.splice(to, 0, u);
  return renumber(next);
}

// 把任務從 (fromUi,fromTi) 搬到 toUi 的 toIndex（toIndex<0 = 接到該職責尾端）。
export function relocateTask(
  doc: OcsDocument,
  fromUi: number,
  fromTi: number,
  toUi: number,
  toIndex: number,
): OcsDocument {
  const next = clone(doc);
  const units = next.ocs_content.ocu_units;
  if (!units[fromUi] || !units[toUi]) return next;
  const [task] = units[fromUi].tasks.splice(fromTi, 1);
  if (!task) return next;
  const dest = units[toUi].tasks;
  const idx = toIndex < 0 || toIndex > dest.length ? dest.length : toIndex;
  dest.splice(idx, 0, task);
  return renumber(next);
}

function ensureBlock(doc: OcsDocument, unitIdx: number, taskIdx: number): CompetencyBlock {
  const task = doc.ocs_content.ocu_units[unitIdx].tasks[taskIdx];
  if (!task.competency_blocks || task.competency_blocks.length === 0) {
    task.competency_blocks = [
      { competency_level: null, indicators: [], outputs: [], knowledge: [], skills: [] },
    ];
  }
  return task.competency_blocks[0];
}

export function getBlock(
  doc: OcsDocument,
  unitIdx: number,
  taskIdx: number,
): CompetencyBlock | undefined {
  return doc.ocs_content?.ocu_units?.[unitIdx]?.tasks?.[taskIdx]?.competency_blocks?.[0];
}

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

// ── 工作筆記 _notes（D28，非契約欄；finalize/export 後端剝除） ────────────────
export function getTaskNotes(doc: OcsDocument, unitIdx: number, taskIdx: number): string {
  return doc.ocs_content?.ocu_units?.[unitIdx]?.tasks?.[taskIdx]?._notes ?? "";
}

export function setTaskNotes(
  doc: OcsDocument,
  unitIdx: number,
  taskIdx: number,
  notes: string,
): OcsDocument {
  const next = clone(doc);
  const task = next.ocs_content?.ocu_units?.[unitIdx]?.tasks?.[taskIdx];
  if (task) {
    if (notes.trim()) task._notes = notes;
    else delete task._notes;
  }
  return next;
}

export function setAttitudes(doc: OcsDocument, items: CodeName[]): OcsDocument {
  const next = clone(doc);
  const list = [...items];
  renumberCoded(list, "A"); // 位置序碼即遞增（A01、A02…）；身分由 _id 維持。
  next.ocs_attitude = { attitudes: list };
  return next;
}

export function completion(doc: OcsDocument): number {
  const units = doc.ocs_content?.ocu_units ?? [];
  const tasks = units.flatMap((u) => u.tasks ?? []);
  const total = 4 * tasks.length + 2;
  let filled = 1; // 表頭固定算 1 格
  if ((doc.ocs_attitude?.attitudes?.length ?? 0) > 0) filled += 1;
  for (const t of tasks) {
    const b = t.competency_blocks?.[0];
    if ((b?.outputs?.length ?? 0) > 0) filled += 1;
    if ((b?.indicators?.length ?? 0) > 0) filled += 1;
    if ((b?.knowledge?.length ?? 0) > 0) filled += 1;
    if ((b?.skills?.length ?? 0) > 0) filled += 1;
  }
  return total > 0 ? filled / total : 0;
}
