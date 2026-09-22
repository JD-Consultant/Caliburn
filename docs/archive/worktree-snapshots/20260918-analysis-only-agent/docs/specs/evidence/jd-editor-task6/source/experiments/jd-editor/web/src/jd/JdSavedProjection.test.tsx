import React from 'react';
import { act, render } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import type { JdChangeReadSuccess, JdDocumentValue, JdReadSuccess } from '@caliburn/jd-editor-contract';
import { JdEditor, applySavedHead, type LiveEditor } from './JdEditor';
import { JdSession } from './useJdSession';
import { api, type JdApi } from './api';

const initial: JdDocumentValue = [{ type: 'p', id: 'empty', children: [{ text: '' }] }];
const head = (revision: string, fragment: JdDocumentValue): JdReadSuccess => ({
  status: 'ok', read_kind: 'current', revision_ref: revision, access: 'read_only', fragment,
  targets: [], selection: null, source_refs: [], change_refs: revision === 'r0' ? [] : [revision], continuation_ref: null,
});
const change = (before: JdReadSuccess, after: JdReadSuccess, operations: JdChangeReadSuccess['native_operations']): JdChangeReadSuccess => ({
  status: 'ok', mode: 'change', change_ref: after.change_refs[0] ?? null, origin: 'ai',
  before_revision_ref: before.revision_ref, after_revision_ref: after.revision_ref,
  before_fragment: before.fragment, after_fragment: after.fragment, native_operations: operations,
  source_refs: [], presentation_limitations: [], continuation_ref: null,
});
function harness() {
  const port = { ...api, document: vi.fn(async () => ({ id: 'A', title: 'A', created_at: '', archived: false, metadata_version: 1 })),
    messages: vi.fn(async () => []), runs: vi.fn(async () => []), read: vi.fn(async () => head('r0', initial)),
    changes: vi.fn(), readRecovery: vi.fn(async () => ({ status: 'no_pending', request_key: null, write_blocked: false, can_recover: false })),
    save: vi.fn(), submit: vi.fn(async () => ({ id: 'run', status: 'running' })),
    lookup: vi.fn(async () => ({ found: true, input_received: true, run: { id: 'run', status: 'completed' } })),
  } as unknown as JdApi;
  const storage = new Map<string, string>();
  const session = new JdSession('A', port, { getItem: key => storage.get(key) ?? null, setItem: (key, value) => { storage.set(key, value); }, removeItem: key => { storage.delete(key); } });
  return { session, port };
}
it('serialization key order alone does not become a manual save before the next interview', async () => {
  const { session, port } = harness();
  await session.load();
  session.edit([{ id: 'empty', children: [{ text: '' }], type: 'p' }]);
  expect(session.dirty).toBe(false);
  session.setText('繼續訪談');
  expect(await session.send(() => null)).toBe(true);
  expect(port.save).not.toHaveBeenCalled();
  expect(port.submit).toHaveBeenCalledOnce();
});
it('two saved native batches stay clean across actual Plate callbacks while manual edits remain dirty', async () => {
  const { session, port } = harness();
  await session.load();
  let editor!: LiveEditor;
  render(<JdEditor value={session.value} locked={false} onReady={value => { editor = value; }} onEdit={value => session.edit(value)} />);
  const applied: boolean[] = [];
  session.bindHead((next, change) => applied.push(applySavedHead(editor, session.head!, next, change)));
  const first = head('r1', [{ type: 'p', id: 'work', children: [{ text: '工作' }] }]);
  vi.mocked(port.read).mockResolvedValue(first);
  vi.mocked(port.changes).mockResolvedValue(change(session.head!, first, [
    { type: 'insert_node', path: [0], node: { id: 'work', children: [{ text: '工作' }], type: 'p' } },
    { type: 'remove_node', path: [1], node: { type: 'p', id: 'empty', children: [{ text: '' }] } },
  ]));
  await act(async () => { await session.refresh(); });
  expect(applied).toEqual([true]);
  expect(session.dirty).toBe(false);
  const second = head('r2', [{ type: 'p', id: 'work', children: [{ text: '工作條件' }] }]);
  vi.mocked(port.read).mockResolvedValue(second);
  vi.mocked(port.changes).mockResolvedValue(change(first, second, [
    { type: 'insert_text', path: [0, 0], offset: 2, text: '條件' },
  ]));
  await act(async () => { await session.refresh(); });
  expect(applied).toEqual([true, true]);
  expect(editor.children).toEqual(second.fragment);
  expect(session.dirty).toBe(false);
  await act(async () => { editor.tf.select({ path: [0, 0], offset: 4 }); editor.tf.insertText('・手改'); });
  expect(session.dirty).toBe(true);
  const candidate = structuredClone(editor.children);
  await act(async () => { await session.refresh(); });
  expect(session.value).toEqual(candidate);
  expect(editor.children).toEqual(candidate);
});
it('a completed run cannot freeze a document and conversation snapshot read before its final write', async () => {
  const { session, port } = harness();
  await session.load();
  let current = head('r0', initial);
  let messages: Awaited<ReturnType<JdApi['messages']>> = [];
  let completed!: (runs: Awaited<ReturnType<JdApi['runs']>>) => void;
  const completion = new Promise<Awaited<ReturnType<JdApi['runs']>>>(resolve => { completed = resolve; });
  vi.mocked(port.runs).mockReturnValue(completion);
  vi.mocked(port.read).mockImplementation(async () => structuredClone(current));
  vi.mocked(port.messages).mockImplementation(async () => structuredClone(messages));
  vi.mocked(port.changes).mockImplementation(async () => change(head('r0', initial), current, []));
  const refreshing = session.refresh();
  // The saved read starts before the run response in the old parallel fetch.
  await Promise.resolve();
  current = head('r1', [{ type: 'p', id: 'work', children: [{ text: '最後保存內容' }] }]);
  messages = [{ id: 'answer', role: 'assistant', text: '已保存' }];
  completed([{ id: 'run', status: 'completed' } as Awaited<ReturnType<JdApi['runs']>>[number]]);
  await refreshing;
  expect(session.run?.status).toBe('completed');
  expect(session.head).toEqual(current);
  expect(session.messages).toEqual(messages);
});
it('typing while a changed-head diff is loading preserves the manual value and its saved baseline', async () => {
  const { session, port } = harness();
  await session.load();
  const baseline = session.head;
  const applied = vi.fn();
  session.bindHead(applied);
  vi.mocked(port.read).mockResolvedValue(head('r1', [{ type: 'p', id: 'empty', children: [{ text: 'AI 新稿' }] }]));
  let release!: (change: JdChangeReadSuccess) => void;
  const diff = new Promise<JdChangeReadSuccess>(resolve => { release = resolve; });
  vi.mocked(port.changes).mockReturnValue(diff);
  const refreshing = session.refresh();
  await vi.waitFor(() => expect(port.changes).toHaveBeenCalledOnce());
  expect(session.locked).toBe(false);
  const manual: JdDocumentValue = [{ type: 'p', id: 'empty', children: [{ text: '員工尚未保存的更正' }] }];
  session.edit(manual);
  release(change(baseline!, await port.read('A'), []));
  await refreshing;
  expect(session.value).toEqual(manual);
  expect(session.head).toEqual(baseline);
  expect(session.dirty).toBe(true);
  expect(applied).not.toHaveBeenCalled();
  expect(session.notice).toContain('未保存修改仍留在畫面');
});
