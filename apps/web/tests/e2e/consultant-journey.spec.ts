import { expect, test } from '@playwright/test';
import type { APIRequestContext, Page } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { isJdProfileView, isJobFile } from '../../src/shared/api/validation';

// These journeys run the real backend, PostgreSQL and UI against the scripted provider
// (apps/api/tests/fixtures/scripted_backend.py). It is a synthetic double: it proves the
// transport, control and reconnect behavior, not model quality or provider acceptance.
const scriptUrl = process.env.CALIBURN_E2E_SCRIPT_URL;
test.skip(!scriptUrl, 'Set CALIBURN_E2E_SCRIPT_URL to the scripted backend (see the README).');

interface ScriptState {
  waiting: number;
  responses: number;
  counts: number;
}

async function createFile(request: APIRequestContext): Promise<string> {
  const response = await request.post('/api/job-files', {
    data: {
      command_id: randomUUID(),
      display_name: `合成顧問旅程 ${randomUUID()}`,
      employee_name: '合成顧問旅程員工',
    },
  });
  expect(response.status()).toBe(201);
  const value: unknown = await response.json();
  if (!isJobFile(value)) throw new Error('Invalid job file');
  return value.job_file_id;
}

async function jobTitle(request: APIRequestContext, fileId: string): Promise<string | null> {
  const response = await request.get(`/api/job-files/${fileId}/jd/profile`);
  expect(response.status()).toBe(200);
  const value: unknown = await response.json();
  if (!isJdProfileView(value)) throw new Error('Invalid JD profile');
  return value.profile.job_title;
}

async function scriptState(request: APIRequestContext): Promise<ScriptState> {
  const response = await request.get(`${scriptUrl}/__script/state`);
  expect(response.status()).toBe(200);
  return (await response.json()) as ScriptState;
}

async function untilHeld(request: APIRequestContext): Promise<void> {
  await expect.poll(async () => (await scriptState(request)).waiting).toBe(1);
}

async function release(request: APIRequestContext): Promise<void> {
  const response = await request.post(`${scriptUrl}/__script/release`, { data: {} });
  expect(await response.json()).toEqual({ released: true });
}

async function send(page: Page, text: string): Promise<void> {
  await page.getByRole('textbox', { name: '訪談內容' }).fill(text);
  await page.getByRole('button', { name: '送出訪談' }).click();
}

// Status chips repeat their words inside longer notices; match the chip label exactly.
function badge(page: Page, label: string) {
  return page.getByText(label, { exact: true });
}

function watchBrowserErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('pageerror', (error) => errors.push(error.message));
  return errors;
}

test('一輪訪談：顧問把職稱與主管寫進 JD，答覆與 JD 重開後相同，變更與 PDF 可讀', async ({
  page,
}) => {
  const errors = watchBrowserErrors(page);
  const fileId = await createFile(page.request);
  const started = (await scriptState(page.request)).responses;
  await page.goto(`/job-files/${fileId}`);
  await send(page, '職稱：前端工程師；主管：李主任');
  const answer = page.getByText(/已記下：前端工程師、李主任/);
  await expect(answer).toBeVisible();
  await expect(badge(page, '已完成並保存')).toBeVisible();
  const profile = page.getByRole('region', { name: 'JD 基本資料' });
  await expect(profile.getByText('前端工程師')).toBeVisible();
  await expect(profile.getByText('李主任')).toBeVisible();

  // Reconnecting reads the same saved answer and the same formal JD.
  await page.reload();
  await expect(page.getByText(/已記下：前端工程師、李主任/)).toBeVisible();
  await expect(page.getByRole('region', { name: 'JD 基本資料' }).getByText('李主任')).toBeVisible();
  // One tool step and one answer: reconnecting never asks the model again.
  expect((await scriptState(page.request)).responses - started).toBe(2);

  // Looking back at this answer offers its public messages and its own JD change view.
  await page.getByRole('button', { name: '回看本次公開處理訊息／JD 操作' }).click();
  // The latest Turn's public messages also stay in the composer, so the text appears twice.
  await expect(page.getByText('我先把你剛說的基本資料記到 JD。').first()).toBeVisible();
  await page.getByRole('button', { name: '查看這輪 JD 變更' }).click();
  const changes = page.getByRole('dialog', { name: '這輪 JD 變更' });
  await expect(changes.getByText(/前端工程師/)).toBeVisible();
  await expect(changes.getByText(/李主任/)).toBeVisible();
  await changes.getByRole('button', { name: '關閉' }).click();

  // The formal version downloads through the page's own export link as a real PDF.
  const downloading = page.waitForEvent('download');
  await page.getByRole('link', { name: '匯出目前 JD（PDF）' }).click();
  const download = await downloading;
  expect(download.suggestedFilename()).toMatch(/\.pdf$/);
  const stream = await download.createReadStream();
  const head = await new Promise<string>((resolve, reject) => {
    const chunks: Buffer[] = [];
    stream.on('data', (chunk: Buffer) => chunks.push(chunk));
    stream.on('end', () => resolve(Buffer.concat(chunks).subarray(0, 5).toString('latin1')));
    stream.on('error', reject);
  });
  expect(head).toBe('%PDF-');
  // Only public messages reach the page: no private reasoning payload, no raw tool call.
  const visible = (await page.locator('body').innerText()) + (await page.content());
  expect(visible).not.toContain('synthetic-opaque');
  expect(visible).not.toContain('revise_jd_profile');
  expect(errors).toEqual([]);
});

