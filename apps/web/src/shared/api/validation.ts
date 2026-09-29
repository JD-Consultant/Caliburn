/** Runtime guards use the same SSOT as generated types; no second field definitions. */
import { Ajv2020 } from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import createJobFileSchema from '../../../../api/contracts/http/create-job-file-request.schema.json' with { type: 'json' };
import interviewHistorySchema from '../../../../api/contracts/http/interview-history.schema.json' with { type: 'json' };
import jobFileListSchema from '../../../../api/contracts/http/job-file-list.schema.json' with { type: 'json' };
import type { CreateJobFileRequest } from './generated/create-job-file-request';
import type { InterviewHistory } from './generated/interview-history';
import type { JobFile, JobFileList } from './generated/job-file-list';

const validator = new Ajv2020();
addFormats(validator);

export const isJobFileList = validator.compile<JobFileList>(jobFileListSchema);
export const isJobFile = validator.compile<JobFile>({
  $ref: '#/$defs/JobFile',
  $defs: jobFileListSchema.$defs,
});
export const isInterviewHistory = validator.compile<InterviewHistory>(interviewHistorySchema);
export const isCreateJobFileRequest = validator.compile<CreateJobFileRequest>(createJobFileSchema);
