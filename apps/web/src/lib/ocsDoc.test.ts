import { describe, expect, it } from "vitest";
import type { OcsDocument, OcsTask } from "@/types";
import {
  addTasksToUnit,
  deleteTask,
  relocateTask,
  reorderUnits,
  setAttitudes,
  setKS,
  setOp,
} from "./ocsDoc";

// 最小 fixture:只鋪 recode 路徑會摸到的欄位。「代碼是位置、身分是 _id」是這組
// 測試守的不變量 —— 結構變動後所有位置碼(T/O/P/K/S)必須與新位置一致。

function task(code: string, name: string, opts?: { k?: string[]; s?: string[] }): OcsTask {
  return {
    task_codes: [{ code, name }],
    competency_blocks: [{
      competency_level: null,
      outputs: [{ code: `O${code.slice(1)}.1`, name: `${name}-產出`, _id: `o-${name}` }],
      indicators: [{ code: `P${code.slice(1)}.1`, text: `${name}-指標`, _id: `p-${name}` }],
      knowledge: (opts?.k ?? []).map((n, i) => ({ code: "", name: n, _id: `k-${name}-${i}` })),
      skills: (opts?.s ?? []).map((n, i) => ({ code: "", name: n, _id: `s-${name}-${i}` })),
    }],
    provenance: { ocs_code: "OCS1", task_code: code },
    _tid: `tid-${name}`,
  } as unknown as OcsTask;
}

function docWith(units: { name: string; tasks: OcsTask[] }[]): OcsDocument {
  return {
    ocs_profile: {
      ocs_code: "OCS1", job_description: "", ocs_level: null,
      ocs_name: {}, category: { job_categories: [], occupations: [], industries: [] },
    },
    ocs_content: {
      ocu_units: units.map((u, i) => ({
        ocu_code: `T${i + 1}`, ocu_name: u.name,
        source: { ocs_code: "OCS1", occupation_name: "" },
        tasks: u.tasks, _uid: `uid-${u.name}`,
      })),
    },
  } as unknown as OcsDocument;
}

const codesOf = (d: OcsDocument, ui: number) =>
  d.ocs_content.ocu_units[ui].tasks.map((t) => ({
    task: t.task_codes?.[0]?.code,
    o: t.competency_blocks?.[0]?.outputs?.map((x) => x.code),
    p: t.competency_blocks?.[0]?.indicators?.map((x) => x.code),
  }));

describe("relocateTask(拖拉換序)", () => {
  it("同職責內換序:任務碼與 O/P 位置碼都跟著新位置(ccdfbde 回歸)", () => {
    const doc = docWith([{ name: "U1", tasks: [task("T1.1", "甲"), task("T1.2", "乙")] }]);
    const next = relocateTask(doc, 0, 1, 0, 0); // 乙拖到最前
    expect(codesOf(next, 0)).toEqual([
      { task: "T1.1", o: ["O1.1.1"], p: ["P1.1.1"] }, // 乙
      { task: "T1.2", o: ["O1.2.1"], p: ["P1.2.1"] }, // 甲
    ]);
    // 身分不動:第一個任務仍是乙
    expect(next.ocs_content.ocu_units[0].tasks[0]._tid).toBe("tid-乙");
  });

  it("跨職責搬移:O/P 前綴換成目的職責/位置", () => {
    const doc = docWith([
      { name: "U1", tasks: [task("T1.1", "甲")] },
      { name: "U2", tasks: [task("T2.1", "丙")] },
    ]);
    const next = relocateTask(doc, 0, 0, 1, -1); // 甲搬到 U2 尾端
    expect(codesOf(next, 1)).toEqual([
      { task: "T2.1", o: ["O2.1.1"], p: ["P2.1.1"] },
      { task: "T2.2", o: ["O2.2.1"], p: ["P2.2.1"] }, // 甲:O1.1.1 → O2.2.1
    ]);
  });
});

