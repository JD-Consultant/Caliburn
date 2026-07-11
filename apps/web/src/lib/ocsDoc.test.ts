import { describe, expect, it } from "vitest";
import type { OcsDocument, OcsTask } from "@/types";
import {
  addCustomDuty,
  addCustomTask,
  addTasksToUnit,
  deleteTask,
  relocateTask,
  reorderUnits,
  clearPrimaryBasis,
  renameTask,
  renameUnit,
  setAttitudes,
  setKS,
  setNoteItems,
  setOcsLevel,
  setOp,
  setTaskLevel,
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
    notes: { prerequisites: [], supplements: [] },
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

describe("位置碼:custom 與官方一視同仁(ADR 0029;spec §7)", () => {
  it("自訂任務/項目與官方一樣依位置連號(T/O/P);身分(_src/provenance)不影響顯示碼", () => {
    const custom = {
      task_codes: [{ code: "", name: "自訂任務" }],
      competency_blocks: [{
        competency_level: null,
        outputs: [{ code: "", name: "自訂產出", _id: "co", _src: "custom" }],
        indicators: [{ code: "", text: "自訂指標", _id: "cp", _src: "custom" }],
        knowledge: [], skills: [],
      }],
      provenance: { ocs_code: "", task_code: "" }, _tid: "tid-custom",
    } as unknown as OcsTask;
    const doc = docWith([
      { name: "U1", tasks: [task("T1.1", "甲")] },   // 官方
      { name: "U2", tasks: [custom] },               // 自訂(無 provenance、items custom)
    ]);
    const next = reorderUnits(doc, 1, 0); // 自訂職責換到最前
    expect(next.ocs_content.ocu_units[0].ocu_code).toBe("T1");
    expect(codesOf(next, 0)).toEqual([{ task: "T1.1", o: ["O1.1.1"], p: ["P1.1.1"] }]); // 自訂照拿位置碼
    expect(codesOf(next, 1)).toEqual([{ task: "T2.1", o: ["O2.1.1"], p: ["P2.1.1"] }]); // 官方隨位置重編
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

describe("改名不斷根 + 級別來源(ADR 0029;spec 2026-07-11 §2.4/§4)", () => {
  it("renameTask:保留 provenance/_refs/_levelSrc(身分不斷根;原名靠 pack 對位顯示)", () => {
    const doc = docWith([{ name: "U1", tasks: [task("T1.1", "甲")] }]);
    doc.ocs_content.ocu_units[0].tasks[0]._refs = [{ ocs_code: "OC1", occupation_name: "甲職", code: "" }];
    doc.ocs_content.ocu_units[0].tasks[0]._levelSrc = { ocs_code: "OC1", occupation_name: "甲職", code: "", level: 3 };
    const next = renameTask(doc, 0, 0, "改過的名字");
    const t = next.ocs_content.ocu_units[0].tasks[0];
    expect(t._refs).toEqual([{ ocs_code: "OC1", occupation_name: "甲職", code: "" }]);
    expect(t._levelSrc).toMatchObject({ level: 3 });
    expect(t.task_codes![0].name).toBe("改過的名字");
  });
  it("renameUnit:保留 source/_refs(身分不斷根)", () => {
    const doc = docWith([{ name: "U1", tasks: [] }]);
    doc.ocs_content.ocu_units[0]._refs = [{ ocs_code: "OC1", occupation_name: "甲職", code: "", ocu_code: "T1" }];
    doc.ocs_content.ocu_units[0].source = { ocs_code: "OC1", occupation_name: "甲職" };
    const next = renameUnit(doc, 0, "新名");
    expect(next.ocs_content.ocu_units[0]._refs).toEqual([{ ocs_code: "OC1", occupation_name: "甲職", code: "", ocu_code: "T1" }]);
    expect(next.ocs_content.ocu_units[0].source).toEqual({ ocs_code: "OC1", occupation_name: "甲職" });
    expect(next.ocs_content.ocu_units[0].ocu_name).toBe("新名");
  });
  it("setTaskLevel 無 src → 清舊 _levelSrc(修殘留)", () => {
    const doc = docWith([{ name: "U1", tasks: [task("T1.1", "甲")] }]);
    const d1 = setTaskLevel(doc, 0, 0, 3, { ocs_code: "OC1", occupation_name: "甲職", code: "", level: 3 });
    expect(d1.ocs_content.ocu_units[0].tasks[0]._levelSrc?.level).toBe(3);
    const d2 = setTaskLevel(d1, 0, 0, 5);
    expect(d2.ocs_content.ocu_units[0].tasks[0]._levelSrc).toBeUndefined();
  });
  it("setOcsLevel:src 給→寫 ocs_profile._levelSrc,未給→清", () => {
    const doc = docWith([{ name: "U1", tasks: [] }]);
    const d1 = setOcsLevel(doc, "4", { ocs_code: "OC1", occupation_name: "甲職", code: "", level: 4 });
    expect(d1.ocs_profile._levelSrc?.level).toBe(4);
    const d2 = setOcsLevel(d1, "5");
    expect(d2.ocs_profile._levelSrc).toBeUndefined();
  });
  it("clearPrimaryBasis:整組清 code+兩名,其他欄不動", () => {
    const doc = docWith([{ name: "U1", tasks: [] }]);
    doc.ocs_profile.ocs_name = { job_category_name: "職類名", occupation_name: "職業名" };
    doc.ocs_profile.job_description = "描述留著";
    const next = clearPrimaryBasis(doc);
    expect(next.ocs_profile.ocs_code).toBe("");
    expect(next.ocs_profile.ocs_name.occupation_name).toBe("");
    expect(next.ocs_profile.ocs_name.job_category_name).toBe("");
    expect(next.ocs_profile.job_description).toBe("描述留著");
  });
});

describe("setNoteItems(notes 影子列,spec 2026-07-04 §3)", () => {
  const base = () => docWith([{ name: "U1", tasks: [] }]);
  it("寫影子列+同步導出契約 string[],顯示碼 n1,n2(不補零)", () => {
    const next = setNoteItems(base(), "prerequisites", [
      { code: "", text: "大學以上", _id: "a", _src: "official",
        _ref: { ocs_code: "OC1", occupation_name: "甲", code: "n1" } },
      { code: "", text: "二年經驗", _id: "b", _src: "custom" },
    ]);
    expect(next.notes.prerequisites).toEqual(["大學以上", "二年經驗"]);
    expect(next.notes._prerequisites!.map((r) => r.code)).toEqual(["n1", "n2"]);
    expect(next.notes._prerequisites![0]._ref!.code).toBe("n1"); // 身分不隨顯示碼動
  });
  it("拖動換序:顯示碼重編、_ref 凍結", () => {
    const d1 = setNoteItems(base(), "supplements", [
      { code: "", text: "甲", _id: "a", _src: "official",
        _ref: { ocs_code: "OC1", occupation_name: "甲", code: "n1" } },
      { code: "", text: "乙", _id: "b", _src: "official",
        _ref: { ocs_code: "OC1", occupation_name: "甲", code: "n2" } },
    ]);
    const rows = d1.notes._supplements!;
    const d2 = setNoteItems(d1, "supplements", [rows[1], rows[0]]);
    expect(d2.notes._supplements!.map((r) => [r.code, r._ref!.code])).toEqual(
      [["n1", "n2"], ["n2", "n1"]]);
    expect(d2.notes.supplements).toEqual(["乙", "甲"]);
  });
  it("純函式:不污染呼叫端 items;空白 text 不進契約欄", () => {
    const items = [{ code: "", text: "", _id: "x" }, { code: "", text: "有值", _id: "y" }];
    const next = setNoteItems(base(), "prerequisites", items);
    expect(items[0].code).toBe("");
    expect(next.notes.prerequisites).toEqual(["有值"]);
    expect(next.notes._prerequisites!.length).toBe(2); // 影子列保留空白列(就地編輯中)
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

describe("addCustomTask / addCustomDuty(訪談抓漏核准落地,RC4)", () => {
  it("addCustomTask:掛到現有職責(by _uid)、位置碼、自訂無來源", () => {
    const doc = docWith([{ name: "U1", tasks: [task("T1.1", "甲")] }]);
    const next = addCustomTask(doc, "uid-U1", "處理床位滿");
    const tasks = next.ocs_content.ocu_units[0].tasks;
    expect(tasks).toHaveLength(2);
    expect(tasks[1].task_codes?.[0]).toEqual({ code: "T1.2", name: "處理床位滿" });
    expect(tasks[1]._tid).toBeTruthy();                              // 有身分
    expect(tasks[1].provenance).toEqual({ ocs_code: "", task_code: "" });  // 公版外
  });

  it("addCustomTask:unit_ref 對不上 → 開自訂職責掛上(核准的任務不消失)", () => {
    const doc = docWith([{ name: "U1", tasks: [] }]);
    const next = addCustomTask(doc, "床位管理", "處理床位滿");
    expect(next.ocs_content.ocu_units).toHaveLength(2);
    const u2 = next.ocs_content.ocu_units[1];
    expect(u2.ocu_name).toBe("床位管理");
    expect(u2.tasks[0].task_codes?.[0]).toEqual({ code: "T2.1", name: "處理床位滿" });
    expect(u2.source).toEqual({ ocs_code: "", occupation_name: "" });  // 自訂職責
  });

  it("addCustomDuty:開新自訂職責、位置碼 T2", () => {
    const doc = docWith([{ name: "U1", tasks: [] }]);
    const next = addCustomDuty(doc, "客戶問題支援");
    expect(next.ocs_content.ocu_units[1].ocu_name).toBe("客戶問題支援");
    expect(next.ocs_content.ocu_units[1].ocu_code).toBe("T2");
  });

  it("純函式:不就地改動原件", () => {
    const doc = docWith([{ name: "U1", tasks: [] }]);
    addCustomTask(doc, "uid-U1", "x");
    expect(doc.ocs_content.ocu_units[0].tasks).toHaveLength(0);
  });
});
