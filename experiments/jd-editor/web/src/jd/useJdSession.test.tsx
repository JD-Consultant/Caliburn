import { it, expect, vi } from "vitest";
import { JdSession } from "./useJdSession";
import { submissionCache, type Submission } from "./submissionCache";
import { api, ApiError, type JdApi } from "./api";
import type {
  JdReadSuccess,
  JdDocumentValue,
} from "@caliburn/jd-editor-contract";
const value: JdDocumentValue = [
  { type: "p", id: "p", children: [{ text: "工作工作" }] },
];
const head: JdReadSuccess = {
  status: "ok",
  read_kind: "current",
  revision_ref: "r1",
  access: "read_only",
  fragment: value,
  targets: [],
  selection: null,
  source_refs: [],
  change_refs: [],
  continuation_ref: null,
};
function harness() {
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
  const port = {
    ...api,
    document: vi.fn(async (id: string) => ({
      id,
      title: id,
      created_at: "2026-09-10T00:00:00Z",
      archived: false,
      metadata_version: 1,
    })),
    read: vi.fn(async () => structuredClone(head)),
    messages: vi.fn(async () => []),
    runs: vi.fn(async () => []),
    save: vi.fn(),
    submit: vi.fn(),
    lookup: vi.fn(),
  } as JdApi;
  return { disk, port };
}
it("dirty save failure blocks run, retains candidate and original chat", async () => {
  const { disk, port } = harness();
  vi.mocked(port.save).mockRejectedValue(Error("offline"));
  const session = new JdSession("A", port, disk);
  await session.load();
  session.edit([{ ...value[0], children: [{ text: "手改" }] }]);
  session.text = "請改工作";
  expect(await session.send(() => null)).toBe(false);
  expect(port.submit).not.toHaveBeenCalled();
  expect(session.text).toBe("請改工作");
  expect(session.dirty).toBe(true);
  expect([...Object.keys(disk)]).toBeTruthy();
});
it("reopen looks up submitted chat without posting or resuming", async () => {
  const { disk, port } = harness();
  disk.setItem(
    "caliburn:jd-plate-clean-v2:run-submission:A",
    JSON.stringify({
      request_key: "old",
      text: "原句",
      abandon_pending: false,
    }),
  );
  vi.mocked(port.lookup).mockResolvedValue({ found: false });
  const session = new JdSession("A", port, disk);
  await session.load();
  expect(port.lookup).toHaveBeenCalledWith("A", "old");
  expect(port.submit).not.toHaveBeenCalled();
  expect(session.text).toBe("原句");
  expect(session.pendingRun?.request_key).toBe("old");
});
it("late reads never overwrite dirty buffer and document B has no A cache", async () => {
  const { disk, port } = harness();
  const a = new JdSession("A", port, disk);
  await a.load();
  a.edit([{ ...value[0], children: [{ text: "A手稿" }] }]);
  await a.refresh();
  expect(a.value[0].children).toEqual([{ text: "A手稿" }]);
  const b = new JdSession("B", port, disk);
  await b.load();
  expect(b.value).toEqual(value);
  expect(b.pendingRun).toBeNull();
});
it("unknown manual result blocks a new identity until exact reconciliation", async () => {
  const { disk, port } = harness();
  vi.mocked(port.save).mockRejectedValue(Error("lost reply"));
  const session = new JdSession("A", port, disk);
  await session.load();
  session.edit([{ ...value[0], children: [{ text: "候選" }] }]);
  await session.save();
  expect(session.locked).toBe(true);
  expect(await session.save()).toBe(false);
  expect(port.save).toHaveBeenCalledTimes(1);
});
it("explicit selection intent never degrades to plain chat when the range disappears", async () => {
  const { disk, port } = harness();
  const session = new JdSession("A", port, disk);
  await session.load();
  session.setText("原話");
  expect(await session.send(() => null, false, true)).toBe(false);
  expect(port.submit).not.toHaveBeenCalled();
  expect(session.text).toBe("原話");
});
it("explicit plain chat omits a still-selected editor range", async () => {
  const { disk, port } = harness();
  const session = new JdSession("A", port, disk);
  await session.load();
  session.setText("原話");
  vi.mocked(port.submit).mockRejectedValue(Error("lost reply"));
  await session.send(
    () => ({
      anchor: { path: [0, 0], offset: 2 },
      focus: { path: [0, 0], offset: 4 },
    }),
    false,
    false,
  );
  expect(vi.mocked(port.submit).mock.calls[0][1]).not.toHaveProperty(
    "jd_selection",
  );
});
it("cache failure does not send a run and retains the original question", async () => {
  const { disk, port } = harness();
  const session = new JdSession("A", port, disk);
  await session.load();
  session.setText("原話");
  disk.setItem = () => {
    throw Error("quota");
  };
  expect(await session.send(() => null)).toBe(false);
  expect(port.submit).not.toHaveBeenCalled();
  expect(session.text).toBe("原話");
});
it("failed revalidation freezes admission until the head can be checked again", async () => {
  const { disk, port } = harness();
  const session = new JdSession("A", port, disk);
  await session.load();
  vi.mocked(port.read).mockRejectedValue(Error("offline"));
  await session.revalidate();
  expect(session.locked).toBe(true);
});
it("unrelated current save cannot consume a reopened confirmed failure candidate", async () => {
  const { disk, port } = harness();
  const old: Submission = { document_id: "A", request_key: "old-key", base_revision_ref: "old-base",
    value: [{ ...value[0], children: [{ text: "ONLY RECOVERABLE OLD TEXT" }] }] };
  submissionCache(disk).write(old);
  vi.mocked(port.save).mockResolvedValue({ status: "stale_base", receipt_durability: "confirmed" } as never);
  const session = new JdSession("A", port, disk);
  await session.load();
  session.edit([{ ...value[0], children: [{ text: "unrelated current edit" }] }]);
  expect(await session.save()).toBe(false);
  expect(port.save).toHaveBeenCalledTimes(1);
  expect(submissionCache(disk).read("A")).toEqual(old);
  const reopened = new JdSession("A", port, disk);
  await reopened.load();
  expect(reopened.candidate).toEqual(old);
  reopened.discardCandidate();
  expect(submissionCache(disk).read("A")).toBeNull();
  reopened.edit([{ ...value[0], children: [{ text: "explicitly retained current edit" }] }]);
  vi.mocked(port.save).mockResolvedValue({ status: "committed", receipt_durability: "confirmed", result_revision_ref: "r1" } as never);
  expect(await reopened.save()).toBe(true);
  expect(reopened.candidate).toBeNull();
});
it.each([409, 422])("only an identity-matched explicit rejection unlocks candidate handling (%s)", async (status) => {
  const { disk, port } = harness();
  vi.mocked(port.save).mockImplementation(async (_id, body) => {
    throw Object.assign(new ApiError(status, "未送入保存"), {
      manualRejection: { admission: "not_admitted", request_key: body.request_key, message: "未送入保存" },
    });
  });
  const session = new JdSession("A", port, disk);
  await session.load();
  session.edit([{ ...value[0], children: [{ text: "拒絕候選" }] }]);
  session.setText("原問句");
  expect(await session.save()).toBe(false);
  expect(session.manualUnknown).toBe(false);
  expect(session.candidate?.value).toEqual(session.value);
  expect(session.text).toBe("原問句");
  session.discardCandidate();
  expect(submissionCache(disk).read("A")).toBeNull();
});
it.each([409, 422, 503])("an unclassified error remains unknown (%s)", async (status) => {
  const { disk, port } = harness();
  vi.mocked(port.save).mockRejectedValue(new ApiError(status, "unknown"));
  const session = new JdSession("A", port, disk);
  await session.load();
  session.edit([{ ...value[0], children: [{ text: "保留" }] }]);
  await session.save();
  session.discardCandidate();
  expect(session.locked).toBe(true);
  expect(session.candidate).not.toBeNull();
});
it("another request's explicit rejection cannot unlock this candidate", async () => {
  const { disk, port } = harness();
  vi.mocked(port.save).mockRejectedValue(new ApiError(422, "different key", {
    admission: "not_admitted", request_key: "different", message: "different key",
  }));
  const session = new JdSession("A", port, disk);
  await session.load();
  session.edit([{ ...value[0], children: [{ text: "仍未知" }] }]);
  await session.save();
  session.discardCandidate();
  expect(session.locked).toBe(true);
  expect(session.candidate).not.toBeNull();
});
