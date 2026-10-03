import { expect, test } from '@playwright/test';
import type { APIRequestContext, Locator, Page } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { isJobFile } from '../../src/shared/api/validation';

async function createFile(request: APIRequestContext): Promise<string> {
  const response = await request.post('/api/job-files', {
    data: {
      command_id: randomUUID(),
      display_name: `合成工作畫面 ${randomUUID()}`,
      employee_name: '合成工作員工',
    },
  });
  expect(response.status()).toBe(201);
  const value: unknown = await response.json();
  if (!isJobFile(value)) throw new Error('Invalid job file');
  return value.job_file_id;
}

async function createArea(page: Page, name: string): Promise<void> {
  await page.getByRole('button', { name: '新增職責', exact: true }).click();
  const field = page.getByRole('textbox', { name: '職責名稱' });
  await field.fill(name);
  await field.press('Enter');
  await expect(field).toHaveCount(0);
  const area = page.getByRole('region', { name, exact: true });
  await expect(area.getByRole('heading', { name, exact: true })).toBeVisible();
  await area.getByText('職責範圍尚未提供').click();
  const scope = page.getByRole('textbox', { name: '職責範圍' });
  await scope.fill('負責約定範圍的工作。');
  await scope.press('Control+Enter');
  await expect(scope).toHaveCount(0);
}

async function createTask(page: Page, area: string, name: string): Promise<void> {
  await page
    .getByRole('region', { name: area, exact: true })
    .getByRole('button', { name: '新增任務', exact: true })
    .click();
  await page.getByRole('textbox', { name: '任務名稱' }).fill(name);
  await page.getByRole('textbox', { name: '工作內容' }).fill('依已確認需求實作與交付。');
  await page.getByRole('button', { name: '儲存任務' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('article', { name, exact: true })).toBeVisible();
}

test('左右並排、整頁不捲動、輸入區常駐；章節導覽、職責收合與窄螢幕分頁可用', async ({
  page,
}, testInfo) => {
  const browserErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(message.text());
  });
  page.on('pageerror', (error) => browserErrors.push(error.message));
  const fileId = await createFile(page.request);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/job-files/${fileId}`);
  await createArea(page, '網站交付');
  for (const task of ['實作頁面', '串接介面', '修正缺陷', '交付驗收', '維護支援', '文件整理'])
    await createTask(page, '網站交付', task);

  // Side by side; only the panes scroll, never the page; the composer is always reachable.
  const interview = await page.getByRole('region', { name: '訪談區' }).boundingBox();
  const jd = await page.getByRole('region', { name: '職務說明書區' }).boundingBox();
  if (!interview || !jd) throw new Error('Missing panes');
  expect(interview.x).toBe(0);
  expect(jd.x).toBeGreaterThanOrEqual(interview.x + interview.width);
  expect(interview.width).toBeGreaterThanOrEqual(380);
  expect(interview.width).toBeLessThanOrEqual(520);
  const pageScrolls = await page.evaluate(
    () => document.documentElement.scrollHeight > window.innerHeight,
  );
  expect(pageScrolls).toBe(false);
  await expect(page.getByRole('textbox', { name: '訪談內容' })).toBeInViewport();

  // Outline: jump to a section and mark it as current.
  const outline = page.getByRole('navigation', { name: 'JD 章節導覽' });
  await outline.getByRole('button', { name: '協作對象' }).click();
  await expect(page.locator('#jd-collaborators')).toBeInViewport();
  await expect(outline.getByRole('button', { name: '協作對象' })).toHaveAttribute(
    'aria-current',
    'location',
  );
  await expect(page.getByRole('textbox', { name: '訪談內容' })).toBeInViewport();
  await page.screenshot({ path: testInfo.outputPath('workspace-desktop.png') });

  // Hierarchy: a responsibility reads as the parent of its tasks, with a larger title and its tasks
  // indented beneath it, so the two levels are told apart at a glance.
  const areaTitle = page.getByRole('heading', { name: '網站交付', exact: true });
  const taskTitle = page.getByRole('heading', { name: '實作頁面', exact: true });
  const areaBox = await areaTitle.boundingBox();
  const taskBox = await taskTitle.boundingBox();
  if (!areaBox || !taskBox) throw new Error('Missing responsibility or task title');
  expect(taskBox.x - areaBox.x).toBeGreaterThanOrEqual(24);
  const fontSize = (title: Locator) =>
    title.evaluate((element) => parseFloat(getComputedStyle(element).fontSize));
  expect(await fontSize(areaTitle)).toBeGreaterThan(await fontSize(taskTitle));

  // Only the item under the pointer shows its toolbar: pointing at a task must not also reveal its
  // responsibility's, or the two rows of icons read as one.
  const toolbarOpacity = (button: Locator) =>
    button.evaluate(
      (element) => getComputedStyle(element.closest('.item-actions') ?? element).opacity,
    );
  const areaTool = page.getByRole('button', { name: '刪除職責' });
  const taskTool = page
    .getByRole('article', { name: '實作頁面', exact: true })
    .getByRole('button', { name: '刪除任務' });
  await areaTitle.hover();
  await expect.poll(() => toolbarOpacity(areaTool)).toBe('1');
  await taskTitle.hover();
  await expect.poll(() => toolbarOpacity(taskTool)).toBe('1');
  await expect.poll(() => toolbarOpacity(areaTool)).toBe('0');

  // A task collapses to its title the same way, without touching the others.
  const description = '依已確認需求實作與交付。';
  const task = page.getByRole('article', { name: '實作頁面', exact: true });
  await task.getByRole('button', { name: '收合任務 實作頁面' }).click();
  await expect(task.getByText(description)).toBeHidden();
  await expect(
    page.getByRole('article', { name: '串接介面', exact: true }).getByText(description),
  ).toBeVisible();
  await task.getByRole('button', { name: '展開任務 實作頁面' }).click();
  await expect(task.getByText(description)).toBeVisible();

  // Collapse hides the tasks but keeps a count; expanding restores them without a reload.
  await page.getByRole('button', { name: '收合職責 網站交付' }).click();
  await expect(page.getByRole('article', { name: '實作頁面', exact: true })).toBeHidden();
  // Exact: the block's own count ("1 項職責・6 項任務") contains this one.
  await expect(page.getByText('6 項任務', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '展開職責 網站交付' }).click();
  await expect(page.getByRole('article', { name: '實作頁面', exact: true })).toBeVisible();

  // Narrow: one pane at a time, switching keeps the unsent draft.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('tab', { name: '訪談' }).click();
  await page.getByRole('textbox', { name: '訪談內容' }).fill('尚未送出的想法');
  await expect(page.getByRole('region', { name: '職務說明書區' })).toBeHidden();
  await page.getByRole('tab', { name: 'JD' }).click();
  await expect(page.getByRole('region', { name: '訪談區' })).toBeHidden();
  await expect(page.getByRole('heading', { name: 'JD 基本資料' })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('workspace-mobile.png') });
  await page.getByRole('tab', { name: '訪談' }).click();
  await expect(page.getByRole('textbox', { name: '訪談內容' })).toHaveValue('尚未送出的想法');
  expect(browserErrors).toEqual([]);
});

test('四個輔助區塊可以收合，章節導覽跳到收合的區塊時會先把它打開', async ({ page }) => {
  const fileId = await createFile(page.request);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/job-files/${fileId}`);
  for (const name of ['所需知識', '所需技能', '主要協作對象', '工作條件與責任邊界']) {
    const section = page.getByRole('region', { name, exact: true });
    await section.getByRole('button', { name: `收合${name}` }).click();
    await expect(section.getByRole('button', { name: `展開${name}` })).toHaveAttribute(
      'aria-expanded',
      'false',
    );
    // Folded to its heading and count: nothing inside it can be reached.
    await expect(section.getByRole('button', { name: /^新增/ })).toHaveCount(0);
  }

  await page
    .getByRole('navigation', { name: 'JD 章節導覽' })
    .getByRole('button', { name: '協作對象' })
    .click();
  const collaborators = page.getByRole('region', { name: '主要協作對象', exact: true });
  await expect(collaborators.getByRole('button', { name: '收合主要協作對象' })).toBeVisible();
  await expect(collaborators.getByRole('button', { name: '新增協作對象' })).toBeInViewport();
});

