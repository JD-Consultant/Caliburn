import { expect, test } from '@playwright/test';
import type { BrowserContext, Page, Route } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { isJobFile } from '../../src/shared/api/validation';
import { isSubmitInterviewInput } from '../../src/features/interview/interview-turn-api';
import type { SubmitInterviewInput } from '../../src/shared/api/generated/submit-interview-input';

async function createFile(page: Page) {
  const response = await page.request.post('/api/job-files', {
    data: {
      command_id: randomUUID(),
      display_name: '合成跨頁競爭 ' + randomUUID(),
      employee_name: '合成員工',
    },
  });
  const file: unknown = await response.json();
  if (!isJobFile(file)) throw new Error('Invalid synthetic file');
  return file;
}

async function turnRoutes(
  context: BrowserContext,
  fileId: string,
  input: (route: Route, command: SubmitInterviewInput) => Promise<void>,
  getTurn: (executionId: string) => unknown,
  recover: () => unknown,
) {
  await context.route('**/api/job-files/' + fileId + '/inputs', async (route) => {
    const command: unknown = route.request().postDataJSON();
    if (!isSubmitInterviewInput(command)) throw new Error('Invalid input command');
    await input(route, command);
  });
  await context.route('**/api/job-files/' + fileId + '/consultant-turns/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const body = path.endsWith('/current')
      ? { turn: null }
      : path.includes('/by-command/')
        ? recover()
        : path.endsWith('/reasoning-summaries')
          ? []
          : getTurn(path.split('/').at(-1) ?? '');
    await route.fulfill({ json: body });
  });
}

function turn(fileId: string, executionId: string, status: 'active' | 'completed') {
  return {
    job_file_id: fileId,
    execution_id: executionId,
    status,
    pause_requested: false,
    input_text: '合成訪談',
    allowed_controls: [],
    commentary: [],
    plan_preview: null,
    candidate: null,
  };
}

async function openComposer(page: Page, fileId: string) {
  await page.goto('/job-files/' + fileId);
  await expect(page.getByRole('button', { name: '送出訪談', exact: true })).toBeEnabled();
}

test.describe('reservation protects the captured input', () => {
  for (const entry of ['first', 'after-completion'] as const) {
    test(`${entry} input stays disabled while another page holds its Web Lock`, async ({
      page,
      context,
    }) => {
      const file = await createFile(page);
      const oldExecution = randomUUID();
      const nextExecution = randomUUID();
      const commands: SubmitInterviewInput[] = [];
      await turnRoutes(
        context,
        file.job_file_id,
        async (route, command) => {
          commands.push(command);
          await route.fulfill({
            json: {
              job_file_id: file.job_file_id,
              command_id: command.command_id,
              execution_id: nextExecution,
              source_id: randomUUID(),
            },
          });
        },
        (id) => turn(file.job_file_id, id, id === oldExecution ? 'completed' : 'active'),
        () => turn(file.job_file_id, oldExecution, 'completed'),
      );
      const holder = await context.newPage();
      await holder.goto('/');
      if (entry === 'after-completion') {
        await holder.evaluate(
          ({ id, execution }) => {
            localStorage.setItem(
              'caliburn:interview-turn:' + id,
              JSON.stringify({ command_id: crypto.randomUUID(), execution_id: execution }),
            );
          },
          { id: file.job_file_id, execution: oldExecution },
        );
      }
      await openComposer(page, file.job_file_id);
      const textbox = page.getByRole('textbox', { name: '訪談內容' });
      const original = '取鎖前固定的合成原文';
      await textbox.fill(original);
      await holder.evaluate(async (id) => {
        const state = window as Window & { releaseInterviewLock?: () => void };
        let acquired: () => void = () => {};
        const locked = new Promise<void>((resolve) => {
          acquired = resolve;
        });
        void navigator.locks.request(
          'caliburn:interview-turn:' + id,
          () =>
            new Promise<void>((resolve) => {
              state.releaseInterviewLock = resolve;
              acquired();
            }),
        );
        await locked;
      }, file.job_file_id);
      try {
        await page.getByRole('button', { name: '送出訪談', exact: true }).click();
        await expect(textbox).toBeDisabled();
        await expect(page.getByRole('button', { name: '正在確認送出…' })).toBeDisabled();
        await expect
          .poll(() =>
            holder.evaluate(
              async (id) =>
                (await navigator.locks.query()).pending?.some(
                  (lock) => lock.name === 'caliburn:interview-turn:' + id,
                ),
              file.job_file_id,
            ),
          )
          .toBe(true);
        await page.keyboard.type('等待期間新增文字');
        await expect(textbox).toHaveValue(original);
        expect(commands).toHaveLength(0);
      } finally {
        await holder.evaluate(() => {
          const state = window as Window & { releaseInterviewLock?: () => void };
          state.releaseInterviewLock?.();
          delete state.releaseInterviewLock;
        });
      }
      await expect(page.getByText('顧問正在處理，尚未正式完成。')).toBeVisible();
      expect(commands).toHaveLength(1);
      expect(commands[0]?.text).toBe(original);
      await expect
        .poll(() =>
          page.evaluate(
            (id) =>
              JSON.parse(
                localStorage.getItem('caliburn:interview-turn:' + id) ?? 'null',
              ) as unknown,
            file.job_file_id,
          ),
        )
        .toMatchObject({ command_id: commands[0]?.command_id, execution_id: nextExecution });
    });
  }
});

