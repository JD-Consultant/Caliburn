// D27 OCS 文件的就地（immutable）更新與完成度計算。每任務一個 competency_block
// → 都讀寫 competency_blocks[0]。完成度公式對齊後端 compute_completion：
// filled = 1(表頭) + (A?1:0) + Σ_task[(O>0)+(P>0)+(K>0)+(S>0)]；total = 4*任務數 + 2。
import type { CodeName, CompetencyBlock, Indicator, OcsDocument } from "@/types";

function clone(doc: OcsDocument): OcsDocument {
  return structuredClone(doc);
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
  block.outputs = outputs;
  block.indicators = indicators;
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
  block[field] = items;
  return next;
}

export function setAttitudes(doc: OcsDocument, items: CodeName[]): OcsDocument {
  const next = clone(doc);
  next.ocs_attitude = { attitudes: items };
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
