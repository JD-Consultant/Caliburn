/** Runtime guards use the same SSOT as generated types; no second field definitions. */
import { createSchemaValidator } from './schema-policy';
import interviewPlanSchema from '../../../../api/contracts/tools/interview-plan.schema.json' with { type: 'json' };
import interviewPlanViewSchema from '../../../../api/contracts/http/interview-plan-view.schema.json' with { type: 'json' };
import type { InterviewPlanView } from './generated/interview-plan-view';
import commentaryUpdateSchema from '../../../../api/contracts/http/commentary-update.schema.json' with { type: 'json' };
import type { CommentaryUpdate } from './generated/commentary-update';
import reasoningSummarySchema from '../../../../api/contracts/http/reasoning-summary.schema.json' with { type: 'json' };
import type { ReasoningSummary } from './generated/reasoning-summary';
import consultantTurnSchema from '../../../../api/contracts/http/consultant-turn.schema.json' with { type: 'json' };
import type { ConsultantTurn } from './generated/consultant-turn';
import currentConsultantTurnSchema from '../../../../api/contracts/http/current-consultant-turn.schema.json' with { type: 'json' };
import type { CurrentConsultantTurn } from './generated/current-consultant-turn';
import createJobFileSchema from '../../../../api/contracts/http/create-job-file-request.schema.json' with { type: 'json' };
import interviewHistorySchema from '../../../../api/contracts/http/interview-history.schema.json' with { type: 'json' };
import jobFileListSchema from '../../../../api/contracts/http/job-file-list.schema.json' with { type: 'json' };
import renameJobFileSchema from '../../../../api/contracts/http/rename-job-file-request.schema.json' with { type: 'json' };
import jdProfileSchema from '../../../../api/contracts/http/jd-profile-view.schema.json' with { type: 'json' };
import reviseJdProfileSchema from '../../../../api/contracts/http/revise-jd-profile-request.schema.json' with { type: 'json' };
import jdAreasSchema from '../../../../api/contracts/http/jd-areas-view.schema.json' with { type: 'json' };
import jdTasksSchema from '../../../../api/contracts/http/jd-tasks-view.schema.json' with { type: 'json' };
import jdWorkSchema from '../../../../api/contracts/http/jd-work-view.schema.json' with { type: 'json' };
import editJdAreasSchema from '../../../../api/contracts/http/edit-jd-areas-request.schema.json' with { type: 'json' };
import editJdTasksSchema from '../../../../api/contracts/http/edit-jd-tasks-request.schema.json' with { type: 'json' };
import jdCapabilitiesSchema from '../../../../api/contracts/http/jd-capabilities-view.schema.json' with { type: 'json' };
import editJdCapabilitiesSchema from '../../../../api/contracts/http/edit-jd-capabilities-request.schema.json' with { type: 'json' };
import jdCollaboratorsSchema from '../../../../api/contracts/http/jd-collaborators-view.schema.json' with { type: 'json' };
import jdConditionsSchema from '../../../../api/contracts/http/jd-conditions-view.schema.json' with { type: 'json' };
import editJdCollaboratorsSchema from '../../../../api/contracts/http/edit-jd-collaborators-request.schema.json' with { type: 'json' };
import editJdConditionsSchema from '../../../../api/contracts/http/edit-jd-conditions-request.schema.json' with { type: 'json' };
import type { CreateJobFileRequest } from './generated/create-job-file-request';
import type { InterviewHistory } from './generated/interview-history';
import type { JobFile, JobFileList } from './generated/job-file-list';
import type { RenameJobFileRequest } from './generated/rename-job-file-request';
import type { JdProfileView } from './generated/jd-profile-view';
import type { ReviseJdProfileRequest } from './generated/revise-jd-profile-request';
import type { JdAreasView } from './generated/jd-areas-view';
import type { JdTasksView } from './generated/jd-tasks-view';
import type { JdWorkView } from './generated/jd-work-view';
import type { EditJdAreasRequest } from './generated/edit-jd-areas-request';
import type { EditJdTasksRequest } from './generated/edit-jd-tasks-request';
import type { JdCapabilitiesView } from './generated/jd-capabilities-view';
import type { EditJdCapabilitiesRequest } from './generated/edit-jd-capabilities-request';
import type { EditJdCollaboratorsRequest } from './generated/edit-jd-collaborators-request';
import type { EditJdConditionsRequest } from './generated/edit-jd-conditions-request';
import type { JdCollaboratorsView } from './generated/jd-collaborators-view';
import type { JdConditionsView } from './generated/jd-conditions-view';

