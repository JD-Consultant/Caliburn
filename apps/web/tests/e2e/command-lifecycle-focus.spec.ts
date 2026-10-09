import { expect, test } from '@playwright/test';
import type { APIRequestContext } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import {
  isJdProfileView,
  isJobFile,
  isReviseJdProfileRequest,
} from '../../src/shared/api/validation';

async function createFile(request: APIRequestContext): Promise<string> {
  const response = await request.post('/api/job-files', {
    data: {
      command_id: randomUUID(),
      display_name: `合成生命週期驗收 ${randomUUID()}`,
      employee_name: '合成驗收員工',
    },
  });
  expect(response.status()).toBe(201);
  const value: unknown = await response.json();
  if (!isJobFile(value)) throw new Error('Invalid job file');
  return value.job_file_id;
}

function delayedResponse() {
  let release: () => void = () => {};
  let committed: () => void = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const ready = new Promise<void>((resolve) => {
    committed = resolve;
  });
  return { gate, ready, release, committed };
}

test('建立已提交但 ACK 遺失，之後 HTML 422 仍保留原命令直到查回成功', async ({ page }) => {
  const commands: string[] = [];
  let jobFileId = '';
  await page.route('**/api/job-files', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    const command = route.request().postData();
    if (command === null) throw new Error('Missing creation payload');
    commands.push(command);
    if (commands.length === 2) {
      await route.fulfill({
        status: 422,
        contentType: 'text/html',
        body: '<html>synthetic proxy rejection</html>',
      });
      return;
    }
    const response = await route.fetch();
    expect(response.status()).toBe(commands.length === 1 ? 201 : 200);
    const value: unknown = await response.json();
    if (!isJobFile(value)) throw new Error('Invalid job file');
    jobFileId = value.job_file_id;
    if (commands.length === 1) await route.abort('connectionreset');
    else await route.fulfill({ response });
  });
  await page.goto('/');
  await page.getByRole('button', { name: '建立職務檔案', exact: true }).click();
  await page.getByRole('textbox', { name: '職務檔案名稱' }).fill('合成未知原結果');
  await page.getByRole('textbox', { name: '受訪員工姓名' }).fill('合成員工');
  await page.getByRole('button', { name: '建立', exact: true }).click();
  const retry = page.getByRole('button', { name: '重新確認建立結果' });
  await expect(retry).toBeEnabled();
  const original = await page.evaluate(() =>
    sessionStorage.getItem('caliburn.pending-job-file-creation'),
  );
  expect(original).not.toBeNull();
  const rejection = page.waitForResponse(
    (response) => response.url().endsWith('/api/job-files') && response.status() === 422,
  );
  await retry.click();
  await rejection;
  await expect(retry).toBeEnabled();
  expect(
    await page.evaluate(() => sessionStorage.getItem('caliburn.pending-job-file-creation')),
  ).toBe(original);
  await expect(page.getByRole('textbox', { name: '職務檔案名稱' })).toBeDisabled();
  await retry.click();
  await expect(page).toHaveURL(new RegExp(`/job-files/${jobFileId}$`));
  expect(commands).toHaveLength(3);
  expect(new Set(commands).size).toBe(1);
  expect(
    await page.evaluate(() => sessionStorage.getItem('caliburn.pending-job-file-creation')),
  ).toBeNull();
});

