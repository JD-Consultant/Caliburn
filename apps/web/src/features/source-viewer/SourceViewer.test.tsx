import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';
import { SourceViewer } from './SourceViewer';

const fileId = '10000000-0000-4000-8000-000000000001';
const revisionId = '20000000-0000-4000-8000-000000000002';
const citationId = '30000000-0000-4000-8000-000000000003';
const sources = {
  revision_id: revisionId,
  references: [
    {
      citation_id: citationId,
      target_label: '任務：處理例外',
      source_kind: 'work_understanding',
      source_label: '例外處理理解',
      needs_recheck: true,
      jd_changed: false,
      source_changed: true,
    },
  ],
};
const root = {
  revision_id: revisionId,
  citation_id: citationId,
  content: {
    kind: 'work_understanding',
    title: '固定理解',
    description: '原引用描述',
    body: '## 原引用正文\n\n處理異常並追蹤。',
    references: [{ kind: 'work_situation', label: '讀取情境', source_ref: 'opaque/child?x=1&y=2' }],
  },
};
const child = {
  revision_id: revisionId,
  citation_id: citationId,
  content: {
    kind: 'work_situation',
    title: '原始情境',
    description: '固定情境描述',
    body: '情境正文',
    references: [{ kind: 'interview', label: '讀取訪談', source_ref: 'opaque/interview#3' }],
  },
};
const interview = {
  revision_id: revisionId,
  citation_id: citationId,
  content: {
    kind: 'interview',
    interview_sequence: 3,
    speaker: 'employee',
    interview_text: '<script>員工原話</script>\n第二行',
  },
};
const basePath = `/api/job-files/${fileId}/jd/sources`;
const contentPath = `${basePath}/${citationId}?revision_id=${revisionId}`;

function serveSources(overrides: Record<string, unknown> = {}) {
  const responses: Record<string, unknown> = {
    [basePath]: sources,
    [contentPath]: root,
    [`${contentPath}&source_ref=opaque%2Fchild%3Fx%3D1%26y%3D2`]: child,
    [`${contentPath}&source_ref=opaque%2Finterview%233`]: interview,
    [`${basePath}/${citationId}/changes?revision_id=${revisionId}`]: {
      revision_id: revisionId,
      citation_id: citationId,
      jd_markdown: 'JD 沒有淨差異。',
      source_markdown: '## 差異\n\n```diff\n- 舊\n+ 新\n```',
    },
    ...overrides,
  };
  const fetch = vi.fn((path: string, options?: RequestInit) => {
    expect(options?.method ?? 'GET').toBe('GET');
    const result = responses[path];
    if (result === undefined) throw new Error(`Unexpected request: ${path}`);
    return Promise.resolve(result instanceof Response ? result.clone() : Response.json(result));
  });
  vi.stubGlobal('fetch', fetch);
  return { fetch, responses };
}

async function openRoot() {
  await userEvent.click(screen.getByRole('button', { name: '正式 JD 來源（唯讀）' }));
  await userEvent.click(await screen.findByRole('button', { name: '例外處理理解' }));
}
const clients: QueryClient[] = [];

function renderViewer(jobFileId = fileId) {
  // Fresh cache entries make missing scope dimensions observable instead of hidden by refetch.
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  clients.push(client);
  const view = (id: string) => (
    <QueryClientProvider client={client}>
      <SourceViewer jobFileId={id} />
    </QueryClientProvider>
  );
  const rendered = render(view(jobFileId));
  return { client, ...rendered, switchFile: (id: string) => rendered.rerender(view(id)) };
}

afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test('formal sources load only when expanded and show their target and recheck status', async () => {
  const fetch = vi.fn((path: string, options?: RequestInit) => {
    expect(path).toBe(`/api/job-files/${fileId}/jd/sources`);
    expect(options?.method ?? 'GET').toBe('GET');
    return Promise.resolve(Response.json(sources));
  });
  vi.stubGlobal('fetch', fetch);
  renderViewer();
  expect(fetch).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('button', { name: '正式 JD 來源（唯讀）' }));
  expect(await screen.findByText('任務：處理例外')).toBeVisible();
  expect(screen.getByRole('button', { name: '例外處理理解' })).toBeVisible();
  expect(screen.getByText('來源已更新')).toBeVisible();
  expect(fetch).toHaveBeenCalledTimes(1);
});

test('follows only returned source refs through root, child and role-numbered interview, with read-only changes', async () => {
  const { fetch } = serveSources();
  renderViewer();
  await openRoot();
  expect(await screen.findByRole('heading', { name: '原引用正文' })).toBeVisible();
  expect(fetch).toHaveBeenCalledTimes(2);
  await userEvent.click(screen.getByRole('button', { name: '讀取情境' }));
  expect(await screen.findByText('情境正文')).toBeVisible();
  expect(screen.queryByRole('heading', { name: '原引用正文' })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: '讀取訪談' }));
  expect(await screen.findByText('訪談 #3 · 員工')).toBeVisible();
  expect(screen.getByText(/<script>員工原話<\/script>/)).toBeVisible();
  expect(document.querySelector('script')).toBeNull();
  await userEvent.click(screen.getByRole('button', { name: '回到直接來源' }));
  expect(await screen.findByRole('heading', { name: '原引用正文' })).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: '查看差異' }));
  await userEvent.click(await screen.findByText('來源變更', { selector: 'summary' }));
  expect(await screen.findByRole('heading', { name: '差異' })).toBeVisible();
  expect(screen.getByText(/最新已發布/)).toBeVisible();
  expect(screen.getByText('來源已更新')).toBeVisible();
  expect(
    screen.queryByRole('button', { name: /^(確認核對|修改引用|保存)$/ }),
  ).not.toBeInTheDocument();
});

test('direct interview sources do not offer Memory changes', async () => {
  serveSources({
    [basePath]: {
      ...sources,
      references: [
        {
          ...sources.references[0],
          source_kind: 'interview',
          needs_recheck: false,
          source_changed: false,
        },
      ],
    },
    [contentPath]: interview,
  });
  renderViewer();
  await openRoot();
  expect(await screen.findByText('訪談 #3 · 員工')).toBeVisible();
  expect(screen.queryByRole('button', { name: '查看差異' })).not.toBeInTheDocument();
});

test.each(['content', 'changes'])(
  '%s conflict requires list reread and clears the old selection',
  async (kind) => {
    const failingPath =
      kind === 'content'
        ? contentPath
        : `${basePath}/${citationId}/changes?revision_id=${revisionId}`;
    const { responses } = serveSources({
      [failingPath]: Response.json({ detail: 'private diagnostics' }, { status: 409 }),
    });
    renderViewer();
    await openRoot();
    if (kind === 'changes') {
      await screen.findByRole('heading', { name: '原引用正文' });
      await userEvent.click(screen.getByRole('button', { name: '查看差異' }));
    }
    expect(await screen.findByText(/正式 JD 已更新，請重新讀取來源列表/)).toBeVisible();
    expect(screen.queryByText('private diagnostics')).not.toBeInTheDocument();
    responses[basePath] = { ...sources, revision_id: '40000000-0000-4000-8000-000000000004' };
    await userEvent.click(screen.getByRole('button', { name: '重新讀取來源列表' }));
    await screen.findByRole('button', { name: '例外處理理解' });
    expect(screen.queryByText(/正式 JD 已更新/)).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '原引用正文' })).not.toBeInTheDocument();
  },
);

