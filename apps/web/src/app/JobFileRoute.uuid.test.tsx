/**
 * A typed or pasted route may spell a UUID in capitals; the app must still address one job file.
 * These cases run the real route, query keys, Web Lock/hint storage and command recovery.
 */
import { type QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import type { JobFile } from '../shared/api/generated/job-file-list';
import { readTurnHint, retainTurnHint } from '../features/interview/interview-turn-api';
import { App } from './App';
import { createAppQueryClient } from './query-client';

const lower = 'abcdefab-cdef-4abc-8def-abcdefabcdef';
const upper = lower.toUpperCase();
const otherFile = '10000000-0000-4000-8000-000000000001';
const commandId = '20000000-0000-4000-8000-000000000002';
const sourceId = '30000000-0000-4000-8000-000000000003';
const executionId = '40000000-0000-4000-8000-000000000004';
const file: JobFile = {
  job_file_id: lower,
  display_name: '合成職務',
  employee_name: '合成員工',
  created_at: '2026-10-09T00:00:00Z',
  name_revision: 1,
};
const profile = {
  revision_id: '50000000-0000-4000-8000-000000000005',
  profile: { job_title: null, organization_unit: null, reports_to: null, purpose: null },
};
const work = {
  revision_id: profile.revision_id,
  areas: [],
  tasks: [],
  capabilities: [],
  task_links: [],
  collaborators: [],
  conditions: [],
};
const clients: QueryClient[] = [];

function turn(jobFileId: string) {
  return {
    job_file_id: jobFileId,
    execution_id: executionId,
    status: 'active',
    pause_requested: false,
    input_text: '合成輸入',
    allowed_controls: ['cancel'],
    commentary: [],
    plan_preview: null,
    candidate: null,
  };
}

interface Backend {
  paths: string[];
  /** What by-command and by-execution reads answer, to exercise identity rejection. */
  turnOwner: string;
  inputs: 'accept' | 'network-failure' | 'other-command' | 'other-file';
}

function stubBackend(options: Partial<Backend> = {}): Backend {
  const backend: Backend = { paths: [], turnOwner: lower, inputs: 'accept', ...options };
  vi.stubGlobal(
    'fetch',
    vi.fn((path: string, init?: RequestInit) => {
      backend.paths.push(path);
      if (path.endsWith('/inputs') && init?.method === 'POST') {
        // The accepted result must echo the command this page generated.
        const sent = JSON.parse(init.body as string) as { command_id: string };
        return backend.inputs !== 'network-failure'
          ? Promise.resolve(
              Response.json(
                {
                  job_file_id: backend.inputs === 'other-file' ? otherFile : lower,
                  command_id: backend.inputs === 'other-command' ? commandId : sent.command_id,
                  source_id: sourceId,
                  execution_id: executionId,
                },
                { status: 202 },
              ),
            )
          : Promise.reject(new TypeError('network down'));
      }
      if (path.endsWith('/interview-plan'))
        return Promise.resolve(Response.json({ job_file_id: lower, plan: null }));
      if (path.endsWith('/consultant-turns/current'))
        return Promise.resolve(Response.json({ turn: null }));
      if (path.includes('/consultant-turns/'))
        return Promise.resolve(Response.json(turn(backend.turnOwner)));
      if (path.endsWith('/jd/work')) return Promise.resolve(Response.json(work));
      if (path.endsWith('/jd/profile')) return Promise.resolve(Response.json(profile));
      if (path.endsWith('/interviews')) return Promise.resolve(Response.json({ messages: [] }));
      return Promise.resolve(Response.json(file));
    }),
  );
  return backend;
}

function renderAt(jobFileId: string) {
  const client = createAppQueryClient();
  clients.push(client);
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/job-files/${jobFileId}`]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function submit(text: string): Promise<void> {
  await userEvent.type(await screen.findByRole('textbox', { name: '訪談內容' }), text);
  await userEvent.click(screen.getByRole('button', { name: '送出訪談' }));
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test('a capitalised UUID route addresses the API and storage with one canonical identity', async () => {
  const backend = stubBackend();
  renderAt(upper);
  expect(await screen.findByRole('textbox', { name: '訪談內容' })).toBeVisible();
  expect(backend.paths.length).toBeGreaterThan(0);
  expect(backend.paths.filter((path) => path.includes(upper))).toEqual([]);
  expect(backend.paths).toContain(`/api/job-files/${lower}`);
});

test('an accepted input under a capitalised route is adopted under the canonical file scope', async () => {
  const backend = stubBackend();
  renderAt(upper);
  await submit('合成輸入');
  await waitFor(() => expect(readTurnHint(lower)?.execution_id).toBe(executionId));
  expect(Object.keys(localStorage).filter((key) => key.includes(upper))).toEqual([]);
  expect(backend.paths.filter((path) => path.includes(upper))).toEqual([]);
  expect(screen.queryByText(/不屬於本次請求/)).not.toBeInTheDocument();
});

test.each(['other-command', 'other-file'] as const)(
  'an accepted result for %s is not adopted and the original command stays recoverable',
  async (inputs) => {
    stubBackend({ inputs });
    renderAt(upper);
    await submit('合成輸入');
    expect(await screen.findByText(/送出結果尚未確認/)).toBeVisible();
    const pending = readTurnHint(lower);
    expect(pending?.execution_id).toBeNull();
    expect(pending?.command_id).not.toBe(commandId);
  },
);

test.each([upper, lower])(
  'an unknown input result is recovered by its original command (route %s)',
  async (route) => {
    stubBackend({ inputs: 'network-failure' });
    const first = renderAt(upper);
    await submit('合成輸入');
    await waitFor(() => expect(readTurnHint(lower)?.execution_id).toBeNull());
    const pending = readTurnHint(lower);
    first.unmount();

    const backend = stubBackend();
    renderAt(route);
    await waitFor(() =>
      expect(readTurnHint(lower)).toEqual({ ...pending, execution_id: executionId }),
    );
    expect(backend.paths).toContain(
      `/api/job-files/${lower}/consultant-turns/by-command/${pending?.command_id}`,
    );
    expect(backend.paths.filter((path) => path.includes(upper))).toEqual([]);
  },
);

test('a recovered Turn that belongs to another job file is still rejected', async () => {
  await retainTurnHint(lower, { command_id: commandId, execution_id: null });
  const backend = stubBackend({ turnOwner: otherFile });
  renderAt(upper);
  await waitFor(() =>
    expect(backend.paths).toContain(
      `/api/job-files/${lower}/consultant-turns/by-command/${commandId}`,
    ),
  );
  expect(await screen.findByText(/不屬於這次訪談/)).toBeVisible();
  expect(readTurnHint(lower)).toEqual({ command_id: commandId, execution_id: null });
});

test('a deleted file clears the same recovery scope whichever spelling opened it', async () => {
  await retainTurnHint(lower, { command_id: commandId, execution_id: null });
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      Promise.resolve(Response.json({ detail: { code: 'job_file_not_found' } }, { status: 404 })),
    ),
  );
  renderAt(upper);
  // The page swaps from the metadata 404 to the app-wide deleted state; wait for the stable one.
  await waitFor(() => expect(screen.getByText('這份職務檔案已刪除')).toBeVisible());
  await waitFor(() => expect(readTurnHint(lower)).toBeNull());
});
