import { expect, test } from '@playwright/test';
import type { APIRequestContext, Page } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { isEditJdTasksRequest, isJdWorkView, isJobFile } from '../../src/shared/api/validation';
import type { JdWorkView } from '../../src/shared/api/generated/jd-work-view';

async function createFile(request: APIRequestContext): Promise<string> {
  const response = await request.post('/api/job-files', {
    data: {
      command_id: randomUUID(),
      display_name: `合成就地編輯 ${randomUUID()}`,
      employee_name: '合成工作員工',
    },
  });
  expect(response.status()).toBe(201);
  const value: unknown = await response.json();
  if (!isJobFile(value)) throw new Error('Invalid job file');
  return value.job_file_id;
}
async function readWork(request: APIRequestContext, fileId: string): Promise<JdWorkView> {
  const response = await request.get(`/api/job-files/${fileId}/jd/work`);
  expect(response.status()).toBe(200);
  const value: unknown = await response.json();
  if (!isJdWorkView(value)) throw new Error('Invalid JD work');
  return value;
}
async function createTaskInArea(page: Page): Promise<void> {
  await page.getByRole('button', { name: '新增職責', exact: true }).click();
  const field = page.getByRole('textbox', { name: '職責名稱' });
  await field.fill('網站交付');
  await field.press('Enter');
  await expect(field).toHaveCount(0);
  await page
    .getByRole('region', { name: '網站交付', exact: true })
    .getByRole('button', { name: '新增任務', exact: true })
    .click();
  await page.getByRole('textbox', { name: '任務名稱' }).fill('實作網頁');
  await page.getByRole('textbox', { name: '工作內容' }).fill('依已確認需求實作與交付。');
  await page.getByRole('button', { name: '新增工作成果' }).click();
  await page.getByRole('textbox', { name: '工作成果 1' }).fill('可操作頁面');
  await page.getByRole('button', { name: '儲存任務' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('article', { name: '實作網頁', exact: true })).toBeVisible();
}

test('點文字就地改一欄：Enter／Ctrl+Enter 各送一筆單欄命令，其他控制項讓位，reload 後仍在', async ({
  page,
}) => {
  const browserErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(message.text());
  });
  page.on('pageerror', (error) => browserErrors.push(error.message));
  const fileId = await createFile(page.request);
  const taskWrites: unknown[] = [];
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith(`/api/job-files/${fileId}/jd/tasks`))
      taskWrites.push(request.postDataJSON());
  });
  await page.goto(`/job-files/${fileId}`);
  await createTaskInArea(page);
  taskWrites.length = 0;

  // Title: click the text, change it, Enter. No dialog; every other edit control waits meanwhile.
  const card = page.getByRole('article', { name: '實作網頁', exact: true });
  await card.getByRole('heading', { name: '實作網頁' }).click();
  const title = page.getByRole('textbox', { name: '任務名稱' });
  await expect(title).toBeFocused();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(card.getByRole('button', { name: '刪除任務' })).toBeDisabled();
  // Save then Cancel sit side by side at the end of the field. A rule meant for the fold head's chevron once
  // pulled them on top of each other, which no unit test can see.
  const save = await page.getByRole('button', { name: '儲存', exact: true }).boundingBox();
  const cancel = await page.getByRole('button', { name: '取消', exact: true }).boundingBox();
  expect(save && cancel && save.x + save.width <= cancel.x).toBe(true);
  await title.fill('實作網站頁面');
  await title.press('Enter');
  const renamed = page.getByRole('article', { name: '實作網站頁面', exact: true });
  await expect(renamed).toBeVisible();
  await expect(renamed.getByRole('button', { name: '刪除任務' })).toBeEnabled();
  expect(taskWrites).toHaveLength(1);

  // Esc abandons a draft without a request.
  await renamed.getByText('依已確認需求實作與交付。').click();
  await page.getByRole('textbox', { name: '工作內容' }).fill('不會送出的草稿');
  await page.keyboard.press('Escape');
  await expect(renamed.getByText('依已確認需求實作與交付。')).toBeVisible();
  expect(taskWrites).toHaveLength(1);

  // Multi-line text: Enter is a new line, Ctrl+Enter saves.
  await renamed.getByText('依已確認需求實作與交付。').click();
  const description = page.getByRole('textbox', { name: '工作內容' });
  await description.press('End');
  await description.pressSequentially('\n完成後交接。');
  expect(taskWrites).toHaveLength(1);
  await description.press('Control+Enter');
  await expect(page.getByRole('textbox', { name: '工作內容' })).toHaveCount(0);
  expect(taskWrites).toHaveLength(2);

  // A list item by keyboard alone: focus its edit button, Enter opens it, Ctrl+Enter saves, focus comes back.
  await renamed.getByRole('button', { name: '修改工作成果 1' }).focus();
  await page.keyboard.press('Enter');
  const outcome = page.getByRole('textbox', { name: '工作成果 1' });
  await expect(outcome).toBeFocused();
  await outcome.pressSequentially('（含驗收）');
  await outcome.press('Control+Enter');
  await expect(renamed.getByText('可操作頁面（含驗收）')).toBeVisible();
  await expect(renamed.getByRole('button', { name: '修改工作成果 1' })).toBeFocused();

  // Each save was one bounded change for that field, at the revision on screen.
  const writes = taskWrites.map((value) => {
    if (!isEditJdTasksRequest(value)) throw new Error('Invalid task command');
    return value.change;
  });
  expect(writes.map((change) => change.action)).toEqual([
    'revise_task',
    'revise_task',
    'revise_task',
  ]);
  const saved = await readWork(page.request, fileId);
  expect(saved.tasks[0]?.title).toBe('實作網站頁面');
  expect(saved.tasks[0]?.description).toBe('依已確認需求實作與交付。\n完成後交接。');
  expect(saved.tasks[0]?.outcomes[0]?.text).toBe('可操作頁面（含驗收）');

  await page.reload();
  await expect(page.getByRole('heading', { name: '實作網站頁面', exact: true })).toBeVisible();
  await expect(page.getByText('可操作頁面（含驗收）')).toBeVisible();
  expect(browserErrors).toEqual([]);
});

