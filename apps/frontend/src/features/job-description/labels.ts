import type { ConditionKind } from '../../shared/api/generated/types.gen';

export const conditionLabels = {
  work_environment: '工作環境',
  schedule_travel: '工時與出差',
  shared_authority: '共通權限',
  shared_collaboration: '共通協作',
  qualification: '資格條件',
} satisfies Record<ConditionKind, string>;
