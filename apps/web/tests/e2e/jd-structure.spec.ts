import { expect, test } from '@playwright/test';
import type { APIRequestContext, Page } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { isJdWorkView, isJobFile } from '../../src/shared/api/validation';
import type { JdWorkView } from '../../src/shared/api/generated/jd-work-view';

async function createFile(request: APIRequestContext): Promise<string> {
  const response = await request.post('/api/job-files', {
    data: {
      command_id: randomUUID(),
      display_name: `合成結構操作 ${randomUUID()}`,
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
  const field = page.getByRole('textbox', { name: '職責名稱' });
  await field.fill(name);
  await field.press('Enter');
  await expect(field).toHaveCount(0);
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
}
async function createTask(page: Page, area: string, name: string): Promise<void> {
  await page
    .getByRole('region', { name: area, exact: true })
    .getByRole('button', { name: '新增任務', exact: true })
    .click();
  await page.getByRole('textbox', { name: '任務名稱' }).fill(name);
  await page.getByRole('button', { name: '新增工作成果' }).click();
  await page.getByRole('textbox', { name: '工作成果 1' }).fill('可操作頁面');
  await page.getByRole('button', { name: '新增工作要求' }).click();
  await page.getByRole('textbox', { name: '工作要求 1' }).fill('核對主要流程');
  await page.getByRole('button', { name: '儲存任務' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('article', { name, exact: true })).toBeVisible();
}

test('沒有整項編輯鈕：搬移、新增、刪除各是一個直接的動作，每個只送一筆命令', async ({ page }) => {
  const browserErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(message.text());
  });
  page.on('pageerror', (error) => browserErrors.push(error.message));
  const fileId = await createFile(page.request);
  const writes: string[] = [];
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().includes(`/api/job-files/${fileId}/jd/`))
      writes.push(request.url());
  });
  await page.goto(`/job-files/${fileId}`);
  await createArea(page, '網站交付');
  await createArea(page, '網站維護');
  await createTask(page, '網站交付', '實作網頁');
  await page.getByRole('button', { name: '新增條件', exact: true }).click();
  await page.getByRole('combobox', { name: '條件分類' }).click();
  await page.getByRole('option', { name: '工時與出差', exact: true }).click();
  await page.getByRole('textbox', { name: '條件內容' }).fill('依約支援上線。');
  await page.getByRole('button', { name: '儲存條件' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  writes.length = 0;

  // The pencil is gone from every kind of item; the profile form is a separate editor and keeps its own.
  await expect(
    page.getByRole('button', { name: /^編輯(職責|任務|知識|技能|協作對象|條件)$/ }),
  ).toHaveCount(0);

  // Move: one menu, the current place checked; choosing another sends one move_task.
  const task = page.getByRole('article', { name: '實作網頁', exact: true });
  await task.getByRole('button', { name: '移到其他職責' }).click();
  await expect(page.getByRole('menuitemradio', { name: '網站交付' })).toBeChecked();
  await page.getByRole('menuitemradio', { name: '網站維護' }).click();
  await expect(
    page
      .getByRole('region', { name: '網站維護', exact: true })
      .getByRole('article', { name: '實作網頁' }),
  ).toBeVisible();
  expect(writes).toHaveLength(1);
  const [siteArea, upkeepArea] = (await readWork(page.request, fileId)).areas;
  expect((await readWork(page.request, fileId)).tasks[0]?.area_id).toBe(upkeepArea?.area_id);
  expect(siteArea?.title).toBe('網站交付');

  // Add: the "+" beside the label opens an empty editor at the end of that list.
  await task.getByRole('button', { name: '新增工作成果' }).click();
  const added = page.getByRole('textbox', { name: '工作成果 2' });
  await expect(added).toBeFocused();
  await added.fill('交接說明');
  await added.press('Control+Enter');
  await expect(added).toHaveCount(0);
  await expect(task.getByText('交接說明', { exact: true })).toBeVisible();
  expect(writes).toHaveLength(2);
  expect(
    (await readWork(page.request, fileId)).tasks[0]?.outcomes.map((item) => item.text),
  ).toEqual(['可操作頁面', '交接說明']);

  // Remove: a confirmation first, as for every delete; then one remove_detail.
  await task.getByRole('button', { name: '刪除工作要求 1' }).click();
  await expect(page.getByRole('dialog')).toContainText('核對主要流程');
  expect(writes).toHaveLength(2);
  await page.getByRole('button', { name: '確認刪除工作要求' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(task.getByText('核對主要流程')).toHaveCount(0);
  expect(writes).toHaveLength(3);
  expect((await readWork(page.request, fileId)).tasks[0]?.requirements).toEqual([]);

  // Reclassify a condition from the same kind of menu: its identity stays, only the category changes.
  const before = (await readWork(page.request, fileId)).conditions[0];
  await page
    .getByRole('article', { name: '工時與出差 1' })
    .getByRole('button', { name: '移到其他分類' })
    .click();
  await page.getByRole('menuitemradio', { name: '必要資格' }).click();
  await expect(page.getByRole('article', { name: '必要資格 1' })).toContainText('依約支援上線。');
  expect(writes).toHaveLength(4);
  const after = (await readWork(page.request, fileId)).conditions[0];
  expect(after).toMatchObject({ condition_id: before?.condition_id, kind: 'qualification' });
  expect(browserErrors).toEqual([]);
});

test('指標沒有 hover 的裝置會看到一行「點任何文字即可直接修改」，滑鼠則不顯示', async ({
  browser,
}) => {
  const hint = '點任何文字即可直接修改。';
  const desktop = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await desktop.goto('/');
  const fileId = await createFile(desktop.request);
  await desktop.goto(`/job-files/${fileId}`);
  await expect(desktop.getByText(hint)).toBeHidden();
  await desktop.close();

  const touch = await browser.newContext({
    viewport: { width: 390, height: 844 },
    hasTouch: true,
    isMobile: true,
  });
  const phone = await touch.newPage();
  await phone.goto(`/job-files/${fileId}`);
  await phone.getByRole('tab', { name: 'JD' }).click();
  await expect(phone.getByText(hint)).toBeVisible();
  await touch.close();
});