test('switching files clears disclosure and selection even with the same revision and citation IDs', async () => {
  const otherFile = '50000000-0000-4000-8000-000000000005';
  const { fetch } = serveSources({
    [`/api/job-files/${otherFile}/jd/sources`]: sources,
    [`/api/job-files/${otherFile}/jd/sources/${citationId}?revision_id=${revisionId}`]: {
      ...root,
      content: { ...root.content, body: '另一檔案正文' },
    },
  });
  const { switchFile } = renderViewer();
  await openRoot();
  await screen.findByRole('heading', { name: '原引用正文' });
  switchFile(otherFile);
  expect(screen.queryByRole('heading', { name: '原引用正文' })).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(2);
  await openRoot();
  expect(await screen.findByText('另一檔案正文')).toBeVisible();
  expect(screen.queryByRole('heading', { name: '原引用正文' })).not.toBeInTheDocument();
});

test.each([
  ['jd-profile', fileId],
  ['jd-profile', fileId, 'formal'],
])(
  'existing invalidation %j refreshes sources and discards selected details',
  async (...queryKey) => {
    const { responses } = serveSources();
    const { client } = renderViewer();
    await openRoot();
    await screen.findByRole('heading', { name: '原引用正文' });
    responses[basePath] = {
      ...sources,
      references: [{ ...sources.references[0], source_label: '新版來源標籤' }],
    };
    await act(() => client.invalidateQueries({ queryKey }));
    expect(await screen.findByRole('button', { name: '新版來源標籤' })).toBeVisible();
    expect(screen.queryByRole('heading', { name: '原引用正文' })).not.toBeInTheDocument();
  },
);

test('same citation on a new formal revision never reuses old content or changes', async () => {
  const nextRevision = '40000000-0000-4000-8000-000000000004';
  const { responses } = serveSources({
    [`${basePath}/${citationId}?revision_id=${nextRevision}`]: {
      ...root,
      revision_id: nextRevision,
      content: { ...root.content, body: '新版固定正文' },
    },
    [`${basePath}/${citationId}/changes?revision_id=${nextRevision}`]: {
      revision_id: nextRevision,
      citation_id: citationId,
      jd_markdown: 'JD 沒有淨差異。',
      source_markdown: '## 新版引用差異',
    },
  });
  renderViewer();
  await openRoot();
  await screen.findByRole('heading', { name: '原引用正文' });
  await userEvent.click(screen.getByRole('button', { name: '查看差異' }));
  await userEvent.click(await screen.findByText('來源變更', { selector: 'summary' }));
  await screen.findByRole('heading', { name: '差異' });
  responses[basePath] = { ...sources, revision_id: nextRevision };
  await userEvent.click(screen.getByRole('button', { name: '重新讀取來源列表' }));
  await userEvent.click(await screen.findByRole('button', { name: '例外處理理解' }));
  expect(await screen.findByText('新版固定正文')).toBeVisible();
  expect(screen.queryByRole('heading', { name: '原引用正文' })).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: '差異' })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: '查看差異' }));
  await userEvent.click(await screen.findByText('來源變更', { selector: 'summary' }));
  expect(await screen.findByRole('heading', { name: '新版引用差異' })).toBeVisible();
});

test('two citations with the same child locator keep separate fixed content', async () => {
  const secondCitation = '60000000-0000-4000-8000-000000000006';
  serveSources({
    [basePath]: {
      ...sources,
      references: [
        ...sources.references,
        { ...sources.references[0], citation_id: secondCitation, source_label: '第二條引用' },
      ],
    },
    [`${basePath}/${secondCitation}?revision_id=${revisionId}`]: {
      ...root,
      citation_id: secondCitation,
    },
    [`${basePath}/${secondCitation}?revision_id=${revisionId}&source_ref=opaque%2Fchild%3Fx%3D1%26y%3D2`]:
      {
        ...child,
        citation_id: secondCitation,
        content: { ...child.content, body: '第二條引用的固定情境' },
      },
  });
  renderViewer();
  await openRoot();
  await userEvent.click(await screen.findByRole('button', { name: '讀取情境' }));
  await screen.findByText('情境正文');
  await userEvent.click(screen.getByRole('button', { name: '第二條引用' }));
  await userEvent.click(await screen.findByRole('button', { name: '讀取情境' }));
  expect(await screen.findByText('第二條引用的固定情境')).toBeVisible();
  expect(screen.queryByText('情境正文')).not.toBeInTheDocument();
});

