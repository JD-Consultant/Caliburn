import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { isCreateJobFileRequest, isJobFileList } from '../../src/shared/api/validation';

async function createFile(page: Page, displayName: string, employeeName: string): Promise<string> {
  await page.getByRole('button', { name: '建立職務檔案' }).click();
  await page.getByRole('textbox', { name: '職務檔案名稱' }).fill(displayName);
  await page.getByRole('textbox', { name: '受訪員工姓名' }).fill(employeeName);
  await page.getByRole('button', { name: '建立', exact: true }).click();
  await expect(page.getByRole('heading', { name: displayName })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'App 開場引導 · 訪談序號 1' })).toBeVisible();
  return page.url();
}

test('建立同名獨立檔案，重新整理、鍵盤與窄螢幕仍可回讀', async ({ page }, testInfo) => {
  const displayName = `合成前端職務 ${randomUUID()}`;
  await page.goto('/');
  const create = page.getByRole('button', { name: '建立職務檔案' });
  await create.click();
  await expect(page.getByRole('textbox', { name: '職務檔案名稱' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(create).toBeFocused();
  const firstUrl = await createFile(page, displayName, '合成員工甲');
  const opening = await page.locator('.interview-text').textContent();
  await page.reload();
  await expect(page.locator('.interview-text')).toHaveText(opening ?? '');
  await page.getByRole('link', { name: /職務檔案清單/ }).click();
  const secondUrl = await createFile(page, displayName, '合成員工乙');
  expect(secondUrl).not.toBe(firstUrl);
  await expect(page.getByText('受訪員工：合成員工乙')).toBeVisible();
  await page.getByRole('link', { name: /職務檔案清單/ }).click();
  const firstLink = page.getByRole('link', { name: new RegExp(`開啟 ${displayName}.*合成員工甲`) });
  const secondLink = page.getByRole('link', {
    name: new RegExp(`開啟 ${displayName}.*合成員工乙`),
  });
  await expect(firstLink).toBeVisible();
  await expect(secondLink).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('job-files-desktop.png'), fullPage: true });
  await firstLink.click();
  await expect(page.getByText('受訪員工：合成員工甲')).toBeVisible();
  await expect(page.getByText('受訪員工：合成員工乙')).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('heading', { name: displayName })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.screenshot({ path: testInfo.outputPath('job-file-mobile.png'), fullPage: true });
});

test('POST 已提交但回應遺失，重新整理後以原命令取得同一檔案', async ({ page }) => {
  const displayName = `合成回應遺失 ${randomUUID()}`;
  const commands: string[] = [];
  await page.route('**/api/job-files', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }
    const body: unknown = route.request().postDataJSON();
    if (!isCreateJobFileRequest(body)) throw new Error('Invalid creation payload');
    commands.push(body.command_id);
    const response = await route.fetch();
    if (commands.length === 1) {
      expect(response.status()).toBe(201);
      await route.abort('failed');
    } else {
      expect(response.status()).toBe(200);
      await route.fulfill({ response });
    }
  });
  await page.goto('/');
  await page.getByRole('button', { name: '建立職務檔案' }).click();
  await page.getByRole('textbox', { name: '職務檔案名稱' }).fill(displayName);
  await page.getByRole('textbox', { name: '受訪員工姓名' }).fill('合成回復員工');
  await page.getByRole('button', { name: '建立', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('建立結果尚未確認');
  await page.reload();
  await page.getByRole('button', { name: '建立職務檔案' }).click();
  await expect(page.getByRole('textbox', { name: '職務檔案名稱' })).toBeDisabled();
  await expect(page.getByRole('textbox', { name: '職務檔案名稱' })).toHaveValue(displayName);
  await page.getByRole('button', { name: '重新確認建立結果' }).click();
  await expect(page.getByRole('heading', { name: displayName })).toBeVisible();
  expect(commands).toHaveLength(2);
  expect(commands[1]).toBe(commands[0]);
  const list: unknown = await (await page.request.get('/api/job-files')).json();
  if (!isJobFileList(list)) throw new Error('Invalid job-file list');
  expect(list.job_files.filter((file) => file.display_name === displayName)).toHaveLength(1);
});

test('服務離線有明確重讀入口，不偽裝成空清單', async ({ page }) => {
  const displayName = `合成離線恢復 ${randomUUID()}`;
  const created = await page.request.post('/api/job-files', {
    data: { command_id: randomUUID(), display_name: displayName, employee_name: '合成員工' },
  });
  expect(created.status()).toBe(201);
  await page.route('**/api/job-files', (route) => route.abort('failed'));
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('連線未完成');
  await expect(page.getByText('尚無職務檔案')).toHaveCount(0);
  await page.unroute('**/api/job-files');
  await page.getByRole('button', { name: '重新讀取' }).click();
  await expect(page.getByRole('link', { name: new RegExp(`開啟 ${displayName}`) })).toBeVisible();
});
