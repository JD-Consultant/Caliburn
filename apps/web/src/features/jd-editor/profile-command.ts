/** File-scoped unconfirmed transport intent, never a second editable JD or official result. */
import type { Profile } from '../../shared/api/generated/jd-profile-view';
import type {
  ProfileField,
  ReviseJdProfileRequest,
} from '../../shared/api/generated/revise-jd-profile-request';
import { isReviseJdProfileRequest } from '../../shared/api/validation';

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
export type ProfileDraft = Record<ProfileField, string>;

export function makeProfileDraft(
  profile: Profile,
  pending: ReviseJdProfileRequest | null,
): ProfileDraft {
  const draft = {
    job_title: profile.job_title ?? '',
    organization_unit: profile.organization_unit ?? '',
    reports_to: profile.reports_to ?? '',
    purpose: profile.purpose ?? '',
  };
  for (const change of pending?.changes ?? []) {
    draft[change.field] = change.action === 'set_field' ? change.value : '';
  }
  return draft;
}

function storageKey(jobFileId: string): string {
  return `caliburn.pending-jd-profile.${jobFileId}`;
}

export function readPendingProfile(jobFileId: string): ReviseJdProfileRequest | null {
  const stored = sessionStorage.getItem(storageKey(jobFileId));
  if (stored === null) return null;
  const command: unknown = JSON.parse(stored);
  if (!isReviseJdProfileRequest(command)) throw new Error('Invalid pending JD command');
  return command;
}

export function retainPendingProfile(jobFileId: string, command: ReviseJdProfileRequest): void {
  sessionStorage.setItem(storageKey(jobFileId), JSON.stringify(command));
}

export function clearPendingProfile(jobFileId: string): void {
  sessionStorage.removeItem(storageKey(jobFileId));
}
