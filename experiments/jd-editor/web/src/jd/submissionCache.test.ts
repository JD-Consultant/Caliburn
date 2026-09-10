import { describe, it, expect } from "vitest";
import { submissionCache, type Submission } from "./submissionCache";
describe("submitted candidate recovery", () => {
  it("retains exact candidate across reopen and confirmed failure until explicit discard", () => {
    const storage = new Map<string, string>();
    const disk = {
      getItem: (k: string) => storage.get(k) ?? null,
      setItem: (k: string, v: string) => {
        storage.set(k, v);
      },
      removeItem: (k: string) => {
        storage.delete(k);
      },
    };
    const payload: Submission = {
      document_id: "A",
      request_key: "same",
      base_revision_ref: "r1",
      value: [{ type: "p", id: "p", children: [{ text: "未保存繁中" }] }],
    };
    submissionCache(disk).write(payload);
    expect(submissionCache(disk).read("A")).toEqual(payload);
    submissionCache(disk).confirm("A", {
      status: "stale_base",
      receipt_durability: "confirmed",
    });
    expect(submissionCache(disk).read("A")).toEqual(payload);
    expect(submissionCache(disk).read("B")).toBeNull();
    submissionCache(disk).confirm("A", {
      status: "committed",
      receipt_durability: "confirmed",
    });
    expect(submissionCache(disk).read("A")).toBeNull();
  });
  it("fails before any network when storage cannot preserve exact payload", () => {
    const disk = {
      getItem: () => null,
      setItem: () => {
        throw Error("quota");
      },
      removeItem: () => {},
    };
    expect(() =>
      submissionCache(disk).write({
        document_id: "A",
        request_key: "x",
        base_revision_ref: "r",
        value: [{ type: "p", id: "p", children: [{ text: "" }] }],
      }),
    ).toThrow("quota");
  });
});