test('同一建立命令的兩個真 API 成功依序送回，當前表單明示成功並收束', async ({ page }) => {
  const originalFile = await createFile(page.request);
  await page.goto(`/job-files/${originalFile}`);
  await page.getByRole('link', { name: '回到職務檔案清單' }).click();
  const responses = [delayedResponse(), delayedResponse()];
  const commands: string[] = [];
  await page.route('**/api/job-files', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    const requestIndex = commands.length;
    const stage = responses[requestIndex];
    const command = route.request().postData();
    if (!stage || command === null) throw new Error('Unexpected creation request');
    commands.push(command);
    const response = await route.fetch();
    expect(response.status()).toBe(requestIndex === 0 ? 201 : 200);
    stage.committed();
    await stage.gate;
    await route.fulfill({ response });
  });
  const [first, second] = responses;
  if (!first || !second) throw new Error('Missing response gates');
  try {
    await page.getByRole('button', { name: '建立職務檔案', exact: true }).click();
    await page.getByRole('textbox', { name: '職務檔案名稱' }).fill('合成同命令恢復');
    await page.getByRole('textbox', { name: '受訪員工姓名' }).fill('合成同命令員工');
    await page.getByRole('button', { name: '建立', exact: true }).click();
    await first.ready;
    await page.goBack();
    await expect(page).toHaveURL(new RegExp(`/job-files/${originalFile}$`));
    await page.getByRole('link', { name: '回到職務檔案清單' }).click();
    await page.getByRole('button', { name: '建立職務檔案', exact: true }).click();
    await page.getByRole('button', { name: '重新確認建立結果' }).click();
    await second.ready;
    expect(commands).toHaveLength(2);
    expect(commands[1]).toBe(commands[0]);
    first.release();
    await expect
      .poll(() => page.evaluate(() => sessionStorage.getItem('caliburn.pending-job-file-creation')))
      .toBeNull();
    await expect(page).toHaveURL(/\/$/);
    second.release();
    await expect(page.getByRole('alert')).toHaveText(
      '本次建立已成功，但本分頁待確認紀錄已變更。請返回清單核對目前狀態。',
    );
    await expect(page.getByRole('button', { name: '建立已成功' })).toBeDisabled();
    await expect(page.getByRole('button', { name: '重新確認建立結果' })).toHaveCount(0);
    await expect(page).toHaveURL(/\/$/);
    await page.getByRole('button', { name: '返回清單' }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    expect(commands).toHaveLength(2);
  } finally {
    first.release();
    second.release();
  }
});

test('瀏覽器 Back 離開建立表單後，真 API 的晚到成功不把畫面拉回新檔案', async ({ page }) => {
  const originalFile = await createFile(page.request);
  await page.goto(`/job-files/${originalFile}`);
  await page.getByRole('link', { name: '職務檔案清單' }).click();
  await expect(page).toHaveURL(/\/$/);
  await page.getByRole('button', { name: '建立職務檔案', exact: true }).click();
  await page.getByRole('textbox', { name: '職務檔案名稱' }).fill('合成晚到建立');
  await page.getByRole('textbox', { name: '受訪員工姓名' }).fill('合成晚到員工');
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  let acknowledge: () => void = () => {};
  const backendCommitted = new Promise<void>((resolve) => {
    acknowledge = resolve;
  });
  await page.route('**/api/job-files', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    // Persist through the real API, then delay only delivery of its successful response.
    const response = await route.fetch();
    expect(response.status()).toBe(201);
    acknowledge();
    await gate;
    await route.fulfill({ response });
  });
  await page.getByRole('button', { name: '建立', exact: true }).click();
  await backendCommitted;
  try {
    await page.goBack();
    await expect(page).toHaveURL(new RegExp(`/job-files/${originalFile}$`));
  } finally {
    release();
  }
  // The original ACK is processed, but no abandoned page callback may navigate.
  await expect
    .poll(() => page.evaluate(() => sessionStorage.getItem('caliburn.pending-job-file-creation')))
    .toBeNull();
  await expect(page).toHaveURL(new RegExp(`/job-files/${originalFile}$`));
  await expect(page.getByRole('heading', { name: '職務說明書（JD）' })).toBeVisible();
});

