import React, { useEffect, useState } from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { JdDocumentValue, JdReadSuccess } from '@caliburn/jd-editor-contract';
import { api, type JdApi } from './api';
import { JdSession } from './useJdSession';
const selected = vi.hoisted(() => ({ session: null as unknown }));
vi.mock('./useJdSession', async original => ({
  ...await original<typeof import('./useJdSession')>(),
  useJdSession: () => {
    const session = selected.session as JdSession;
    const [, render] = useState(0);
    useEffect(() => { session.onChange = () => render(n => n + 1); }, [session]);
    return session;
  },
}));
import { JdWorkspace } from './JdWorkspace';
const value = (text: string): JdDocumentValue => [{ type: 'p', id: 'work', children: [{ text }] }];
const head = (revision: string): JdReadSuccess => ({
  status: 'ok', read_kind: 'current', revision_ref: revision, access: 'read_only', fragment: value('已保存內容'),
  targets: [], selection: null, source_refs: [], change_refs: [], continuation_ref: null,
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
it.each(['r1', 'r2'])('explicit reload at %s updates the actual sole editor and preserves the unsent chat', async revision => {
  const port = { ...api, read: vi.fn(async () => head(revision)) } as JdApi;
  const session = new JdSession('A', port, { getItem: () => null, setItem: () => {}, removeItem: () => {} });
  session.head = head('r1'); session.value = value('未保存修改'); session.dirty = true;
  session.loading = false; session.serverWriteBlocked = false; session.text = '未送出的補充';
  selected.session = session;
  const { container } = render(<JdWorkspace document="A" />);
  expect(screen.getByRole('textbox', { name: '職務說明書正文' }).textContent).toBe('未保存修改');
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
  fireEvent.click(screen.getByRole('button', { name: '捨棄畫面修改並載入最新稿' }));
  expect(port.read).not.toHaveBeenCalled();
  confirm.mockReturnValue(true);
  fireEvent.click(screen.getByRole('button', { name: '捨棄畫面修改並載入最新稿' }));
  await waitFor(() => expect(session.busy).toBe(false));
  expect(screen.getByRole('textbox', { name: '職務說明書正文' }).textContent).toBe('已保存內容');
  expect(container.querySelectorAll('[contenteditable=true]')).toHaveLength(1);
  expect(session.dirty).toBe(false);
  expect(session.text).toBe('未送出的補充');
  expect(port.read).toHaveBeenCalledOnce();
});
