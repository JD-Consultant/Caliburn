import { expect, test } from '@playwright/test';
import type { APIRequestContext, Locator, Page } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import {
  isJdProfileView,
  isJobFile,
  isReviseJdProfileRequest,
} from '../../src/shared/api/validation';
import type { JdProfileView } from '../../src/shared/api/generated/jd-profile-view';

async function createFile(request: APIRequestContext): Promise<string> {
  const response = await request.post('/api/job-files', {
    data: {
      command_id: randomUUID(),
      display_name: `合成JD ${randomUUID()}`,
      employee_name: '合成JD員工',
    },
  });
  expect(response.status()).toBe(201);
  const value: unknown = await response.json();
  if (!isJobFile(value)) throw new Error('Invalid file response');
  return value.job_file_id;
}

async function readProfile(request: APIRequestContext, endpoint: string): Promise<JdProfileView> {
  const response = await request.get(endpoint);
  expect(response.status()).toBe(200);
  const value: unknown = await response.json();
  if (!isJdProfileView(value)) throw new Error('Invalid JD profile');
  return value;
}

/**
 * Opens one basic-data field in place the keyboard way: its edit button is visually hidden (a click on
 * the text is the shortcut) and only marked aria-disabled while the page is busy, so the test waits for it
 * to be enabled, as a person would wait for a control to respond.
 */
async function open(editor: Locator, page: Page, label: string): Promise<Locator> {
  const edit = editor.getByRole('button', { name: `修改${label}` });
  await expect(edit).toHaveAttribute('aria-disabled', 'false');
  await edit.focus();
  await page.keyboard.press('Enter');
  const field = page.getByRole('textbox', { name: label });
  await expect(field).toBeFocused();
  return field;
}

