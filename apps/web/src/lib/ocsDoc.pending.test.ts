// T8(ADR 0030):`_pending` 四態轉移矩陣——accept/reject × add/mod/del × 行內/集合。
// 不變量:✓=去標(del=真刪)、✗=還原(add=刪、mod=回prev、del=留原);每次決策後
// renumber(位置碼與新位置一致);延遲生效欄(表頭主基準)✓ 才寫入。
import { describe, expect, it } from "vitest";
import type { OcsDocument, OcsTask } from "@/types";
import {
  acceptPending, listPending, pendingStatus, rejectPending, resolveAllPending,
} from "./ocsDoc";

const M = (op: "add" | "mod" | "del", extra: object = {}) =>
  ({ op, by: "ai", turn_id: 3, ...extra });

function baseDoc(): OcsDocument {
  const task: OcsTask = {
    task_codes: [{ code: "T1.1", name: "回歸測試" }],
    competency_blocks: [{
      competency_level: null,
      outputs: [], indicators: [],
      knowledge: [
        { code: "K01", name: "既有知識", _id: "k-old" },
        { code: null, name: "AI 新增知識", _id: "k-new", _pending: M("add") },
      ],
      skills: [{ code: "S01", name: "既有技能", _id: "s-old", _pending: M("del") }],
    }],
    details: {
      frequency: "每雙週",
      _pending: { frequency: M("mod", { prev: "每月" }) },
    },
    _tid: "t1",
  } as unknown as OcsTask;
  return {
    ocs_profile: {
      ocs_code: "OLD-CODE", job_description: "", ocs_level: null,
      ocs_name: {}, category: { job_categories: [], occupations: [], industries: [] },
      _pending: { ocs_code: M("mod", { prev: "OLD-CODE", value: "NEW-CODE" }) },
    },
    notes: { prerequisites: [], supplements: [] },
    ocs_content: { ocu_units: [{
      ocu_code: "T1", ocu_name: "測試", tasks: [task], _uid: "u1",
      source: { ocs_code: "X", occupation_name: "" },
    }] },
    ocs_attitude: { attitudes: [] },
  } as unknown as OcsDocument;
}

const K_NEW = "ocs_content.ocu_units.u1.tasks.t1.competency_blocks.0.knowledge.k-new";
const S_OLD = "ocs_content.ocu_units.u1.tasks.t1.competency_blocks.0.skills.s-old";
const FREQ = "ocs_content.ocu_units.u1.tasks.t1.details.frequency";

describe("行內條目 add", () => {
  it("accept=去標+renumber 給碼", () => {
    const d = acceptPending(baseDoc(), K_NEW);
    const ks = d.ocs_content.ocu_units[0].tasks[0].competency_blocks[0].knowledge;
    expect(ks).toHaveLength(2);
    expect(pendingStatus(ks[1])).toBe("confirmed");
    expect(ks[1].code).toBe("K02");                      // A4 文件級 K 重編
  });
  it("reject=整筆移除", () => {
    const d = rejectPending(baseDoc(), K_NEW);
    const ks = d.ocs_content.ocu_units[0].tasks[0].competency_blocks[0].knowledge;
    expect(ks.map((k) => k._id)).toEqual(["k-old"]);
  });
});

describe("行內條目 del", () => {
  it("accept=真刪", () => {
    const d = acceptPending(baseDoc(), S_OLD);
    expect(d.ocs_content.ocu_units[0].tasks[0].competency_blocks[0].skills).toHaveLength(0);
  });
  it("reject=去標留原", () => {
    const d = rejectPending(baseDoc(), S_OLD);
    const ss = d.ocs_content.ocu_units[0].tasks[0].competency_blocks[0].skills;
    expect(ss).toHaveLength(1);
    expect(pendingStatus(ss[0])).toBe("confirmed");
  });
});

describe("行內條目 mod(name/text 葉)", () => {
  it("accept=保新值;reject=還原 prev", () => {
    const doc = baseDoc();
    const k = doc.ocs_content.ocu_units[0].tasks[0].competency_blocks[0].knowledge[0];
    k.name = "AI 改過的名字";
    (k as unknown as Record<string, unknown>)._pending = M("mod", { prev: "既有知識" });
    const path = "ocs_content.ocu_units.u1.tasks.t1.competency_blocks.0.knowledge.k-old";
    const acc = acceptPending(doc, path);
    expect(acc.ocs_content.ocu_units[0].tasks[0].competency_blocks[0].knowledge[0].name)
      .toBe("AI 改過的名字");
    const rej = rejectPending(doc, path);
    expect(rej.ocs_content.ocu_units[0].tasks[0].competency_blocks[0].knowledge[0].name)
      .toBe("既有知識");
    expect(pendingStatus(rej.ocs_content.ocu_units[0].tasks[0].competency_blocks[0].knowledge[0]))
      .toBe("confirmed");
  });
});

