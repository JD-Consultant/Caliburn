// 訪談建議 → 文件套用(T12;ADR 0025「套用由前端以既有寫入路徑執行」)。
// Path 文法與後端 executor/diff 同族:段以 `.` 連接;list 段用穩定 id(_tid/_uid/_id)
// 或 index。純函式、回新物件(給 autosave commit(next) 用)。
// add_task:/add_duty: 前綴的建議不在此自動套(重編碼是 ocsDoc.renumber 的職權,
// 由使用者經選單/表格加入)——applyAccepted 將其分流到 manual 清單。
import type { OcsDocument } from "@/types";

const STABLE_ID_KEYS = ["_tid", "_uid", "_id"] as const;

type Node = Record<string, unknown> | unknown[] | unknown;

function stepInto(node: Node, seg: string): Node | undefined {
  if (Array.isArray(node)) {
    for (const item of node) {
      if (item && typeof item === "object") {
        const rec = item as Record<string, unknown>;
        if (STABLE_ID_KEYS.some((k) => String(rec[k] ?? "") === seg)) return item;
      }
    }
    const idx = Number(seg);
    return Number.isInteger(idx) ? node[idx] : undefined;
  }
  if (node && typeof node === "object") {
    return (node as Record<string, unknown>)[seg];
  }
  return undefined;
}

export function getAtPath(doc: OcsDocument, path: string): unknown {
  let node: Node = doc as unknown as Node;
  for (const seg of path.split(".")) {
    node = stepInto(node, seg);
    if (node === undefined) return undefined;
  }
  return node;
}

/** 葉寫入;`…<task>.details.<slot>` 的 details 缺殼自動建。回新文件;path 無效回 null。 */
export function setAtPath(doc: OcsDocument, path: string, value: unknown): OcsDocument | null {
  const next = structuredClone(doc);
  const segs = path.split(".");
  let node: Node = next as unknown as Node;
  for (let i = 0; i < segs.length - 1; i++) {
    let child = stepInto(node, segs[i]);
    if (child === undefined) {
      // 只容許 details 缺殼:當前段是 "details" 且 parent 是物件(task)
      if (segs[i] === "details" && node && typeof node === "object" && !Array.isArray(node)) {
        child = {};
        (node as Record<string, unknown>)["details"] = child;
      } else {
        return null;
      }
    }
    node = child;
  }
  if (!node || typeof node !== "object" || Array.isArray(node)) return null;
  (node as Record<string, unknown>)[segs[segs.length - 1]] = value;
  return next;
}

export interface AcceptedSuggestion { doc_path: string; new_value: unknown }

export interface ApplyResult {
  doc: OcsDocument;                    // 套用後文件(=原件若無變)
  applied: string[];                   // 成功套用的 path
  manual: AcceptedSuggestion[];        // add_task:/add_duty:(請使用者用選單加入)
  failed: string[];                    // path 無效(文件已被改走)
}

export function applyAccepted(
  doc: OcsDocument,
  accepted: AcceptedSuggestion[],
): ApplyResult {
  let cur = doc;
  const applied: string[] = [];
  const manual: AcceptedSuggestion[] = [];
  const failed: string[] = [];
  for (const s of accepted) {
    if (s.doc_path.startsWith("add_task:") || s.doc_path.startsWith("add_duty:")) {
      manual.push(s);
      continue;
    }
    const next = setAtPath(cur, s.doc_path, s.new_value);
    if (next === null) failed.push(s.doc_path);
    else { cur = next; applied.push(s.doc_path); }
  }
  return { doc: cur, applied, manual, failed };
}
