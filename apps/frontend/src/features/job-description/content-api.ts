/** JD 內容的具名 HTTP 操作；完整回覆交給保存協調決定快取更新。 */
import type {
  JobDescriptionResponse,
  AddCollaborationRequest,
  AddConditionRequest,
  AddDutyRequest,
  AddKnowledgeRequest,
  AddSkillRequest,
  AddTaskRequest,
  UpdateCollaborationRequest,
  UpdateConditionRequest,
  UpdateDutyRequest,
  UpdateJobDescriptionRequest,
  UpdateKnowledgeRequest,
  UpdateSkillRequest,
  UpdateTaskRequest,
} from '../../shared/api/generated/types.gen';

import {
  validateAddCollaborationRequest,
  validateAddConditionRequest,
  validateAddDutyRequest,
  validateAddKnowledgeRequest,
  validateAddSkillRequest,
  validateAddTaskRequest,
  validateUpdateCollaborationRequest,
  validateUpdateConditionRequest,
  validateUpdateDutyRequest,
  validateUpdateJobDescriptionRequest,
  validateUpdateKnowledgeRequest,
  validateUpdateSkillRequest,
  validateUpdateTaskRequest,
} from '../../shared/api/generated/validators';
import { deleteJobDescriptionContent, writeJobDescription } from './api-transport';

// UI 的單項操作從正式 PATCH 型別投影；外送仍由同一生成 validator 驗證。
type WriteInput = Pick<UpdateTaskRequest, 'expected_version' | 'correlation_id'>;
type TaskChange = NonNullable<UpdateTaskRequest['changes']>[number];
type TaskTextInput = WriteInput &
  Pick<Extract<TaskChange, { action: 'add_outcome' }>, 'text'>;
type PlacementInput = WriteInput & NonNullable<UpdateDutyRequest['placement']>;
type TaskPlacementInput = WriteInput & NonNullable<UpdateTaskRequest['placement']>;
type CreateDefinitionInput = WriteInput &
  Pick<
    Extract<TaskChange, { action: 'create_and_link_knowledge' }>,
    'name' | 'description'
  >;

export function updateJobDescription(
  workspaceId: string,
  jdId: string,
  body: UpdateJobDescriptionRequest,
): Promise<JobDescriptionResponse> {
  return writeJobDescription(
    workspaceId,
    jdId,
    ``,
    'PATCH',
    body,
    validateUpdateJobDescriptionRequest,
    200,
  );
}

export function addDuty(
  workspaceId: string,
  jdId: string,
  body: AddDutyRequest,
): Promise<JobDescriptionResponse> {
  return writeJobDescription(
    workspaceId,
    jdId,
    `/duties`,
    'POST',
    body,
    validateAddDutyRequest,
    201,
  );
}

export function updateDuty(
  workspaceId: string,
  jdId: string,
  dutyId: string,
  body: UpdateDutyRequest,
): Promise<JobDescriptionResponse> {
  return writeJobDescription(
    workspaceId,
    jdId,
    `/duties/${encodeURIComponent(dutyId)}`,
    'PATCH',
    body,
    validateUpdateDutyRequest,
    200,
  );
}

export function deleteDuty(
  workspaceId: string,
  jdId: string,
  dutyId: string,
  expectedVersion: number,
): Promise<JobDescriptionResponse> {
  return deleteJobDescriptionContent(
    workspaceId,
    jdId,
    `/duties/${encodeURIComponent(dutyId)}`,
    expectedVersion,
  );
}

export function moveDuty(
  workspaceId: string,
  jdId: string,
  dutyId: string,
  body: PlacementInput,
): Promise<JobDescriptionResponse> {
  const { before_id, ...write } = body;
  return updateDuty(workspaceId, jdId, dutyId, {
    ...write,
    placement: before_id === undefined ? {} : { before_id },
  });
}

export function addTask(
  workspaceId: string,
  jdId: string,
  body: AddTaskRequest,
): Promise<JobDescriptionResponse> {
  return writeJobDescription(
    workspaceId,
    jdId,
    `/tasks`,
    'POST',
    body,
    validateAddTaskRequest,
    201,
  );
}

export function updateTask(
  workspaceId: string,
  jdId: string,
  taskId: string,
  body: UpdateTaskRequest,
): Promise<JobDescriptionResponse> {
  return writeJobDescription(
    workspaceId,
    jdId,
    `/tasks/${encodeURIComponent(taskId)}`,
    'PATCH',
    body,
    validateUpdateTaskRequest,
    200,
  );
}

