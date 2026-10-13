/** Seeded immutable publications use the real HTTP reader; no Memory response is intercepted. */
import { expect, test } from '@playwright/test';

const seededFile = process.env.CALIBURN_E2E_MEMORY_FILE_ID;
test.skip(
  !seededFile,
  'Provide the file ID created by public_memory_browser_seed.py in the isolated test schema.',
);

test('Memory 導覽與正文沿固定發布版本，手機版可閱讀並以鍵盤關閉', async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/job-files/${seededFile}`);
  const open = page.getByRole('button', { name: 'Memory', exact: true });
  await open.click();
  const dialog = page.getByRole('dialog', { name: '目前已發布的 Memory' });
  await expect(dialog.getByText(/^涵蓋至第 /)).toBeVisible();
  await expect(dialog.getByRole('button', { name: '合成：每季盤點', exact: true })).toBeVisible();
  await expect(dialog.getByRole('button', { name: '合成：每月盤點', exact: true })).toHaveCount(0);
  const version = await dialog.getByText(/^版本：/).innerText();
  await dialog.getByRole('button', { name: '合成：每季盤點', exact: true }).click();
  await expect(dialog.getByText('每季核對實物，並追查差異。', { exact: true })).toBeVisible();
  await expect(dialog.getByText(version, { exact: true })).toBeVisible();
  await expect(dialog.getByRole('button', { name: '← 回到 Memory 導覽' })).toBeFocused();
  await page.screenshot({ path: testInfo.outputPath('published-memory-mobile.png') });
  await dialog.getByRole('button', { name: '← 回到 Memory 導覽' }).click();
  await expect(dialog.getByRole('button', { name: '重新讀取 Memory' })).toBeFocused();
  await dialog.getByRole('button', { name: '重新讀取 Memory' }).click();
  await expect(dialog.getByRole('button', { name: '重新讀取 Memory' })).toBeEnabled();
  await expect(dialog.getByRole('button', { name: '重新讀取 Memory' })).toBeFocused();
  await expect(dialog.getByText(version, { exact: true })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(open).toBeFocused();
  expect(errors).toEqual([]);
});

test('Memory 正文首次失敗後重讀，保留鍵盤焦點並可關閉', async ({ page }) => {
  let failed = false;
  await page.route('**/memory/*/objects/*', async (route) => {
    if (!failed) {
      failed = true;
      await route.fulfill({ status: 503, json: { detail: 'synthetic_read_failure' } });
    } else await route.continue();
  });
  await page.goto(`/job-files/${seededFile}`);
  await page.getByRole('button', { name: 'Memory', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '目前已發布的 Memory' });
  await dialog.getByRole('button', { name: '合成：每季盤點', exact: true }).click();
  await expect(dialog.getByRole('alert')).toBeVisible();
  const retry = dialog.getByRole('button', { name: '重新讀取正文' });
  await retry.click();
  await expect(dialog.getByText('每季核對實物，並追查差異。', { exact: true })).toBeVisible();
  await expect(retry).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
});
