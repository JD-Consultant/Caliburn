import { expect, test } from '@playwright/test';
import type { APIRequestContext, Locator, Page } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import {
  isEditJdCapabilitiesRequest,
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
      display_name: `合成能力編輯 ${randomUUID()}`,
      employee_name: '合成員工',
    },
  });
  expect(response.status()).toBe(201);
  const value: unknown = await response.json();
  if (!isJobFile(value)) throw new Error('Invalid file');
  for (const title of ['實作頁面', '交付檢查']) {
    const current = await readWork(request, value.job_file_id);
    const task = await request.post(`/api/job-files/${value.job_file_id}/jd/tasks`, {
      data: {
        command_id: randomUUID(),
        expected_revision_id: current.revision_id,
        change: {
          action: 'create_task',
          area_id: null,
          title,
          description: '按已確認需求執行。',
          outcomes: [],
          requirements: [],
        },
      },
    });
    expect(task.status()).toBe(200);
  }
  return value.job_file_id;
}

async function createCapability(
  page: Page,
  label: string,
  name: string,
  description: string,
): Promise<void> {
  await page.getByRole('button', { name: `新增${label}`, exact: true }).click();
  await page.getByRole('textbox', { name: `${label}名稱` }).fill(name);
  await page.getByRole('textbox', { name: `${label}說明` }).fill(description);
  await page.getByRole('button', { name: `儲存${label}` }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(
    page.getByRole('article', { name: `${label}：${name || `尚未命名的${label}`}` }),
  ).toBeVisible();
}

async function link(page: Page, task: Locator, label: string, name: string): Promise<void> {
  await task.getByRole('combobox', { name: `新增${label}關聯` }).click();
  await page.getByRole('option', { name: new RegExp(name) }).click();
  await expect(task.getByRole('link', { name, exact: true })).toBeVisible();
}

test('共用定義與兩任務關係 CRUD、獨立排序、反向用途、重開及窄螢幕', async ({ page }, testInfo) => {
  test.setTimeout(60_000);
  const browserErrors: string[] = [];
  page.on('pageerror', (error) => browserErrors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(message.text());
  });
  const fileId = await createFile(page.request);
  await page.goto(`/job-files/${fileId}`);
  await createCapability(page, '知識', '資料介面', '理解狀態與錯誤訊號。');
  await createCapability(page, '知識', '瀏覽器行為', '理解事件傳遞及頁面生命週期。');
  await createCapability(page, '技能', '診斷問題', '定位前端故障並驗證修正。');
  const first = page.getByRole('article', { name: '實作頁面', exact: true });
  const second = page.getByRole('article', { name: '交付檢查', exact: true });
  await link(page, first, '知識', '資料介面');
  await link(page, second, '知識', '資料介面');
  await link(page, first, '知識', '瀏覽器行為');
  await link(page, first, '技能', '診斷問題');
  const baseline = await readWork(page.request, fileId);
  const knowledge = baseline.capabilities.find((item) => item.name === '資料介面');
  const firstTask = baseline.tasks.find((item) => item.title === '實作頁面');
  if (!knowledge || !firstTask) throw new Error('Missing seeded objects');
  const definition = page.getByRole('article', { name: '知識：資料介面' });
  await expect(definition.getByRole('link')).toHaveCount(2);
  await expect(definition.getByRole('button', { name: '刪除知識' })).toBeDisabled();
  await definition.getByRole('button', { name: '下移知識' }).click();
  await expect
    .poll(
      async () =>
        (await readWork(page.request, fileId)).capabilities.filter(
          (item) => item.kind === 'knowledge',
        )[0]?.name,
    )
    .toBe('瀏覽器行為');
  expect(
    (await readWork(page.request, fileId)).task_links.filter(
      (item) => item.task_id === firstTask.task_id,
    )[0]?.capability_id,
  ).toBe(knowledge.capability_id);
  await first.getByRole('button', { name: '下移知識關聯 資料介面' }).click();
  await expect
    .poll(
      async () =>
        (await readWork(page.request, fileId)).task_links.filter(
          (item) => item.task_id === firstTask.task_id,
        )[0]?.capability_id,
    )
    .not.toBe(knowledge.capability_id);
  await definition.getByRole('button', { name: '編輯知識' }).click();
  await page.getByRole('textbox', { name: '知識名稱' }).fill('介面錯誤處理');
  await page.getByRole('button', { name: '儲存知識' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(first.getByRole('link', { name: '介面錯誤處理' })).toBeVisible();
  await expect(second.getByRole('link', { name: '介面錯誤處理' })).toBeVisible();
  await page.reload();
  const renamed = page.getByRole('article', { name: '知識：介面錯誤處理' });
  await expect(renamed.getByRole('link')).toHaveCount(2);
  await renamed.screenshot({
    path: testInfo.outputPath('shared-knowledge-desktop.png'),
    animations: 'disabled',
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await renamed.getByRole('button', { name: '編輯知識' }).click();
  await expect(page.getByRole('textbox', { name: '知識名稱' })).toBeFocused();
  await expect(page.getByRole('button', { name: '儲存知識' })).toBeInViewport();
  await page.screenshot({
    path: testInfo.outputPath('knowledge-mobile.png'),
    animations: 'disabled',
  });
  await page.getByRole('button', { name: '返回 JD' }).click();
  await first.getByRole('button', { name: '解除知識 介面錯誤處理' }).click();
  await expect(first.getByRole('link', { name: '介面錯誤處理' })).toHaveCount(0);
  await expect(renamed.getByRole('button', { name: '刪除知識' })).toBeDisabled();
  await second.getByRole('button', { name: '解除知識 介面錯誤處理' }).click();
  await expect(renamed.getByRole('button', { name: '刪除知識' })).toBeEnabled();
  await renamed.getByRole('button', { name: '刪除知識' }).click();
  await page.getByRole('button', { name: '確認刪除知識' }).click();
  await expect(renamed).toHaveCount(0);
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await first.getByRole('button', { name: '刪除任務' }).click();
  await page.getByRole('button', { name: '確認刪除任務' }).click();
  await expect(first).toHaveCount(0);
  await expect(
    page.getByRole('article', { name: '技能：診斷問題' }).getByText('尚無關聯任務'),
  ).toBeVisible();
  const current = await readWork(page.request, fileId);
  expect(current.capabilities.map((item) => item.name)).toEqual(['瀏覽器行為', '診斷問題']);
  expect(current.task_links).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  expect(browserErrors).toEqual([]);
});

test('知識真提交後丟回應，重開後確認同一命令且只呈現後來的新內容', async ({ page }) => {
  const fileId = await createFile(page.request);
  const endpoint = `/api/job-files/${fileId}/jd/capabilities`;
  const commands: string[] = [];
  await page.route(`**${endpoint}`, async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }
    const payload: unknown = route.request().postDataJSON();
    if (!isEditJdCapabilitiesRequest(payload)) throw new Error('Invalid capability request');
    commands.push(JSON.stringify(payload));
    const response = await route.fetch();
    expect(response.status()).toBe(200);
    if (commands.length === 1) await route.abort('failed');
    else await route.fulfill({ response });
  });
  await page.goto(`/job-files/${fileId}`);
  await page.getByRole('button', { name: '新增知識', exact: true }).click();
  await page.getByRole('textbox', { name: '知識名稱' }).fill('原知識');
  await page.getByRole('button', { name: '儲存知識' }).click();
  await expect(page.getByRole('dialog')).toContainText('結果尚未確認');
  const saved = await readWork(page.request, fileId);
  const capabilityId = saved.capabilities[0]?.capability_id;
  if (!capabilityId) throw new Error('Missing committed capability');
  const rename = await page.request.post(endpoint, {
    data: {
      command_id: randomUUID(),
      expected_revision_id: saved.revision_id,
      change: {
        action: 'revise_capability',
        capability_id: capabilityId,
        changes: [{ field: 'name', value: '後來改名' }],
      },
    },
  });
  expect(rename.status()).toBe(200);
  await page.reload();
  await expect(page.getByRole('article', { name: '知識：後來改名' })).toBeVisible();
  await expect(page.getByRole('button', { name: '新增知識', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: '重新確認修改結果' }).click();
  await expect(page.getByRole('button', { name: '重新確認修改結果' })).toHaveCount(0);
  expect(commands).toHaveLength(2);
  expect(commands[0]).toBe(commands[1]);
  const current = await readWork(page.request, fileId);
  expect(current.capabilities).toHaveLength(1);
  expect(current.capabilities[0]?.name).toBe('後來改名');
  await expect(page.getByRole('article', { name: '知識：原知識' })).toHaveCount(0);
});
