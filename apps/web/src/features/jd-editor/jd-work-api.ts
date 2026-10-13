/** Related collections share one observed revision, not independently refreshed heads. */
import { queryOptions } from '@tanstack/react-query';
import type {
  EditJdAreasRequest,
  EditJdTasksRequest,
  EditJdCapabilitiesRequest,
  EditJdCollaboratorsRequest,
  EditJdConditionsRequest,
} from '../../shared/api/generated/http/types.gen';

import '../../shared/api/http';
import {
  readJdWork,
  editJdAreas,
  editJdTasks,
  editJdCapabilities,
  editJdCollaborators,
  editJdConditions,
} from '../../shared/api/generated/http/sdk.gen';
import {
  isEditJdAreasRequest,
  isEditJdTasksRequest,
  isEditJdCapabilitiesRequest,
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
      readJdWork({ path: { job_file_id: jobFileId }, signal, throwOnError: true }).then(
        ({ data }) => data,
      ),
  });
}

export async function editJdWork(jobFileId: string, command: WorkCommand): Promise<void> {
  const options = {
    path: { job_file_id: jobFileId },
    throwOnError: true as const,
    meta: { correlation: { jobFileId, commandId: command.request.command_id } },
  };
  switch (command.collection) {
    case 'areas':
      await editJdAreas({ ...options, body: command.request });
      break;
    case 'tasks':
      await editJdTasks({ ...options, body: command.request });
      break;
    case 'capabilities':
      await editJdCapabilities({ ...options, body: command.request });
      break;
    case 'collaborators':
      await editJdCollaborators({ ...options, body: command.request });
      break;
    case 'conditions':
      await editJdConditions({ ...options, body: command.request });
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
