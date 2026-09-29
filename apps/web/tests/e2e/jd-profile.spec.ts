import { expect, test } from '@playwright/test';
import type { APIRequestContext } from '@playwright/test';
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

test('人工編輯四欄、局部清空、重開、鍵盤與窄螢幕保持正式資料', async ({ page }, testInfo) => {
  const fileId = await createFile(page.request);
  await page.goto(`/job-files/${fileId}`);
  const editor = page.getByRole('region', { name: 'JD 基本資料' });
  await expect(editor.getByText('尚未提供')).toHaveCount(4);
  const opening = await page.locator('.interview-text').textContent();
  const edit = page.getByRole('button', { name: '編輯基本資料' });
  await edit.click();
  await expect(page.getByRole('textbox', { name: '職務名稱' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(edit).toBeFocused();
  await edit.click();
  await page.getByRole('textbox', { name: '職務名稱' }).fill('前端工程師');
  await page.getByRole('textbox', { name: '所屬單位／工作範圍' }).fill('產品團隊');
  await page.getByRole('textbox', { name: '匯報關係' }).fill('產品主管');
  await page
    .getByRole('textbox', { name: '職務目的' })
    .fill('交付約定範圍內的網站前端。\n維護使用者可操作的功能。');
  await page.getByRole('button', { name: '儲存基本資料' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(editor.getByText('前端工程師')).toBeVisible();
  await page.reload();
  await expect(editor.getByText('產品團隊')).toBeVisible();
  await expect(page.getByText('受訪員工：合成JD員工')).toBeVisible();
  await expect(page.locator('.interview-text')).toHaveText(opening ?? '');
  await page.screenshot({ path: testInfo.outputPath('jd-profile-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await edit.click();
  await expect(page.getByRole('textbox', { name: '職務名稱' })).toBeFocused();
  await page.getByRole('textbox', { name: '職務目的' }).fill('');
  await page.screenshot({
    path: testInfo.outputPath('jd-profile-edit-mobile.png'),
    animations: 'disabled',
  });
  await page.getByRole('button', { name: '儲存基本資料' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
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

test('表單過期與 A 已准入均拒絕新人工修改，不偷偷換基準', async ({ page }) => {
  const fileId = await createFile(page.request);
  const endpoint = `/api/job-files/${fileId}/jd/profile`;
  const original = await readProfile(page.request, endpoint);
  await page.goto(`/job-files/${fileId}`);
  await page.getByRole('button', { name: '編輯基本資料' }).click();
  await page.getByRole('textbox', { name: '職務名稱' }).fill('舊基準送出');
  const other = await page.request.post(endpoint, {
    data: {
      command_id: randomUUID(),
      expected_revision_id: original.revision_id,
      changes: [{ action: 'set_field', field: 'job_title', value: '其他分頁已保存' }],
    },
  });
  expect(other.status()).toBe(200);
  await page.getByRole('button', { name: '儲存基本資料' }).click();
  await expect(page.getByText(/修改未被接受，可能已有其他修改/)).toBeVisible();
  await expect(page.getByRole('textbox', { name: '職務名稱' })).toHaveValue('舊基準送出');
  await page.getByRole('button', { name: '讀取目前 JD' }).click();
  await expect(page.getByText('其他分頁已保存')).toBeVisible();
  const beforeActive = await readProfile(page.request, endpoint);
  await page.getByRole('button', { name: '編輯基本資料' }).click();
  await page.getByRole('textbox', { name: '職務名稱' }).fill('顧問期間不得修改');
  const accepted = await page.request.post(`/api/job-files/${fileId}/inputs`, {
    data: { command_id: randomUUID(), text: '合成未完成輸入' },
  });
  expect(accepted.status()).toBe(202);
  await page.getByRole('button', { name: '儲存基本資料' }).click();
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
  await page.getByRole('button', { name: '編輯基本資料' }).click();
  await page.getByRole('textbox', { name: '職務名稱' }).fill('第一份已保存內容');
  await page.getByRole('button', { name: '儲存基本資料' }).click();
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
  await page.reload();
  await page.getByRole('button', { name: '編輯基本資料' }).click();
  await expect(page.getByRole('textbox', { name: '職務名稱' })).toHaveValue('第一份已保存內容');
  await expect(page.getByRole('textbox', { name: '職務名稱' })).toBeDisabled();
  await page.getByRole('button', { name: '重新確認修改結果' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByText('後來已保存內容')).toBeVisible();
  expect(sent).toHaveLength(2);
  expect(sent[1]).toBe(sent[0]);
  expect(await readProfile(page.request, endpoint)).toEqual(latest);
});
