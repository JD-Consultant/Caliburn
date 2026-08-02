import { queryOptions } from "@tanstack/react-query";

import { getConsultation, getDocument, listDocuments } from "./jobAnalysisApi";

export const jobAnalysisKeys = {
  documents: ["job-analysis", "documents"] as const,
  document: (documentId: string) =>
    ["job-analysis", "documents", documentId] as const,
  consultation: (documentId: string) =>
    ["job-analysis", "documents", documentId, "consultation"] as const,
};

export function documentListQueryOptions() {
  return queryOptions({
    queryKey: jobAnalysisKeys.documents,
    queryFn: listDocuments,
  });
}

export function consultationQueryOptions(documentId: string) {
  return queryOptions({
    queryKey: jobAnalysisKeys.consultation(documentId),
    queryFn: () => getConsultation(documentId),
  });
}

export function documentQueryOptions(documentId: string) {
  return queryOptions({
    queryKey: jobAnalysisKeys.document(documentId),
    queryFn: () => getDocument(documentId),
  });
}

export function jobAnalysisInvalidationKeys(documentId: string) {
  return [
    jobAnalysisKeys.document(documentId),
    jobAnalysisKeys.documents,
    jobAnalysisKeys.consultation(documentId),
  ] as const;
}