describe("reorderUnits / deleteTask(其他結構變動)", () => {
  it("職責換序:T 碼與底下任務的 O/P 全部重編", () => {
    const doc = docWith([
      { name: "U1", tasks: [task("T1.1", "甲")] },
      { name: "U2", tasks: [task("T2.1", "丙")] },
    ]);
    const next = reorderUnits(doc, 1, 0);
    expect(next.ocs_content.ocu_units.map((u) => u.ocu_code)).toEqual(["T1", "T2"]);
    expect(codesOf(next, 0)).toEqual([{ task: "T1.1", o: ["O1.1.1"], p: ["P1.1.1"] }]); // 丙
    expect(next.ocs_content.ocu_units[0].ocu_name).toBe("U2");
  });

  it("刪任務:後面任務的碼往前補", () => {
    const doc = docWith([{ name: "U1", tasks: [task("T1.1", "甲"), task("T1.2", "乙")] }]);
    const next = deleteTask(doc, 0, 0);
    expect(codesOf(next, 0)).toEqual([{ task: "T1.1", o: ["O1.1.1"], p: ["P1.1.1"] }]); // 乙補位
  });
});

describe("setOp / setKS(內容編輯的重編)", () => {
  it("setOp:O/P 依任務位置重編", () => {
    const doc = docWith([{ name: "U1", tasks: [task("T1.1", "甲")] }]);
    const next = setOp(doc, 0, 0,
      [{ code: "", name: "x", _id: "x" }, { code: "", name: "y", _id: "y" }],
      [{ code: "", text: "z", _id: "z" }]);
    const b = next.ocs_content.ocu_units[0].tasks[0].competency_blocks![0];
    expect(b.outputs!.map((o) => o.code)).toEqual(["O1.1.1", "O1.1.2"]);
    expect(b.indicators!.map((i) => i.code)).toEqual(["P1.1.1"]);
  });

  it("setKS(A4 文件級):同名 K 跨任務共碼、首現給號", () => {
    const doc = docWith([
      { name: "U1", tasks: [task("T1.1", "甲", { k: ["資料庫" ] }), task("T1.2", "乙")] },
    ]);
    const next = setKS(doc, 0, 1, "knowledge", [
      { code: "", name: "資料庫", _id: "k2" }, // 與甲同名 → 共碼 K01
      { code: "", name: "網路", _id: "k3" },
    ]);
    const [t1, t2] = next.ocs_content.ocu_units[0].tasks;
    expect(t1.competency_blocks![0].knowledge!.map((k) => k.code)).toEqual(["K01"]);
    expect(t2.competency_blocks![0].knowledge!.map((k) => k.code)).toEqual(["K01", "K02"]);
  });

  it("結構變動後 K 碼依新首現序重編", () => {
    const doc = docWith([
      { name: "U1", tasks: [task("T1.1", "甲", { k: ["資料庫"] }), task("T1.2", "乙", { k: ["網路"] })] },
    ]);
    const next = relocateTask(doc, 0, 1, 0, 0); // 乙到最前 → 網路首現
    const [t1, t2] = next.ocs_content.ocu_units[0].tasks;
    expect(t1.competency_blocks![0].knowledge!.map((k) => k.code)).toEqual(["K01"]); // 網路
    expect(t2.competency_blocks![0].knowledge!.map((k) => k.code)).toEqual(["K02"]); // 資料庫
  });
});

describe("setAttitudes / addTasksToUnit", () => {
  it("態度:位置序碼 A01、A02", () => {
    const doc = docWith([{ name: "U1", tasks: [] }]);
    const next = setAttitudes(doc, [
      { code: "", name: "細心", _id: "a1" }, { code: "", name: "誠信", _id: "a2" },
    ]);
    expect(next.ocs_attitude!.attitudes!.map((a) => a.code)).toEqual(["A01", "A02"]);
  });

  it("setter 是純函式:不就地改動呼叫端傳入的 items(cache 舊快照不可被污染)", () => {
    const doc = docWith([{ name: "U1", tasks: [task("T1.1", "甲")] }]);
    const outputs = [{ code: "", name: "x", _id: "x" }];
    const atts = [{ code: "", name: "細心", _id: "a1" }];
    setOp(doc, 0, 0, outputs, []);
    setAttitudes(doc, atts);
    expect(outputs[0].code).toBe(""); // 不能被 renumber 就地寫成 O1.1.1
    expect(atts[0].code).toBe("");
  });

  it("池任務入職責:接尾端並照位置給碼", () => {
    const doc = docWith([{ name: "U1", tasks: [task("T1.1", "甲")] }]);
    const next = addTasksToUnit(doc, 0, [
      { name: "新任務", srcs: [], provenance: { ocs_code: "OCS1", task_code: "T9.9" } },
    ]);
    const t = next.ocs_content.ocu_units[0].tasks[1];
    expect(t.task_codes?.[0]).toEqual({ code: "T1.2", name: "新任務" });
  });
});