test('two actual pages submitting simultaneously keep one original command', async ({
  page,
  context,
}) => {
  const file = await createFile(page);
  const executionId = randomUUID();
  const requests: SubmitInterviewInput[] = [];
  let release: () => void = () => {};
  const deferred = new Promise<void>((resolve) => {
    release = resolve;
  });
  await turnRoutes(
    context,
    file.job_file_id,
    async (route, command) => {
      requests.push(command);
      await deferred;
      await route.fulfill({
        json: {
          job_file_id: file.job_file_id,
          command_id: command.command_id,
          execution_id: executionId,
          source_id: randomUUID(),
        },
      });
    },
    () => turn(file.job_file_id, executionId, 'active'),
    () => turn(file.job_file_id, executionId, 'active'),
  );
  const other = await context.newPage();
  await Promise.all([openComposer(page, file.job_file_id), openComposer(other, file.job_file_id)]);
  await page.getByRole('textbox', { name: '訪談內容' }).fill('第一頁合成文字');
  await other.getByRole('textbox', { name: '訪談內容' }).fill('第二頁合成文字');
  await Promise.all(
    [page, other].map((tab) =>
      tab.evaluate(() => {
        document.querySelector<HTMLFormElement>('.composer-dock form')?.requestSubmit();
      }),
    ),
  );
  await expect.poll(() => requests.length).toBe(1);
  const winner = requests[0];
  if (!winner) throw new Error('Expected one command');
  await expect
    .poll(() =>
      page.evaluate(
        (id) =>
          JSON.parse(localStorage.getItem('caliburn:interview-turn:' + id) ?? 'null') as unknown,
        file.job_file_id,
      ),
    )
    .toMatchObject({ command_id: winner.command_id });
  release();
  await expect
    .poll(() =>
      page.evaluate(
        (id) =>
          JSON.parse(localStorage.getItem('caliburn:interview-turn:' + id) ?? 'null') as unknown,
        file.job_file_id,
      ),
    )
    .toMatchObject({ command_id: winner.command_id, execution_id: executionId });
  expect(requests).toHaveLength(1);
});

test('old page deferred ACK cannot replace a newer page completed-turn reservation', async ({
  page,
  context,
}) => {
  const file = await createFile(page);
  const oldExecution = randomUUID(),
    nextExecution = randomUUID();
  const commands: SubmitInterviewInput[] = [];
  let release: () => void = () => {};
  const deferred = new Promise<void>((resolve) => {
    release = resolve;
  });
  await turnRoutes(
    context,
    file.job_file_id,
    async (route, command) => {
      commands.push(command);
      const first = commands.length === 1;
      if (first) await deferred;
      await route.fulfill({
        json: {
          job_file_id: file.job_file_id,
          command_id: command.command_id,
          execution_id: first ? oldExecution : nextExecution,
          source_id: randomUUID(),
        },
      });
    },
    (executionId) =>
      turn(file.job_file_id, executionId, executionId === oldExecution ? 'completed' : 'active'),
    () => turn(file.job_file_id, oldExecution, 'completed'),
  );
  await openComposer(page, file.job_file_id);
  await page.getByRole('textbox', { name: '訪談內容' }).fill('第一輪合成文字');
  await page.getByRole('button', { name: '送出訪談', exact: true }).click();
  await expect.poll(() => commands.length).toBe(1);
  const other = await context.newPage();
  await openComposer(other, file.job_file_id);
  await expect(other.getByText('這次訪談已完成並保存。')).toBeVisible();
  await other.getByRole('textbox', { name: '訪談內容' }).fill('下一輪合成文字');
  await other.getByRole('button', { name: '送出訪談', exact: true }).click();
  await expect.poll(() => commands.length).toBe(2);
  const next = commands[1];
  if (!next) throw new Error('Expected next command');
  await expect
    .poll(() =>
      other.evaluate(
        (id) =>
          JSON.parse(localStorage.getItem('caliburn:interview-turn:' + id) ?? 'null') as unknown,
        file.job_file_id,
      ),
    )
    .toMatchObject({ command_id: next.command_id, execution_id: nextExecution });
  release();
  await expect(page.getByText('顧問正在處理，尚未正式完成。')).toBeVisible();
  expect(
    await page.evaluate(
      (id) =>
        JSON.parse(localStorage.getItem('caliburn:interview-turn:' + id) ?? 'null') as unknown,
      file.job_file_id,
    ),
  ).toEqual({ command_id: next.command_id, execution_id: nextExecution });
});

