// T12:建議套用純函式(path 文法與後端 executor 同族)。
import { describe, expect, it } from "vitest";

import { applyAccepted, getAtPath, setAtPath } from "./interviewDoc";
import type { OcsDocument } from "@/types";

const FREQ = "ocs_content.ocu_units.u1.tasks.t1.details.frequency";

function doc(): OcsDocument {
  return {
    ocs_profile: { ocs_code: "X", job_description: "" },
    ocs_content: {
      ocu_units: [{
        _uid: "u1", ocu_name: "測試",
        tasks: [{ _tid: "t1", task_codes: [{ code: "T1.1", name: "回歸" }], competency_blocks: [] }],
      }],
    },
  } as unknown as OcsDocument;
}

describe("setAtPath / getAtPath", () => {
  it("穩定 id 解析 + details 缺殼自動建 + 不可變", () => {
    const d = doc();
    const next = setAtPath(d, FREQ, "每雙週");
    expect(next).not.toBeNull();
    expect(getAtPath(next!, FREQ)).toBe("每雙週");
    expect(getAtPath(d, FREQ)).toBeUndefined();          // 原件不變
  });

  it("path 走不到 → null(文件被改走的防呆)", () => {
    expect(setAtPath(doc(), "ocs_content.ocu_units.u9.tasks.t9.details.frequency", "x"))
      .toBeNull();
  });

  it("index 段後援(無穩定 id 時)", () => {
    const d = doc();
    const next = setAtPath(d, "ocs_content.ocu_units.0.tasks.0.details.volume", "300條");
    expect(getAtPath(next!, FREQ.replace("frequency", "volume"))).toBe("300條");
  });
});

describe("applyAccepted", () => {
  it("slot 建議套用、add_* 分流 manual、壞 path 進 failed", () => {
    const out = applyAccepted(doc(), [
      { doc_path: FREQ, new_value: "每雙週" },
      { doc_path: "add_task:客戶問題單重現", new_value: { unit_ref: "u1", name: "客戶問題單重現" } },
      { doc_path: "ocs_content.ocu_units.u9.tasks.t9.details.x", new_value: "?" },
    ]);
    expect(out.applied).toEqual([FREQ]);
    expect(out.manual[0].doc_path).toContain("add_task");
    expect(out.failed).toHaveLength(1);
    expect(getAtPath(out.doc, FREQ)).toBe("每雙週");
  });
});
