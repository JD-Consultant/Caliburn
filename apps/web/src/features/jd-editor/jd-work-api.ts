/** Related collections share one observed revision, not independently refreshed heads. */
import { queryOptions } from '@tanstack/react-query';
import type { EditJdAreasRequest } from '../../shared/api/generated/edit-jd-areas-request';
import type { EditJdTasksRequest } from '../../shared/api/generated/edit-jd-tasks-request';
import type { EditJdCapabilitiesRequest } from '../../shared/api/generated/edit-jd-capabilities-request';
import type { EditJdCollaboratorsRequest } from '../../shared/api/generated/edit-jd-collaborators-request';
import type { EditJdConditionsRequest } from '../../shared/api/generated/edit-jd-conditions-request';
import { requestJson } from '../../shared/api/http';
import {
  isJdAreasView,
  isJdTasksView,
  isJdWorkView,
  isEditJdAreasRequest,
  isEditJdTasksRequest,
  isJdCapabilitiesView,
  isEditJdCapabilitiesRequest,
  isJdCollaboratorsView,
  isJdConditionsView,
  isEditJdCollaboratorsRequest,
  isEditJdConditionsRequest,
} from '../../shared/api/validation';

export type WorkCommand =
  | { collection: 'areas'; request: EditJdAreasRequest }
  | { collection: 'tasks'; request: EditJdTasksRequest }
  | { collection: 'capabilities'; request: EditJdCapabilitiesRequest }
  | { collection: 'collaborators'; request: EditJdCollaboratorsRequest }
  | { collection: 'conditions'; request: EditJdConditionsRequest };

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
    (value.collection === 'capabilities' && isEditJdCapabilitiesRequest(value.request)) ||
    (value.collection === 'collaborators' && isEditJdCollaboratorsRequest(value.request)) ||
    (value.collection === 'conditions' && isEditJdConditionsRequest(value.request))
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
  switch (command.collection) {
    case 'areas':
      await requestJson(url, isJdAreasView, options);
      break;
    case 'tasks':
      await requestJson(url, isJdTasksView, options);
      break;
    case 'capabilities':
      await requestJson(url, isJdCapabilitiesView, options);
      break;
    case 'collaborators':
      await requestJson(url, isJdCollaboratorsView, options);
      break;
    case 'conditions':
      await requestJson(url, isJdConditionsView, options);
      break;
  }
}

export type WorkIntent =
  | { collection: 'areas'; change: EditJdAreasRequest['change'] }
  | { collection: 'tasks'; change: EditJdTasksRequest['change'] }
  | { collection: 'capabilities'; change: EditJdCapabilitiesRequest['change'] }
  | { collection: 'collaborators'; change: EditJdCollaboratorsRequest['change'] }
  | { collection: 'conditions'; change: EditJdConditionsRequest['change'] };

export function commandFor(revisionId: string, intent: WorkIntent): WorkCommand {
  const base = { command_id: crypto.randomUUID(), expected_revision_id: revisionId };
  switch (intent.collection) {
    case 'areas':
      return { collection: 'areas', request: { ...base, change: intent.change } };
    case 'tasks':
      return { collection: 'tasks', request: { ...base, change: intent.change } };
    case 'capabilities':
      return { collection: 'capabilities', request: { ...base, change: intent.change } };
    case 'collaborators':
      return { collection: 'collaborators', request: { ...base, change: intent.change } };
    case 'conditions':
      return { collection: 'conditions', request: { ...base, change: intent.change } };
  }
}