export function deleteTask(
  workspaceId: string,
  jdId: string,
  taskId: string,
  expectedVersion: number,
): Promise<JobDescriptionResponse> {
  return deleteJobDescriptionContent(
    workspaceId,
    jdId,
    `/tasks/${encodeURIComponent(taskId)}`,
    expectedVersion,
  );
}

export function moveTask(
  workspaceId: string,
  jdId: string,
  taskId: string,
  body: TaskPlacementInput,
): Promise<JobDescriptionResponse> {
  const { destination_duty_id, before_id, ...write } = body;
  return updateTask(workspaceId, jdId, taskId, {
    ...write,
    placement: { destination_duty_id, ...(before_id === undefined ? {} : { before_id }) },
  });
}

export function addKnowledge(
  workspaceId: string,
  jdId: string,
  body: AddKnowledgeRequest,
): Promise<JobDescriptionResponse> {
  return writeJobDescription(
    workspaceId,
    jdId,
    `/knowledge`,
    'POST',
    body,
    validateAddKnowledgeRequest,
    201,
  );
}

export function updateKnowledge(
  workspaceId: string,
  jdId: string,
  knowledgeId: string,
  body: UpdateKnowledgeRequest,
): Promise<JobDescriptionResponse> {
  return writeJobDescription(
    workspaceId,
    jdId,
    `/knowledge/${encodeURIComponent(knowledgeId)}`,
    'PATCH',
    body,
    validateUpdateKnowledgeRequest,
    200,
  );
}

export function deleteKnowledge(
  workspaceId: string,
  jdId: string,
  knowledgeId: string,
  expectedVersion: number,
): Promise<JobDescriptionResponse> {
  return deleteJobDescriptionContent(
    workspaceId,
    jdId,
    `/knowledge/${encodeURIComponent(knowledgeId)}`,
    expectedVersion,
  );
}

export function moveKnowledge(
  workspaceId: string,
  jdId: string,
  knowledgeId: string,
  body: PlacementInput,
): Promise<JobDescriptionResponse> {
  const { before_id, ...write } = body;
  return updateKnowledge(workspaceId, jdId, knowledgeId, {
    ...write,
    placement: before_id === undefined ? {} : { before_id },
  });
}

export function addSkill(
  workspaceId: string,
  jdId: string,
  body: AddSkillRequest,
): Promise<JobDescriptionResponse> {
  return writeJobDescription(
    workspaceId,
    jdId,
    `/skills`,
    'POST',
    body,
    validateAddSkillRequest,
    201,
  );
}

export function updateSkill(
  workspaceId: string,
  jdId: string,
  skillId: string,
  body: UpdateSkillRequest,
): Promise<JobDescriptionResponse> {
  return writeJobDescription(
    workspaceId,
    jdId,
    `/skills/${encodeURIComponent(skillId)}`,
    'PATCH',
    body,
    validateUpdateSkillRequest,
    200,
  );
}

export function deleteSkill(
  workspaceId: string,
  jdId: string,
  skillId: string,
  expectedVersion: number,
): Promise<JobDescriptionResponse> {
  return deleteJobDescriptionContent(
    workspaceId,
    jdId,
    `/skills/${encodeURIComponent(skillId)}`,
    expectedVersion,
  );
}

export function moveSkill(
  workspaceId: string,
  jdId: string,
  skillId: string,
  body: PlacementInput,
): Promise<JobDescriptionResponse> {
  const { before_id, ...write } = body;
  return updateSkill(workspaceId, jdId, skillId, {
    ...write,
    placement: before_id === undefined ? {} : { before_id },
  });
}

export function addCollaboration(
  workspaceId: string,
  jdId: string,
  body: AddCollaborationRequest,
): Promise<JobDescriptionResponse> {
  return writeJobDescription(
    workspaceId,
    jdId,
    `/collaborations`,
    'POST',
    body,
    validateAddCollaborationRequest,
    201,
  );
}

export function updateCollaboration(
  workspaceId: string,
  jdId: string,
  collaborationId: string,
  body: UpdateCollaborationRequest,
): Promise<JobDescriptionResponse> {
  return writeJobDescription(
    workspaceId,
    jdId,
    `/collaborations/${encodeURIComponent(collaborationId)}`,
    'PATCH',
    body,
    validateUpdateCollaborationRequest,
    200,
  );
}