const validator = createSchemaValidator();
validator.addSchema(interviewPlanSchema, 'tools/interview-plan.schema.json');
validator.addSchema(jdAreasSchema, 'jd-areas-view.schema.json');
validator.addSchema(jdTasksSchema, 'jd-tasks-view.schema.json');
validator.addSchema(jdCapabilitiesSchema, 'jd-capabilities-view.schema.json');
validator.addSchema(jdCollaboratorsSchema, 'jd-collaborators-view.schema.json');
validator.addSchema(jdConditionsSchema, 'jd-conditions-view.schema.json');
validator.addSchema(jdProfileSchema, 'jd-profile-view.schema.json');
validator.addSchema(jdWorkSchema, 'jd-work-view.schema.json');
validator.addSchema(consultantTurnSchema, 'consultant-turn.schema.json');

export const isInterviewPlanView = validator.compile<InterviewPlanView>(interviewPlanViewSchema);
export const isConsultantTurn = validator.compile<ConsultantTurn>(consultantTurnSchema);
export const isCurrentConsultantTurn = validator.compile<CurrentConsultantTurn>(
  currentConsultantTurnSchema,
);
export const isCommentaryUpdate = validator.compile<CommentaryUpdate>(commentaryUpdateSchema);
export const isReasoningSummary = validator.compile<ReasoningSummary>(reasoningSummarySchema);

export function isReasoningSummaryList(value: unknown): value is ReasoningSummary[] {
  return Array.isArray(value) && value.every((item: unknown) => isReasoningSummary(item));
}

export const isJobFileList = validator.compile<JobFileList>(jobFileListSchema);
export const isJobFile = validator.compile<JobFile>({
  $ref: '#/$defs/JobFile',
  $defs: jobFileListSchema.$defs,
});
export const isInterviewHistory = validator.compile<InterviewHistory>(interviewHistorySchema);
export const isCreateJobFileRequest = validator.compile<CreateJobFileRequest>(createJobFileSchema);
export const isRenameJobFileRequest = validator.compile<RenameJobFileRequest>(renameJobFileSchema);
export const isJdProfileView = validator.compile<JdProfileView>(jdProfileSchema);
export const isReviseJdProfileRequest =
  validator.compile<ReviseJdProfileRequest>(reviseJdProfileSchema);
export const isJdAreasView = validator.compile<JdAreasView>(jdAreasSchema);
export const isJdTasksView = validator.compile<JdTasksView>(jdTasksSchema);
export const isJdWorkView = validator.compile<JdWorkView>(jdWorkSchema);
export const isEditJdAreasRequest = validator.compile<EditJdAreasRequest>(editJdAreasSchema);
export const isEditJdTasksRequest = validator.compile<EditJdTasksRequest>(editJdTasksSchema);
export const isJdCapabilitiesView = validator.compile<JdCapabilitiesView>(jdCapabilitiesSchema);
export const isEditJdCapabilitiesRequest =
  validator.compile<EditJdCapabilitiesRequest>(editJdCapabilitiesSchema);
export const isJdCollaboratorsView = validator.compile<JdCollaboratorsView>(jdCollaboratorsSchema);
export const isJdConditionsView = validator.compile<JdConditionsView>(jdConditionsSchema);
export const isEditJdCollaboratorsRequest =
  validator.compile<EditJdCollaboratorsRequest>(editJdCollaboratorsSchema);
export const isEditJdConditionsRequest =
  validator.compile<EditJdConditionsRequest>(editJdConditionsSchema);
