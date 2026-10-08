import { StrictMode } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { InterviewComposer } from '../features/interview/InterviewComposer';
import { InterviewHistory } from '../features/interview/InterviewHistory';
import { consultantTurnQuery, retainTurnHint } from '../features/interview/interview-turn-api';
import { JdProfileEditor } from '../features/jd-editor/JdProfileEditor';
import { JdWorkEditor } from '../features/jd-editor/JdWorkEditor';
import { createAppQueryClient } from './query-client';

const fileId = '10000000-0000-4000-8000-000000000001';
const executionId = '20000000-0000-4000-8000-000000000002';
const revisionId = '30000000-0000-4000-8000-000000000003';
const sourceId = '40000000-0000-4000-8000-000000000004';
const areaId = '50000000-0000-4000-8000-000000000005';
const active = {
  job_file_id: fileId,
  execution_id: executionId,
  status: 'active',
  pause_requested: false,
  input_text: '本輪輸入',
  allowed_controls: [],
  commentary: [],
  plan_preview: null,
  candidate: null,
};
const clients: QueryClient[] = [];

function readBody(path: string, current: boolean): unknown {
  if (path.endsWith('/jd/profile'))
    return {
      revision_id: revisionId,
      profile: {
        job_title: current ? '本輪正式職稱' : '舊職稱',
        organization_unit: null,
        reports_to: null,
        purpose: null,
      },
    };
  if (path.endsWith('/jd/work'))
    return {
      revision_id: revisionId,
      areas: [{ area_id: areaId, title: current ? '本輪正式職責' : '舊職責', scope_text: null }],
      tasks: [],
      capabilities: [],
      task_links: [],
      collaborators: [],
      conditions: [],
    };
  if (path.endsWith('/interviews'))
    return {
      messages: current
        ? [
            {
              source_id: sourceId,
              interview_sequence: 1,
              speaker: 'employee',
              interview_text: '本輪正式訪談',
              execution_id: null,
            },
          ]
        : [],
    };
  if (path.endsWith('/reasoning-summaries')) return [];
  return { ...active, status: current ? 'completed' : 'active' };
}

function renderWorkspace(strict: boolean) {
  const client = createAppQueryClient();
  clients.push(client);
  const page = (
    <QueryClientProvider client={client}>
      <InterviewHistory jobFileId={fileId} />
      <InterviewComposer jobFileId={fileId} />
      <JdProfileEditor jobFileId={fileId} />
      <JdWorkEditor jobFileId={fileId} />
    </QueryClientProvider>
  );
  render(strict ? <StrictMode>{page}</StrictMode> : page);
  return client;
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  retainTurnHint(fileId, { command_id: sourceId, execution_id: executionId });
});
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test.each([false, true])(
  'completion replaces earlier unresolved formal reads and ignores their late results (StrictMode: %s)',
  async (strict) => {
    let completed = false;
    const oldReads: (() => void)[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn((path: string) => {
        if (!completed && (path.includes('/jd/') || path.endsWith('/interviews'))) {
          return new Promise<Response>((resolve) =>
            oldReads.push(() => resolve(Response.json(readBody(path, false)))),
          );
        }
        return Promise.resolve(Response.json(readBody(path, completed)));
      }),
    );
    const client = renderWorkspace(strict);
    await screen.findByText('本輪輸入');
    await waitFor(() => expect(oldReads.length).toBeGreaterThanOrEqual(3));

    completed = true;
    await act(async () => {
      await client.invalidateQueries({
        queryKey: consultantTurnQuery(fileId, executionId).queryKey,
      });
    });
    expect(await screen.findByText('本輪正式職稱')).toBeVisible();
    expect(await screen.findByRole('heading', { name: '本輪正式職責' })).toBeVisible();
    expect(await screen.findByText('本輪正式訪談')).toBeVisible();

    await act(async () => {
      oldReads.forEach((finish) => finish());
      await Promise.resolve();
    });
    expect(screen.getByText('本輪正式職稱')).toBeVisible();
    expect(screen.queryByText('舊職稱')).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '舊職責' })).not.toBeInTheDocument();
  },
);

test('failed completion refresh reports saved data separately, retries only by request, and recovers without resending input', async () => {
  let completed = false;
  let failRefresh = false;
  const fetch = vi.fn((path: string) =>
    Promise.resolve(
      failRefresh && path.endsWith('/jd/profile')
        ? Response.json({}, { status: 503 })
        : Response.json(readBody(path, completed)),
    ),
  );
  vi.stubGlobal('fetch', fetch);
  const client = renderWorkspace(true);
  await screen.findByText('舊職稱');
  completed = true;
  failRefresh = true;
  await act(async () => {
    await client.invalidateQueries({ queryKey: consultantTurnQuery(fileId, executionId).queryKey });
  });

  expect(await screen.findByText(/訪談已保存，但畫面尚未更新/)).toBeVisible();
  expect(screen.getByText('這次訪談已完成並保存。')).toBeVisible();
  const failedReads = fetch.mock.calls.length;
  await userEvent.type(screen.getByLabelText('訪談內容'), '下一輪草稿');
  expect(fetch.mock.calls).toHaveLength(failedReads);

  failRefresh = false;
  await userEvent.click(screen.getByRole('button', { name: '重新更新訪談與 JD' }));
  expect(await screen.findByText('本輪正式職稱')).toBeVisible();
  await waitFor(() =>
    expect(screen.queryByText(/訪談已保存，但畫面尚未更新/)).not.toBeInTheDocument(),
  );
  expect(screen.getByLabelText('訪談內容')).toHaveValue('下一輪草稿');
  expect(fetch.mock.calls.every(([path]) => !path.endsWith('/inputs'))).toBe(true);
});
