import type {
  DutyOrderWrite,
  DutyView,
  DutyWrite,
} from "@caliburn/job-analysis-contract";

export interface DutyFormValue {
  statement: string;
}

export const COMPETENCY_LEVEL_OPTIONS = [
  {
    value: "1",
    label: "第 1 級",
    summary: "可預計規律／密切監督／常規重複／不需特殊訓練",
  },
  {
    value: "2",
    label: "第 2 級",
    summary: "大多可預計／經常監督／需理解判斷／基本知識技能",
  },
  {
    value: "3",
    label: "第 3 級",
    summary: "部分變動／一般監督／獨立完成／少許判斷能力",
  },
  {
    value: "4",
    label: "第 4 級",
    summary: "經常變動／少許監督／規劃設計／判斷與決定",
  },
  {
    value: "5",
    label: "第 5 級",
    summary: "複雜變動／最少監督／自主完成／策略思考判斷",
  },
  {
    value: "6",
    label: "第 6 級",
    summary: "高度複雜／整合專業／專業創新／策略決策原創",
  },
] as const;

export function emptyDutyForm(): DutyFormValue {
  return { statement: "" };
}

export function fromDutyView(duty: DutyView): DutyFormValue {
  return { statement: duty.statement };
}

export function toDutyWrite(value: DutyFormValue): DutyWrite {
  return { statement: value.statement.trim() };
}

export function toDutyOrderWrite(
  duties: Array<Pick<DutyView, "duty_id">>,
): DutyOrderWrite {
  return { ordered_duty_ids: duties.map((duty) => duty.duty_id) };
}

export function isDutyFormDirty(
  baseline: DutyFormValue,
  current: DutyFormValue,
): boolean {
  return JSON.stringify(baseline) !== JSON.stringify(current);
}
