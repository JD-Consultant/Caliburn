import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import type { Mock } from 'vitest';
import type { JdProfileView } from '../../shared/api/generated/jd-profile-view';
import { isReviseJdProfileRequest } from '../../shared/api/validation';
import { JdProfileEditor } from './JdProfileEditor';
import { jdProfileQuery } from './jd-profile-api';

const fileId = '10000000-0000-4000-8000-000000000001';
const original: JdProfileView = {
  revision_id: '20000000-0000-4000-8000-000000000002',
  profile: {
    job_title: '前端工程師',
    organization_unit: '產品團隊',
    reports_to: null,
    purpose: '原目的',
  },
};
const updated: JdProfileView = {
  revision_id: '30000000-0000-4000-8000-000000000003',
  profile: { ...original.profile, job_title: '維護工程師', purpose: null },
};
const clients: QueryClient[] = [];

function renderEditor(readOnly = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <JdProfileEditor key={fileId} jobFileId={fileId} readOnly={readOnly} />
      </QueryClientProvider>,
    ),
  };
}

type Fetch = Mock<(path: string, options?: RequestInit) => Promise<Response>>;

function writes(fetch: Fetch): unknown[] {
  return fetch.mock.calls
    .filter(([, options]) => options?.method === 'POST')
    .map(([, options]) => {
      if (typeof options?.body !== 'string') throw new Error('Missing command body');
      const body: unknown = JSON.parse(options.body);
      return body;
    });
}

/** Opens a field by clicking its text, types the new text and presses Enter. */
async function edit(oldText: string, label: string, text: string): Promise<HTMLElement> {
  await userEvent.click(await screen.findByText(oldText));
  const field = await screen.findByRole('textbox', { name: label });
  await userEvent.clear(field);
  await userEvent.type(field, `${text}{Enter}`);
  return field;
}

beforeEach(() => sessionStorage.clear());
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test('click a field’s text to edit it in place: Enter sends one change for that field at the opening revision, no dialog', async () => {
  let current = original;
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((_path, options) => {
    if (options?.method === 'POST') {
      current = updated;
      return Promise.resolve(Response.json(original));
    }
    return Promise.resolve(Response.json(current));
  });
  vi.stubGlobal('fetch', fetch);
  renderEditor();
  await userEvent.click(await screen.findByText('前端工程師'));
  expect(await screen.findByRole('textbox', { name: '職務名稱' })).toHaveFocus();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '編輯基本資料' })).not.toBeInTheDocument();

  await userEvent.clear(screen.getByRole('textbox', { name: '職務名稱' }));
  await userEvent.type(screen.getByRole('textbox', { name: '職務名稱' }), '維護工程師{Enter}');

  // The write is answered with the old view; the screen follows the latest GET, never that answer.
  expect(await screen.findByText('維護工程師')).toBeVisible();
  const [command] = writes(fetch);
  if (!isReviseJdProfileRequest(command)) throw new Error('Invalid command');
  expect(command.expected_revision_id).toBe(original.revision_id);
  expect(command.changes).toEqual([
    { action: 'set_field', field: 'job_title', value: '維護工程師' },
  ]);
  expect(writes(fetch)).toHaveLength(1);
  expect(screen.getByText('產品團隊')).toBeVisible();
});

test('emptying an optional field clears it, and a field without a value can be filled in place', async () => {
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation(() => Promise.resolve(Response.json(original)));
  vi.stubGlobal('fetch', fetch);
  renderEditor();

  await userEvent.click(await screen.findByText('原目的'));
  await userEvent.clear(await screen.findByRole('textbox', { name: '職務目的' }));
  await userEvent.click(screen.getByRole('button', { name: '儲存' }));
  await waitFor(() => expect(writes(fetch)).toHaveLength(1));
  expect(writes(fetch)[0]).toMatchObject({
    changes: [{ action: 'clear_field', field: 'purpose' }],
  });

  // The unknown reporting line shows its placeholder, and that placeholder is the way in.
  await waitFor(() => expect(screen.queryByRole('textbox')).not.toBeInTheDocument());
  await userEvent.click(await screen.findByText('尚未提供'));
  await userEvent.type(await screen.findByRole('textbox', { name: '匯報關係' }), '產品總監{Enter}');
  await waitFor(() => expect(writes(fetch)).toHaveLength(2));
  expect(writes(fetch)[1]).toMatchObject({
    changes: [{ action: 'set_field', field: 'reports_to', value: '產品總監' }],
  });
});

