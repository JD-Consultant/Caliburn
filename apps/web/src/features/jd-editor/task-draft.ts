/** Local editable rows retain server detail identity; new row keys never become server IDs. */
import type { Detail } from '../../shared/api/generated/jd-work-view';
import type { TaskChange } from '../../shared/api/generated/edit-jd-tasks-request';

export interface DetailDraft {
  key: string;
  detailId?: string;
  text: string;
}

export function makeDetailDraft(details: readonly Detail[]): DetailDraft[] {
  return details.map((detail) => ({
    key: detail.detail_id,
    detailId: detail.detail_id,
    text: detail.text,
  }));
}

export function detailChanges(
  original: readonly Detail[],
  draft: readonly DetailDraft[],
  kind: 'outcome' | 'requirement',
): TaskChange[] {
  const changes: TaskChange[] = original
    .filter((detail) => !draft.some((row) => row.detailId === detail.detail_id))
    .map((detail) => ({ action: 'remove_detail', detail_id: detail.detail_id }));
  for (const row of draft) {
    if (!row.detailId) changes.push({ action: 'add_detail', kind, text: row.text });
    else if (original.find((detail) => detail.detail_id === row.detailId)?.text !== row.text)
      changes.push({ action: 'revise_detail', detail_id: row.detailId, text: row.text });
  }
  return changes;
}
