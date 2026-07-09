// T7(0028 D1):AI 預勾清單 ↔ 知識包對位 + PoolPick 組裝(純函式;元件保持薄)。
import { describe, expect, it } from "vitest";

import { buildCurationRows, markAlreadyInDoc, picksFromRows } from "@/lib/curation";
import type { KnowledgePack, OcsDocument, PickerPrecheckItem } from "@/types";

// 最小 pack:units/tasks 池 + source_tasks(unitRows/taskRows 只吃這三處)
const PACK = {
  occupation_details: [],
  source_tasks: {
    "urn:t1": { ocs_code: "ISD", ocs_name: "軟體測試工程人員", ocu_code: "U1",
                task_code: "T1", task_name: "需求訪談",
                k_refs: [], s_refs: [], o_refs: [], p_refs: [], competency_level: null },
    "urn:t2": { ocs_code: "ISD", ocs_name: "軟體測試工程人員", ocu_code: "U1",
                task_code: "T2", task_name: "介面設計",
                k_refs: [], s_refs: [], o_refs: [], p_refs: [], competency_level: null },
  },
  pools: {
    units: { "規劃": { srcs: [{ ocs_code: "ISD", ocs_name: "軟體測試工程人員", ocu_code: "U1" }] } },
    tasks: { "需求訪談": { srcs: ["urn:t1"] }, "介面設計": { srcs: ["urn:t2"] } },
  },
} as unknown as KnowledgePack;

const ITEMS: PickerPrecheckItem[] = [
  { key: "ISD:T1", name: "需求訪談", unit: "規劃", quote: "我會跟客戶開需求訪談" },
  { key: "ISD:T9", name: "不存在的任務", unit: "規劃", quote: "隨便" },
];
const IN = (precheck: PickerPrecheckItem[], others: { key: string; name: string;
  unit: string | null }[] = []) => ({ precheck, others });

describe("buildCurationRows", () => {
  it("以 key(ocs:task_code)對位 pack 列;找得到=found+srcs,找不到=found:false", () => {
    const rows = buildCurationRows(IN(ITEMS), PACK);
    expect(rows[0]).toMatchObject({ key: "ISD:T1", name: "需求訪談", found: true,
                                    prechecked: true });
    expect(rows[0].srcs[0]).toMatchObject({ ocs_code: "ISD", task_code: "T1" });
    expect(rows[1].found).toBe(false);
  });

  it("無 pack → 全列 found:false(引文仍在,可顯示不可寫)", () => {
    const rows = buildCurationRows(IN(ITEMS), undefined);
    expect(rows.every((r) => !r.found)).toBe(true);
    expect(rows[0].quote).toBe("我會跟客戶開需求訪談");
  });

  it("others 照列(D8 全檢查表):prechecked:false、無引文", () => {
    const rows = buildCurationRows(
      IN([], [{ key: "ISD:T2", name: "介面設計", unit: "規劃" }]), PACK);
    expect(rows[0]).toMatchObject({ key: "ISD:T2", found: true,
                                    prechecked: false, quote: "" });
  });
});

describe("picksFromRows", () => {
  it("按職責分組出 PoolPick;provenance 由 key 拆出;未對位列跳過", () => {
    const rows = buildCurationRows(IN(ITEMS), PACK);
    const picks = picksFromRows(rows, PACK);
    expect(picks).toHaveLength(1);
    expect(picks[0].unit.name).toBe("規劃");
    expect(picks[0].unit.srcs[0].ocs_code).toBe("ISD");
    expect(picks[0].tasks).toHaveLength(1);           // 未對位的 ISD:T9 被跳過
    expect(picks[0].tasks[0]).toMatchObject({
      name: "需求訪談", provenance: { ocs_code: "ISD", task_code: "T1" },
    });
  });

  it("item.unit 對不上 unit 池 → 以 ownTaskKeys 反查職責", () => {
    const items: PickerPrecheckItem[] = [
      { key: "ISD:T2", name: "介面設計", unit: "後端亂給的名字", quote: "q" }];
    const picks = picksFromRows(buildCurationRows(IN(items), PACK), PACK);
    expect(picks[0].unit.name).toBe("規劃");          // 由任務反查回官方職責
  });
});

describe("markAlreadyInDoc(重複添加守衛;對齊編輯器 TaskPickerMenu 鎖定)", () => {
  const doc = {
    ocs_content: { ocu_units: [{ ocu_name: "規劃", tasks: [
      { task_codes: [{ code: "T1.1", name: "改過名的需求訪談" }],
        provenance: { ocs_code: "ISD", task_code: "T1" }, competency_blocks: [{}] },
      { task_codes: [{ code: "T1.2", name: "介面設計" }],
        provenance: { ocs_code: "", task_code: "" }, competency_blocks: [{}] },
    ] }] },
  } as unknown as OcsDocument;

  it("provenance 對上(即使改過名)→ already;名稱對上(自訂/斷鏈)→ already", () => {
    const rows = markAlreadyInDoc(buildCurationRows(IN([
      { key: "ISD:T1", name: "需求訪談", unit: "規劃", quote: "q1" },   // provenance 命中
      { key: "ISD:T2", name: "介面設計", unit: "規劃", quote: "q2" },   // 名稱命中
    ]), PACK), doc);
    expect(rows.map((r) => !!r.already)).toEqual([true, true]);
  });

  it("不在文件 → 不標 already;picksFromRows 跳過 already 列", () => {
    const rows = markAlreadyInDoc(buildCurationRows(IN([
      { key: "ISD:T1", name: "需求訪談", unit: "規劃", quote: "q1" },
    ]), PACK), { ocs_content: { ocu_units: [] } } as unknown as OcsDocument);
    expect(rows[0].already).toBeFalsy();
    const inDoc = markAlreadyInDoc(buildCurationRows(IN([
      { key: "ISD:T1", name: "需求訪談", unit: "規劃", quote: "q1" },
    ]), PACK), doc);
    expect(picksFromRows(inDoc, PACK)).toHaveLength(0);   // already 不再產 pick
  });
});