test('就地編輯後丟回應：草稿留在原處，重新確認重送原命令而不重複寫入', async ({ page }) => {
  const fileId = await createFile(page.request);
  const endpoint = `/api/job-files/${fileId}/jd/tasks`;
  await page.goto(`/job-files/${fileId}`);
  await createTaskInArea(page);

  const sent: string[] = [];
  await page.route(`**${endpoint}`, async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }
    sent.push(route.request().postData() ?? '');
    const response = await route.fetch();
    expect(response.status()).toBe(200);
    if (sent.length === 1) await route.abort('failed');
    else await route.fulfill({ response });
  });
  const card = page.getByRole('article', { name: '實作網頁', exact: true });
  await card.getByRole('heading', { name: '實作網頁' }).click();
  const title = page.getByRole('textbox', { name: '任務名稱' });
  await title.fill('丟回應後仍保存');
  await title.press('Enter');

  // The server saved it but the answer was lost: the draft stays, disabled, with the way forward beside it.
  await expect(page.getByRole('alert')).toContainText('JD 修改結果尚未確認');
  await expect(title).toBeDisabled();
  await expect(title).toHaveValue('丟回應後仍保存');
  await expect(page.getByRole('button', { name: '重新確認修改結果' })).toHaveCount(1);
  expect((await readWork(page.request, fileId)).tasks[0]?.title).toBe('丟回應後仍保存');

  await page.getByRole('button', { name: '重新確認修改結果' }).click();
  await expect(page.getByRole('textbox', { name: '任務名稱' })).toHaveCount(0);
  await expect(page.getByRole('article', { name: '丟回應後仍保存', exact: true })).toBeVisible();
  expect(sent).toHaveLength(2);
  expect(sent[1]).toBe(sent[0]);
  expect((await readWork(page.request, fileId)).tasks).toHaveLength(1);
});

test('窄螢幕：點文字就地編輯，儲存鈕在視窗內，整頁不橫向捲動', async ({ page }) => {
  const fileId = await createFile(page.request);
  await page.goto(`/job-files/${fileId}`);
  await createTaskInArea(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('tab', { name: 'JD' }).click();

  const card = page.getByRole('article', { name: '實作網頁', exact: true });
  await card.getByText('依已確認需求實作與交付。').click();
  const description = page.getByRole('textbox', { name: '工作內容' });
  await expect(description).toBeFocused();
  await expect(page.getByRole('button', { name: '儲存', exact: true })).toBeInViewport();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await description.fill('窄螢幕改過的內容');
  await page.getByRole('button', { name: '儲存', exact: true }).click();
  await expect(card.getByText('窄螢幕改過的內容')).toBeVisible();
  expect((await readWork(page.request, fileId)).tasks[0]?.description).toBe('窄螢幕改過的內容');
});

test('輸入法組字中的 Enter 只是選字，不會送出；組字結束後 Enter 才儲存', async ({ page }) => {
  const fileId = await createFile(page.request);
  const writes: string[] = [];
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith(`/api/job-files/${fileId}/jd/tasks`))
      writes.push(request.url());
  });
  await page.goto(`/job-files/${fileId}`);
  await createTaskInArea(page);
  writes.length = 0;

  await page
    .getByRole('article', { name: '實作網頁', exact: true })
    .getByRole('heading', { name: '實作網頁' })
    .click();
  const title = page.getByRole('textbox', { name: '任務名稱' });
  await title.press('End');

  // Zhuyin is being typed: the keyboard's Enter picks the candidate (the browser reports it as the IME's
  // "Process" key). The form must not treat it as Save; only the browser's own implicit submission decides.
  const ime = await page.context().newCDPSession(page);
  await ime.send('Input.imeSetComposition', { text: 'ㄇㄧ', selectionStart: 2, selectionEnd: 2 });
  await ime.send('Input.dispatchKeyEvent', {
    type: 'rawKeyDown',
    key: 'Process',
    code: 'Enter',
    windowsVirtualKeyCode: 229,
  });
  await ime.send('Input.dispatchKeyEvent', {
    type: 'keyUp',
    key: 'Enter',
    code: 'Enter',
    windowsVirtualKeyCode: 13,
  });
  await page.evaluate(
    () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))),
  );
  await expect(title).toBeVisible();
  expect(writes).toHaveLength(0);

  await ime.send('Input.imeSetComposition', { text: '', selectionStart: 0, selectionEnd: 0 });
  await title.pressSequentially('！');
  await title.press('Enter');
  await expect(page.getByRole('textbox', { name: '任務名稱' })).toHaveCount(0);
  expect(writes).toHaveLength(1);
});
