/* Generated from FastAPI OpenAPI; do not edit. */
import type { ValidateFunction } from 'ajv';
import type {
  AddCitationRequest,
  AddCollaborationRequest,
  AddConditionRequest,
  AddDutyRequest,
  AddKnowledgeRequest,
  AddOutcomeChange,
  AddRequirementChange,
  AddSkillRequest,
  AddTaskRequest,
  Answer,
  AnswerInput,
  AnswerRequest,
  AnswerTurnRequest,
  CancelStatus,
  CancellationData,
  CancellationEvent,
  ChangeCitationsRequest,
  CitationChangeRequest,
  CitationComparisonResponse,
  CitationDetailsResponse,
  CitationResponse,
  CitationSourceResponse,
  CitationTargetKind,
  CollaborationResponse,
  CollectionDifferenceResponse,
  CollectionKind,
  CommitStatus,
  CompactionView,
  ConcurrencyReason,
  ConditionKind,
  ConditionResponse,
  ConfirmCitationRequest,
  ContentValue,
  CreateAndLinkKnowledgeChange,
  CreateAndLinkSkillChange,
  CreateJobDescriptionRequest,
  CreateWorkspaceRequest,
  DeleteOutcomeChange,
  DeleteRequirementChange,
  DutyResponse,
  ErrorDetail,
  ErrorResponse,
  ExistingDefinitionRequest,
  FieldDifferenceResponse,
  HistoryEntryResponse,
  HistoryPageResponse,
  HistoryResponse,
  InterruptView,
  InterviewReferenceRequest,
  InterviewReferenceResponse,
  ItemDifferenceResponse,
  ItemKind,
  JobDescriptionContentResponse,
  JobDescriptionDifferenceResponse,
  JobDescriptionErrorDetail,
  JobDescriptionErrorResponse,
  JobDescriptionResponse,
  JobDescriptionTurnChangesResponse,
  JsonValue,
  KnowledgeResponse,
  LinkKnowledgeChange,
  LinkSkillChange,
  MemoryCitationContentResponse,
  MemoryCitationItemResponse,
  MemoryContentResponse,
  MemoryItemResponse,
  MemoryMapEntryResponse,
  MemoryMapResponse,
  MemoryReferenceRequest,
  MemoryReferenceResponse,
  MessageContent,
  MessageKind,
  MessageView,
  ModelDeltaData,
  MoveKnowledgeReferenceChange,
  MoveOutcomeChange,
  MoveRequirementChange,
  MoveSkillReferenceChange,
  NewDefinitionRequest,
  OccupationReference,
  OccupationReferenceHit,
  PlacementRequest,
  PlanResponse,
  PublishedVersion,
  Question,
  QuestionExchange,
  QuestionOption,
  ReasoningSummaryDeltaEvent,
  ReferenceCompetencyBlock,
  ReferenceEvidence,
  ReferenceIndicator,
  ReferenceNamedContent,
  ReferenceRetrievalPolicy,
  ReferenceSearchRequest,
  ReferenceSearchResponse,
  ReferenceTaskDetail,
  ReferenceTaskName,
  ReferenceTaskSummary,
  ReferenceUnit,
  RemoveCitationRequest,
  RenameWorkspaceRequest,
  RestoreJobDescriptionRequest,
  ResyncRequiredData,
  ResyncRequiredEvent,
  SavedQuestion,
  SkillResponse,
  SourceReferenceRequest,
  SourceReferenceResponse,
  Speaker,
  StepView,
  SubmitTurnRequest,
  TaskPlacementRequest,
  TaskResponse,
  TaskTextResponse,
  TextContent,
  TextDeltaEvent,
  ToolCallData,
  ToolCallEvent,
  ToolCallView,
  TranscriptMessage,
  TurnEvent,
  TurnStatusEvent,
  TurnView,
  UnlinkKnowledgeChange,
  UnlinkSkillChange,
  UpdateCollaborationRequest,
  UpdateConditionRequest,
  UpdateDutyRequest,
  UpdateJobDescriptionRequest,
  UpdateKnowledgeRequest,
  UpdateOutcomeChange,
  UpdateRequirementChange,
  UpdateSkillRequest,
  UpdateTaskRequest,
  UsageView,
  ValidationIssue,
  WorkspaceConflictDetail,
  WorkspaceConflictReason,
  WorkspaceConflictResponse,
  WorkspacePageResponse,
  WorkspaceResponse,
  caliburn__modules__job_description__presentation__api__schemas__citations__CitationRequests__1,
  caliburn__modules__job_description__presentation__api__schemas__citations__CitationRequests__2,
  JdDeleteTaskData,
} from './types.gen';

