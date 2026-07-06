// D27 OCS 文件的就地（immutable）更新與完成度計算。每任務一個 competency_block
// → 都讀寫 competency_blocks[0]。完成度公式對齊後端 compute_completion：
// filled = 1(表頭) + (A?1:0) + Σ_task[(O>0)+(P>0)+(K>0)+(S>0)]；total = 4*任務數 + 2。
import type { CodeName, CompetencyBlock, Indicator, NoteItem, OcsDocument, OcsTask, OcuUnit, SourceRef } from "@/types";

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

// A4（ocs-schema「文件層級去重」）：K/S 碼以 name 為 key 全文件共用——首現給號、
// 同名共碼、空名各給新號；身分仍看 _id/_ref（碼共用、身分各自）。O/P 維持任務範圍、
// A 維持全域（renumberCoded）。任何 K/S 內容變動與結構變動（renumber）都要重跑。
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

// 唯一重編點:所有位置碼(職責 T#、任務 T#.#、O/P 任務範圍、態度 A、文件級 K/S)
// 都在這裡依當前位置重寫;冪等,結構變動與內容編輯的 setter 收尾都走這裡,
// 「漏重編」類 bug 結構上不可能發生。名稱/區塊/provenance/_id 不動。
function renumber(doc: OcsDocument): OcsDocument {
  const units = doc.ocs_content?.ocu_units ?? [];
  units.forEach((u, ui) => {
    u.ocu_code = `T${ui + 1}`;
    (u.tasks ?? []).forEach((t, ti) => {
      const tc = t.task_codes?.[0] ?? { code: "", name: "" };
      tc.code = `T${ui + 1}.${ti + 1}`;
      t.task_codes = [tc, ...(t.task_codes ?? []).slice(1)];
      const b = t.competency_blocks?.[0];
      if (b) {
        // O/P 是任務範圍位置碼:任務位置變了要跟著重編(身分由 _id 維持)
        renumberCoded(b.outputs ?? [], `O${ui + 1}.${ti + 1}.`);
        renumberCoded(b.indicators ?? [], `P${ui + 1}.${ti + 1}.`);
      }
    });
  });
  renumberCoded(doc.ocs_attitude?.attitudes ?? [], "A"); // 態度全域位置碼(A01…)
  for (const f of ["prerequisites", "supplements"] as const) {
    const rows = doc.notes?.[`_${f}`];
    if (rows) {
      rows.forEach((r, i) => { r.code = `n${i + 1}`; }); // n 碼不補零(spec 2026-07-04)
      doc.notes[f] = rows.map((r) => r.text).filter(Boolean); // 契約欄 string[] = 影子列投影
    }
  }
  renumberDocKS(doc); // K/S 首現序隨任務順序變，一併重編
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

export function setOcsLevel(
  doc: OcsDocument,
  value: string,
  src?: SourceRef & { level: number },
): OcsDocument {
  const next = clone(doc);
  const n = parseInt(value, 10);
  next.ocs_profile.ocs_level = Number.isFinite(n) ? n : null;
  if (src) next.ocs_profile._levelSrc = src; // 值==官方值即官方(spec §9 決策 6)
  else delete next.ocs_profile._levelSrc;
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

// 再點已選基準=整組清空(spec 2026-07-04 §9 決策 4):代碼↔名稱綁定一起進出;
// 級別/描述/類別不動(_levelSrc 保留=歷史來源)。
export function clearPrimaryBasis(doc: OcsDocument): OcsDocument {
  const next = clone(doc);
  next.ocs_profile.ocs_code = "";
  next.ocs_profile.ocs_name.occupation_name = "";
  next.ocs_profile.ocs_name.job_category_name = "";
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

// ── 說明與補充事項（notes）編輯──影子列為唯一真相（spec 2026-07-04 §3）:
// notes._<field> 存 NoteItem 物件列,契約欄 string[] 由 renumber 導出;
// finalize/export 剝 `_` 後契約乾淨(後端零改動)。
export type NoteField = "prerequisites" | "supplements";

export function setNoteItems(doc: OcsDocument, field: NoteField, items: NoteItem[]): OcsDocument {
  const next = clone(doc);
  if (!next.notes) next.notes = { prerequisites: [], supplements: [] };
  next.notes[`_${field}`] = items.map((it) => ({ ...it })); // 拷貝:不污染呼叫端(cache 舊快照)
  return renumber(next); // n 碼重編 + 契約欄導出都在 renumber(單一重編點)
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
  const unit = next.ocs_content.ocu_units[ui];
  if (unit.ocu_name === name) return next;
  unit.ocu_name = name;
  // 改名=斷鏈變自訂(spec 2026-07-04 §5;與 OPKS「改內容→自訂」一致;底下任務身分不受影響)
  delete unit._refs;
  unit.source = { ocs_code: "", occupation_name: "" };
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

// ── 批次入文件（P3 前端寫入路徑；spec 資料流決策①：單一寫入路徑＝前端編輯+PATCH）──
// 職責以 ocu_name 併入既有列（同 key 不重建），任務 append；provenance＝首個來源、
// _refs＝全部來源（合併列雙來源引用）；最後 renumber（位置碼 + A4 文件級 K/S）。
export interface PoolPick {
  unit: { name: string; srcs: SourceRef[] };
  tasks: { name: string; srcs: SourceRef[]; provenance: { ocs_code: string; task_code: string } }[];
}

function taskFromPool(t: PoolPick["tasks"][number]): OcsTask {
  const task: OcsTask = {
    task_codes: [{ code: "", name: t.name }],
    competency_blocks: [emptyBlock()],
    provenance: { ocs_code: t.provenance.ocs_code, task_code: t.provenance.task_code },
    _tid: uid(),
  };
  if (t.srcs.length) task._refs = t.srcs;
  return task;
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
    for (const t of pick.tasks) unit.tasks.push(taskFromPool(t));
  }
  return renumber(next);
}

// 往既有職責(by index)加池任務——每職責列「選任務 ▾」(P3 UI 修訂:表格中心,
// 職責先入表格、任務再從列上挑;不走名字對位,避免改過名的職責被誤判)。
export function addTasksToUnit(doc: OcsDocument, ui: number, tasks: PoolPick["tasks"]): OcsDocument {
  const next = clone(doc);
  const unit = next.ocs_content.ocu_units[ui];
  if (!unit) return next;
  for (const t of tasks) unit.tasks.push(taskFromPool(t));
  return renumber(next);
}

// 訪談抓漏核准 → 前端落地(ADR 0025 不變量2:人核准的建議=人的寫入,由前端套用;
// 重編碼是前端 renumber 職權)。RC4:原本核准後丟 manual 叫使用者自己去「選任務▾」加,
// 找不到=體驗斷裂;現在核准即落地。unit_ref 是 LLM 給的參照(_uid/顯示碼/職責名任一),
// 對不上就開一個自訂職責掛上,核准的任務絕不消失。
export function addCustomTask(doc: OcsDocument, unitRef: string, name: string): OcsDocument {
  const next = clone(doc);
  const units = next.ocs_content.ocu_units;
  let unit = units.find(
    (u) => u._uid === unitRef || u.ocu_code === unitRef || u.ocu_name === unitRef,
  );
  if (!unit) {
    unit = {
      ocu_code: "", ocu_name: unitRef || "公司自訂職責",
      source: { ocs_code: "", occupation_name: "" }, tasks: [], _uid: uid(),
    } as OcuUnit;
    units.push(unit);
  }
  const t = emptyTask();
  t.task_codes = [{ code: "", name }];   // 自訂任務(provenance 留空;renumber 給位置碼)
  unit.tasks.push(t);
  return renumber(next);
}

// 訪談抓漏的新職責:一律開自訂職責(公版外;renumber 給 T{n} 位置碼)。
export function addCustomDuty(doc: OcsDocument, name: string): OcsDocument {
  const next = clone(doc);
  next.ocs_content.ocu_units.push({
    ocu_code: "", ocu_name: name || "公司自訂職責",
    source: { ocs_code: "", occupation_name: "" }, tasks: [], _uid: uid(),
  } as OcuUnit);
  return renumber(next);
}

// 任務是否已有內容(四格/級別/筆記)——選單「取消勾選=移除」的鎖定判定:
// 有內容的任務不能從選單移除,只能在表格刪(防誤刪已填資料)。
export function taskHasContent(task: OcsTask): boolean {
  const b = task.competency_blocks?.[0];
  return !!(
    (b?.outputs?.length ?? 0) || (b?.indicators?.length ?? 0) ||
    (b?.knowledge?.length ?? 0) || (b?.skills?.length ?? 0) ||
    b?.competency_level != null || task._notes
  );
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
  // 淺拷貝每個 item:renumber 就地改 code,不可污染呼叫端(cache 舊快照)的物件。
  block.outputs = outputs.map((o) => ({ ...o }));
  block.indicators = indicators.map((i) => ({ ...i }));
  return renumber(next);
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
  block[field] = items.map((it) => ({ ...it }));
  return renumber(next);
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

// 設定單一任務的級別（competency_block.competency_level）。空字串→null。
// src 有值時（帶官方）一併記下任務的官方級別來源 _levelSrc（含任務；export 剝除）。
export function setTaskLevel(
  doc: OcsDocument,
  unitIdx: number,
  taskIdx: number,
  value: number | string | null,
  src?: SourceRef & { level: number },
): OcsDocument {
  const next = clone(doc);
  const block = ensureBlock(next, unitIdx, taskIdx);
  if (value === null || value === "") block.competency_level = null;
  else {
    const n = typeof value === "number" ? value : parseInt(value, 10);
    block.competency_level = Number.isFinite(n) ? n : null;
  }
  const t = next.ocs_content.ocu_units[unitIdx].tasks[taskIdx];
  if (src) t._levelSrc = src;
  else delete t._levelSrc; // 值≠官方 → 來源清掉(spec §2:不留殘留)
  return next;
}

export function setAttitudes(doc: OcsDocument, items: CodeName[]): OcsDocument {
  const next = clone(doc);
  next.ocs_attitude = { attitudes: items.map((it) => ({ ...it })) }; // 拷貝再交給 renumber 給碼
  return renumber(next);
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
