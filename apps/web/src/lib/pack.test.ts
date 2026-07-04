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
