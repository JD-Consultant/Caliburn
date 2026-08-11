// Public entrypoint for the consultation feature.
// ConsultationPanel/ConsultationWorkspace intentionally live outside this
// feature (app/workspace/[document_id]/_components) because they coordinate
// both task-proposal and OPKS-proposal review in one UI.
export { ProposalCard } from "./ProposalCard";
export { groupProposals, operationForDraft } from "./jobAnalysisProposals";
