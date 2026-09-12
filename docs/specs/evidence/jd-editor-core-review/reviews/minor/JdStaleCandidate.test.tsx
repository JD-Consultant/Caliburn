import { expect, it, vi } from 'vitest';
import type { JdDocumentValue, JdManualSaveResult, JdReadSuccess } from '@caliburn/jd-editor-contract';
import { api, ApiError, type JdApi } from './api';
import { JdSession } from './useJdSession';
import { submissionCache } from './submissionCache';

const value = (text: string): JdDocumentValue => [{ type: 'p', id: 'work', children: [{ text }] }];
const head = (revision: string, text: string): JdReadSuccess => ({
  status: 'ok', read_kind: 'current', revision_ref: revision, access: 'read_only',
  fragment: value(text), targets: [], selection: null, source_refs: [], change_refs: [], continuation_ref: null,
});
const failure: JdManualSaveResult = {
  status: 'stale_base', operation_ref: 'operation', base_revision_ref: 'r1', result_revision_ref: 'r2',
  change_ref: null, document_effect: 'unchanged', receipt_durability: 'confirmed', actual_changes: null,
  error: null, next_action: 'reread_current',
};
function harness() {
  const storage = new Map<string, string>();
  const disk = { getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, raw: string) => { storage.set(key, raw); }, removeItem: (key: string) => { storage.delete(key); } };
  const port = { ...api,
    document: vi.fn(async () => ({ id: 'A', title: '我的工作', created_at: '', archived: false, metadata_version: 1 })),
    messages: vi.fn(async () => []), runs: vi.fn(async () => []), read: vi.fn(async () => head('r1', '原稿')),
    save: vi.fn(), readRecovery: vi.fn(async (_id: string, key?: string) => ({ status: 'no_pending', request_key: key ?? null, write_blocked: false, can_recover: false })),
  } as JdApi;
  return { disk, port, session: new JdSession('A', port, disk) };
}

it('a confirmed stale submission can reach the current editable draft without losing its saved candidate or chat', async () => {
  const { disk, port, session } = harness();
  await session.load();
  session.edit(value('尚未保存的員工更正'));
  session.setText('這段補充仍未送出');
  vi.mocked(port.read).mockResolvedValue(head('r2', '已保存的新責任'));
  vi.mocked(port.save).mockImplementation(async (_id, body) => {
    vi.mocked(port.readRecovery).mockImplementation(async (_doc, key) => ({
      status: 'available', request_key: key ?? body.request_key, write_blocked: false, can_recover: false, result: failure,
    }));
    return failure;
  });
  expect(await session.save()).toBe(false);
  const candidate = submissionCache(disk).read('A');
  expect(candidate?.value).toEqual(value('尚未保存的員工更正'));
  expect(session.canRetryCandidate).toBe(false);
  expect(await session.save(true)).toBe(false);
  expect(port.save).toHaveBeenCalledOnce();
  await session.revalidate();
  expect(session.head?.revision_ref).toBe('r1');
  expect(await session.loadSavedHead()).toBe(true);
  expect(session.head?.revision_ref).toBe('r2');
  expect(session.value).toEqual(value('已保存的新責任'));
  expect(session.dirty).toBe(false);
  expect(session.candidate).toEqual(candidate);
  expect(submissionCache(disk).read('A')).toEqual(candidate);
  expect(session.text).toBe('這段補充仍未送出');
  expect(port.save).toHaveBeenCalledOnce();
  // The employee copies the required part, explicitly discards the old sent
  // candidate, then saves a new intent against the actual current revision.
  session.edit(value('已保存的新責任；員工更正'));
  session.discardCandidate();
  vi.mocked(port.save).mockResolvedValue({ ...failure, status: 'committed', document_effect: 'committed', result_revision_ref: 'r3' });
  vi.mocked(port.read).mockResolvedValue(head('r3', '已保存的新責任；員工更正'));
  expect(await session.save()).toBe(true);
  expect(vi.mocked(port.save).mock.calls[1][1].base_revision_ref).toBe('r2');
  expect(vi.mocked(port.save).mock.calls[1][1].request_key).not.toBe(candidate?.request_key);
  expect(session.text).toBe('這段補充仍未送出');
});

it('an unknown outcome never substitutes the current head for the unsaved buffer', async () => {
  const { disk, port, session } = harness();
  await session.load();
  session.edit(value('原候選'));
  vi.mocked(port.save).mockRejectedValue(Error('lost reply'));
  await session.save();
  vi.mocked(port.read).mockResolvedValue(head('r2', '其他新版'));
  await session.revalidate();
  expect(session.head?.revision_ref).toBe('r1');
  expect(session.value).toEqual(value('原候選'));
  expect(session.dirty).toBe(true);
  expect(submissionCache(disk).read('A')?.value).toEqual(value('原候選'));
  expect(port.save).toHaveBeenCalledOnce();
  expect(await session.loadSavedHead()).toBe(false);
});

it('failed explicit reload preserves the buffer, base and unsent chat', async () => {
  const { port, session } = harness();
  await session.load();
  session.edit(value('尚未送出的手改'));
  session.setText('原問句');
  vi.mocked(port.read).mockRejectedValue(Error('offline'));
  expect(await session.loadSavedHead()).toBe(false);
  expect(session.value).toEqual(value('尚未送出的手改'));
  expect(session.head?.revision_ref).toBe('r1');
  expect(session.text).toBe('原問句');
  expect(session.dirty).toBe(true);
  expect(port.save).not.toHaveBeenCalled();
});

it('saving an older candidate keeps newer typing visibly unsaved until an explicit reload', async () => {
  const { port, session } = harness();
  await session.load();
  session.edit(value('先前候選'));
  vi.mocked(port.save).mockImplementationOnce(async (_id, body) => {
    throw new ApiError(409, 'not admitted', { admission: 'not_admitted', request_key: body.request_key, message: 'not admitted' });
  });
  await session.save();
  expect(session.locked).toBe(false);
  session.edit(value('之後手改'));
  session.setText('保留聊天');
  vi.mocked(port.save).mockResolvedValue({ ...failure, status: 'committed', document_effect: 'committed' });
  vi.mocked(port.read).mockResolvedValue(head('r2', '先前候選'));
  expect(await session.save(true)).toBe(true);
  expect(session.value).toEqual(value('之後手改'));
  expect(session.dirty).toBe(true);
  expect(session.notice).toContain('畫面上的修改尚未保存');
  expect(await session.loadSavedHead()).toBe(true);
  expect(session.value).toEqual(value('先前候選'));
  expect(session.text).toBe('保留聊天');
});