export function deleteCollaboration(
  workspaceId: string,
  jdId: string,
  collaborationId: string,
  expectedVersion: number,
): Promise<JobDescriptionResponse> {
  return deleteJobDescriptionContent(
    workspaceId,
    jdId,
    `/collaborations/${encodeURIComponent(collaborationId)}`,
    expectedVersion,
  );
}

export function moveCollaboration(
  workspaceId: string,
  jdId: string,
  collaborationId: string,
  body: PlacementInput,
): Promise<JobDescriptionResponse> {
  const { before_id, ...write } = body;
  return updateCollaboration(workspaceId, jdId, collaborationId, {
    ...write,
    placement: before_id === undefined ? {} : { before_id },
  });
}

export function addCondition(
  workspaceId: string,
  jdId: string,
  body: AddConditionRequest,
): Promise<JobDescriptionResponse> {
  return writeJobDescription(
    workspaceId,
    jdId,
    `/conditions`,
    'POST',
    body,
    validateAddConditionRequest,
    201,
  );
}

export function updateCondition(
  workspaceId: string,
  jdId: string,
  conditionId: string,
  body: UpdateConditionRequest,
): Promise<JobDescriptionResponse> {
  return writeJobDescription(
    workspaceId,
    jdId,
    `/conditions/${encodeURIComponent(conditionId)}`,
    'PATCH',
    body,
    validateUpdateConditionRequest,
    200,
  );
}

export function deleteCondition(
  workspaceId: string,
  jdId: string,
  conditionId: string,
  expectedVersion: number,
): Promise<JobDescriptionResponse> {
  return deleteJobDescriptionContent(
    workspaceId,
    jdId,
    `/conditions/${encodeURIComponent(conditionId)}`,
    expectedVersion,
  );
}

export function moveCondition(
  workspaceId: string,
  jdId: string,
  conditionId: string,
  body: PlacementInput,
): Promise<JobDescriptionResponse> {
  const { before_id, ...write } = body;
  return updateCondition(workspaceId, jdId, conditionId, {
    ...write,
    placement: before_id === undefined ? {} : { before_id },
  });
}

export function addOutcome(
  workspaceId: string,
  jdId: string,
  taskId: string,
  body: TaskTextInput,
): Promise<JobDescriptionResponse> {
  const { text, ...write } = body;
  return updateTask(workspaceId, jdId, taskId, {
    ...write,
    changes: [{ action: 'add_outcome', text }],
  });
}

export function updateOutcome(
  workspaceId: string,
  jdId: string,
  taskId: string,
  outcomeId: string,
  body: TaskTextInput,
): Promise<JobDescriptionResponse> {
  const { text, ...write } = body;
  return updateTask(workspaceId, jdId, taskId, {
    ...write,
    changes: [{ action: 'update_outcome', id: outcomeId, text }],
  });
}

export function deleteOutcome(
  workspaceId: string,
  jdId: string,
  taskId: string,
  outcomeId: string,
  expectedVersion: number,
): Promise<JobDescriptionResponse> {
  return updateTask(workspaceId, jdId, taskId, {
    expected_version: expectedVersion,
    changes: [{ action: 'delete_outcome', id: outcomeId }],
  });
}

export function moveOutcome(
  workspaceId: string,
  jdId: string,
  taskId: string,
  outcomeId: string,
  body: PlacementInput,
): Promise<JobDescriptionResponse> {
  const { before_id, ...write } = body;
  return updateTask(workspaceId, jdId, taskId, {
    ...write,
    changes: [
      {
        action: 'move_outcome',
        id: outcomeId,
        ...(before_id === undefined ? {} : { before_id }),
      },
    ],
  });
}

export function addRequirement(
  workspaceId: string,
  jdId: string,
  taskId: string,
  body: TaskTextInput,
): Promise<JobDescriptionResponse> {
  const { text, ...write } = body;
  return updateTask(workspaceId, jdId, taskId, {
    ...write,
    changes: [{ action: 'add_requirement', text }],
  });
}

export function updateRequirement(
  workspaceId: string,
  jdId: string,
  taskId: string,
  requirementId: string,
  body: TaskTextInput,
): Promise<JobDescriptionResponse> {
  const { text, ...write } = body;
  return updateTask(workspaceId, jdId, taskId, {
    ...write,
    changes: [{ action: 'update_requirement', id: requirementId, text }],
  });
}