export declare const validateAddCitationRequest: ValidateFunction<AddCitationRequest>;
export declare const validateAddCollaborationRequest: ValidateFunction<AddCollaborationRequest>;
export declare const validateAddConditionRequest: ValidateFunction<AddConditionRequest>;
export declare const validateAddDutyRequest: ValidateFunction<AddDutyRequest>;
export declare const validateAddKnowledgeRequest: ValidateFunction<AddKnowledgeRequest>;
export declare const validateAddOutcomeChange: ValidateFunction<AddOutcomeChange>;
export declare const validateAddRequirementChange: ValidateFunction<AddRequirementChange>;
export declare const validateAddSkillRequest: ValidateFunction<AddSkillRequest>;
export declare const validateAddTaskRequest: ValidateFunction<AddTaskRequest>;
export declare const validateAnswer: ValidateFunction<Answer>;
export declare const validateAnswerInput: ValidateFunction<AnswerInput>;
export declare const validateAnswerRequest: ValidateFunction<AnswerRequest>;
export declare const validateAnswerTurnRequest: ValidateFunction<AnswerTurnRequest>;
export declare const validateCancelStatus: ValidateFunction<CancelStatus>;
export declare const validateCancellationData: ValidateFunction<CancellationData>;
export declare const validateCancellationEvent: ValidateFunction<CancellationEvent>;
export declare const validateChangeCitationsRequest: ValidateFunction<ChangeCitationsRequest>;
export declare const validateCitationChangeRequest: ValidateFunction<CitationChangeRequest>;
export declare const validateCitationComparisonResponse: ValidateFunction<CitationComparisonResponse>;
export declare const validateCitationDetailsResponse: ValidateFunction<CitationDetailsResponse>;
export declare const validateCitationResponse: ValidateFunction<CitationResponse>;
export declare const validateCitationSourceResponse: ValidateFunction<CitationSourceResponse>;
export declare const validateCitationTargetKind: ValidateFunction<CitationTargetKind>;
export declare const validateCollaborationResponse: ValidateFunction<CollaborationResponse>;
export declare const validateCollectionDifferenceResponse: ValidateFunction<CollectionDifferenceResponse>;
export declare const validateCollectionKind: ValidateFunction<CollectionKind>;
export declare const validateCommitStatus: ValidateFunction<CommitStatus>;
export declare const validateCompactionView: ValidateFunction<CompactionView>;
export declare const validateConcurrencyReason: ValidateFunction<ConcurrencyReason>;
export declare const validateConditionKind: ValidateFunction<ConditionKind>;
export declare const validateConditionResponse: ValidateFunction<ConditionResponse>;
export declare const validateConfirmCitationRequest: ValidateFunction<ConfirmCitationRequest>;
export declare const validateContentValue: ValidateFunction<ContentValue>;
export declare const validateCreateAndLinkKnowledgeChange: ValidateFunction<CreateAndLinkKnowledgeChange>;
export declare const validateCreateAndLinkSkillChange: ValidateFunction<CreateAndLinkSkillChange>;
export declare const validateCreateJobDescriptionRequest: ValidateFunction<CreateJobDescriptionRequest>;
export declare const validateCreateWorkspaceRequest: ValidateFunction<CreateWorkspaceRequest>;
export declare const validateDeleteOutcomeChange: ValidateFunction<DeleteOutcomeChange>;
export declare const validateDeleteRequirementChange: ValidateFunction<DeleteRequirementChange>;
export declare const validateDutyResponse: ValidateFunction<DutyResponse>;
export declare const validateErrorDetail: ValidateFunction<ErrorDetail>;
export declare const validateErrorResponse: ValidateFunction<ErrorResponse>;
export declare const validateExistingDefinitionRequest: ValidateFunction<ExistingDefinitionRequest>;
export declare const validateFieldDifferenceResponse: ValidateFunction<FieldDifferenceResponse>;
export declare const validateHistoryEntryResponse: ValidateFunction<HistoryEntryResponse>;
export declare const validateHistoryPageResponse: ValidateFunction<HistoryPageResponse>;
export declare const validateHistoryResponse: ValidateFunction<HistoryResponse>;
export declare const validateInterruptView: ValidateFunction<InterruptView>;
export declare const validateInterviewReferenceRequest: ValidateFunction<InterviewReferenceRequest>;
export declare const validateInterviewReferenceResponse: ValidateFunction<InterviewReferenceResponse>;
export declare const validateItemDifferenceResponse: ValidateFunction<ItemDifferenceResponse>;
export declare const validateItemKind: ValidateFunction<ItemKind>;
export declare const validateJobDescriptionContentResponse: ValidateFunction<JobDescriptionContentResponse>;
export declare const validateJobDescriptionDifferenceResponse: ValidateFunction<JobDescriptionDifferenceResponse>;
export declare const validateJobDescriptionErrorDetail: ValidateFunction<JobDescriptionErrorDetail>;
export declare const validateJobDescriptionErrorResponse: ValidateFunction<JobDescriptionErrorResponse>;
export declare const validateJobDescriptionResponse: ValidateFunction<JobDescriptionResponse>;
export declare const validateJobDescriptionTurnChangesResponse: ValidateFunction<JobDescriptionTurnChangesResponse>;
export declare const validateJsonValue: ValidateFunction<JsonValue>;
export declare const validateKnowledgeResponse: ValidateFunction<KnowledgeResponse>;
export declare const validateLinkKnowledgeChange: ValidateFunction<LinkKnowledgeChange>;
export declare const validateLinkSkillChange: ValidateFunction<LinkSkillChange>;
export declare const validateMemoryCitationContentResponse: ValidateFunction<MemoryCitationContentResponse>;
export declare const validateMemoryCitationItemResponse: ValidateFunction<MemoryCitationItemResponse>;
export declare const validateMemoryContentResponse: ValidateFunction<MemoryContentResponse>;
export declare const validateMemoryItemResponse: ValidateFunction<MemoryItemResponse>;
export declare const validateMemoryMapEntryResponse: ValidateFunction<MemoryMapEntryResponse>;
export declare const validateMemoryMapResponse: ValidateFunction<MemoryMapResponse>;
export declare const validateMemoryReferenceRequest: ValidateFunction<MemoryReferenceRequest>;
export declare const validateMemoryReferenceResponse: ValidateFunction<MemoryReferenceResponse>;
export declare const validateMessageContent: ValidateFunction<MessageContent>;
export declare const validateMessageKind: ValidateFunction<MessageKind>;
export declare const validateMessageView: ValidateFunction<MessageView>;
export declare const validateModelDeltaData: ValidateFunction<ModelDeltaData>;
export declare const validateMoveKnowledgeReferenceChange: ValidateFunction<MoveKnowledgeReferenceChange>;
export declare const validateMoveOutcomeChange: ValidateFunction<MoveOutcomeChange>;
export declare const validateMoveRequirementChange: ValidateFunction<MoveRequirementChange>;
export declare const validateMoveSkillReferenceChange: ValidateFunction<MoveSkillReferenceChange>;
export declare const validateNewDefinitionRequest: ValidateFunction<NewDefinitionRequest>;
export declare const validateOccupationReference: ValidateFunction<OccupationReference>;
export declare const validateOccupationReferenceHit: ValidateFunction<OccupationReferenceHit>;
export declare const validatePlacementRequest: ValidateFunction<PlacementRequest>;
export declare const validatePlanResponse: ValidateFunction<PlanResponse>;
export declare const validatePublishedVersion: ValidateFunction<PublishedVersion>;
export declare const validateQuestion: ValidateFunction<Question>;
export declare const validateQuestionExchange: ValidateFunction<QuestionExchange>;
export declare const validateQuestionOption: ValidateFunction<QuestionOption>;
export declare const validateReasoningSummaryDeltaEvent: ValidateFunction<ReasoningSummaryDeltaEvent>;
export declare const validateReferenceCompetencyBlock: ValidateFunction<ReferenceCompetencyBlock>;
export declare const validateReferenceEvidence: ValidateFunction<ReferenceEvidence>;
export declare const validateReferenceIndicator: ValidateFunction<ReferenceIndicator>;
export declare const validateReferenceNamedContent: ValidateFunction<ReferenceNamedContent>;
export declare const validateReferenceRetrievalPolicy: ValidateFunction<ReferenceRetrievalPolicy>;
export declare const validateReferenceSearchRequest: ValidateFunction<ReferenceSearchRequest>;
export declare const validateReferenceSearchResponse: ValidateFunction<ReferenceSearchResponse>;
export declare const validateReferenceTaskDetail: ValidateFunction<ReferenceTaskDetail>;
export declare const validateReferenceTaskName: ValidateFunction<ReferenceTaskName>;
export declare const validateReferenceTaskSummary: ValidateFunction<ReferenceTaskSummary>;
export declare const validateReferenceUnit: ValidateFunction<ReferenceUnit>;
export declare const validateRemoveCitationRequest: ValidateFunction<RemoveCitationRequest>;
export declare const validateRenameWorkspaceRequest: ValidateFunction<RenameWorkspaceRequest>;
export declare const validateRestoreJobDescriptionRequest: ValidateFunction<RestoreJobDescriptionRequest>;
export declare const validateResyncRequiredData: ValidateFunction<ResyncRequiredData>;
export declare const validateResyncRequiredEvent: ValidateFunction<ResyncRequiredEvent>;
export declare const validateSavedQuestion: ValidateFunction<SavedQuestion>;
export declare const validateSkillResponse: ValidateFunction<SkillResponse>;
export declare const validateSourceReferenceRequest: ValidateFunction<SourceReferenceRequest>;
export declare const validateSourceReferenceResponse: ValidateFunction<SourceReferenceResponse>;
export declare const validateSpeaker: ValidateFunction<Speaker>;
export declare const validateStepView: ValidateFunction<StepView>;
export declare const validateSubmitTurnRequest: ValidateFunction<SubmitTurnRequest>;
export declare const validateTaskPlacementRequest: ValidateFunction<TaskPlacementRequest>;
export declare const validateTaskResponse: ValidateFunction<TaskResponse>;
export declare const validateTaskTextResponse: ValidateFunction<TaskTextResponse>;
export declare const validateTextContent: ValidateFunction<TextContent>;
export declare const validateTextDeltaEvent: ValidateFunction<TextDeltaEvent>;
export declare const validateToolCallData: ValidateFunction<ToolCallData>;
export declare const validateToolCallEvent: ValidateFunction<ToolCallEvent>;
export declare const validateToolCallView: ValidateFunction<ToolCallView>;
export declare const validateTranscriptMessage: ValidateFunction<TranscriptMessage>;
export declare const validateTurnEvent: ValidateFunction<TurnEvent>;
export declare const validateTurnStatusEvent: ValidateFunction<TurnStatusEvent>;
export declare const validateTurnView: ValidateFunction<TurnView>;
export declare const validateUnlinkKnowledgeChange: ValidateFunction<UnlinkKnowledgeChange>;
export declare const validateUnlinkSkillChange: ValidateFunction<UnlinkSkillChange>;
export declare const validateUpdateCollaborationRequest: ValidateFunction<UpdateCollaborationRequest>;
export declare const validateUpdateConditionRequest: ValidateFunction<UpdateConditionRequest>;
export declare const validateUpdateDutyRequest: ValidateFunction<UpdateDutyRequest>;
export declare const validateUpdateJobDescriptionRequest: ValidateFunction<UpdateJobDescriptionRequest>;
export declare const validateUpdateKnowledgeRequest: ValidateFunction<UpdateKnowledgeRequest>;
export declare const validateUpdateOutcomeChange: ValidateFunction<UpdateOutcomeChange>;
export declare const validateUpdateRequirementChange: ValidateFunction<UpdateRequirementChange>;
export declare const validateUpdateSkillRequest: ValidateFunction<UpdateSkillRequest>;
export declare const validateUpdateTaskRequest: ValidateFunction<UpdateTaskRequest>;
export declare const validateUsageView: ValidateFunction<UsageView>;
export declare const validateValidationIssue: ValidateFunction<ValidationIssue>;
export declare const validateWorkspaceConflictDetail: ValidateFunction<WorkspaceConflictDetail>;
export declare const validateWorkspaceConflictReason: ValidateFunction<WorkspaceConflictReason>;
export declare const validateWorkspaceConflictResponse: ValidateFunction<WorkspaceConflictResponse>;
export declare const validateWorkspacePageResponse: ValidateFunction<WorkspacePageResponse>;
export declare const validateWorkspaceResponse: ValidateFunction<WorkspaceResponse>;
export declare const validatecaliburn__modules__job_description__presentation__api__schemas__citations__CitationRequests__1: ValidateFunction<caliburn__modules__job_description__presentation__api__schemas__citations__CitationRequests__1>;
export declare const validatecaliburn__modules__job_description__presentation__api__schemas__citations__CitationRequests__2: ValidateFunction<caliburn__modules__job_description__presentation__api__schemas__citations__CitationRequests__2>;
export declare const validateTurnViewArray: ValidateFunction<TurnView[]>;
export declare const validateStepViewArray: ValidateFunction<StepView[]>;
export declare const validateQuestionExchangeArray: ValidateFunction<QuestionExchange[]>;
export declare const validateTranscriptMessageArray: ValidateFunction<
  TranscriptMessage[]
>;
export declare const validateExpectedVersionQuery: ValidateFunction<
  JdDeleteTaskData['query']['expected_version']
>;
