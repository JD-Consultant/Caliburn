import type { ReasoningSummary } from './generated/http/types.gen';
import { isReasoningSummary } from './generated/http/validators.js';

export {
  isInterviewPlanView,
  isConsultantTurn,
  isCurrentConsultantTurn,
  isCommentaryUpdate,
  isReasoningSummary,
  isJobFileList,
  isJobFile,
  isInterviewHistory,
  isCreateJobFileRequest,
  isRenameJobFileRequest,
  isJdProfileView,
  isReviseJdProfileRequest,
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
} from './generated/http/validators.js';

export function isReasoningSummaryList(value: unknown): value is ReasoningSummary[] {
  return Array.isArray(value) && value.every((item: unknown) => isReasoningSummary(item));
}
