// AI 任務盤(0028 D1 + D9 資料源收斂):盤=編輯器知識包全量(unitRows/taskRows),
// 後端只送 AI 疊加層(precheck:key+quote)。身分機制全借編輯器:任務=URN、職責=名稱。
import { describe, expect, it } from "vitest";

import { buildBoard, picksFromBoard } from "@/lib/curation";
import type { KnowledgePack, OcsDocument, PickerPrecheckItem } from "@/types";

// 最小 pack:兩職責(規劃 U1×2 任務、維運 U2×1 任務)。URN=真格式 ocs:{code}:T:{tcode}
// (taskUrns 對位靠它;pools.tasks srcs=source_tasks 的 key)。
const PACK = {
  occupation_details: [],
  source_tasks: {
    "ocs:ISD:T:T1": { ocs_code: "ISD", ocs_name: "軟體測試工程人員", ocu_code: "U1",
                      task_code: "T1", task_name: "需求訪談",
                      k_refs: [], s_refs: [], o_refs: [], p_refs: [], competency_level: null },
    "ocs:ISD:T:T2": { ocs_code: "ISD", ocs_name: "軟體測試工程人員", ocu_code: "U1",
                      task_code: "T2", task_name: "介面設計",
                      k_refs: [], s_refs: [], o_refs: [], p_refs: [], competency_level: null },
    "ocs:ISD:T:T5": { ocs_code: "ISD", ocs_name: "軟體測試工程人員", ocu_code: "U2",
                      task_code: "T5", task_name: "上線部署",
                      k_refs: [], s_refs: [], o_refs: [], p_refs: [], competency_level: null },
  },
  pools: {
    units: {
      "規劃": { srcs: [{ ocs_code: "ISD", ocs_name: "軟體測試工程人員", ocu_code: "U1" }] },
      "維運": { srcs: [{ ocs_code: "ISD", ocs_name: "軟體測試工程人員", ocu_code: "U2" }] },
    },
    tasks: {
      "需求訪談": { srcs: ["ocs:ISD:T:T1"] },
      "介面設計": { srcs: ["ocs:ISD:T:T2"] },
      "上線部署": { srcs: ["ocs:ISD:T:T5"] },
    },
  },
} as unknown as KnowledgePack;

const EMPTY_DOC = { ocs_content: { ocu_units: [] } } as unknown as OcsDocument;
const PRE: PickerPrecheckItem[] = [
  { key: "ISD:T1", name: "需求訪談", unit: "規劃", quote: "我會跟客戶開需求訪談" }];

describe("buildBoard(D9:盤=pack 全量、AI=疊加層)", () => {
  it("職責/任務=pack 全宇宙照列(池序);precheck 以 key 對位疊 prechecked+quote", () => {
    const b = buildBoard(PRE, PACK, EMPTY_DOC);
    expect(b.duties.map((d) => d.unit)).toEqual(["規劃", "維運"]);
    expect(b.duties[0]).toMatchObject({ total: 2, prechecked: 1, defaultOn: true, inDoc: false });
    expect(b.duties[1]).toMatchObject({ total: 1, prechecked: 0, defaultOn: false });
    expect(b.tasks.map((t) => t.name)).toEqual(["需求訪談", "介面設計", "上線部署"]);
    expect(b.tasks[0]).toMatchObject({ unit: "規劃", prechecked: true,
                                       quote: "我會跟客戶開需求訪談", already: false });
    expect(b.tasks[1]).toMatchObject({ prechecked: false, quote: "" });
  });

  it("無 pack → 空盤(彈窗顯示載入態);precheck 對不上 pack 的項忽略", () => {
    expect(buildBoard(PRE, undefined, EMPTY_DOC)).toEqual({ duties: [], tasks: [] });
    const b = buildBoard([{ key: "XX:T9", name: "幽靈", unit: "無", quote: "q" }], PACK, EMPTY_DOC);
    expect(b.tasks.every((t) => !t.prechecked)).toBe(true);
  });

  it("已在文件=URN 對位鎖 already(編輯器 TaskPickerMenu 同機制;改過名也認得);職責名稱對位 inDoc", () => {
    const doc = {
      ocs_content: { ocu_units: [{ ocu_name: "規劃", tasks: [
        { task_codes: [{ code: "T1.1", name: "改過名的需求訪談" }],
          provenance: { ocs_code: "ISD", task_code: "T1" }, competency_blocks: [{}] },
      ] }] },
    } as unknown as OcsDocument;
    const b = buildBoard([], PACK, doc);
    expect(b.tasks.find((t) => t.name === "需求訪談")).toMatchObject({ already: true });
    expect(b.tasks.find((t) => t.name === "介面設計")).toMatchObject({ already: false });
    expect(b.duties[0]).toMatchObject({ inDoc: true, already: 1 });
  });
});

describe("picksFromBoard(寫入=addFromPool 同一路;provenance 規則同 TaskPickerMenu)", () => {
  it("按職責分組;provenance 取與職責同職業的來源;already 列跳過", () => {
    const b = buildBoard(PRE, PACK, EMPTY_DOC);
    const picks = picksFromBoard(
      b.tasks.filter((t) => t.name !== "介面設計"), b);
    expect(picks).toHaveLength(2);
    expect(picks[0].unit.name).toBe("規劃");
    expect(picks[0].unit.srcs[0]).toMatchObject({ ocs_code: "ISD", ocu_code: "U1" });
    expect(picks[0].tasks[0]).toMatchObject({
      name: "需求訪談", provenance: { ocs_code: "ISD", task_code: "T1" } });
    expect(picks[1].unit.name).toBe("維運");
  });

  it("already 列不產 pick(重複添加守衛)", () => {
    const doc = {
      ocs_content: { ocu_units: [{ ocu_name: "規劃", tasks: [
        { task_codes: [{ code: "T1.1", name: "需求訪談" }],
          provenance: { ocs_code: "ISD", task_code: "T1" }, competency_blocks: [{}] },
      ] }] },
    } as unknown as OcsDocument;
    const b = buildBoard([], PACK, doc);
    expect(picksFromBoard(b.tasks.filter((t) => t.name === "需求訪談"), b)).toHaveLength(0);
  });
});
