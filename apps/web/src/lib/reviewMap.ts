// 追蹤修訂映射(0028 D7;T8):interview evidence(review=pending)→ 文件格標記。
// 「AI 直寫在**同格**以追蹤修訂樣式呈現」的資料源;人改的格無 evidence 即無標記。
// path 文法鏡像後端 ledger/executor:list 段=穩定 id(_uid/_tid)優先、index 後援
// ——所以每任務給**兩形 prefix** 都試。

export interface ReviewMark { quote: string }

export interface EvidenceRow {
  doc_path: string; quote: string; turn_seq: number; verified: boolean; review: string;
}

// 11 細項槽標籤(鏡像 apps/api app/interview/slots.py 的 SLOT_DEFS;改那邊要同步這邊)
export const DETAIL_SLOT_LABELS: Record<string, string> = {
  frequency: "頻率", time_share_pct: "工作比重", duration: "單次耗時",
  volume: "數量批次", trigger: "觸發條件", inputs: "準備材料", tools: "工具系統",
  collaborators: "協作對象", wait_points: "等待瓶頸", exceptions: "例外處理",
  standards: "完成標準",
};

export function buildReviewMap(evidence: EvidenceRow[]): Map<string, ReviewMark> {
  const m = new Map<string, ReviewMark>();
  for (const e of evidence) {
    if (e.review === "pending") m.set(e.doc_path, { quote: e.quote });
  }
  return m;
}

export type CellKindKey = "outputs" | "indicators" | "knowledge" | "skills";

export interface TaskMarks {
  details: Record<string, ReviewMark>;          // slot key → mark
  cells: Partial<Record<CellKindKey, ReviewMark>>;
}

const CELL_RE = /^competency_blocks\.\d+\.(outputs|indicators|knowledge|skills)/;

// prefixes = 該任務的候選 path 前綴(uid 形 + index 形);掃 map 分類到 details/cells。
export function taskMarks(map: Map<string, ReviewMark>, prefixes: string[]): TaskMarks {
  const out: TaskMarks = { details: {}, cells: {} };
  for (const [path, mark] of map) {
    const pre = prefixes.find((p) => path.startsWith(p + "."));
    if (!pre) continue;
    const rest = path.slice(pre.length + 1);
    if (rest.startsWith("details.")) {
      out.details[rest.slice("details.".length)] = mark;
    } else {
      const m = CELL_RE.exec(rest);
      if (m) out.cells[m[1] as CellKindKey] = mark;
    }
  }
  return out;
}
