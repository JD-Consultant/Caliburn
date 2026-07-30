import { queryOptions } from "@tanstack/react-query";

import { getDocument, listDocuments } from "./jobAnalysisApi";

export const jobAnalysisKeys = {
  documents: ["job-analysis", "documents"] as const,
  document: (documentId: string) =>
    ["job-analysis", "documents", documentId] as const,
};

export function documentListQueryOptions() {
  return queryOptions({
    queryKey: jobAnalysisKeys.documents,
    queryFn: listDocuments,
  });
}

export function documentQueryOptions(documentId: string) {
  return queryOptions({
    queryKey: jobAnalysisKeys.document(documentId),
    queryFn: () => getDocument(documentId),
  });
}