test('職責與任務整段可以收合（含未歸屬任務），未歸屬任務也能單獨收合，章節導覽會把整段打開', async ({
  page,
}) => {
  const fileId = await createFile(page.request);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/job-files/${fileId}`);
  await createArea(page, '網站交付');
  await createTask(page, '網站交付', '實作頁面');
  await createTask(page, '未歸屬任務', '整理雜務');

  const unassigned = page.getByRole('region', { name: '未歸屬任務', exact: true });
  await expect(unassigned.getByText('1 項任務')).toBeVisible();
  await unassigned.getByRole('button', { name: '收合未歸屬任務' }).click();
  await expect(unassigned.getByRole('heading', { name: '未歸屬任務' })).toBeVisible();
  await expect(unassigned.getByText('1 項任務')).toBeVisible();
  await expect(page.getByRole('article', { name: '整理雜務', exact: true })).toHaveCount(0);
  await expect(unassigned.getByRole('button', { name: '新增任務', exact: true })).toHaveCount(0);
  await expect(page.getByRole('article', { name: '實作頁面', exact: true })).toBeVisible();
  await unassigned.getByRole('button', { name: '展開未歸屬任務' }).click();
  await expect(page.getByRole('article', { name: '整理雜務', exact: true })).toBeVisible();

  // The whole block: the responsibilities, the unassigned tasks and the add row go; the sections below stay.
  await page.getByRole('button', { name: '收合職責與任務' }).click();
  await expect(page.getByText('1 項職責・2 項任務')).toBeVisible();
  await expect(page.getByRole('region', { name: '網站交付', exact: true })).toHaveCount(0);
  await expect(unassigned).toHaveCount(0);
  await expect(page.getByRole('button', { name: '新增職責', exact: true })).toHaveCount(0);
  await expect(page.getByRole('region', { name: '所需知識', exact: true })).toBeVisible();

  await page
    .getByRole('navigation', { name: 'JD 章節導覽' })
    .getByRole('button', { name: '職責與任務' })
    .click();
  await expect(page.getByRole('button', { name: '收合職責與任務' })).toHaveAttribute(
    'aria-expanded',
    'true',
  );
  await expect(page.getByRole('region', { name: '網站交付', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '新增職責', exact: true })).toBeVisible();
});
