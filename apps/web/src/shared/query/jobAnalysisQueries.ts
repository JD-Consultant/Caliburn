import type { ConsultantSnapshotView } from "@caliburn/job-analysis-contract";
import { queryOptions, type QueryClient } from "@tanstack/react-query";

import {
  getConsultantDocument,
  getConsultantSnapshot,
  getConsultation,
  getDocument,
  listConsultantDocuments,
  listDocuments,
} from "../api/jobAnalysisApi";

export const jobAnalysisKeys = {
  consultantDocuments: ["job-analysis", "consultant-documents"] as const,
  consultantDocument: (documentId: string) =>
    ["job-analysis", "consultant-documents", documentId] as const,
  consultantSnapshot: (documentId: string) =>
    ["job-analysis", "consultant-documents", documentId, "snapshot"] as const,
  documents: ["job-analysis", "documents"] as const,
  document: (documentId: string) =>
    ["job-analysis", "documents", documentId] as const,
  consultation: (documentId: string) =>
    ["job-analysis", "documents", documentId, "consultation"] as const,
};

export function consultantDocumentListQueryOptions() {
  return queryOptions({
    queryKey: jobAnalysisKeys.consultantDocuments,
    queryFn: listConsultantDocuments,
  });
}

export function consultantDocumentQueryOptions(documentId: string) {
  return queryOptions({
    queryKey: jobAnalysisKeys.consultantDocument(documentId),
    queryFn: () => getConsultantDocument(documentId),
  });
}

export function consultantSnapshotQueryOptions(documentId: string) {
  return queryOptions({
    queryKey: jobAnalysisKeys.consultantSnapshot(documentId),
    queryFn: () => getConsultantSnapshot(documentId),
  });
}

export function consultantInvalidationKeys(documentId: string) {
  return [
    jobAnalysisKeys.consultantSnapshot(documentId),
    jobAnalysisKeys.consultantDocument(documentId),
    jobAnalysisKeys.consultantDocuments,
  ] as const;
}

export function chooseNewestConsultantSnapshot<T extends { revision: number }>(
  current: T | undefined,
  incoming: T,
): T {
  return current && current.revision > incoming.revision ? current : incoming;
}

export function cacheConsultantSnapshot(
  queryClient: QueryClient,
  documentId: string,
  incoming: ConsultantSnapshotView,
): void {
  queryClient.setQueryData<ConsultantSnapshotView>(
    jobAnalysisKeys.consultantSnapshot(documentId),
    (current) => chooseNewestConsultantSnapshot(current, incoming),
  );
}

export async function refreshConsultantQueries(
  queryClient: QueryClient,
  documentId: string,
): Promise<void> {
  await Promise.all(
    consultantInvalidationKeys(documentId).map((queryKey) =>
      queryClient.invalidateQueries({ queryKey }),
    ),
  );
}

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
