import { describe, expect, it } from "vitest";

import {
  consultantDocumentListQueryOptions,
  consultantDocumentQueryOptions,
  consultantInvalidationKeys,
  consultantSnapshotQueryOptions,
  chooseNewestConsultantSnapshot,
  jobAnalysisKeys,
} from "./jobAnalysisQueries";

describe("durable consultant query identity", () => {
  it("keeps the catalog, document metadata and snapshot in separate keys", () => {
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
