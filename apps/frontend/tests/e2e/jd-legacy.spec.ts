import { test, expect } from './fixtures';
import { validateJobDescriptionResponse } from '../../src/shared/api/generated/validators';

test('JD 點文字、單一槽、鍵盤保存及收合導覽保留草稿', async ({ page, synthetic }) => {
  const workspace = await synthetic.createWorkspace('就地編輯');
  await page.goto(`/workspaces/${workspace.workspace_id}/jd`);
  await expect(
    page.getByRole('button', { name: '修改職務名稱', exact: true }),
  ).toHaveAttribute('aria-disabled', 'false');
  await page.getByRole('button', { name: '修改職務名稱', exact: true }).focus();
  await page.keyboard.press('Enter');
  const title = page.getByRole('textbox', { name: '職務名稱', exact: true });
  await expect(title).toBeFocused();
  await title.fill('營運分析師');
  await expect(
    page.getByRole('button', { name: '修改組織單位', exact: true }),
  ).toHaveAttribute('aria-disabled', 'true');
  const saved = page.waitForResponse(
    (response) =>
      response.request().method() === 'PATCH' &&
      response.url().includes('/job-descriptions/'),
  );
  await title.press('Enter');
  expect((await saved).status()).toBe(200);
  await expect(page.getByRole('textbox', { name: '職務名稱', exact: true })).toHaveCount(
    0,
  );
  await expect(
    page.getByRole('button', { name: '修改職務名稱', exact: true }),
  ).toBeFocused();

  await page.getByRole('button', { name: '修改職務目的', exact: true }).focus();
  await page.keyboard.press('Enter');
  const purpose = page.getByRole('textbox', { name: '職務目的', exact: true });
  await purpose.fill('尚未保存的多行內容\n保留第二行');
  await page.getByRole('button', { name: '收合基本資料', exact: true }).click();
  await expect(purpose).toBeHidden();
  await page
    .getByRole('navigation', { name: 'JD 章節導覽' })
    .getByRole('button', { name: '基本資料', exact: true })
    .click();
  await expect(purpose).toHaveValue('尚未保存的多行內容\n保留第二行');
  await expect(purpose).toBeVisible();
  await purpose.press('Escape');
  await expect(page.getByRole('textbox', { name: '職務目的', exact: true })).toHaveCount(
    0,
  );
  await page.reload();
  await expect(page.getByText('營運分析師', { exact: true })).toBeVisible();
  await expect(page.getByText('尚未保存的多行內容', { exact: true })).toHaveCount(0);
});

test('外部改版引發衝突時保留人工草稿，核對後才明確套用', async ({ page, synthetic }) => {
  const workspace = await synthetic.createWorkspace('版本衝突');
  const response = await synthetic.request.get(
    `/workspaces/${workspace.workspace_id}/job-description`,
  );
  const jd: unknown = await response.json();
  if (!validateJobDescriptionResponse(jd)) throw new Error('Invalid initialized JD');
  const path = `/workspaces/${workspace.workspace_id}/job-descriptions/${jd.job_description_id}`;
  await page.goto(`/workspaces/${workspace.workspace_id}/jd`);
  await expect(
    page.getByRole('button', { name: '修改職務名稱', exact: true }),
  ).toHaveAttribute('aria-disabled', 'false');
  await page.getByRole('button', { name: '修改職務名稱', exact: true }).focus();
  await page.keyboard.press('Enter');
  const title = page.getByRole('textbox', { name: '職務名稱', exact: true });
  await title.fill('人工保留稿');
  const changed = await synthetic.request.patch(path, {
    data: { expected_version: jd.version, job_title: '另一分頁已保存' },
  });
  expect(changed.status()).toBe(200);
  const conflict = page.waitForResponse(
    (result) => result.request().method() === 'PATCH' && result.url().endsWith(path),
  );
  await title.press('Enter');
  expect((await conflict).status()).toBe(409);
  await expect(title).toHaveValue('人工保留稿');
  await expect(page.getByRole('alert').filter({ hasText: '本次未保存' })).toBeVisible();
  await page.getByRole('button', { name: '重新讀取', exact: true }).click();
  await expect(page.getByText('目前內容：另一分頁已保存', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '已核對，繼續編輯', exact: true }).click();
  const applied = page.waitForResponse(
    (result) => result.request().method() === 'PATCH' && result.url().endsWith(path),
  );
  await page.getByRole('button', { name: '套用輸入', exact: true }).click();
  expect((await applied).status()).toBe(200);
  await expect(page.getByText('人工保留稿', { exact: true })).toBeVisible();
});

test('PDF 503 有界故障攔截只顯示失敗，沒有假下載', async ({ page, synthetic }) => {
  const workspace = await synthetic.createWorkspace('PDF 故障');
  await page.route('**/export.pdf', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: { code: 'pdf_export_unavailable' } }),
    }),
  );
  const downloads: string[] = [];
  page.on('download', (download) => downloads.push(download.suggestedFilename()));
  await page.goto(`/workspaces/${workspace.workspace_id}/jd`);
  await page.getByRole('button', { name: '下載 PDF', exact: true }).click();
  await expect(
    page.getByRole('alert').filter({ hasText: '尚未設定字型或瀏覽器' }),
  ).toBeVisible();
  expect(downloads).toEqual([]);
});
