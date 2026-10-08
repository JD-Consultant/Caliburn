import { expect, test } from '@playwright/test';
import type { APIRequestContext, Locator } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { isJdWorkView, isJobFile } from '../../src/shared/api/validation';

// Windows High Contrast ("forced colors") drops box-shadow and background tints. An edge, a selected
// state or a focus ring drawn only with them disappears, so the composer, the buttons, the current
// section and a focused field need a real border or outline there.

async function createFile(request: APIRequestContext): Promise<string> {
  const response = await request.post('/api/job-files', {
    data: {
      command_id: randomUUID(),
      display_name: `合成高對比 ${randomUUID()}`,
      employee_name: '合成高對比員工',
    },
  });
  expect(response.status()).toBe(201);
  const value: unknown = await response.json();
  if (!isJobFile(value)) throw new Error('Invalid job file');
  return value.job_file_id;
}

/** The edge and the outline the browser still paints around an element. */
function paintedAround(locator: Locator): Promise<{ border: boolean; outline: boolean }> {
  return locator.evaluate((element) => {
    const style = getComputedStyle(element);
    const sides = ['top', 'right', 'bottom', 'left'] as const;
    return {
      border: sides.some(
        (side) =>
          parseFloat(style.getPropertyValue(`border-${side}-width`)) > 0 &&
          style.getPropertyValue(`border-${side}-style`) !== 'none',
      ),
      outline: style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0,
    };
  });
}

test('強制色彩（Windows 高對比）下，輸入器、送出鈕、目前章節、聚焦與對話框仍畫得出邊界', async ({
  page,
}) => {
  await page.emulateMedia({ forcedColors: 'active' });
  const fileId = await createFile(page.request);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/job-files/${fileId}`);

  const field = page.getByRole('textbox', { name: '訪談內容' });
  const composer = page.locator('.composer-card');
  await expect(field).toBeVisible();
  expect((await paintedAround(composer)).border).toBe(true);
  expect((await paintedAround(page.getByRole('button', { name: '送出訪談' }))).border).toBe(true);
  // The speaker avatar is a tinted disc: without the tint it is a bare letter unless it keeps an edge.
  expect((await paintedAround(page.locator('.pane-heading .msg-avatar'))).border).toBe(true);

  const current = page
    .getByRole('navigation', { name: 'JD 章節導覽' })
    .locator('[aria-current="location"]');
  await expect(current).toHaveCount(1);
  expect((await paintedAround(current)).border).toBe(true);

  await field.focus();
  await expect.poll(async () => (await paintedAround(composer)).outline).toBe(true);

  await page.getByRole('button', { name: '新增任務', exact: true }).click();
  expect((await paintedAround(page.getByRole('dialog'))).border).toBe(true);
  await page.getByRole('textbox', { name: '任務名稱' }).focus();
  const focusedField = page.locator('.MuiOutlinedInput-root.Mui-focused');
  await expect.poll(async () => (await paintedAround(focusedField)).outline).toBe(true);
});

test('強制色彩下，就地編輯的鍵盤焦點環與儲存鈕仍畫得出來', async ({ page }) => {
  await page.emulateMedia({ forcedColors: 'active' });
  const fileId = await createFile(page.request);
  const work = await page.request.get(`/api/job-files/${fileId}/jd/work`);
  const base: unknown = await work.json();
  if (!isJdWorkView(base)) throw new Error('Invalid JD work');
  const created = await page.request.post(`/api/job-files/${fileId}/jd/tasks`, {
    data: {
      command_id: randomUUID(),
      expected_revision_id: base.revision_id,
      change: {
        action: 'create_task',
        area_id: null,
        title: '高對比任務',
        description: '高對比內容',
        outcomes: [],
        requirements: [],
      },
    },
  });
  expect(created.status()).toBe(200);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/job-files/${fileId}`);

  // The edit button is visually hidden, so its focus ring is drawn around the whole text: an outline.
  const editTitle = page.getByRole('button', { name: '修改任務名稱' });
  await expect(editTitle).toHaveAttribute('aria-disabled', 'false');
  await editTitle.focus();
  const ringed = page.locator('.inline-text:has(> .inline-text__edit:focus-visible)');
  await expect(ringed).toHaveCount(1);
  expect((await paintedAround(ringed)).outline).toBe(true);

  await page.keyboard.press('Enter');
  const focusedField = page.locator('.MuiOutlinedInput-root.Mui-focused');
  await expect.poll(async () => (await paintedAround(focusedField)).outline).toBe(true);
  expect(
    (await paintedAround(page.getByRole('button', { name: '儲存', exact: true }))).border,
  ).toBe(true);
});
