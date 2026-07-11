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

// ── 全域選任務:來源職責解析(spec §6) ────────────────────────────────────────
import { primarySkeletonPicks, resolveHomeUnit, taskPickFromRow, taskRows } from "./pack";
import type { OcsDocument } from "@/types";

describe("全域選任務:來源職責解析(spec §6)", () => {
  const pack = {
    pools: {
      units: {
        職責甲: { srcs: [{ ocs_code: "OC1", ocs_name: "甲", ocu_code: "T1" }] },
        職責乙: { srcs: [{ ocs_code: "OC2", ocs_name: "乙", ocu_code: "U1" }] },
      },
      tasks: { 巡檢: { srcs: ["u1", "u2"] } },
      outputs: {}, indicators: {}, knowledge: {}, skills: {}, attitudes: {},
      job_categories: {}, occupations: {}, industries: {}, prerequisites: {}, supplements: {},
    },
    source_tasks: {
      u1: { ocs_code: "OC1", ocs_name: "甲", ocu_code: "T1", ocu_name: "職責甲", task_code: "T1.1", task_name: "巡檢", competency_level: null },
      u2: { ocs_code: "OC2", ocs_name: "乙", ocu_code: "U1", ocu_name: "職責乙", task_code: "U1.1", task_name: "巡檢", competency_level: null },
    },
    occupation_details: [],
  } as unknown as KnowledgePack;
  const row = taskRows(pack)[0]; // 巡檢, urns=[u1,u2]
  const emptyDoc = { ocs_content: { ocu_units: [] } } as unknown as OcsDocument;

  it("多來源取與主基準同 ocs_code 者優先;職責不在文件 → existingIdx=-1", () => {
    const home = resolveHomeUnit(row, emptyDoc, pack, "OC2")!;
    expect(home.ocuName).toBe("職責乙");
    expect(home.unitSrc.ocu_code).toBe("U1");
    expect(home.existingIdx).toBe(-1);
  });

  it("職責已在文件(改過名)→ existingIdx 靠 _refs 身分命中", () => {
    const doc = { ocs_content: { ocu_units: [
      { ocu_name: "職責乙(改過)", _refs: [{ ocs_code: "OC2", occupation_name: "乙", code: "", ocu_code: "U1" }], tasks: [] },
    ] } } as unknown as OcsDocument;
    expect(resolveHomeUnit(row, doc, pack, "OC2")!.existingIdx).toBe(0);
  });

  it("taskPickFromRow:provenance 取主基準來源", () => {
    expect(taskPickFromRow(row, "OC2").provenance).toEqual({ ocs_code: "OC2", task_code: "U1.1" });
  });

  it("primarySkeletonPicks:主基準全部職責+官方任務整組", () => {
    const picks = primarySkeletonPicks(pack, "OC2");
    expect(picks.map((p) => p.unit.name)).toEqual(["職責乙"]);
    expect(picks[0].tasks.map((t) => t.name)).toEqual(["巡檢"]);
  });
});

// ── 參考選單身分對位:改字不斷根(ADR 0029) ──────────────────────────────────
import { docItemForOption, optionInDoc, originalNameNote, renamedRefItem } from "./pack";

describe("參考選單身分對位(ADR 0029:改字不斷根)", () => {
  const ref = { ocs_code: "OC1", occupation_name: "職業A", code: "O1.1.1" };
  const option: OptionItem = { code: "", name: "官方產出A", srcs: [ref] };

  it("改名後:身分仍命中(勾選不掉)、副行出原名、_ref 仍在、_src 轉 custom", () => {
    const renamed = renamedRefItem(
      { name: "官方產出A", _id: "x", _src: "official" as const, _ref: ref }, "我改的說法");
    expect(renamed._ref).toEqual(ref);                    // _ref 仍在(不斷根)
    expect(renamed._src).toBe("custom");
    expect(renamed.name).toBe("我改的說法");
    expect(optionInDoc([renamed], option)).toBe(true);     // 勾選仍 ✓(按身分)
    expect(originalNameNote([renamed], option)).toBe("官方產出A"); // 副行出原名
  });

  it("未改名:命中但無原名副行", () => {
    const v = { name: "官方產出A", _src: "official" as const, _ref: ref };
    expect(optionInDoc([v], option)).toBe(true);
    expect(originalNameNote([v], option)).toBeNull();
  });

  it("未勾列:docItemForOption=undefined(UI 據此隱藏改名入口)", () => {
    expect(docItemForOption([], option)).toBeUndefined();
    expect(optionInDoc([], option)).toBe(false);
  });

  it("同名但無來源身分的自訂項 → 不誤判為官方選項(判定按身分不按名)", () => {
    const custom = { name: "官方產出A", _src: "custom" as const };
    expect(optionInDoc([custom], option)).toBe(false);
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