test('處理中：即時公開訊息、JD 唯讀、重開與另一分頁找回同一處理，暫停停妥後續作，不重送輸入', async ({
  page,
  context,
}) => {
  const errors = watchBrowserErrors(page);
  const fileId = await createFile(page.request);
  await page.goto(`/job-files/${fileId}`);
  await send(page, '請稍候 [[hold]]');
  await untilHeld(page.request);
  await expect(badge(page, '顧問處理中')).toBeVisible();
  await expect(page.getByText('我需要一點時間整理，請稍候。')).toBeVisible();
  await expect(page.getByText('顧問處理中，JD 暫時唯讀；完成或取消後才能人工修改。')).toBeVisible();
  await expect(page.getByRole('button', { name: '編輯基本資料' })).toHaveCount(0);
  const sent = (await scriptState(page.request)).responses;

  // Reload and a second tab both rediscover the same processing Turn and send nothing.
  await page.reload();
  await expect(badge(page, '顧問處理中')).toBeVisible();
  const other = await context.newPage();
  await other.goto(`/job-files/${fileId}`);
  await expect(badge(other, '顧問處理中')).toBeVisible();
  await expect(other.getByRole('button', { name: '編輯基本資料' })).toHaveCount(0);
  await other.close();
  expect((await scriptState(page.request)).responses).toBe(sent);

  // A pause is only requested until the Turn reaches a safe point.
  await page.getByRole('button', { name: '暫停處理' }).click();
  await expect(badge(page, '等待安全點暫停')).toBeVisible();
  await release(page.request);
  await expect(badge(page, '已暫停')).toBeVisible();
  await expect(
    page.getByText('這輪處理已暫停，JD 仍為唯讀；繼續完成或取消後才能人工修改。'),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: '編輯基本資料' })).toHaveCount(0);

  // Resuming completes the same answer without another model request.
  await page.getByRole('button', { name: '繼續處理' }).click();
  await expect(badge(page, '已完成並保存')).toBeVisible();
  await expect(page.getByText(/可以說說你最近一次實際做的工作/)).toBeVisible();
  await expect(page.getByRole('button', { name: '編輯基本資料' })).toBeVisible();
  expect((await scriptState(page.request)).responses).toBe(sent);
  expect(errors).toEqual([]);
});

test('處理中取消：候選改動被丟棄，原輸入不列入正式訪談且可取回，正式 JD 不變', async ({ page }) => {
  const errors = watchBrowserErrors(page);
  const fileId = await createFile(page.request);
  await page.goto(`/job-files/${fileId}`);
  await send(page, '職稱：不該保存的職稱 [[hold]]');
  await untilHeld(page.request);

  // The consultant's edit exists only as a candidate; the formal JD and PDF stay formal.
  await expect(page.getByText('JD 候選預覽')).toBeVisible();
  await expect(page.getByText('不該保存的職稱')).toBeVisible();
  expect(await jobTitle(page.request, fileId)).toBeNull();
  expect((await page.request.get(`/api/job-files/${fileId}/jd/export.pdf`)).status()).toBe(200);

  await page.getByRole('button', { name: '取消處理' }).click();
  await release(page.request);
  await expect(badge(page, '已取消')).toBeVisible();
  await expect(page.getByText('這次處理已取消，原輸入未列入正式訪談。')).toBeVisible();
  await expect(page.getByText('不該保存的職稱')).toBeHidden();
  expect(await jobTitle(page.request, fileId)).toBeNull();

  // The unformalized input can be taken back for editing; nothing was consumed.
  await page.getByRole('button', { name: '取回原文編輯' }).click();
  await expect(page.getByRole('textbox', { name: '訪談內容' })).toHaveValue(
    '職稱：不該保存的職稱 [[hold]]',
  );
  expect(errors).toEqual([]);
});

test('模型拒絕這次輸入：處理未完成、原輸入未列入正式訪談，之後可主動送出新輸入', async ({
  page,
}) => {
  const fileId = await createFile(page.request);
  await page.goto(`/job-files/${fileId}`);
  await send(page, '這句會被拒絕 [[reject]]');
  await expect(badge(page, '未完成')).toBeVisible();
  await expect(
    page.getByText('這次處理未能完成，原輸入未列入正式訪談。請確認服務狀態後再主動送出。'),
  ).toBeVisible();
  const formal = await page.request.get(`/api/job-files/${fileId}/interviews`);
  expect(formal.status()).toBe(200);

  await page.getByRole('button', { name: '開始下一次訪談' }).click();
  await send(page, '單位：產品團隊');
  await expect(badge(page, '已完成並保存')).toBeVisible();
  await expect(
    page.getByRole('region', { name: 'JD 基本資料' }).getByText('產品團隊'),
  ).toBeVisible();
});
