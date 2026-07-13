// 側欄 UI 純邏輯(T9;ADR 0030 §6.5)——放 lib 供 vitest(元件層無 DOM 測試環境)。

// ── 議程三態(+boundary 劃線) ────────────────────────────────────────────────
export type AgendaState = "pending" | "in_progress" | "completed" | "boundary";
export interface AgendaItem { key: string; label: string; state: AgendaState }

// update_plan 樣式:✓ 完成(淡)/▸ 進行中(粗)/○ 待進行/— 劃線不談(刪除線)。
export const AGENDA_GLYPH: Record<AgendaState, string> = {
  completed: "✓", in_progress: "▸", pending: "○", boundary: "—",
};

export function agendaCounts(items: AgendaItem[]): { done: number; total: number } {
  const scored = items.filter((i) => i.state !== "boundary");   // 劃線不計分母
  return { done: scored.filter((i) => i.state === "completed").length, total: scored.length };
}

// ── chips(AskUserQuestion 樣式):推薦優先排序+永遠可自由輸入 ────────────────
export interface ChipOption { label: string; recommended: boolean }

export function chipOptions(options: string[], recommended?: string | null): ChipOption[] {
  const chips = options.map((o) => ({ label: o, recommended: o === recommended }));
  chips.sort((a, b) => Number(b.recommended) - Number(a.recommended));  // 推薦排前(穩定)
  return chips;
}

// ── 「正在整理…」判定:鏡像後端喚醒閘 worth_scribing(明顯無素材就不顯示) ──
const META_PHRASES = new Set([
  "跳過", "沒有", "下一題", "好", "嗯", "ok", "okay", "沒了", "對",
  "是", "不是", "謝謝", "hi", "hello", "嗨", "你好",
]);

export function hasMaterial(text: string): boolean {
  const t = (text ?? "").trim().toLowerCase();
  if (!t || META_PHRASES.has(t)) return false;
  return t.length >= 6 || /\d/.test(t);
}

// ── 職類建議卡(0031 A 案):widget→卡片項的窄化(空/畸形項過濾) ──────────────
import type { OccPrecheckItem, OpenPickerWidget } from "@/types";

export function occSuggestions(w: OpenPickerWidget | null | undefined): OccPrecheckItem[] {
  if (!w || w.kind !== "open_picker" || w.picker !== "occupation") return [];
  return (w.precheck ?? []).filter(
    (p): p is OccPrecheckItem =>
      typeof (p as OccPrecheckItem).code === "string" && !!(p as OccPrecheckItem).code,
  );
}

// ── 打字機動畫(體感字元級 streaming;點擊即全顯) ────────────────────────────
export const TYPEWRITER_CHARS_PER_TICK = 3;

export function typewriterSlice(text: string, tick: number): string {
  return text.slice(0, tick * TYPEWRITER_CHARS_PER_TICK);
}

export function typewriterDone(text: string, tick: number): boolean {
  return tick * TYPEWRITER_CHARS_PER_TICK >= text.length;
}