for (const cleanup of ['available', 'fails-once'] as const) {
  test(`confirmed deletion with ${cleanup} storage cleans every open page and restores focus`, async ({
    page,
    context,
  }) => {
    const file = await createFile(page);
    const otherFile = await createFile(page);
    let deleteRequests = 0;
    context.on('request', (request) => {
      if (
        request.method() === 'DELETE' &&
        new URL(request.url()).pathname === '/api/job-files/' + file.job_file_id
      )
        deleteRequests += 1;
    });
    const workspace = await context.newPage();
    await workspace.goto('/job-files/' + file.job_file_id);
    await expect(
      workspace.getByRole('heading', { name: file.display_name, exact: true }),
    ).toBeVisible();
    await page.goto('/');
    await expect(
      page.getByRole('button', {
        name: '刪除 ' + file.display_name + '（合成員工，' + file.job_file_id.slice(0, 8) + '）',
        exact: true,
      }),
    ).toBeVisible();
    let listRefreshes = 0;
    page.on('request', (request) => {
      if (request.method() === 'GET' && new URL(request.url()).pathname === '/api/job-files')
        listRefreshes += 1;
    });
    for (const tab of [page, workspace]) {
      await tab.evaluate(
        ({ id, other, command }) => {
          for (const fileId of [id, other]) {
            for (const kind of ['jd-profile', 'jd-work', 'job-file-rename'])
              sessionStorage.setItem('caliburn.pending-' + kind + '.' + fileId, '{}');
            localStorage.setItem(
              'caliburn:interview-turn:' + fileId,
              JSON.stringify({ command_id: command, execution_id: null }),
            );
          }
        },
        { id: file.job_file_id, other: otherFile.job_file_id, command: randomUUID() },
      );
    }
    if (cleanup === 'fails-once') {
      await workspace.evaluate((id) => {
        const descriptor = Object.getOwnPropertyDescriptor(Storage.prototype, 'removeItem');
        if (!descriptor) throw new Error('Missing native Storage.removeItem');
        const removeSession = Storage.prototype.removeItem.bind(sessionStorage);
        const removeLocal = Storage.prototype.removeItem.bind(localStorage);
        Object.defineProperty(Storage.prototype, 'removeItem', {
          ...descriptor,
          value(this: Storage, key: string) {
            if (this === sessionStorage && key === 'caliburn.pending-jd-profile.' + id) {
              Object.defineProperty(Storage.prototype, 'removeItem', descriptor);
              throw new DOMException('Synthetic one-time storage denial', 'SecurityError');
            }
            if (this === sessionStorage) removeSession(key);
            else removeLocal(key);
          },
        });
      }, file.job_file_id);
    }
    await page
      .getByRole('button', {
        name: '刪除 ' + file.display_name + '（合成員工，' + file.job_file_id.slice(0, 8) + '）',
        exact: true,
      })
      .click();
    await page.getByRole('button', { name: '永久刪除', exact: true }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.getByRole('button', { name: '建立職務檔案', exact: true })).toBeFocused();
    await expect(workspace.getByRole('heading', { name: '這份職務檔案已刪除' })).toBeVisible();
    expect(listRefreshes).toBe(1);
    if (cleanup === 'fails-once') {
      await expect(workspace.getByText(/職務檔案已刪除，但瀏覽器資料未能完整清理/)).toBeVisible();
      expect(
        await workspace.evaluate(
          (id) => sessionStorage.getItem('caliburn.pending-jd-profile.' + id),
          file.job_file_id,
        ),
      ).toBe('{}');
      await page.evaluate((id) => {
        const notification = new BroadcastChannel('caliburn:job-file-lifecycle');
        notification.postMessage({ type: 'job_file_deleted', job_file_id: id });
        notification.close();
      }, file.job_file_id);
      await expect(workspace.getByText(/職務檔案已刪除，但瀏覽器資料未能完整清理/)).toHaveCount(0);
      await expect(workspace.getByRole('heading', { name: '這份職務檔案已刪除' })).toBeVisible();
    }
    for (const tab of [page, workspace]) {
      const result = await tab.evaluate(
        ({ id, other }) => ({
          cleared: ['jd-profile', 'jd-work', 'job-file-rename'].every(
            (kind) => sessionStorage.getItem('caliburn.pending-' + kind + '.' + id) === null,
          ),
          otherKept: ['jd-profile', 'jd-work', 'job-file-rename'].every(
            (kind) => sessionStorage.getItem('caliburn.pending-' + kind + '.' + other) === '{}',
          ),
          hint: localStorage.getItem('caliburn:interview-turn:' + id),
          otherHint: localStorage.getItem('caliburn:interview-turn:' + other),
        }),
        { id: file.job_file_id, other: otherFile.job_file_id },
      );
      expect(result.cleared).toBe(true);
      expect(result.otherKept).toBe(true);
      expect(result.hint).toBeNull();
      expect(result.otherHint).not.toBeNull();
    }
    expect(deleteRequests).toBe(1);
    expect(listRefreshes).toBe(1);
  });
}
