import { describe, expect, it } from "vitest";

import {
  emptyDutyForm,
  fromDutyView,
  isDutyFormDirty,
  toDutyOrderWrite,
  toDutyWrite,
} from "./jobAnalysisDuties";

describe("Current JD Duty form mapping", () => {
  it("trims a Duty statement and drops an empty statement", () => {
    expect(toDutyWrite({ statement: " 門市營運 " })).toEqual({
      statement: "門市營運",
    });
    expect(toDutyWrite({ statement: "   " })).toEqual({ statement: "" });
  });

  it("round-trips a Duty view without treating display order as identity", () => {
    const view = {
      duty_id: "entry-1-d0",
      statement: "門市營運",
      display_order: 2,
    };
    const form = fromDutyView(view);

    expect(form).toEqual({ statement: "門市營運" });
    expect(toDutyOrderWrite([view, { ...view, duty_id: "entry-2-d0" }])).toEqual({
      ordered_duty_ids: ["entry-1-d0", "entry-2-d0"],
    });
    expect(isDutyFormDirty(form, emptyDutyForm())).toBe(true);
  });
});
