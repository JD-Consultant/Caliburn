/** Display vocabulary only; the generated schema owns the allowed wire values. */
import type { ConditionKind } from '../../shared/api/generated/edit-jd-conditions-request';

export const conditionLabels: Record<ConditionKind, string> = {
  work_environment: '工作環境',
  schedule_travel: '工時與出差',
  shared_authority: '共通權限界線',
  shared_collaboration: '共通協作界線',
  qualification: '必要資格',
};

export function isConditionKind(value: string): value is ConditionKind {
  return Object.hasOwn(conditionLabels, value);
}
