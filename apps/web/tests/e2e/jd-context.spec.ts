/** Human job context editing against the real API/PG, not mocked successful writes. */
import { expect, test } from '@playwright/test';
import type { APIRequestContext, Page } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import {
  isEditJdConditionsRequest,
  isJdWorkView,
  isJobFile,
} from '../../src/shared/api/validation';
import type { JdWorkView } from '../../src/shared/api/generated/jd-work-view';

async function readWork(request: APIRequestContext, fileId: string): Promise<JdWorkView> {
  const response = await request.get(`/api/job-files/${fileId}/jd/work`);
  expect(response.status()).toBe(200);
  const value: unknown = await response.json();
  if (!isJdWorkView(value)) throw new Error('Invalid work view');
  return value;
}
async function createFile(request: APIRequestContext): Promise<string> {
  const response = await request.post('/api/job-files', {
    data: {
      command_id: randomUUID(),
      display_name: `合成協作條件 ${randomUUID()}`,
      employee_name: '合成員工',
    },
  });
  expect(response.status()).toBe(201);
  const value: unknown = await response.json();
  if (!isJobFile(value)) throw new Error('Invalid job file');
  return value.job_file_id;
}
async function createCollaborator(page: Page, name: string, scope: string): Promise<void> {
  await page.getByRole('button', { name: '新增協作對象', exact: true }).click();
  await page.getByRole('textbox', { name: '協作對象名稱' }).fill(name);
  await page.getByRole('textbox', { name: '協作範圍' }).fill(scope);
  await page.getByRole('button', { name: '儲存協作對象' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
}
async function createCondition(page: Page, kind: string, text: string): Promise<void> {
  await page.getByRole('button', { name: '新增條件', exact: true }).click();
  await page.getByRole('combobox', { name: '條件分類' }).click();
  await page.getByRole('option', { name: kind, exact: true }).click();
  await page.getByRole('textbox', { name: '條件內容' }).fill(text);
  await page.getByRole('button', { name: '儲存條件' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
}

test('協作與共通條件增修刪、分類內排序、更正分類、重開與窄螢幕', async ({ page }, testInfo) => {
  test.setTimeout(60_000);
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  const fileId = await createFile(page.request);
  await page.goto(`/job-files/${fileId}`);
  await createCollaborator(page, '', '配合確認前端介面狀態。');
  await createCollaborator(page, '產品同事', '釐清已確認需求的範圍。');
  const initial = await readWork(page.request, fileId);
  const firstId = initial.collaborators[0]?.collaborator_id;
  const unnamed = page.getByRole('article', { name: '協作對象：尚未命名' });
  await unnamed.getByRole('button', { name: '編輯協作對象' }).click();
  await page.getByRole('textbox', { name: '協作對象名稱' }).fill('後端同事');
  await page.getByRole('button', { name: '儲存協作對象' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  const named = page.getByRole('article', { name: '協作對象：後端同事' });
  await named.getByRole('button', { name: '下移協作對象' }).click();
  await expect
    .poll(async () => (await readWork(page.request, fileId)).collaborators[1]?.collaborator_id)
    .toBe(firstId);
  await createCondition(page, '工時與出差', '依排程支援約定上線。');
  await createCondition(page, '工作環境', '主要在辦公室處理前端工作。');
  await createCondition(page, '工時與出差', '必要時配合跨區會議。');
  const beforeMove = await readWork(page.request, fileId);
  const source = beforeMove.conditions.find((item) => item.text === '依排程支援約定上線。');
  if (!source) throw new Error('Missing condition');
  const firstCondition = page.getByRole('article', { name: '工時與出差 1' });
  await firstCondition.getByRole('button', { name: '下移條件' }).click();
  await expect
    .poll(
      async () =>
        (await readWork(page.request, fileId)).conditions.filter(
          (item) => item.kind === 'schedule_travel',
        )[0]?.text,
    )
    .toBe('必要時配合跨區會議。');
  const secondCondition = page.getByRole('article', { name: '工時與出差 2' });
  await secondCondition.getByRole('button', { name: '編輯條件' }).click();
  await page.getByRole('combobox', { name: '條件分類' }).click();
  await page.getByRole('option', { name: '共通協作界線', exact: true }).click();
  await page.getByRole('textbox', { name: '條件內容' }).fill('依約配合上線，由產品同事確認排程。');
  await page.getByRole('button', { name: '儲存條件' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.reload();
  const updated = await readWork(page.request, fileId);
  expect(
    updated.conditions.find((item) => item.condition_id === source.condition_id),
  ).toMatchObject({
    kind: 'shared_collaboration',
    text: '依約配合上線，由產品同事確認排程。',
  });
  expect(updated.conditions.find((item) => item.kind === 'work_environment')).toEqual(
    beforeMove.conditions.find((item) => item.kind === 'work_environment'),
  );
  await expect(page.getByRole('region', { name: '共通協作界線', exact: true })).toContainText(
    '依約配合上線',
  );
  await page
    .getByRole('region', { name: '工作條件與責任邊界', exact: true })
    .screenshot({ path: testInfo.outputPath('conditions-desktop.png'), animations: 'disabled' });
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .getByRole('article', { name: '共通協作界線 1' })
    .getByRole('button', { name: '編輯條件' })
    .click();
  await expect(page.getByRole('textbox', { name: '條件內容' })).toBeFocused();
  await expect(page.getByRole('button', { name: '儲存條件' })).toBeInViewport();
  await page.screenshot({
    path: testInfo.outputPath('condition-mobile.png'),
    animations: 'disabled',
  });
  await page.getByRole('button', { name: '返回 JD' }).click();
  await named.getByRole('button', { name: '刪除協作對象' }).click();
  await page.getByRole('button', { name: '確認刪除協作對象' }).click();
  await expect(named).toHaveCount(0);
  await expect(page.getByRole('dialog')).toHaveCount(0);
  const shared = page.getByRole('article', { name: '共通協作界線 1' });
  await shared.getByRole('button', { name: '刪除條件' }).click();
  await page.getByRole('button', { name: '確認刪除條件' }).click();
  await expect(shared).toHaveCount(0);
  const final = await readWork(page.request, fileId);
  expect(final.collaborators.map((item) => item.name)).toEqual(['產品同事']);
  expect(final.conditions).toHaveLength(2);
  expect(final.tasks).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  expect(errors).toEqual([]);
});

test('條件提交後丟回應，再修改分類；重開確認原命令不覆蓋新稿', async ({ page }) => {
  const fileId = await createFile(page.request);
  const endpoint = `/api/job-files/${fileId}/jd/conditions`;
  const commands: string[] = [];
  await page.route(`**${endpoint}`, async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }
    const payload: unknown = route.request().postDataJSON();
    if (!isEditJdConditionsRequest(payload)) throw new Error('Invalid condition request');
    commands.push(JSON.stringify(payload));
    const response = await route.fetch();
    expect(response.status()).toBe(200);
    if (commands.length === 1) await route.abort('failed');
    else await route.fulfill({ response });
  });
  await page.goto(`/job-files/${fileId}`);
  await page.getByRole('button', { name: '新增條件' }).click();
  await page.getByRole('combobox', { name: '條件分類' }).click();
  await page.getByRole('option', { name: '工時與出差' }).click();
  await page.getByRole('textbox', { name: '條件內容' }).fill('依約配合上線。');
  await page.getByRole('button', { name: '儲存條件' }).click();
  await expect(page.getByRole('dialog')).toContainText('結果尚未確認');
  const saved = await readWork(page.request, fileId);
  const id = saved.conditions[0]?.condition_id;
  if (!id) throw new Error('Missing saved condition');
  const revised = await page.request.post(endpoint, {
    data: {
      command_id: randomUUID(),
      expected_revision_id: saved.revision_id,
      change: {
        action: 'revise_condition',
        condition_id: id,
        changes: [{ field: 'kind', value: 'shared_collaboration' }],
      },
    },
  });
  expect(revised.status()).toBe(200);
  await page.reload();
  await expect(page.getByRole('region', { name: '共通協作界線', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '新增條件' })).toBeDisabled();
  await page.getByRole('button', { name: '重新確認修改結果' }).click();
  await expect(page.getByRole('button', { name: '重新確認修改結果' })).toHaveCount(0);
  expect(commands).toHaveLength(2);
  expect(commands[0]).toBe(commands[1]);
  const latest = await readWork(page.request, fileId);
  expect(latest.conditions).toEqual([
    { condition_id: id, kind: 'shared_collaboration', text: '依約配合上線。' },
  ]);
});
