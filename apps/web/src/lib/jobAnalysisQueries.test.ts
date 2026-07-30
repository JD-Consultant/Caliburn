import { describe, expect, it } from "vitest";

import {
  documentListQueryOptions,
  documentQueryOptions,
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
  });

  it("does not opt the mutable document state into persisted cache", () => {
    expect(documentListQueryOptions().meta?.persist).not.toBe(true);
    expect(documentQueryOptions("doc-1").meta?.persist).not.toBe(true);
  });
});
