// 訪談建議 → 文件套用(T12;ADR 0025「套用由前端以既有寫入路徑執行」)。
// Path 文法與後端 executor/diff 同族:段以 `.` 連接;list 段用穩定 id(_tid/_uid/_id)
// 或 index。純函式、回新物件(給 autosave commit(next) 用)。
// add_task:/add_duty: 前綴的建議核准即落地——走 ocsDoc.addCustomTask/addCustomDuty
// (renumber 是前端職權;RC4:不再丟回給使用者自己加)。
import { addCustomDuty, addCustomTask } from "@/lib/ocsDoc";
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

// v2 書記自訂項落點:能力區塊 K/S/O/P 與文件層態度=**append 到陣列**(非覆蓋)
const ARRAY_FIELDS = ["knowledge", "skills", "outputs", "indicators", "attitudes"] as const;

/** append 到陣列型欄位(競能區塊/態度);陣列缺殼自動建。回新文件;parent 無效回 null。 */
export function appendAtPath(doc: OcsDocument, path: string, item: unknown): OcsDocument | null {
  const next = structuredClone(doc);
  const segs = path.split(".");
  let node: Node = next as unknown as Node;
  for (let i = 0; i < segs.length - 1; i++) {
    node = stepInto(node, segs[i]);
    if (node === undefined) return null;
  }
  if (!node || typeof node !== "object") return null;
  const rec = node as Record<string, unknown>;
  const last = segs[segs.length - 1];
  const arr = rec[last];
  if (Array.isArray(arr)) arr.push(item);
  else if (arr === undefined) rec[last] = [item];
  else return null;
  return next;
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
  applied: string[];                   // 成功套用的 path / add_* 標記
  failed: string[];                    // slot path 無效(文件已被改走)
}

export function applyAccepted(
  doc: OcsDocument,
  accepted: AcceptedSuggestion[],
): ApplyResult {
  let cur = doc;
  const applied: string[] = [];
  const failed: string[] = [];
  for (const s of accepted) {
    if (s.doc_path.startsWith("add_task:")) {
      const v = (s.new_value ?? {}) as { unit_ref?: string; name?: string };
      cur = addCustomTask(cur, v.unit_ref ?? "", v.name ?? s.doc_path.slice("add_task:".length));
      applied.push(s.doc_path);
      continue;
    }
    if (s.doc_path.startsWith("add_duty:")) {
      const v = (s.new_value ?? {}) as { name?: string };
      cur = addCustomDuty(cur, v.name ?? s.doc_path.slice("add_duty:".length));
      applied.push(s.doc_path);
      continue;
    }
    // v2:自訂能力項/態度 → append 到陣列(doc_path 末段是陣列型欄位);其餘=葉寫入
    const last = s.doc_path.split(".").pop() ?? "";
    const isArrayField = (ARRAY_FIELDS as readonly string[]).includes(last);
    const next = isArrayField
      ? appendAtPath(cur, s.doc_path, s.new_value)
      : setAtPath(cur, s.doc_path, s.new_value);
    if (next === null) failed.push(s.doc_path);
    else { cur = next; applied.push(s.doc_path); }
  }
  return { doc: cur, applied, failed };
}
