import { formalJdQueries } from './jd-queries';
import { refreshQueries } from '../../shared/api/refresh-queries';
/** The basic data and the collections are two editors over one revision: only one edit may be open or unconfirmed. */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import type { JdProfileView } from '../../shared/api/generated/jd-profile-view';
import type { JdWorkView } from '../../shared/api/generated/jd-work-view';
import { EditSlots } from './EditSlots';
import { JdProfileEditor } from './JdProfileEditor';
import { JdWorkEditor } from './JdWorkEditor';

const fileId = '10000000-0000-4000-8000-000000000001';
const revision = '20000000-0000-4000-8000-000000000002';
const areaId = '30000000-0000-4000-8000-000000000003';
const profile: JdProfileView = {
  revision_id: revision,
  profile: { job_title: '前端工程師', organization_unit: null, reports_to: null, purpose: null },
};
const work: JdWorkView = {
  revision_id: revision,
  areas: [{ area_id: areaId, title: '網站交付', scope_text: '原範圍' }],
  tasks: [],
  capabilities: [],
  task_links: [],
  collaborators: [],
  conditions: [],
};
const clients: QueryClient[] = [];

function renderBoth() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      <EditSlots>
        <JdProfileEditor
          refresh={() => refreshQueries(client, formalJdQueries(fileId))}
          jobFileId={fileId}
        />
        <JdWorkEditor
          refresh={() => refreshQueries(client, formalJdQueries(fileId))}
          jobFileId={fileId}
        />
      </EditSlots>
    </QueryClientProvider>,
  );
}

function serve(post?: () => Promise<Response>) {
  const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>();
  fetch.mockImplementation((path, options) => {
    if (options?.method === 'POST') return post ? post() : Promise.resolve(Response.json({}));
    return Promise.resolve(Response.json(path.endsWith('/jd/profile') ? profile : work));
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

beforeEach(() => sessionStorage.clear());
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});

test('while a basic-data field is open, no collection field can be opened, and the reverse', async () => {
  serve();
  renderBoth();
  await userEvent.click(await screen.findByText('前端工程師'));
  await screen.findByRole('textbox', { name: '職務名稱' });

  const areaScope = await screen.findByRole('button', { name: '修改職責範圍' });
  expect(areaScope).toHaveAttribute('aria-disabled', 'true');
  await userEvent.click(screen.getByText('原範圍'));
  expect(screen.queryByRole('textbox', { name: '職責範圍' })).not.toBeInTheDocument();

  // Cancel frees the collections; opening one now holds the basic data.
  await userEvent.click(screen.getByRole('button', { name: '取消' }));
  await userEvent.click(screen.getByText('原範圍'));
  await screen.findByRole('textbox', { name: '職責範圍' });
  expect(screen.getByRole('button', { name: '修改職務名稱' })).toHaveAttribute(
    'aria-disabled',
    'true',
  );
  await userEvent.click(screen.getByText('前端工程師'));
  expect(screen.queryByRole('textbox', { name: '職務名稱' })).not.toBeInTheDocument();
});

test('an unconfirmed basic-data command keeps the collections still until it is confirmed', async () => {
  let attempt = 0;
  serve(() => {
    attempt += 1;
    return attempt === 1
      ? Promise.reject(new TypeError('lost response'))
      : Promise.resolve(Response.json(profile));
  });
  renderBoth();
  await userEvent.click(await screen.findByText('前端工程師'));
  const field = await screen.findByRole('textbox', { name: '職務名稱' });
  await userEvent.clear(field);
  await userEvent.type(field, '維護工程師{Enter}');
  await screen.findByText(/JD 修改結果尚未確認/);

  await userEvent.click(screen.getByRole('button', { name: '取消' }));
  expect(screen.getByRole('button', { name: '修改職責範圍' })).toHaveAttribute(
    'aria-disabled',
    'true',
  );
  await userEvent.click(screen.getByText('原範圍'));
  expect(screen.queryByRole('textbox', { name: '職責範圍' })).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole('button', { name: '重新確認修改結果' }));
  await waitFor(() =>
    expect(screen.getByRole('button', { name: '修改職責範圍' })).toHaveAttribute(
      'aria-disabled',
      'false',
    ),
  );
});
