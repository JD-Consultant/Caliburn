/** Runtime guards use the same SSOT as generated types; no second field definitions. */
import { Ajv2020 } from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
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

const validator = new Ajv2020();
addFormats(validator);
validator.addSchema(jdAreasSchema, 'jd-areas-view.schema.json');
validator.addSchema(jdTasksSchema, 'jd-tasks-view.schema.json');
validator.addSchema(jdCapabilitiesSchema, 'jd-capabilities-view.schema.json');

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
