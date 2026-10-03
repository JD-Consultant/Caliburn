/** The four basic-data fields and the one command that revises them. */
import type {
  ProfileField,
  ReviseJdProfileRequest,
} from '../../shared/api/generated/revise-jd-profile-request';

export const profileLabels: Record<ProfileField, string> = {
  job_title: '職務名稱',
  organization_unit: '所屬單位／工作範圍',
  reports_to: '匯報關係',
  purpose: '職務目的',
};

export const profileFields: readonly ProfileField[] = [
  'job_title',
  'organization_unit',
  'reports_to',
  'purpose',
];

/** What an inline edit of a basic-data field wants done, before it has a command identity or a revision. */
export interface ProfileIntent {
  collection: 'profile';
  changes: ReviseJdProfileRequest['changes'];
}

export function profileCommandFor(
  revisionId: string,
  intent: ProfileIntent,
): ReviseJdProfileRequest {
  return {
    command_id: crypto.randomUUID(),
    expected_revision_id: revisionId,
    changes: intent.changes,
  };
}