test('點基本資料的欄位就地逐欄修改、局部清空、重開、鍵盤與窄螢幕保持正式資料', async ({
  page,
}, testInfo) => {
  const fileId = await createFile(page.request);
  await page.goto(`/job-files/${fileId}`);
  const editor = page.getByRole('region', { name: 'JD 基本資料' });
  await expect(editor.getByText('尚未提供')).toHaveCount(4);
  await expect(page.getByRole('button', { name: '編輯基本資料' })).toHaveCount(0);
  const opening = await page.locator('.interview-text').textContent();

  // Keyboard: the hidden edit button opens the editor with focus in it; Esc puts focus back on the button.
  const editTitle = editor.getByRole('button', { name: '修改職務名稱' });
  await editTitle.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('textbox', { name: '職務名稱' })).toBeFocused();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(editTitle).toBeFocused();

  // Each field saves on its own: Enter for one line, Ctrl+Enter for the multi-line purpose.
  const set = async (label: string, text: string, key: string) => {
    const field = await open(editor, page, label);
    await field.fill(text);
    await field.press(key);
    await expect(page.getByRole('textbox', { name: label })).toHaveCount(0);
  };
  await set('職務名稱', '前端工程師', 'Enter');
  await set('所屬單位／工作範圍', '產品團隊', 'Enter');
  await set('匯報關係', '產品主管', 'Enter');
  await set('職務目的', '交付約定範圍內的網站前端。\n維護使用者可操作的功能。', 'Control+Enter');
  await expect(editor.getByText('前端工程師')).toBeVisible();
  await page.reload();
  await expect(editor.getByText('產品團隊')).toBeVisible();
  await expect(page.getByText('受訪員工：合成JD員工')).toBeVisible();
  await expect(page.locator('.interview-text')).toHaveText(opening ?? '');
  await page.screenshot({ path: testInfo.outputPath('jd-profile-desktop.png'), fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  // Narrow screens show one pane at a time; the JD lives in its own tab.
  await page.getByRole('tab', { name: 'JD' }).click();
  const purpose = await open(editor, page, '職務目的');
  await purpose.fill('');
  await page.screenshot({
    path: testInfo.outputPath('jd-profile-edit-mobile.png'),
    animations: 'disabled',
  });
  await page.getByRole('button', { name: '儲存', exact: true }).click();
  await expect(page.getByRole('textbox', { name: '職務目的' })).toHaveCount(0);
  await expect(editor.getByText('尚未提供')).toHaveCount(1);
  await expect(editor.getByText('產品主管')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  const profile = await readProfile(page.request, `/api/job-files/${fileId}/jd/profile`);
  expect(profile.profile).toEqual({
    job_title: '前端工程師',
    organization_unit: '產品團隊',
    reports_to: '產品主管',
    purpose: null,
  });
});

test('編輯器過期與 A 已准入均拒絕新人工修改，不偷偷換基準', async ({ page }) => {
  const fileId = await createFile(page.request);
  const endpoint = `/api/job-files/${fileId}/jd/profile`;
  const original = await readProfile(page.request, endpoint);
  await page.goto(`/job-files/${fileId}`);
  const editor = page.getByRole('region', { name: 'JD 基本資料' });
  const title = await open(editor, page, '職務名稱');
  await title.fill('舊基準送出');
  const other = await page.request.post(endpoint, {
    data: {
      command_id: randomUUID(),
      expected_revision_id: original.revision_id,
      changes: [{ action: 'set_field', field: 'job_title', value: '其他分頁已保存' }],
    },
  });
  expect(other.status()).toBe(200);
  await title.press('Enter');
  await expect(page.getByText(/修改未被接受，可能已有其他修改/)).toBeVisible();
  await expect(page.getByRole('textbox', { name: '職務名稱' })).toHaveValue('舊基準送出');
  await page.getByRole('button', { name: '讀取目前 JD' }).click();
  await expect(page.getByText('其他分頁已保存')).toBeVisible();
  const beforeActive = await readProfile(page.request, endpoint);

  const again = await open(editor, page, '職務名稱');
  await again.fill('顧問期間不得修改');
  const accepted = await page.request.post(`/api/job-files/${fileId}/inputs`, {
    data: { command_id: randomUUID(), text: '合成未完成輸入' },
  });
  expect(accepted.status()).toBe(202);
  await again.press('Enter');
  await expect(page.getByText(/修改未被接受，可能已有其他修改/)).toBeVisible();
  expect(await readProfile(page.request, endpoint)).toEqual(beforeActive);
});

test('真提交後丟回應，reload 用原命令取原結果但呈現最新稿', async ({ page }) => {
  const fileId = await createFile(page.request);
  const endpoint = `/api/job-files/${fileId}/jd/profile`;
  const sent: string[] = [];
  await page.route(`**${endpoint}`, async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }
    const body: unknown = route.request().postDataJSON();
    if (!isReviseJdProfileRequest(body)) throw new Error('Invalid JD edit');
    sent.push(JSON.stringify(body));
    const response = await route.fetch();
    expect(response.status()).toBe(200);
    if (sent.length === 1) await route.abort('failed');
    else await route.fulfill({ response });
  });
  await page.goto(`/job-files/${fileId}`);
  const editor = page.getByRole('region', { name: 'JD 基本資料' });
  const title = await open(editor, page, '職務名稱');
  await title.fill('第一份已保存內容');
  await title.press('Enter');
  await expect(page.getByText(/JD 修改結果尚未確認/)).toBeVisible();
  const first = await readProfile(page.request, endpoint);
  const later = await page.request.post(endpoint, {
    data: {
      command_id: randomUUID(),
      expected_revision_id: first.revision_id,
      changes: [{ action: 'set_field', field: 'job_title', value: '後來已保存內容' }],
    },
  });
  expect(later.status()).toBe(200);
  const latest = await readProfile(page.request, endpoint);

  // After a reload the unconfirmed command is found again; it is re-confirmed unchanged, over the later save.
  await page.reload();
  await expect(page.getByText(/有尚未確認的 JD 修改/)).toBeVisible();
  await page.getByRole('button', { name: '重新確認修改結果' }).click();
  await expect(page.getByText('後來已保存內容')).toBeVisible();
  expect(sent).toHaveLength(2);
  expect(sent[1]).toBe(sent[0]);
  expect(await readProfile(page.request, endpoint)).toEqual(latest);
});