test('whitespace only is refused with a reason; the draft stays and nothing is sent', async () => {
  const fetch = vi.fn().mockImplementation(() => Promise.resolve(Response.json(original)));
  vi.stubGlobal('fetch', fetch);
  renderEditor();
  await userEvent.click(await screen.findByText('前端工程師'));
  const field = await screen.findByRole('textbox', { name: '職務名稱' });
  await userEvent.clear(field);
  await userEvent.type(field, '   ');
  await userEvent.click(screen.getByRole('button', { name: '儲存' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('不能是空白');
  expect(field).toHaveValue('   ');
  expect(fetch).toHaveBeenCalledTimes(1);
});

test('saving without a change closes the editor and sends nothing; an unsaved identity is never sent', async () => {
  const fetch = vi.fn().mockImplementation(() => Promise.resolve(Response.json(original)));
  vi.stubGlobal('fetch', fetch);
  renderEditor();
  await userEvent.click(await screen.findByText('前端工程師'));
  await userEvent.click(await screen.findByRole('button', { name: '儲存' }));
  expect(screen.queryByRole('textbox', { name: '職務名稱' })).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(1);

  await userEvent.click(await screen.findByText('前端工程師'));
  const field = await screen.findByRole('textbox', { name: '職務名稱' });
  await userEvent.clear(field);
  await userEvent.type(field, '新內容');
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('storage unavailable');
  });
  await userEvent.click(screen.getByRole('button', { name: '儲存' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('尚未送出');
  expect(fetch).toHaveBeenCalledTimes(1);
});

test('a lost response keeps the draft in the editor, which re-confirms the same command from there', async () => {
  let current = original;
  let attempt = 0;
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((_path, options) => {
    if (options?.method === 'POST') {
      attempt += 1;
      current = updated;
      return attempt === 1
        ? Promise.reject(new TypeError('lost response'))
        : Promise.resolve(Response.json(updated));
    }
    return Promise.resolve(Response.json(current));
  });
  vi.stubGlobal('fetch', fetch);
  renderEditor();
  const field = await edit('前端工程師', '職務名稱', '維護工程師');

  expect(await screen.findByRole('alert')).toHaveTextContent('JD 修改結果尚未確認');
  expect(field).toHaveValue('維護工程師');
  expect(field).toBeDisabled();
  await userEvent.click(screen.getByRole('button', { name: '重新確認修改結果' }));
  await waitFor(() =>
    expect(screen.queryByRole('textbox', { name: '職務名稱' })).not.toBeInTheDocument(),
  );
  expect(writes(fetch)).toHaveLength(2);
  expect(writes(fetch)[1]).toEqual(writes(fetch)[0]);
  expect(sessionStorage.length).toBe(0);
});

test('after a reload the unconfirmed command is found again and re-confirmed unchanged, never over a later draft', async () => {
  let current = original;
  let attempt = 0;
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((_path, options) => {
    if (options?.method === 'POST') {
      attempt += 1;
      current = { ...updated, profile: { ...updated.profile, job_title: '後來的職務名稱' } };
      return attempt === 1
        ? Promise.reject(new TypeError('lost response'))
        : Promise.resolve(Response.json(updated));
    }
    return Promise.resolve(Response.json(current));
  });
  vi.stubGlobal('fetch', fetch);
  const first = renderEditor();
  await edit('前端工程師', '職務名稱', '維護工程師');
  await screen.findByRole('alert');
  first.unmount();

  renderEditor();
  expect(await screen.findByText(/有尚未確認的 JD 修改/)).toBeVisible();
  // Nothing new can be started while the old command waits.
  await userEvent.click(await screen.findByText('產品團隊'));
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: '重新確認修改結果' }));
  expect(await screen.findByText('後來的職務名稱')).toBeVisible();
  expect(writes(fetch)).toHaveLength(2);
  expect(writes(fetch)[1]).toEqual(writes(fetch)[0]);
  expect(sessionStorage.length).toBe(0);
});

test('an explicit rejection is not retried and keeps the draft; the person reads the current JD first', async () => {
  let current = original;
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((_path, options) => {
    if (options?.method === 'POST') {
      current = updated;
      return Promise.resolve(
        Response.json({ detail: { code: 'jd_revision_stale' } }, { status: 409 }),
      );
    }
    return Promise.resolve(Response.json(current));
  });
  vi.stubGlobal('fetch', fetch);
  renderEditor();
  const field = await edit('前端工程師', '職務名稱', '不能覆蓋');

  expect(await screen.findByRole('alert')).toHaveTextContent('修改未被接受');
  expect(field).toHaveValue('不能覆蓋');
  expect(field).toBeDisabled();
  expect(writes(fetch)).toHaveLength(1);
  await userEvent.click(screen.getByRole('button', { name: '讀取目前 JD' }));
  expect(await screen.findByText('維護工程師')).toBeVisible();
});

test('a background refresh does not replace the open editor’s draft or its revision', async () => {
  let current = original;
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((_path, options) =>
    Promise.resolve(
      options?.method === 'POST' ? Response.json({}, { status: 409 }) : Response.json(current),
    ),
  );
  vi.stubGlobal('fetch', fetch);
  const view = renderEditor();
  await userEvent.click(await screen.findByText('前端工程師'));
  const field = await screen.findByRole('textbox', { name: '職務名稱' });
  await userEvent.clear(field);
  await userEvent.type(field, '本次草稿');
  current = updated;
  await act(async () => {
    await view.client.invalidateQueries({ queryKey: jdProfileQuery(fileId).queryKey });
  });
  expect(screen.getByRole('textbox', { name: '職務名稱' })).toHaveValue('本次草稿');
  await userEvent.click(screen.getByRole('button', { name: '儲存' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('修改未被接受');
  expect(writes(fetch)[0]).toMatchObject({ expected_revision_id: original.revision_id });
});

test('a failed background refresh keeps the profile draft, shows the error and blocks new writes until recovery', async () => {
  let current = original;
  let readFails = false;
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((_path, options) => {
    if (options?.method === 'POST') return Promise.resolve(Response.json({}, { status: 409 }));
    return Promise.resolve(readFails ? Response.json({}, { status: 503 }) : Response.json(current));
  });
  vi.stubGlobal('fetch', fetch);
  const { client } = renderEditor();
  await userEvent.click(await screen.findByText('前端工程師'));
  const field = await screen.findByRole('textbox', { name: '職務名稱' });
  await userEvent.clear(field);
  await userEvent.type(field, '未提交草稿');

  readFails = true;
  await act(async () => {
    await client.invalidateQueries({ queryKey: jdProfileQuery(fileId).queryKey });
  });

  expect(await screen.findByRole('alert')).toBeVisible();
  expect(field).toBeVisible();
  expect(screen.getByRole('textbox', { name: '職務名稱' })).toHaveValue('未提交草稿');
  expect(field).toBeDisabled();
  expect(screen.getByRole('button', { name: '儲存' })).toBeDisabled();
  expect(screen.getByRole('button', { name: '修改所屬單位／工作範圍' })).toHaveAttribute(
    'aria-disabled',
    'true',
  );
  const form = field.closest('form');
  if (!form) throw new Error('Missing inline edit form');
  fireEvent.submit(form);
  expect(writes(fetch)).toHaveLength(0);

  current = updated;
  readFails = false;
  await userEvent.click(screen.getByRole('button', { name: '重新讀取 JD' }));
  await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  expect(screen.getByRole('textbox', { name: '職務名稱' })).toHaveValue('未提交草稿');
  expect(field).toBeEnabled();
  await userEvent.click(screen.getByRole('button', { name: '儲存' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('修改未被接受');
  expect(writes(fetch)).toHaveLength(1);
  expect(writes(fetch)[0]).toMatchObject({
    expected_revision_id: original.revision_id,
    changes: [{ action: 'set_field', field: 'job_title', value: '未提交草稿' }],
  });
});

test.each(['invalid', 'offline'])(
  'a %s read is not an empty JD and offers no way to edit',
  async (failure) => {
    vi.stubGlobal(
      'fetch',
      failure === 'invalid'
        ? vi.fn().mockResolvedValue(Response.json({ profile: {} }))
        : vi.fn().mockRejectedValue(new TypeError('offline')),
    );
    renderEditor();
    expect(await screen.findByRole('alert')).toBeVisible();
    expect(screen.queryByRole('button', { name: /^修改/ })).not.toBeInTheDocument();
    expect(screen.queryByText('尚未提供')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '重新讀取 JD' })).toBeEnabled();
  },
);

test('while a command is in flight a second Save and Esc do nothing; the editor closes when it is accepted', async () => {
  let finish: (value: Response) => void = () => {
    throw new Error('Uninitialized');
  };
  const response = new Promise<Response>((resolve) => {
    finish = resolve;
  });
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((_path, options) =>
    options?.method === 'POST' ? response : Promise.resolve(Response.json(original)),
  );
  vi.stubGlobal('fetch', fetch);
  renderEditor();
  await userEvent.click(await screen.findByText('前端工程師'));
  const field = await screen.findByRole('textbox', { name: '職務名稱' });
  await userEvent.clear(field);
  await userEvent.type(field, '尚未確認');
  await userEvent.dblClick(screen.getByRole('button', { name: '儲存' }));
  await userEvent.keyboard('{Escape}');
  expect(screen.getByRole('textbox', { name: '職務名稱' })).toBeVisible();
  expect(writes(fetch)).toHaveLength(1);
  await act(async () => {
    finish(Response.json(updated));
    await response;
  });
  await waitFor(() =>
    expect(screen.queryByRole('textbox', { name: '職務名稱' })).not.toBeInTheDocument(),
  );
});

test('while a Turn owns the JD the fields are plain text', async () => {
  const fetch = vi.fn().mockImplementation(() => Promise.resolve(Response.json(original)));
  vi.stubGlobal('fetch', fetch);
  renderEditor(true);
  await userEvent.click(await screen.findByText('前端工程師'));
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: '修改職務名稱' })).toHaveAttribute(
    'aria-disabled',
    'true',
  );
});
