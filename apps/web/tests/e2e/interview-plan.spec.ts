import { expect, test } from '@playwright/test';
import type { APIRequestContext } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import type { ConsultantTurn } from '../../src/shared/api/generated/consultant-turn';
import { isJobFile } from '../../src/shared/api/validation';

// Files and the idle read use the real isolated App. Controlled status/plan responses below
// exercise browser presentation and retry, not execution eligibility or model quality.
async function createFile(request: APIRequestContext): Promise<string> {
  const response = await request.post('/api/job-files', {
    data: {
      command_id: randomUUID(),
      display_name: `合成訪談規劃 ${randomUUID()}`,
      employee_name: '合成規劃員工',
    },
  });
  expect(response.status()).toBe(201);
  const value: unknown = await response.json();
  if (!isJobFile(value)) throw new Error('Invalid job file');
  return value.job_file_id;
}

test('正式未建立筆記可讀且唯讀；原生折疊展開與刻意清空分開呈現', async ({ page }, testInfo) => {
  const fileId = await createFile(page.request);
  await page.goto(`/job-files/${fileId}`);
  const plan = page.getByRole('region', { name: '工作計畫' });
  await expect(plan.getByText('尚未建立工作計畫。')).toBeVisible();
  await expect(plan.getByRole('textbox')).toHaveCount(0);
  await plan.locator('summary').click();
  await expect(plan.getByText('尚未建立工作計畫。')).not.toBeVisible();
  await plan.locator('summary').click();
  await expect(plan.getByText('尚未建立工作計畫。')).toBeVisible();

  await page.route(`**/api/job-files/${fileId}/interview-plan`, async (route) => {
    await route.fulfill({ json: { job_file_id: fileId, plan: '' } });
  });
  await page.reload();
  await expect(plan.getByText('工作計畫目前沒有記錄項目。')).toBeVisible();
  await expect(plan.getByText(/訪談.*完成/)).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('interview-plan-empty.png') });
});

for (const terminalStatus of ['completed', 'cancelled', 'failed'] as const) {
  test(`${terminalStatus} 同一畫面撤下候選；GET 失敗保留上一採用版，主動重讀才確認`, async ({
    page,
  }, testInfo) => {
    const fileId = await createFile(page.request);
    const executionId = randomUUID();
    let status: ConsultantTurn['status'] = 'active';
    let succeeds = false;
    let planReads = 0;
    const turn = (): ConsultantTurn => ({
      job_file_id: fileId,
      execution_id: executionId,
      status,
      pause_requested: status === 'paused',
      input_text: '合成訪談規劃',
      allowed_controls: [],
      commentary: [],
      candidate: null,
      // Deliberately keep the stale preview in the terminal response to test render selection.
      plan_preview: { plan: '## 本輪追問\n- 候選尚待確認' },
    });
    await page.route(`**/api/job-files/${fileId}/consultant-turns/current`, async (route) => {
      await route.fulfill({ json: { turn: turn() } });
    });
    await page.route(
      `**/api/job-files/${fileId}/consultant-turns/${executionId}`,
      async (route) => {
        await route.fulfill({ json: turn() });
      },
    );
    await page.route(`**/api/job-files/${fileId}/interview-plan`, async (route) => {
      planReads += 1;
      const terminal = status === terminalStatus;
      if (terminal && !succeeds) {
        await route.fulfill({
          status: 503,
          json: { detail: { code: 'interview_plan_unavailable' } },
        });
      } else {
        await route.fulfill({
          json: {
            job_file_id: fileId,
            plan: terminal ? '## 採用追問\n- 終局正式筆記' : '## 上輪追問\n- 原正式筆記',
          },
        });
      }
    });
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.goto(`/job-files/${fileId}`);
    const plan = page.getByRole('region', { name: '工作計畫' });
    await expect(plan.getByText('候選尚待確認')).toBeVisible();
    await expect.poll(() => planReads).toBe(1);
    status = 'paused';
    await expect(page.getByText('已暫停', { exact: true })).toBeVisible();
    await expect(plan.getByText('候選尚待確認')).toBeVisible();

    status = terminalStatus;
    await expect(plan.getByRole('button', { name: '重新讀取工作計畫' })).toBeVisible();
    await expect(plan.getByText('候選尚待確認')).toHaveCount(0);
    await expect(plan.getByText('上一採用版，等待更新')).toBeVisible();
    await expect(plan.getByText('原正式筆記')).toBeVisible();
    succeeds = true;
    await plan.getByRole('button', { name: '重新讀取工作計畫' }).click();
    await expect(plan.getByText('終局正式筆記')).toBeVisible();
    await expect(plan.getByText('已採用工作計畫')).toBeVisible();
    await expect(plan.getByText('上一採用版，等待更新')).toHaveCount(0);
    expect(planReads).toBe(3);
    expect(errors).toEqual([]);
    if (terminalStatus === 'completed')
      await page.screenshot({ path: testInfo.outputPath('interview-plan-adopted.png') });
  });
}
