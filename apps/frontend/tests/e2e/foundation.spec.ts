import { randomUUID } from 'node:crypto';
import { test, expect } from './fixtures';
import { validateWorkspaceResponse } from '../../src/shared/api/generated/validators';

test('原子建立、鍵盤修正與對話框焦點', async ({ page, synthetic }) => {
  await page.goto('/workspaces');
  const opener = page.getByRole('button', { name: '建立工作區', exact: true });
  await opener.focus();
  await page.keyboard.press('Enter');
  const input = page.getByRole('textbox', { name: '受訪者姓名', exact: true });
  await expect(input).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(opener).toBeFocused();
  await opener.click();
  await input.fill('   ');
  await input.press('Enter');
  await expect(input).toHaveAttribute('aria-invalid', 'true');
  await expect(input).toHaveValue('   ');
  const name = `鍵盤修正 ${randomUUID().slice(0, 8)}`;
  await input.fill(name);
  let extraJdPosts = 0;
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith('/job-description'))
      extraJdPosts++;
  });
  const created = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().endsWith('/api/workspaces'),
  );
  await input.press('Enter');
  const response = await created;
  expect(response.status()).toBe(201);
  const workspace: unknown = await response.json();
  if (!validateWorkspaceResponse(workspace))
    throw new Error('Invalid Workspace response');
  synthetic.track(workspace.workspace_id);
  await expect(page.getByText('開場引導', { exact: true })).toBeVisible();
  await expect(
    page.getByRole('heading', { name: '職務說明書', level: 1, exact: true }),
  ).toBeVisible();
  expect(extraJdPosts).toBe(0);
  await page.reload();
  await expect(page.getByText('開場引導', { exact: true })).toBeVisible();
  expect(extraJdPosts).toBe(0);
});

test('工作區改名、刪除與舊深連結不復活', async ({ page, synthetic }) => {
  const workspace = await synthetic.createWorkspace('清單生命週期');
  const renamed = workspace.interviewee_name + ' 已改名';
  await page.goto('/workspaces');
  await page
    .getByRole('button', {
      name: `變更 ${workspace.interviewee_name} 的姓名`,
      exact: true,
    })
    .click();
  await page.getByRole('textbox', { name: '受訪者姓名', exact: true }).fill(renamed);
  await page.getByRole('button', { name: '確認', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.goto(`/workspaces/${workspace.workspace_id.toUpperCase()}/jd`);
  await expect(page.getByRole('heading', { name: renamed, exact: true })).toBeVisible();
  await page.getByRole('link', { name: '工作區', exact: true }).click();
  await page
    .getByRole('button', { name: `刪除 ${renamed} 的工作區`, exact: true })
    .click();
  await page.getByRole('button', { name: '永久刪除', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(
    page.getByRole('button', { name: '建立工作區', exact: true }),
  ).toBeFocused();
  await page.goBack();
  await expect(page.getByRole('alert')).toContainText('這份工作區已不存在');
  await expect(
    page.getByRole('heading', { name: '職務說明書', exact: true }),
  ).toHaveCount(0);
});

test('桌面與窄版同掛載、草稿、IME、長內容及高對比', async ({
  page,
  synthetic,
}, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  const { workspace } = await synthetic.createCompleteDocument();
  await page.goto(`/workspaces/${workspace.workspace_id}/jd`);
  await expect(page.getByText('營運規劃與流程改善專員', { exact: true })).toBeVisible();
  const composer = page.getByRole('textbox', { name: '訪談內容', exact: true });
  await composer.fill('尚未送出的訪談草稿');
  let posts = 0;
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith('/agent/turns')) posts++;
  });
  await composer.dispatchEvent('keydown', {
    key: 'Enter',
    code: 'Enter',
    isComposing: true,
    keyCode: 229,
    bubbles: true,
  });
  await expect(composer).toHaveValue('尚未送出的訪談草稿');
  expect(posts).toBe(0);
  await page.screenshot({
    path: testInfo.outputPath('desktop.png'),
    animations: 'disabled',
  });
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    await page.getByRole('tab', { name: 'JD', exact: true }).click();
    await expect(page.getByText('營運規劃與流程改善專員', { exact: true })).toBeVisible();
    const dimensions = await page.evaluate(() => ({
      actual: document.documentElement.scrollWidth,
      viewport: innerWidth,
    }));
    expect(dimensions.actual).toBeLessThanOrEqual(dimensions.viewport);
    await page.screenshot({
      path: testInfo.outputPath(`mobile-${width}.png`),
      animations: 'disabled',
    });
    await page.getByRole('tab', { name: '訪談', exact: true }).click();
    await expect(composer).toHaveValue('尚未送出的訪談草稿');
  }
  await page.emulateMedia({ forcedColors: 'active', reducedMotion: 'reduce' });
  await composer.focus();
  await expect(composer).toBeFocused();
  await expect(page.locator('.composer-card')).toHaveCSS('border-top-style', 'solid');
  await page.screenshot({
    path: testInfo.outputPath('forced-colors.png'),
    animations: 'disabled',
  });
  expect(errors).toEqual([]);
});

test('恢復請求尚未確認時 Escape 不繞過受控對話框，失敗後仍可核對', async ({
  page,
  synthetic,
}) => {
  const workspace = await synthetic.createWorkspace('恢復關閉邊界');
  let release!: () => void;
  let accepted!: () => void;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  const started = new Promise<void>((resolve) => {
    accepted = resolve;
  });
  await page.route('**/job-descriptions/*:restore', async (route) => {
    accepted();
    await held;
    await route.abort('connectionreset');
  });
  await page.goto(`/workspaces/${workspace.workspace_id}/jd/history`);
  await page.getByRole('button', { name: '預覽版本 1', exact: true }).click();
  await page.getByRole('button', { name: '恢復此版本', exact: true }).click();
  await page.getByRole('button', { name: '確認恢復', exact: true }).click();
  await started;
  try {
    await page.keyboard.press('Escape');
    await expect(
      page.getByRole('dialog', { name: '恢復版本 1', exact: true }),
    ).toBeVisible();
  } finally {
    release();
  }
  await expect(
    page.getByRole('link', { name: '返回目前 JD 核對', exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('dialog').getByRole('alert')).toContainText(
    '無法確認是否已恢復',
  );
});
