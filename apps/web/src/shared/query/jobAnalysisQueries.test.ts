import { describe, expect, it } from "vitest";

import {
  documentListQueryOptions,
  documentQueryOptions,
  consultationQueryOptions,
  consultantDocumentListQueryOptions,
  consultantDocumentQueryOptions,
  consultantInvalidationKeys,
  consultantSnapshotQueryOptions,
  chooseNewestConsultantSnapshot,
  jobAnalysisInvalidationKeys,
  jobAnalysisKeys,
} from "./jobAnalysisQueries";

describe("job-analysis query identity", () => {
  it("keeps the library and each open document in separate keys", () => {
    expect(jobAnalysisKeys.documents).toEqual(["job-analysis", "documents"]);
    expect(jobAnalysisKeys.document("doc-1")).toEqual([
      "job-analysis",
      "documents",
      "doc-1",
    ]);
    expect(documentListQueryOptions().queryKey).toEqual(
      jobAnalysisKeys.documents,
    );
    expect(documentQueryOptions("doc-1").queryKey).toEqual(
      jobAnalysisKeys.document("doc-1"),
    );
    expect(consultationQueryOptions("doc-1").queryKey).toEqual(
      jobAnalysisKeys.consultation("doc-1"),
    );
  });

  it("invalidates both the open document and the library after a write", () => {
    expect(jobAnalysisInvalidationKeys("doc-1")).toEqual([
      jobAnalysisKeys.document("doc-1"),
      jobAnalysisKeys.documents,
      jobAnalysisKeys.consultation("doc-1"),
    ]);
  });

  it("does not opt the mutable document state into persisted cache", () => {
    expect(documentListQueryOptions().meta?.persist).not.toBe(true);
    expect(documentQueryOptions("doc-1").meta?.persist).not.toBe(true);
    expect(consultationQueryOptions("doc-1").meta?.persist).not.toBe(true);
  });

  it("keeps the durable consultant catalog and snapshot in purpose-first keys", () => {
    expect(jobAnalysisKeys.consultantDocuments).toEqual([
      "job-analysis",
      "consultant-documents",
    ]);
    expect(consultantDocumentListQueryOptions().queryKey).toEqual(
      jobAnalysisKeys.consultantDocuments,
    );
    expect(consultantDocumentQueryOptions("doc-1").queryKey).toEqual(
      jobAnalysisKeys.consultantDocument("doc-1"),
    );
    expect(consultantSnapshotQueryOptions("doc-1").queryKey).toEqual(
      jobAnalysisKeys.consultantSnapshot("doc-1"),
    );
    expect(consultantInvalidationKeys("doc-1")).toEqual([
      jobAnalysisKeys.consultantSnapshot("doc-1"),
      jobAnalysisKeys.consultantDocument("doc-1"),
      jobAnalysisKeys.consultantDocuments,
    ]);
  });

  it("never lets an out-of-order mutation response replace a newer snapshot", () => {
    const current = { revision: 8, marker: "newer SSE refetch" };
    const delayedMutation = { revision: 7, marker: "older mutation response" };

    expect(chooseNewestConsultantSnapshot(current, delayedMutation)).toBe(current);
    expect(
      chooseNewestConsultantSnapshot(current, {
        revision: 9,
        marker: "newest authority response",
      }),
    ).toEqual({ revision: 9, marker: "newest authority response" });
  });
});