describe("集合式 scalar 槽(details)", () => {
  it("mod accept=去標保新值", () => {
    const d = acceptPending(baseDoc(), FREQ);
    const det = d.ocs_content.ocu_units[0].tasks[0].details as Record<string, unknown>;
    expect(det.frequency).toBe("每雙週");
    expect(det._pending).toBeUndefined();
  });
  it("mod reject=還原 prev", () => {
    const d = rejectPending(baseDoc(), FREQ);
    const det = d.ocs_content.ocu_units[0].tasks[0].details as Record<string, unknown>;
    expect(det.frequency).toBe("每月");
    expect(det._pending).toBeUndefined();
  });
  it("del accept=槽值移除;del reject=留值", () => {
    const doc = baseDoc();
    const det = doc.ocs_content.ocu_units[0].tasks[0].details as Record<string, unknown>;
    det._pending = { frequency: M("del", { prev: "每雙週" }) };
    const acc = acceptPending(doc, FREQ);
    expect((acc.ocs_content.ocu_units[0].tasks[0].details as Record<string, unknown>).frequency)
      .toBeUndefined();
    const rej = rejectPending(doc, FREQ);
    expect((rej.ocs_content.ocu_units[0].tasks[0].details as Record<string, unknown>).frequency)
      .toBe("每雙週");
  });
});

describe("表頭主基準(延遲生效:欄位不動、value 在標記)", () => {
  it("accept 才寫入 value", () => {
    const d = acceptPending(baseDoc(), "ocs_profile.ocs_code");
    expect(d.ocs_profile.ocs_code).toBe("NEW-CODE");
    expect((d.ocs_profile as unknown as Record<string, unknown>)._pending).toBeUndefined();
  });
  it("reject=欄位保持原值、只去標", () => {
    const d = rejectPending(baseDoc(), "ocs_profile.ocs_code");
    expect(d.ocs_profile.ocs_code).toBe("OLD-CODE");
    expect((d.ocs_profile as unknown as Record<string, unknown>)._pending).toBeUndefined();
  });
});

describe("任務級 add(整任務待審)", () => {
  const withPendingTask = () => {
    const doc = baseDoc();
    doc.ocs_content.ocu_units[0].tasks.push({
      task_codes: [{ code: null, name: "AI 提的新任務" }],
      competency_blocks: [], details: null, _tid: "t-new",
      _pending: M("add"),
    } as unknown as OcsTask);
    return doc;
  };
  it("accept=去標+renumber 給位置碼", () => {
    const d = acceptPending(withPendingTask(), "ocs_content.ocu_units.u1.tasks.t-new");
    const t = d.ocs_content.ocu_units[0].tasks[1];
    expect(pendingStatus(t)).toBe("confirmed");
    expect(t.task_codes[0].code).toBe("T1.2");
  });
  it("reject=任務消失", () => {
    const d = rejectPending(withPendingTask(), "ocs_content.ocu_units.u1.tasks.t-new");
    expect(d.ocs_content.ocu_units[0].tasks).toHaveLength(1);
  });
});

describe("listPending / resolveAllPending", () => {
  it("計數涵蓋行內+集合+表頭", () => {
    const entries = listPending(baseDoc());
    const paths = entries.map((e) => e.path).sort();
    expect(paths).toEqual([FREQ, K_NEW, S_OLD, "ocs_profile.ocs_code"].sort());
  });
  it("批量接受/拒絕後歸零", () => {
    expect(listPending(resolveAllPending(baseDoc(), "accept"))).toHaveLength(0);
    const rejected = resolveAllPending(baseDoc(), "reject");
    expect(listPending(rejected)).toHaveLength(0);
    // 拒絕語意抽查:add 消失、del 留原、mod 回 prev、表頭不動
    expect(rejected.ocs_content.ocu_units[0].tasks[0].competency_blocks[0].knowledge)
      .toHaveLength(1);
    expect(rejected.ocs_content.ocu_units[0].tasks[0].competency_blocks[0].skills)
      .toHaveLength(1);
    expect(rejected.ocs_profile.ocs_code).toBe("OLD-CODE");
  });
});
