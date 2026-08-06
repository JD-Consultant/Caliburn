import { describe, expect, it } from "vitest";

import { exportFilename } from "./jobAnalysisExport";

describe("exportFilename", () => {
  it("keeps a normal title and adds the extension", () => {
    expect(exportFilename("門市營運專員")).toBe("門市營運專員.xlsx");
  });

  it("strips characters the file system would reject", () => {
    expect(exportFilename('營運/週報:草稿?')).toBe("營運週報草稿.xlsx");
  });

  it("falls back rather than producing a nameless file", () => {
    expect(exportFilename("   ")).toBe("職務說明書.xlsx");
    expect(exportFilename("///")).toBe("職務說明書.xlsx");
  });
});
