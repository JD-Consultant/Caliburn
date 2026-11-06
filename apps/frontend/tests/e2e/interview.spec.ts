import { test, expect } from './fixtures';
import {
  validateMemoryMapResponse,
  validatePlanResponse,
  validateTranscriptMessageArray,
  validateTurnViewArray,
} from '../../src/shared/api/generated/validators.js';

test('正式訪談：遺失受理回覆仍同輪、完整問答、Plan/Memory、冷重開與取消', async ({
  page,
  synthetic,
}, testInfo) => {
  const workspace = await synthetic.createWorkspace('訪談正式旅程');
  const path = `/workspaces/${workspace.workspace_id}`;
  const initialMessages: unknown = await (
    await synthetic.request.get(`${path}/interview/messages`)
  ).json();
  expect(validateTranscriptMessageArray(initialMessages)).toBe(true);
  if (!validateTranscriptMessageArray(initialMessages))
    throw new Error('invalid transcript');
  expect(initialMessages).toHaveLength(1);
  expect(initialMessages[0]?.speaker).toBe('app');

  let submissions = 0;
  await page.route(`**/api${path}/agent/turns`, async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    submissions++;
    // The real Host accepts the request; only its acknowledgement is lost.
    await route.fetch();
    await route.abort('connectionreset');
  });
  await page.goto(`${path}/jd`);
  await expect(page.getByText('開場引導', { exact: true })).toBeVisible();
  const composer = page.getByRole('textbox', { name: '訪談內容' });
  await composer.fill('我負責庫存盤點。');
  await composer.press('Enter');
  const questions = page.getByRole('form', { name: '回答顧問問題' });
  await expect(questions).toBeVisible();
  expect(submissions).toBe(1);
  const firstTurns: unknown = await (
    await synthetic.request.get(`${path}/agent/turns`)
  ).json();
  if (!validateTurnViewArray(firstTurns)) throw new Error('invalid turns');
  expect(firstTurns).toHaveLength(1);
  await page.unroute(`**/api${path}/agent/turns`);
  await questions.getByRole('radio', { name: '逐筆核對庫存，交主管複核' }).check();
  await questions
    .getByRole('group', { name: '異常判斷還有補充嗎？' })
    .getByRole('checkbox', { name: '略過此題' })
    .check();
  await questions.getByRole('button', { name: '送出全部回答' }).click();
  await expect(page.getByText(/已完成處理紀錄/)).toBeVisible();
  await expect(questions).toHaveCount(0);
  await page.getByText(/已完成處理紀錄/).click();
  await page.getByText('處理紀錄與用量', { exact: true }).click();
  await expect(page.getByLabel('本輪模型回覆用量', { exact: true })).toContainText(
    '84 tokens',
  );
  await page.getByText('模型步 1', { exact: true }).click();
  await expect(page.getByLabel('模型步 1 用量', { exact: true })).toContainText(
    '21 tokens',
  );
  await page.getByText('工作計畫', { exact: true }).click();
  await expect(
    page.getByText('盤點流程已整理；異常判斷待釐清。', { exact: true }),
  ).toBeVisible();

  await expect
    .poll(
      async () => {
        const map: unknown = await (await synthetic.request.get(`${path}/memory`)).json();
        return validateMemoryMapResponse(map) ? map.published_version : null;
      },
      { timeout: 20_000 },
    )
    .not.toBeNull();
  const memory: unknown = await (await synthetic.request.get(`${path}/memory`)).json();
  if (!validateMemoryMapResponse(memory)) throw new Error('invalid memory');
  const situation = memory.items.find((item) => item.kind === 'situation');
  if (!situation) throw new Error('missing published situation');
  await page.getByRole('button', { name: '工作記憶', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '目前已發布的 Memory' });
  await dialog.getByRole('button', { name: situation.title, exact: true }).click();
  await dialog.getByRole('button', { name: '訪談來源 1', exact: true }).click();
  await expect(
    dialog.getByText('逐筆核對庫存，交主管複核', { exact: false }),
  ).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button', { name: '工作記憶', exact: true })).toBeFocused();

  await page.reload();
  await expect(page.getByText(/已完成處理紀錄/)).toBeVisible();
  await expect(questions).toHaveCount(0);
  const beforePlan: unknown = await (await synthetic.request.get(`${path}/plan`)).json();
  if (!validatePlanResponse(beforePlan)) throw new Error('invalid plan');
  await composer.fill('暫改核准責任，待我確認。');
  await composer.press('Enter');
  await expect(questions).toBeVisible();
  const cancelled = page.waitForResponse(
    (response) =>
      response.url().endsWith('/cancel') && response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: '取消本輪', exact: true }).click();
  expect((await cancelled).status()).toBe(204);
  await expect(questions).toHaveCount(0);
  await expect(page.getByText('暫改核准責任，待我確認。', { exact: true })).toHaveCount(
    0,
  );
  const afterPlan: unknown = await (await synthetic.request.get(`${path}/plan`)).json();
  if (!validatePlanResponse(afterPlan)) throw new Error('invalid restored plan');
  expect(afterPlan.body).toEqual(beforePlan.body);
  const remaining: unknown = await (
    await synthetic.request.get(`${path}/agent/turns`)
  ).json();
  if (!validateTurnViewArray(remaining)) throw new Error('invalid remaining turns');
  expect(remaining).toHaveLength(1);
  await testInfo.attach('interview-desktop', {
    body: await page.screenshot({ animations: 'disabled' }),
    contentType: 'image/png',
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await composer.fill('窄版未送草稿');
  await page.getByRole('tab', { name: 'JD', exact: true }).click();
  await page.getByRole('tab', { name: '訪談', exact: true }).click();
  await expect(composer).toHaveValue('窄版未送草稿');
  await testInfo.attach('interview-mobile', {
    body: await page.screenshot({ animations: 'disabled' }),
    contentType: 'image/png',
  });
});
