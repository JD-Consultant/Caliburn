import { describe, expect, it } from "vitest";
import { packSrcToRef } from "./pack";

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
