// T9:側欄純邏輯——議程三態、chips 推薦排序、正在整理判定、打字機切片、職類建議卡窄化。
import { describe, expect, it } from "vitest";
import {
  AGENDA_GLYPH, agendaCounts, chipOptions, hasMaterial, occSuggestions,
  typewriterDone, typewriterSlice, type AgendaItem,
} from "./interviewUi";
import type { OpenPickerWidget } from "@/types";

describe("職類建議卡窄化(0031)", () => {
  it("occupation+precheck → 項目;task/畸形項 → 空", () => {
    const w: OpenPickerWidget = {
      kind: "open_picker", picker: "occupation", query: "全端",
      precheck: [{ code: "INM3514-001v4", name: "網站前端開發人員", reason: "依你描述" }],
    };
    expect(occSuggestions(w)).toHaveLength(1);
    expect(occSuggestions({ ...w, picker: "task" })).toEqual([]);
    expect(occSuggestions({ ...w, precheck: undefined })).toEqual([]);
    expect(occSuggestions(null)).toEqual([]);
  });
});

const ITEMS: AgendaItem[] = [
  { key: "t1", label: "回歸測試", state: "completed" },
  { key: "t2", label: "缺陷分析", state: "in_progress" },
  { key: "t3", label: "報表", state: "pending" },
  { key: "t4", label: "薪資", state: "boundary" },
];

describe("議程三態", () => {
  it("四態各有 glyph;boundary 不進完成分母", () => {
    expect(ITEMS.map((i) => AGENDA_GLYPH[i.state])).toEqual(["✓", "▸", "○", "—"]);
    expect(agendaCounts(ITEMS)).toEqual({ done: 1, total: 3 });
  });
});

describe("chips 推薦標記", () => {
  it("推薦選項排最前且標記 recommended", () => {
    const chips = chipOptions(["每天", "每週", "每月"], "每週");
    expect(chips[0]).toEqual({ label: "每週", recommended: true });
    expect(chips.map((c) => c.label)).toEqual(["每週", "每天", "每月"]);
  });
  it("無推薦=保序、全不標", () => {
    const chips = chipOptions(["A", "B"]);
    expect(chips.map((c) => c.label)).toEqual(["A", "B"]);
    expect(chips.every((c) => !c.recommended)).toBe(true);
  });
});

describe("正在整理判定(鏡像喚醒閘)", () => {
  it("meta/寒暄不顯示;有素材才顯示", () => {
    expect(hasMaterial("跳過")).toBe(false);
    expect(hasMaterial("ok")).toBe(false);
    expect(hasMaterial("")).toBe(false);
    expect(hasMaterial("30%")).toBe(true);
    expect(hasMaterial("每天要對三條產線做首件檢查")).toBe(true);
  });
});

describe("打字機(點擊跳過=直接取全文)", () => {
  it("逐 tick 增字、tick 足夠即完成", () => {
    const text = "一二三四五六七八九十";
    expect(typewriterSlice(text, 1).length).toBeLessThan(text.length);
    expect(typewriterSlice(text, 100)).toBe(text);
    expect(typewriterDone(text, 1)).toBe(false);
    expect(typewriterDone(text, 100)).toBe(true);
  });
});
