/** Related collections share one observed revision, not independently refreshed heads. */
import { queryOptions } from '@tanstack/react-query';
import type { EditJdAreasRequest } from '../../shared/api/generated/edit-jd-areas-request';
import type { EditJdTasksRequest } from '../../shared/api/generated/edit-jd-tasks-request';
import type { EditJdCapabilitiesRequest } from '../../shared/api/generated/edit-jd-capabilities-request';
import { requestJson } from '../../shared/api/http';
import {
  isJdAreasView,
  isJdTasksView,
  isJdWorkView,
  isEditJdAreasRequest,
  isEditJdTasksRequest,
  isJdCapabilitiesView,
  isEditJdCapabilitiesRequest,
} from '../../shared/api/validation';

export type WorkCommand =
  | { collection: 'areas'; request: EditJdAreasRequest }
  | { collection: 'tasks'; request: EditJdTasksRequest }
  | { collection: 'capabilities'; request: EditJdCapabilitiesRequest };

export function isWorkCommand(value: unknown): value is WorkCommand {
  if (
    typeof value !== 'object' ||
    value === null ||
    !('collection' in value) ||
    !('request' in value)
  )
    return false;
  return (
    (value.collection === 'areas' && isEditJdAreasRequest(value.request)) ||
    (value.collection === 'tasks' && isEditJdTasksRequest(value.request)) ||
    (value.collection === 'capabilities' && isEditJdCapabilitiesRequest(value.request))
  );
}

export function jdWorkQuery(jobFileId: string) {
  return queryOptions({
    queryKey: ['jd-work', jobFileId, 'formal'],
    queryFn: ({ signal }) =>
      requestJson(`/api/job-files/${encodeURIComponent(jobFileId)}/jd/work`, isJdWorkView, {
        signal,
      }),
  });
}

export async function editJdWork(jobFileId: string, command: WorkCommand): Promise<void> {
  const options = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(command.request),
  };
  const url = `/api/job-files/${encodeURIComponent(jobFileId)}/jd/${command.collection}`;
  if (command.collection === 'areas') await requestJson(url, isJdAreasView, options);
  else if (command.collection === 'tasks') await requestJson(url, isJdTasksView, options);
  else await requestJson(url, isJdCapabilitiesView, options);
}

export type WorkIntent =
  | { collection: 'areas'; change: EditJdAreasRequest['change'] }
  | { collection: 'tasks'; change: EditJdTasksRequest['change'] }
  | { collection: 'capabilities'; change: EditJdCapabilitiesRequest['change'] };

export function commandFor(revisionId: string, intent: WorkIntent): WorkCommand {
  const base = { command_id: crypto.randomUUID(), expected_revision_id: revisionId };
  switch (intent.collection) {
    case 'areas':
      return { collection: 'areas', request: { ...base, change: intent.change } };
    case 'tasks':
      return { collection: 'tasks', request: { ...base, change: intent.change } };
    case 'capabilities':
      return { collection: 'capabilities', request: { ...base, change: intent.change } };
  }
}
