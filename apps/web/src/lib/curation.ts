// AI 任務裁剪 ↔ 知識包對位(0028 D1;T7)。純函式:CurationDialog 保持薄。
// 引擎 widget 給 {key:"ocs:task_code", name, unit, quote};這裡對回 pack 的
// tasks/units 池列,組出既有 addFromPool 吃的 PoolPick(同一寫入路徑)。
import type { PoolPick } from "@/lib/ocsDoc";
import { taskRows, unitRows } from "@/lib/pack";
import type { KnowledgePack, OcsDocument, PickerPrecheckItem, SourceRef } from "@/types";

export interface CurationRow {
  key: string;            // "ocs_code:task_code"(引擎的檢查表 key)
  name: string;           // 任務名(pack 池 key;找不到時用引擎給的)
  unit: string;           // 職責名(顯示分組)
  quote: string;          // 引文理由(反盲簽 D4:每列附「你說的那句」)
  srcs: SourceRef[];      // 溯源(SourceLine 顯示;pack 對位而來)
  found: boolean;         // pack 對位成功=可寫入;false=只顯示不可套用
  already?: boolean;      // 已在文件(provenance/名稱對位)→「已加入」鎖定,不可再套
}

function splitKey(key: string): { ocs: string; taskCode: string } {
  const i = key.indexOf(":");
  return i < 0 ? { ocs: key, taskCode: "" }
               : { ocs: key.slice(0, i), taskCode: key.slice(i + 1) };
}

export function buildCurationRows(
  items: PickerPrecheckItem[], pack?: KnowledgePack,
): CurationRow[] {
  const rows = pack ? taskRows(pack) : [];
  return items.map((it) => {
    const { ocs, taskCode } = splitKey(it.key);
    const row = rows.find((r) =>
      r.srcs.some((s) => s.ocs_code === ocs && s.task_code === taskCode));
    return { key: it.key, name: row?.name ?? it.name, unit: it.unit ?? "",
             quote: it.quote, srcs: row?.srcs ?? [], found: !!row };
  });
}

// 已在文件的列標 already(重複添加守衛;對齊編輯器 TaskPickerMenu「已加入」鎖定):
// provenance(ocs_code:task_code,改過名也認得)或任務名相同 → 鎖。
export function markAlreadyInDoc(rows: CurationRow[], doc: OcsDocument): CurationRow[] {
  const prov = new Set<string>();
  const names = new Set<string>();
  for (const u of doc.ocs_content?.ocu_units ?? []) {
    for (const t of u.tasks ?? []) {
      if (t.provenance?.ocs_code && t.provenance?.task_code) {
        prov.add(`${t.provenance.ocs_code}:${t.provenance.task_code}`);
      }
      const nm = t.task_codes?.[0]?.name;
      if (nm) names.add(nm);
    }
  }
  return rows.map((r) =>
    prov.has(r.key) || names.has(r.name) ? { ...r, already: true } : r);
}

// 勾選列 → PoolPick[](按職責分組;職責 srcs 由 unit 池對位,對不上以 ownTaskKeys 反查)。
export function picksFromRows(rows: CurationRow[], pack: KnowledgePack): PoolPick[] {
  const units = unitRows(pack);
  const byUnit = new Map<string, PoolPick>();
  for (const r of rows) {
    if (!r.found || r.already) continue;
    const unitRow = units.find((u) => u.name === r.unit)
      ?? units.find((u) => u.ownTaskKeys.includes(r.name));
    const uname = unitRow?.name ?? (r.unit || "公司自訂職責");
    const pick = byUnit.get(uname)
      ?? { unit: { name: uname, srcs: unitRow?.srcs ?? [] }, tasks: [] };
    const { ocs, taskCode } = splitKey(r.key);
    pick.tasks.push({ name: r.name, srcs: r.srcs,
                      provenance: { ocs_code: ocs, task_code: taskCode } });
    byUnit.set(uname, pick);
  }
  return [...byUnit.values()];
}
