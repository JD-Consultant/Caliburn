import { readFile } from 'node:fs/promises';
import { test, expect } from './fixtures';
import {
  validateJobDescriptionResponse,
  validateMemoryMapResponse,
  validateTurnViewArray,
} from '../../src/shared/api/generated/validators.js';

test('完成輪比較、固定引用、實際PDF與只撤銷JD；歷史往返保留草稿', async ({
  page,
  synthetic,
}, testInfo) => {
  const workspace = await synthetic.createWorkspace('完成輪比較');
  const base = `/workspaces/${workspace.workspace_id}`;
  await page.goto(`${base}/jd`);
  const composer = page.getByRole('textbox', { name: '訪談內容', exact: true });
  await composer.fill('我負責庫存盤點。');
  await composer.press('Enter');
  const questions = page.getByRole('form', { name: '回答顧問問題' });
  await expect(questions).toBeVisible();
  await questions.getByRole('radio', { name: '逐筆核對庫存，交主管複核' }).check();
  await questions
    .getByRole('group', { name: '異常判斷還有補充嗎？' })
    .getByRole('checkbox', { name: '略過此題' })
    .check();
  await questions.getByRole('button', { name: '送出全部回答' }).click();
  await expect(page.getByText(/已完成處理紀錄/)).toBeVisible();
  await expect(questions).toHaveCount(0);
  const jdPane = page.locator('#pane-jd');
  await expect(jdPane.getByText('核對庫存差異', { exact: true }).first()).toBeVisible();
  await page.getByText(/已完成處理紀錄/).click();
  await page.getByText('處理紀錄與用量', { exact: true }).click();
  await expect(page.getByLabel('本輪模型回覆用量', { exact: true })).toContainText(
    '合計 84 tokens',
  );
  await page.screenshot({
    path: testInfo.outputPath('completed-desktop.png'),
    animations: 'disabled',
  });

  await page.getByRole('button', { name: 'JD 來源（唯讀）', exact: true }).click();
  const source = page.getByRole('complementary', { name: 'JD 來源回查', exact: true });
  await source.locator('.jd-source-list-button').click();
  await expect(
    source.getByText('選擇：逐筆核對庫存，交主管複核', { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath('citation-desktop.png'),
    animations: 'disabled',
  });
  await page.getByRole('button', { name: '關閉來源面板', exact: true }).click();
  await expect(
    page.getByRole('button', { name: 'JD 來源（唯讀）', exact: true }),
  ).toBeFocused();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: '下載 PDF', exact: true }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.pdf$/);
  const pdfPath = testInfo.outputPath('completed-jd.pdf');
  await download.saveAs(pdfPath);
  expect((await readFile(pdfPath)).subarray(0, 5).toString()).toBe('%PDF-');

  await composer.fill('看過歷史後仍保留的草稿');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('tab', { name: 'JD', exact: true }).click();
  await page.getByRole('button', { name: '版本歷史', exact: true }).click();
  await page.getByRole('link', { name: '返回職務說明書', exact: true }).click();
  await expect(page.getByRole('tab', { name: 'JD', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await page.getByRole('tab', { name: '訪談', exact: true }).click();
  await expect(composer).toHaveValue('看過歷史後仍保留的草稿');
  await page.setViewportSize({ width: 1440, height: 1000 });

  await expect
    .poll(
      async () => {
        const body: unknown = await (
          await synthetic.request.get(`${base}/memory`)
        ).json();
        return validateMemoryMapResponse(body) ? body.published_version : null;
      },
      { timeout: 20000 },
    )
    .not.toBeNull();
  const beforeMessages: unknown = await (
    await synthetic.request.get(`${base}/interview/messages`)
  ).json();
  const beforePlan: unknown = await (await synthetic.request.get(`${base}/plan`)).json();
  const beforeMemory: unknown = await (
    await synthetic.request.get(`${base}/memory`)
  ).json();
  const beforeTurns: unknown = await (
    await synthetic.request.get(`${base}/agent/turns`)
  ).json();
  if (!validateTurnViewArray(beforeTurns)) throw new Error('Invalid turns');
  const beforeJd: unknown = await (
    await synthetic.request.get(`${base}/job-description`)
  ).json();
  if (!validateJobDescriptionResponse(beforeJd)) throw new Error('Invalid JD');
  await page.getByRole('button', { name: '該輪 JD 變更', exact: true }).click();
  await expect(page.getByText(/這是固定歷史比較/)).toBeVisible();
  await page.getByRole('button', { name: '撤銷此輪 JD 改動', exact: true }).click();
  const restored = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/turns/') &&
      response.url().endsWith(':restore'),
  );
  await page.getByRole('button', { name: '確認撤銷此輪 JD 改動', exact: true }).click();
  expect((await restored).status()).toBe(200);
  await expect(
    page.getByRole('alert').filter({ hasText: '此輪 JD 撤銷已完成' }),
  ).toBeVisible();
  await expect(jdPane.getByText('核對庫存差異', { exact: true })).toHaveCount(0);
  const afterJd: unknown = await (
    await synthetic.request.get(`${base}/job-description`)
  ).json();
  if (!validateJobDescriptionResponse(afterJd)) throw new Error('Invalid restored JD');
  expect(afterJd.tasks).toEqual([]);
  expect(afterJd.version).toBeGreaterThan(beforeJd.version);
  expect(await (await synthetic.request.get(`${base}/agent/turns`)).json()).toEqual(
    beforeTurns,
  );
  expect(
    await (await synthetic.request.get(`${base}/interview/messages`)).json(),
  ).toEqual(beforeMessages);
  expect(await (await synthetic.request.get(`${base}/plan`)).json()).toEqual(beforePlan);
  expect(await (await synthetic.request.get(`${base}/memory`)).json()).toEqual(
    beforeMemory,
  );
});
