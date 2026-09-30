import { expect, test } from '@playwright/test';
import type { APIRequestContext, Page } from '@playwright/test';
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

  // Collapse hides the tasks but keeps a count; expanding restores them without a reload.
  await page.getByRole('button', { name: '收合職責 網站交付' }).click();
  await expect(page.getByRole('article', { name: '實作頁面', exact: true })).toBeHidden();
  await expect(page.getByText('6 項任務')).toBeVisible();
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
