import { describe, expect, it } from "vitest";
import { isOfficialBasis, noteRowsFromStrings, packSrcToRef, primaryDefaults } from "./pack";
import type { KnowledgePack } from "@/types";

describe("packSrcToRef", () => {
  it("帶上 ocu_code(職責身分對位;spec 2026-07-04 §6)", () => {
    const ref = packSrcToRef({
      ocs_code: "OC1", ocs_name: "甲職業", ocu_code: "T2", ocu_name: "維護",
      task_code: "T2.3", task_name: "保養", code: "K07", competency_level: 4,
    });
    expect(ref).toEqual({
      ocs_code: "OC1", occupation_name: "甲職業", code: "K07",
      ocu_code: "T2", task_code: "T2.3", task_name: "保養",
    });
  });
  it("缺欄位時 ocu_code/task_code 為 undefined、code 為空字串", () => {
    const ref = packSrcToRef({ ocs_code: "OC1", ocs_name: "甲職業" });
    expect(ref.code).toBe("");
    expect(ref.ocu_code).toBeUndefined();
    expect(ref.task_code).toBeUndefined();
  });
});

describe("primaryDefaults / isOfficialBasis(spec 2026-07-04 §4)", () => {
  const opts = [
    { code: "", name: "甲", srcs: [{ ocs_code: "OC1", occupation_name: "甲職", code: "n1" }] },
    { code: "", name: "乙", srcs: [{ ocs_code: "OC2", occupation_name: "乙職", code: "n1" }] },
    { code: "", name: "丙", srcs: [
      { ocs_code: "OC2", occupation_name: "乙職", code: "n2" },
      { ocs_code: "OC1", occupation_name: "甲職", code: "n2" },
    ] },
  ];
  it("篩出 srcs 含主基準碼的選項(不重排)", () => {
    expect(primaryDefaults(opts, "OC1").map((o) => o.name)).toEqual(["甲", "丙"]);
  });
  it("isOfficialBasis:只認 occupation_details 裡的 code", () => {
    const pack = { occupation_details: [{ ocs_code: "OC1" }] } as unknown as KnowledgePack;
    expect(isOfficialBasis(pack, "OC1")).toBe(true);
    expect(isOfficialBasis(pack, "自訂碼")).toBe(false);
    expect(isOfficialBasis(pack, "")).toBe(false);
  });
});

describe("noteRowsFromStrings(舊 draft 遷移,spec §3)", () => {
  it("命中池→official+_ref(首來源);未命中→custom;顯示碼照序", () => {
    const pool = { 大學以上: { srcs: [{ ocs_code: "OC1", ocs_name: "甲職", code: "n1" }] } };
    const rows = noteRowsFromStrings(["大學以上", "自己打的"], pool);
    expect(rows[0]).toMatchObject({ code: "n1", text: "大學以上", _src: "official" });
    expect(rows[0]._ref).toMatchObject({ ocs_code: "OC1", code: "n1" });
    expect(rows[1]).toMatchObject({ code: "n2", text: "自己打的", _src: "custom" });
    expect(rows[0]._id).toBeTruthy();
  });
});

// ── 相似比對(ADR 0022):render-only 顯示變換 ──────────────────────────────────
import { groupedValueOptions, taskRowsWithSimilar } from "./pack";
import type { MatchResult, OptionItem } from "@/types";

const opt = (name: string, ocs: string): OptionItem =>
  ({ code: "", name, srcs: [{ ocs_code: ocs, occupation_name: ocs, code: "A1" }] });
const mkMatch = (ids: string[][]): MatchResult => ({
  groups: ids.map((g) => ({ medoid: g[0], members: g.map((id) => ({ id, score: 0.93 })) })),
  possible_matches: [],
  config: { kind: "attitude", theta_high: 0.9, theta_low: 0.7, model: "bge-m3" },
});

describe("groupedValueOptions(spec §4)", () => {
  const flat = [opt("團隊合作", "OC1"), opt("團隊意識", "OC2"), opt("持續學習", "OC3")];

  it("match 缺席 → 原樣返回(降級 = 逐位元同現狀)", () => {
    expect(groupedValueOptions(flat, undefined, "OC1")).toEqual(flat);
  });

  it("survivorship:主基準成員在群內必為代表;其餘進 variants(不變量 B)", () => {
    const out = groupedValueOptions(flat, mkMatch([["團隊合作", "團隊意識"]]), "OC2");
    expect(out).toHaveLength(2);
    expect(out[0].name).toBe("團隊意識");                 // OC2 = 主基準 → 代表
    expect(out[0].variants?.map((v) => v.name)).toEqual(["團隊合作"]);
  });

  it("主基準不在群內 → 文字最長當代表(tie → 名稱升序)", () => {
    const out = groupedValueOptions(flat, mkMatch([["團隊合作", "團隊意識"]]), "OC9");
    expect(out[0].name).toBe("團隊合作");                 // 等長 → 升序取先
  });

  it("代表列就是成員本人(身分不變),池序保持,群外選項原位", () => {
    const out = groupedValueOptions(flat, mkMatch([["團隊合作", "團隊意識"]]), "OC1");
    expect(out[0]).toMatchObject({ name: "團隊合作", srcs: flat[0].srcs });  // 真身
    expect(out[1].name).toBe("持續學習");
  });

  it("群成員對不上池(id 缺)→ 不收合,原樣列出", () => {
    const out = groupedValueOptions(flat, mkMatch([["團隊合作", "不存在的"]]), "OC1");
    expect(out.map((o) => o.name)).toEqual(["團隊合作", "團隊意識", "持續學習"]);
    expect(out[0].variants).toBeUndefined();
  });
});

describe("taskRowsWithSimilar(spec §4)", () => {
  it("灰區對雙向掛 similarTo;無 similarity → 原樣", () => {
    const pack = {
      pools: { units: {}, tasks: { 巡檢: { srcs: ["ocs:OC1:T:T1"] }, 控管: { srcs: ["ocs:OC2:T:T2"] } } },
      source_tasks: {
        "ocs:OC1:T:T1": { ocs_code: "OC1", ocs_name: "", task_code: "T1", task_name: "巡檢" },
        "ocs:OC2:T:T2": { ocs_code: "OC2", ocs_name: "", task_code: "T2", task_name: "控管" },
      },
      similarity: { task: { groups: [], possible_matches: [{ left_id: "巡檢", right_id: "控管", score: 0.85 }],
        config: { kind: "task", theta_high: 0.95, theta_low: 0.8, model: "bge-m3" } } },
    } as unknown as KnowledgePack;
    const rows = taskRowsWithSimilar(pack);
    expect(rows.find((r) => r.name === "巡檢")?.similarTo).toEqual([{ name: "控管", score: 0.85 }]);
    expect(rows.find((r) => r.name === "控管")?.similarTo).toEqual([{ name: "巡檢", score: 0.85 }]);
    const bare = taskRowsWithSimilar({ ...pack, similarity: undefined } as unknown as KnowledgePack);
    expect(bare.every((r) => r.similarTo === undefined)).toBe(true);
  });
});
