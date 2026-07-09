// T8(0028 D7):evidence(review=pending)→ 文件格追蹤修訂標記的映射。純函式。
import { describe, expect, it } from "vitest";

import { buildReviewMap, DETAIL_SLOT_LABELS, taskMarks } from "@/lib/reviewMap";

const EV = [
  { doc_path: "ocs_content.ocu_units.u1.tasks.t1.details.frequency",
    quote: "每兩週跑一次", turn_seq: 1, verified: true, review: "pending" },
  { doc_path: "ocs_content.ocu_units.u1.tasks.t1.competency_blocks.0.knowledge",
    quote: "要懂測試設計", turn_seq: 1, verified: true, review: "pending" },
  { doc_path: "ocs_content.ocu_units.u1.tasks.t1.details.tools",
    quote: "用 Postman", turn_seq: 2, verified: true, review: "accepted" },   // 已收→不標
  { doc_path: "ocs_content.ocu_units.0.tasks.0.details.volume",
    quote: "三百多條", turn_seq: 3, verified: true, review: "pending" },      // index 形 path
];

describe("buildReviewMap", () => {
  it("只收 review=pending;path→quote", () => {
    const m = buildReviewMap(EV);
    expect(m.size).toBe(3);
    expect(m.get("ocs_content.ocu_units.u1.tasks.t1.details.frequency")?.quote)
      .toBe("每兩週跑一次");
    expect(m.has("ocs_content.ocu_units.u1.tasks.t1.details.tools")).toBe(false);
  });
});

describe("taskMarks", () => {
  it("依 prefix(uid 形+index 形後援)分類 details 槽與 O/P/K/S 格", () => {
    const m = buildReviewMap(EV);
    const marks = taskMarks(m, [
      "ocs_content.ocu_units.u1.tasks.t1",
      "ocs_content.ocu_units.0.tasks.0",
    ]);
    expect(marks.details.frequency?.quote).toBe("每兩週跑一次");
    expect(marks.details.volume?.quote).toBe("三百多條");     // index 形也對到
    expect(marks.cells.knowledge?.quote).toBe("要懂測試設計");
    expect(marks.cells.outputs).toBeUndefined();
  });

  it("prefix 不符 → 空", () => {
    const m = buildReviewMap(EV);
    const marks = taskMarks(m, ["ocs_content.ocu_units.u9.tasks.t9"]);
    expect(Object.keys(marks.details)).toHaveLength(0);
    expect(Object.keys(marks.cells)).toHaveLength(0);
  });
});

describe("DETAIL_SLOT_LABELS", () => {
  it("11 槽標籤齊(鏡像後端 slots.py)", () => {
    expect(Object.keys(DETAIL_SLOT_LABELS)).toHaveLength(11);
    expect(DETAIL_SLOT_LABELS.wait_points).toBe("等待瓶頸");
  });
});
