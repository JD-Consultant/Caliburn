import { expect, test } from '@playwright/test';
import type { APIRequestContext, Page } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { isEditJdTasksRequest, isJdWorkView, isJobFile } from '../../src/shared/api/validation';
import type { JdWorkView } from '../../src/shared/api/generated/jd-work-view';

async function createFile(request: APIRequestContext): Promise<string> {
  const response = await request.post('/api/job-files', {
    data: {
      command_id: randomUUID(),
      display_name: `合成職責任務 ${randomUUID()}`,
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
async function createArea(page: Page, name: string): Promise<void> {
  await page.getByRole('button', { name: '新增職責', exact: true }).click();
  await page.getByRole('textbox', { name: '職責名稱' }).fill(name);
  await page.getByRole('textbox', { name: '職責範圍' }).fill('負責約定範圍的工作。');
  await page.getByRole('button', { name: '儲存職責' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
}
async function createTask(page: Page, area: string, name: string): Promise<void> {
  await page
    .getByRole('region', { name: area, exact: true })
    .getByRole('button', { name: '新增任務', exact: true })
    .click();
  await page.getByRole('textbox', { name: '任務名稱' }).fill(name);
  await page.getByRole('textbox', { name: '工作內容' }).fill('依已確認需求實作與交付。');
  await page.getByRole('button', { name: '新增工作成果' }).click();
  await page.getByRole('textbox', { name: '工作成果 1' }).fill('可操作頁面');
  await page.getByRole('button', { name: '新增工作成果' }).click();
  await page.getByRole('textbox', { name: '工作成果 2' }).fill('交接說明');
  await page.getByRole('button', { name: '新增工作要求' }).click();
  await page.getByRole('textbox', { name: '工作要求 1' }).fill('核對主要流程');
  await page.getByRole('button', { name: '儲存任務' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('article', { name, exact: true })).toBeVisible();
}

test('職責任務 CRUD、排序、跨組移動及刪職責保留任務，reload 與窄螢幕可用', async ({
  page,
}, testInfo) => {
  const browserErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(message.text());
  });
  page.on('pageerror', (error) => browserErrors.push(error.message));
  const fileId = await createFile(page.request);
  await page.goto(`/job-files/${fileId}`);
  await createArea(page, '網站交付');
  await createArea(page, '網站維護');
  await page
    .getByRole('region', { name: '網站維護', exact: true })
    .getByRole('button', { name: '上移職責' })
    .click();
  await expect
    .poll(async () => (await readWork(page.request, fileId)).areas[0]?.title)
    .toBe('網站維護');
  await createTask(page, '網站交付', '實作網頁');
  await createTask(page, '網站交付', '交付檢查');
  const before = await readWork(page.request, fileId);
  const task = before.tasks.find((item) => item.title === '實作網頁');
  if (!task) throw new Error('Missing task');
  const card = page.getByRole('article', { name: '實作網頁', exact: true });
  await card.getByRole('button', { name: '下移任務' }).click();
  await expect
    .poll(async () => (await readWork(page.request, fileId)).tasks[1]?.task_id)
    .toBe(task.task_id);
  await card.getByRole('button', { name: '下移工作成果 1' }).click();
  await expect
    .poll(
      async () =>
        (await readWork(page.request, fileId)).tasks.find((item) => item.task_id === task.task_id)
          ?.outcomes[0]?.text,
    )
    .toBe('交接說明');
  await card.getByRole('button', { name: '編輯任務' }).click();
  await page.getByRole('combobox', { name: '所屬職責' }).click();
  await page.getByRole('option', { name: '網站維護' }).click();
  await page.getByRole('textbox', { name: '工作內容' }).fill('維護約定頁面並記錄限制。');
  await page.getByRole('textbox', { name: '工作成果 1' }).fill('完整交接說明');
  await page.getByRole('button', { name: '儲存任務' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  const maintenance = page.getByRole('region', { name: '網站維護', exact: true });
  await expect(maintenance.getByRole('article', { name: '實作網頁' })).toBeVisible();
  await maintenance.getByRole('button', { name: '編輯職責' }).click();
  await page.getByRole('textbox', { name: '職責名稱' }).fill('前端維護');
  await page.getByRole('button', { name: '儲存職責' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  const renamed = page.getByRole('region', { name: '前端維護', exact: true });
  await renamed.getByRole('button', { name: '刪除職責' }).click();
  await expect(page.getByRole('dialog')).toContainText('任務會保留');
  await page.getByRole('button', { name: '確認刪除職責' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  const unassigned = page.getByRole('region', { name: '未歸屬任務', exact: true });
  await expect(unassigned.getByRole('article', { name: '實作網頁' })).toBeVisible();
  await page.reload();
  await expect(unassigned.getByText('完整交接說明')).toBeVisible();
  const after = await readWork(page.request, fileId);
  const retained = after.tasks.find((item) => item.task_id === task.task_id);
  expect(retained?.area_id).toBeNull();
  expect(retained?.outcomes.map((detail) => detail.detail_id)).toEqual(
    [...task.outcomes].reverse().map((detail) => detail.detail_id),
  );
  expect(retained?.requirements).toEqual(task.requirements);
  await page.screenshot({
    path: testInfo.outputPath('jd-work-desktop.png'),
    fullPage: true,
    animations: 'disabled',
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await unassigned.getByRole('button', { name: '編輯任務' }).click();
  await expect(page.getByRole('textbox', { name: '任務名稱' })).toHaveValue('實作網頁');
  await expect(page.getByRole('combobox', { name: '所屬職責' })).toContainText('未歸屬任務');
  await expect(page.getByRole('textbox', { name: '任務名稱' })).toBeFocused();
  await expect(page.getByRole('button', { name: '儲存任務' })).toBeInViewport();
  await page.screenshot({
    path: testInfo.outputPath('jd-task-mobile.png'),
    animations: 'disabled',
  });
  await page.getByRole('button', { name: '移除工作要求 1' }).click();
  await page.getByRole('button', { name: '儲存任務' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect(
    (await readWork(page.request, fileId)).tasks.find((item) => item.task_id === task.task_id)
      ?.requirements,
  ).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await unassigned.getByRole('button', { name: '刪除任務' }).click();
  await page.getByRole('button', { name: '確認刪除任務' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(unassigned.getByRole('article')).toHaveCount(0);
  expect((await readWork(page.request, fileId)).tasks.map((item) => item.title)).toEqual([
    '交付檢查',
  ]);
  expect(browserErrors).toEqual([]);
});

test('集合修改後編輯 profile，再新增集合，兩個方向都刷新共用基底', async ({ page }) => {
  const fileId = await createFile(page.request);
  await page.goto(`/job-files/${fileId}`);
  await createArea(page, '前端交付');
  await page.getByRole('button', { name: '編輯基本資料' }).click();
  await page.getByRole('textbox', { name: '職務名稱' }).fill('前端工程師');
  await page.getByRole('button', { name: '儲存基本資料' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await createArea(page, '前端維護');
  await expect(page.getByText('前端工程師', { exact: true })).toBeVisible();
  expect((await readWork(page.request, fileId)).areas).toHaveLength(2);
});

test('任務真提交後丟回應，目標後來已刪除仍可確認原命令而不復活', async ({ page }) => {
  const fileId = await createFile(page.request);
  const endpoint = `/api/job-files/${fileId}/jd/tasks`;
  const sent: string[] = [];
  await page.route(`**${endpoint}`, async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }
    const value: unknown = route.request().postDataJSON();
    if (!isEditJdTasksRequest(value)) throw new Error('Invalid task command');
    sent.push(JSON.stringify(value));
    const response = await route.fetch();
    expect(response.status()).toBe(200);
    if (sent.length === 1) await route.abort('failed');
    else await route.fulfill({ response });
  });
  await page.goto(`/job-files/${fileId}`);
  await page.getByRole('button', { name: '新增任務', exact: true }).click();
  await page.getByRole('textbox', { name: '任務名稱' }).fill('先建立後刪除');
  await page.getByRole('button', { name: '儲存任務' }).click();
  await expect(page.getByText(/JD 修改結果尚未確認/)).toBeVisible();
  const saved = await readWork(page.request, fileId);
  const deleted = await page.request.post(endpoint, {
    data: {
      command_id: randomUUID(),
      expected_revision_id: saved.revision_id,
      change: { action: 'delete_task', task_id: saved.tasks[0]?.task_id },
    },
  });
  expect(deleted.status()).toBe(200);
  await page.reload();
  await page.getByRole('button', { name: '重新確認修改結果' }).click();
  await expect(page.getByRole('button', { name: '重新確認修改結果' })).toHaveCount(0);
  await expect(page.getByRole('article', { name: '先建立後刪除' })).toHaveCount(0);
  expect(sent).toHaveLength(2);
  expect(sent[1]).toBe(sent[0]);
  expect((await readWork(page.request, fileId)).tasks).toEqual([]);
});

test('職責表單不覆蓋其他提交，A 已准入也不能新增人工任務', async ({ page }) => {
  const fileId = await createFile(page.request);
  await page.goto(`/job-files/${fileId}`);
  await page.getByRole('button', { name: '新增職責', exact: true }).click();
  await page.getByRole('textbox', { name: '職責名稱' }).fill('過期新增');
  const before = await readWork(page.request, fileId);
  expect(
    (
      await page.request.post(`/api/job-files/${fileId}/jd/areas`, {
        data: {
          command_id: randomUUID(),
          expected_revision_id: before.revision_id,
          change: { action: 'create_area', title: '其他分頁職責', scope_text: null },
        },
      })
    ).status(),
  ).toBe(200);
  await page.getByRole('button', { name: '儲存職責' }).click();
  await expect(page.getByRole('dialog')).toContainText('修改未被接受');
  await page.getByRole('button', { name: '讀取目前 JD' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: '其他分頁職責' })).toBeVisible();
  expect(
    (
      await page.request.post(`/api/job-files/${fileId}/inputs`, {
        data: { command_id: randomUUID(), text: '合成進行中輸入' },
      })
    ).status(),
  ).toBe(202);
  await page
    .getByRole('region', { name: '未歸屬任務', exact: true })
    .getByRole('button', { name: '新增任務', exact: true })
    .click();
  await page.getByRole('textbox', { name: '任務名稱' }).fill('不得保存');
  await page.getByRole('button', { name: '儲存任務' }).click();
  await expect(page.getByRole('dialog')).toContainText('修改未被接受');
  expect((await readWork(page.request, fileId)).tasks).toEqual([]);
});
