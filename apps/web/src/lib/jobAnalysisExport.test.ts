import { describe, expect, it } from "vitest";

import { canExport, exportFilename } from "./jobAnalysisExport";

describe("job-analysis export", () => {
  it("disables export while any editor is dirty", () => {
    expect(
      canExport({ header: true, duty: false, task: false, opks: false }),
    ).toBe(false);
  });

  it("allows export when every editor is clean", () => {
    expect(
      canExport({ header: false, duty: false, task: false, opks: false }),
    ).toBe(true);
  });

  it("creates a safe xlsx filename from the document title", () => {
    expect(exportFilename("門市/營運專員 ")).toBe("門市_營運專員.xlsx");
    expect(exportFilename("   ")).toBe("職務說明書.xlsx");
  });
});
