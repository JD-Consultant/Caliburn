import { expect, test } from '@playwright/test';
import type { BrowserContext, Page } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { isJobFile } from '../../src/shared/api/validation';
import { isSubmitInterviewInput } from '../../src/features/interview/interview-turn-api';
import type { SubmitInterviewInput } from '../../src/shared/api/generated/submit-interview-input';

async function createFile(page: Page) {
  const response = await page.request.post('/api/job-files', {
    data: {
      command_id: randomUUID(),
      display_name: '合成大寫路由 ' + randomUUID(),
      employee_name: '合成員工',
    },
  });
  const file: unknown = await response.json();
  if (!isJobFile(file)) throw new Error('Invalid synthetic file');
  // The API emits the canonical lower-case spelling; the tests type the capitalised one.
  expect(file.job_file_id).toBe(file.job_file_id.toLowerCase());
  return file;
}

function turn(fileId: string, executionId: string) {
  return {
    job_file_id: fileId,
    execution_id: executionId,
    status: 'active',
    pause_requested: false,
    input_text: '合成訪談',
    allowed_controls: [],
    commentary: [],
    plan_preview: null,
    candidate: null,
  };
}

/**
 * The specific stubs below match the canonical id exactly. A capitalised request would miss them,
 * so a catch-all first keeps any input POST away from the real backend; later routes win.
 */
async function stubTurnApi(
  context: BrowserContext,
  fileId: string,
  executionId: string,
  inputs: { commands: SubmitInterviewInput[]; urls: string[]; fail: boolean },
) {
  await context.route(/\/api\/job-files\/[^/]+\/inputs$/i, (route) =>
    route.abort('blockedbyclient'),
  );
  await context.route('**/api/job-files/' + fileId + '/inputs', async (route) => {
    const command: unknown = route.request().postDataJSON();
    if (!isSubmitInterviewInput(command)) throw new Error('Invalid input command');
    inputs.commands.push(command);
    inputs.urls.push(route.request().url());
    if (inputs.fail) return route.abort('failed');
    return route.fulfill({
      status: 202,
      json: {
        job_file_id: fileId,
        command_id: command.command_id,
        source_id: randomUUID(),
        execution_id: executionId,
      },
    });
  });
  await context.route('**/api/job-files/' + fileId + '/consultant-turns/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    await route.fulfill({
      json: path.endsWith('/current')
        ? { turn: null }
        : path.endsWith('/reasoning-summaries')
          ? []
          : turn(fileId, executionId),
    });
  });
}

async function send(page: Page, spelling: string) {
  await page.goto('/job-files/' + spelling);
  await expect(page.getByRole('button', { name: '送出訪談', exact: true })).toBeEnabled();
  await page.getByRole('textbox', { name: '訪談內容' }).fill('合成訪談');
  await page.getByRole('button', { name: '送出訪談', exact: true }).click();
}

const hintKeys = (page: Page) =>
  page.evaluate(() =>
    Object.keys(localStorage).filter((key) => key.startsWith('caliburn:interview-turn:')),
  );

test.describe('a capitalised UUID route is the same job file', () => {
  test('one canonical POST, one canonical recovery hint', async ({ page, context }) => {
    const file = await createFile(page);
    const executionId = randomUUID();
    const inputs = { commands: [] as SubmitInterviewInput[], urls: [] as string[], fail: false };
    await stubTurnApi(context, file.job_file_id, executionId, inputs);

    await send(page, file.job_file_id.toUpperCase());

    await expect.poll(() => inputs.commands.length).toBe(1);
    expect(inputs.urls[0]).toContain('/api/job-files/' + file.job_file_id + '/inputs');
    await expect
      .poll(() => hintKeys(page))
      .toEqual(['caliburn:interview-turn:' + file.job_file_id]);
    const hint = await page.evaluate(
      (key) => localStorage.getItem(key),
      'caliburn:interview-turn:' + file.job_file_id,
    );
    expect(JSON.parse(hint ?? 'null')).toEqual({
      command_id: inputs.commands[0]?.command_id,
      execution_id: executionId,
    });
  });

  test('an unknown result is recovered by its command from either spelling', async ({
    page,
    context,
  }) => {
    const file = await createFile(page);
    const executionId = randomUUID();
    const inputs = { commands: [] as SubmitInterviewInput[], urls: [] as string[], fail: true };
    await stubTurnApi(context, file.job_file_id, executionId, inputs);
    const recoveries: string[] = [];
    context.on('request', (request) => {
      if (request.url().includes('/by-command/')) recoveries.push(new URL(request.url()).pathname);
    });

    await send(page, file.job_file_id.toUpperCase());
    await expect.poll(() => inputs.commands.length).toBe(1);
    const commandId = inputs.commands[0]?.command_id ?? '';
    await expect
      .poll(() =>
        page.evaluate(
          (key) => JSON.parse(localStorage.getItem(key) ?? 'null') as unknown,
          'caliburn:interview-turn:' + file.job_file_id,
        ),
      )
      .toEqual({ command_id: commandId, execution_id: null });

    await page.goto('/job-files/' + file.job_file_id);
    await expect
      .poll(() =>
        page.evaluate(
          (key) => JSON.parse(localStorage.getItem(key) ?? 'null') as unknown,
          'caliburn:interview-turn:' + file.job_file_id,
        ),
      )
      .toEqual({ command_id: commandId, execution_id: executionId });
    expect(recoveries).toContain(
      '/api/job-files/' + file.job_file_id + '/consultant-turns/by-command/' + commandId,
    );
    expect(await hintKeys(page)).toEqual(['caliburn:interview-turn:' + file.job_file_id]);
  });
});