test('JD 的真 API 晚到成功保留後來的命令，且不關閉仍掛載的編輯器', async ({ page }) => {
  const fileId = await createFile(page.request);
  const endpoint = `/api/job-files/${fileId}/jd/profile`;
  const key = `caliburn.pending-jd-profile.${fileId}`;
  const response = delayedResponse();
  let posts = 0;
  await page.route(`**${endpoint}`, async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    posts += 1;
    const committed = await route.fetch();
    expect(committed.status()).toBe(200);
    response.committed();
    await response.gate;
    await route.fulfill({ response: committed });
  });
  try {
    await page.goto(`/job-files/${fileId}`);
    const editor = page.getByRole('region', { name: 'JD 基本資料' });
    const editTitle = editor.getByRole('button', { name: '修改職務名稱' });
    await expect(editTitle).toHaveAttribute('aria-disabled', 'false');
    await editTitle.focus();
    await page.keyboard.press('Enter');
    const field = editor.getByRole('textbox', { name: '職務名稱' });
    await field.fill('合成原命令的職務');
    await field.press('Enter');
    await response.ready;
    const raw = await page.evaluate((storageKey) => sessionStorage.getItem(storageKey), key);
    const original: unknown = JSON.parse(raw ?? 'null');
    if (!isReviseJdProfileRequest(original)) throw new Error('Missing original JD command');
    const next = { ...original, command_id: randomUUID() };
    await page.evaluate(
      ({ storageKey, command }) => {
        sessionStorage.setItem(storageKey, JSON.stringify(command));
      },
      { storageKey: key, command: next },
    );
    response.release();
    await expect(editor.getByRole('alert')).toContainText('修改已保存，但本分頁待確認紀錄已變更');
    await expect(field).toHaveValue('合成原命令的職務');
    await expect(editor.getByRole('button', { name: '重新確認修改結果' })).toBeDisabled();
    await expect(editor.getByRole('button', { name: '讀取目前 JD' })).toBeVisible();
    expect(await page.evaluate((storageKey) => sessionStorage.getItem(storageKey), key)).toBe(
      JSON.stringify(next),
    );
    const saved: unknown = await (await page.request.get(endpoint)).json();
    if (!isJdProfileView(saved)) throw new Error('Invalid saved profile');
    expect(saved.profile.job_title).toBe('合成原命令的職務');
    expect(posts).toBe(1);
  } finally {
    response.release();
  }
});

test('來源面板可用鍵盤開啟關閉，焦點回到 disclosure／原徽章，失效徽章有 fallback', async ({
  page,
}) => {
  const fileId = await createFile(page.request);
  const profileResponse = await page.request.get(`/api/job-files/${fileId}/jd/profile`);
  expect(profileResponse.status()).toBe(200);
  const profile: unknown = await profileResponse.json();
  if (!isJdProfileView(profile)) throw new Error('Invalid JD profile');
  const citationId = randomUUID();
  const reference = {
    citation_id: citationId,
    target: { kind: 'profile_field', field: 'job_title', item_id: null, task_id: null },
    target_label: '職務名稱',
    source_kind: 'interview',
    source_label: '合成鍵盤來源',
    needs_recheck: false,
    jd_changed: false,
    source_changed: false,
  };
  await page.route(`**/api/job-files/${fileId}/jd/sources`, (route) =>
    route.fulfill({
      json: { revision_id: profile.revision_id, references: [reference] },
    }),
  );
  await page.route(`**/api/job-files/${fileId}/jd/sources/${citationId}?*`, (route) =>
    route.fulfill({
      json: {
        revision_id: profile.revision_id,
        citation_id: citationId,
        content: {
          kind: 'interview',
          interview_sequence: 1,
          speaker: 'employee',
          interview_text: '合成鍵盤回查原話',
        },
      },
    }),
  );
  await page.goto(`/job-files/${fileId}`);
  const disclosure = page.getByRole('button', { name: '正式 JD 來源（唯讀）' });
  const close = page.getByRole('button', { name: '關閉來源面板' });
  await disclosure.focus();
  await page.keyboard.press('Enter');
  await expect(close).toBeVisible();
  await close.focus();
  await page.keyboard.press('Enter');
  await expect(disclosure).toBeFocused();
  await expect(disclosure).toHaveAttribute('aria-expanded', 'false');

  const badge = page.getByRole('button', { name: '來源 1 筆', exact: true });
  await badge.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByText('合成鍵盤回查原話')).toBeVisible();
  await close.focus();
  await page.keyboard.press('Enter');
  await expect(badge).toBeFocused();

  await page.keyboard.press('Enter');
  await expect(page.getByText('合成鍵盤回查原話')).toBeVisible();
  // The formal profile supports in-place editing while this non-modal sheet is open.
  // Opening that field removes its badge, so the original trigger is no longer available.
  const editTitle = page.getByRole('button', { name: '修改職務名稱', exact: true });
  await expect(editTitle).toHaveAttribute('aria-disabled', 'false');
  await editTitle.focus();
  await page.keyboard.press('Enter');
  await expect(badge).toHaveCount(0);
  await close.focus();
  await page.keyboard.press('Enter');
  await expect(disclosure).toBeFocused();
});