export function deleteRequirement(
  workspaceId: string,
  jdId: string,
  taskId: string,
  requirementId: string,
  expectedVersion: number,
): Promise<JobDescriptionResponse> {
  return updateTask(workspaceId, jdId, taskId, {
    expected_version: expectedVersion,
    changes: [{ action: 'delete_requirement', id: requirementId }],
  });
}

export function moveRequirement(
  workspaceId: string,
  jdId: string,
  taskId: string,
  requirementId: string,
  body: PlacementInput,
): Promise<JobDescriptionResponse> {
  const { before_id, ...write } = body;
  return updateTask(workspaceId, jdId, taskId, {
    ...write,
    changes: [
      {
        action: 'move_requirement',
        id: requirementId,
        ...(before_id === undefined ? {} : { before_id }),
      },
    ],
  });
}

export function linkKnowledge(
  workspaceId: string,
  jdId: string,
  taskId: string,
  knowledgeId: string,
  body: WriteInput,
): Promise<JobDescriptionResponse> {
  return updateTask(workspaceId, jdId, taskId, {
    ...body,
    changes: [{ action: 'link_knowledge', id: knowledgeId }],
  });
}

export function unlinkKnowledge(
  workspaceId: string,
  jdId: string,
  taskId: string,
  knowledgeId: string,
  expectedVersion: number,
): Promise<JobDescriptionResponse> {
  return updateTask(workspaceId, jdId, taskId, {
    expected_version: expectedVersion,
    changes: [{ action: 'unlink_knowledge', id: knowledgeId }],
  });
}

export function moveKnowledgeReference(
  workspaceId: string,
  jdId: string,
  taskId: string,
  knowledgeId: string,
  body: PlacementInput,
): Promise<JobDescriptionResponse> {
  const { before_id, ...write } = body;
  return updateTask(workspaceId, jdId, taskId, {
    ...write,
    changes: [
      {
        action: 'move_knowledge_reference',
        id: knowledgeId,
        ...(before_id === undefined ? {} : { before_id }),
      },
    ],
  });
}

export function linkSkill(
  workspaceId: string,
  jdId: string,
  taskId: string,
  skillId: string,
  body: WriteInput,
): Promise<JobDescriptionResponse> {
  return updateTask(workspaceId, jdId, taskId, {
    ...body,
    changes: [{ action: 'link_skill', id: skillId }],
  });
}

export function unlinkSkill(
  workspaceId: string,
  jdId: string,
  taskId: string,
  skillId: string,
  expectedVersion: number,
): Promise<JobDescriptionResponse> {
  return updateTask(workspaceId, jdId, taskId, {
    expected_version: expectedVersion,
    changes: [{ action: 'unlink_skill', id: skillId }],
  });
}

export function moveSkillReference(
  workspaceId: string,
  jdId: string,
  taskId: string,
  skillId: string,
  body: PlacementInput,
): Promise<JobDescriptionResponse> {
  const { before_id, ...write } = body;
  return updateTask(workspaceId, jdId, taskId, {
    ...write,
    changes: [
      {
        action: 'move_skill_reference',
        id: skillId,
        ...(before_id === undefined ? {} : { before_id }),
      },
    ],
  });
}

export function reclassifyCondition(
  workspaceId: string,
  jdId: string,
  conditionId: string,
  body: WriteInput & Pick<AddConditionRequest, 'kind'>,
): Promise<JobDescriptionResponse> {
  return updateCondition(workspaceId, jdId, conditionId, body);
}

export function createAndLinkKnowledge(
  workspaceId: string,
  jdId: string,
  taskId: string,
  body: CreateDefinitionInput,
): Promise<JobDescriptionResponse> {
  const { name, description, ...write } = body;
  return updateTask(workspaceId, jdId, taskId, {
    ...write,
    changes: [
      {
        action: 'create_and_link_knowledge',
        name,
        ...(description === undefined ? {} : { description }),
      },
    ],
  });
}

export function createAndLinkSkill(
  workspaceId: string,
  jdId: string,
  taskId: string,
  body: CreateDefinitionInput,
): Promise<JobDescriptionResponse> {
  const { name, description, ...write } = body;
  return updateTask(workspaceId, jdId, taskId, {
    ...write,
    changes: [
      {
        action: 'create_and_link_skill',
        name,
        ...(description === undefined ? {} : { description }),
      },
    ],
  });
}
