/** Where a task can belong: one of the responsibilities, or none. Shared by the create form and the move menu. */
import type { Area } from '../../shared/api/generated/jd-work-view';

/** The value that stands for "no responsibility"; it is never sent, `area_id` is null instead. */
export const UNASSIGNED = 'unassigned';

export interface AreaChoice {
  value: string;
  label: string;
}

export function areaChoices(areas: readonly Area[]): AreaChoice[] {
  return [
    ...areas.map((area) => ({
      value: area.area_id,
      label: area.title ?? area.scope_text ?? '尚未命名的職責',
    })),
    { value: UNASSIGNED, label: '未歸屬任務' },
  ];
}
