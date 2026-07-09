// AI 任務盤(0028 D1;D9 資料源收斂)。純函式:CurationDialog 保持薄。
// **盤=編輯器知識包**(unitRows/taskRows 全量,同 UnitPicker/TaskPickerMenu 的宇宙),
// **後端只送 AI 疊加層**(precheck:{key:"ocs:task_code", quote});清單不再由後端組
// (ADR 0021:知識包=所有選單的資料源)。身分機制全借編輯器:任務=URN(taskUrns,
// 改過名也認得)、職責=名稱、寫入=addFromPool(單一寫入路徑)。
import type { PoolPick } from "@/lib/ocsDoc";
import { taskHasContent } from "@/lib/ocsDoc";
import { taskRows, unitRows, type TaskRowVM } from "@/lib/pack";
import { taskUrns } from "@/lib/urn";
import type { KnowledgePack, OcsDocument, PickerPrecheckItem, SourceRef } from "@/types";

export interface BoardTaskRow {
  name: string;            // tasks 池 key(與 TaskPickerMenu 同列)
  unit: string;            // 所屬職責(own;合併列跨職責只列首個 own 職責下一次)
  srcs: SourceRef[];
  prechecked: boolean;     // AI 預勾
  quote: string;           // AI 引文理由(反盲簽 D4;空字串=不顯示)
  already: boolean;        // 已在文件(URN 對位)→ 鎖「已加入」不可再套
  filled: boolean;         // 已在文件且已填內容(顯示用)
}

export interface BoardDutyRow {
  unit: string;
  srcs: SourceRef[];       // 職責來源(addFromPool 的 unit srcs)
  total: number;           // 官方任務數
  prechecked: number;      // 其中 AI 預勾數
  already: number;         // 其中已在文件數
  inDoc: boolean;          // 職責本身已在文件(名稱對位=UnitPickerMenu 同機制)
  defaultOn: boolean;      // 步1 預設勾(=有 AI 預勾任務)
}

export interface CurationBoard { duties: BoardDutyRow[]; tasks: BoardTaskRow[] }

function splitKey(key: string): { ocs: string; taskCode: string } {
  const i = key.indexOf(":");
  return i < 0 ? { ocs: key, taskCode: "" }
               : { ocs: key.slice(0, i), taskCode: key.slice(i + 1) };
}

// 全盤組裝:pack 全部職責(池序=職位優先序)→ 各職責自己的官方任務;precheck 以 key
// 對位疊加(pack 未載/過舊對不上的項忽略——pack 是 memo 依賴,重抓到後自然浮現)。
export function buildBoard(
  precheck: PickerPrecheckItem[], pack: KnowledgePack | undefined, doc: OcsDocument,
): CurationBoard {
  if (!pack) return { duties: [], tasks: [] };
  const byName = new Map(taskRows(pack).map((r) => [r.name, r]));
  // 文件內任務 URN → 已填?(TaskPickerMenu urnLoc 同機制;守衛對「當前文件」算 §16.18)
  const urnFilled = new Map<string, boolean>();
  for (const u of doc.ocs_content?.ocu_units ?? []) {
    for (const t of u.tasks ?? []) {
      const filled = taskHasContent(t);
      for (const urn of taskUrns(t)) urnFilled.set(urn, filled);
    }
  }
  const preOf = (row: TaskRowVM) =>
    precheck.find((p) => {
      const { ocs, taskCode } = splitKey(p.key);
      return row.srcs.some((s) => s.ocs_code === ocs && s.task_code === taskCode);
    });
  const docUnitNames = new Set(
    (doc.ocs_content?.ocu_units ?? []).map((u) => u.ocu_name));

  const duties: BoardDutyRow[] = [];
  const tasks: BoardTaskRow[] = [];
  const seen = new Set<string>();
  for (const u of unitRows(pack)) {
    const duty: BoardDutyRow = {
      unit: u.name, srcs: u.srcs, total: 0, prechecked: 0, already: 0,
      inDoc: docUnitNames.has(u.name), defaultOn: false,
    };
    for (const key of u.ownTaskKeys) {
      if (seen.has(key)) continue;
      const row = byName.get(key);
      if (!row) continue;
      seen.add(key);
      const hit = row.urns.map((urn) => urnFilled.get(urn)).find((v) => v !== undefined);
      const pre = preOf(row);
      duty.total += 1;
      if (pre) { duty.prechecked += 1; duty.defaultOn = true; }
      if (hit !== undefined) duty.already += 1;
      tasks.push({ name: row.name, unit: u.name, srcs: row.srcs,
                   prechecked: !!pre, quote: pre?.quote ?? "",
                   already: hit !== undefined, filled: hit === true });
    }
    duties.push(duty);
  }
  return { duties, tasks };
}

// 勾選列 → PoolPick[](addFromPool 吃;按職責分組)。provenance 規則同 TaskPickerMenu
// pickOf:優先取「與本職責同職業」的來源;already 列跳過(重複添加守衛)。
export function picksFromBoard(rows: BoardTaskRow[], board: CurationBoard): PoolPick[] {
  const dutyOf = new Map(board.duties.map((d) => [d.unit, d]));
  const byUnit = new Map<string, PoolPick>();
  for (const r of rows) {
    if (r.already) continue;
    const duty = dutyOf.get(r.unit);
    const unitOcc = duty?.srcs?.[0]?.ocs_code ?? "";
    const pref = r.srcs.find((s) => s.ocs_code === unitOcc) ?? r.srcs[0];
    const pick = byUnit.get(r.unit)
      ?? { unit: { name: r.unit, srcs: duty?.srcs ?? [] }, tasks: [] };
    pick.tasks.push({
      name: r.name, srcs: r.srcs,
      provenance: { ocs_code: pref?.ocs_code ?? "", task_code: pref?.task_code ?? "" },
    });
    byUnit.set(r.unit, pick);
  }
  return [...byUnit.values()];
}