test('unreadable fixed content remains an error and preserves needs_recheck', async () => {
  serveSources({
    [contentPath]: Response.json({ detail: { code: 'source_not_found' } }, { status: 404 }),
  });
  renderViewer();
  await openRoot();
  expect(await screen.findByRole('alert')).toHaveTextContent('此來源目前無法讀取');
  expect(screen.getByText('來源已更新')).toBeVisible();
  expect(screen.queryByText(/找不到這份職務檔案/)).not.toBeInTheDocument();
});

test('missing review baseline is not presented as a transient outage or an empty comparison', async () => {
  serveSources({
    [`${basePath}/${citationId}/changes?revision_id=${revisionId}`]: Response.json(
      { detail: { code: 'jd_review_baseline_not_available', message: 'private diagnostics' } },
      { status: 503 },
    ),
  });
  renderViewer();
  await userEvent.click(screen.getByRole('button', { name: '正式 JD 來源（唯讀）' }));
  await userEvent.click(await screen.findByRole('button', { name: '查看差異' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(
    '無法取得此引用的核對基準，尚不能比較 JD 變更。',
  );
  expect(screen.queryByText(/private diagnostics|暫時無法使用|沒有淨差異/)).not.toBeInTheDocument();
  expect(screen.getByText('來源已更新')).toBeVisible();
});

test.each([404, 503])(
  'list HTTP %s is an error, never an empty or confirmed list',
  async (status) => {
    serveSources({ [basePath]: Response.json({}, { status }) });
    renderViewer();
    await userEvent.click(screen.getByRole('button', { name: '正式 JD 來源（唯讀）' }));
    expect(await screen.findByRole('alert')).toBeVisible();
    expect(screen.queryByText(/目前正式 JD 沒有附帶引用/)).not.toBeInTheDocument();
  },
);

test('no references is neutral and not an assertion that JD is wrong or already checked', async () => {
  serveSources({ [basePath]: { ...sources, references: [] } });
  renderViewer();
  await userEvent.click(screen.getByRole('button', { name: '正式 JD 來源（唯讀）' }));
  expect(
    await screen.findByText(/目前正式 JD 沒有附帶引用；這不代表內容錯誤或已完成核對/),
  ).toBeVisible();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

test.each([
  { ...root, revision_id: '60000000-0000-4000-8000-000000000006' },
  { ...root, citation_id: '60000000-0000-4000-8000-000000000006' },
  { ...root, reasoning: 'private reasoning' },
  { ...root, content: { ...root.content, kind: 'candidate' } },
])('rejects foreign identity and private or candidate response fields', async (response) => {
  serveSources({ [contentPath]: response });
  renderViewer();
  await openRoot();
  expect(await screen.findByRole('alert')).toBeVisible();
  expect(screen.queryByRole('heading', { name: '原引用正文' })).not.toBeInTheDocument();
  expect(screen.queryByText('private reasoning')).not.toBeInTheDocument();
});

test('a late response from a previous file cannot reappear after switching', async () => {
  let finish: ((response: Response) => void) | undefined;
  const pending = new Promise<Response>((resolve) => {
    finish = resolve;
  });
  vi.stubGlobal(
    'fetch',
    vi.fn((path: string) =>
      path === basePath ? Promise.resolve(Response.json(sources)) : pending,
    ),
  );
  const { switchFile } = renderViewer();
  await openRoot();
  switchFile('50000000-0000-4000-8000-000000000005');
  await act(async () => {
    finish?.(Response.json(root));
    await pending;
  });
  await waitFor(() =>
    expect(screen.queryByRole('heading', { name: '原引用正文' })).not.toBeInTheDocument(),
  );
});
