/** Browser coverage of committed fold reveals, focus visibility and persistent responsive panes. */
import { expect, test } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import type { JdWorkView } from '../../src/shared/api/generated/jd-work-view';
import { isJobFile } from '../../src/shared/api/validation';

test('雙向交叉連結展開所有祖先並保留草稿，窄寬版切換保持分頁語義', async ({ page }) => {
  const response = await page.request.post('/api/job-files', {
    data: {
      command_id: randomUUID(),
      display_name: `合成導覽 ${randomUUID()}`,
      employee_name: '合成員工',
    },
  });
  expect(response.status()).toBe(201);
  const file: unknown = await response.json();
  if (!isJobFile(file)) throw new Error('Invalid job file');
  const areaId = randomUUID();
  const capabilityId = randomUUID();
  const taskId = randomUUID();
  const view: JdWorkView = {
    revision_id: randomUUID(),
    areas: [{ area_id: areaId, title: '網站交付', scope_text: null }],
    tasks: [
      {
        task_id: taskId,
        area_id: areaId,
        title: '實作頁面',
        description: '原工作內容',
        outcomes: [],
        requirements: [],
      },
    ],
    capabilities: [
      { capability_id: capabilityId, kind: 'knowledge', name: '資料介面', description: null },
    ],
    task_links: [{ task_id: taskId, capability_id: capabilityId }],
    collaborators: [],
    conditions: [],
  };
  // Synthetic JD read only; no model, command or actual employee content is submitted.
  await page.route(`**/api/job-files/${file.job_file_id}/jd/work`, (route) =>
    route.fulfill({ json: view }),
  );
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/job-files/${file.job_file_id}`);
  const task = page.getByRole('article', { name: '實作頁面', exact: true });
  await task.getByText('原工作內容', { exact: true }).click();
  const draft = task.getByRole('textbox', { name: '工作內容', exact: true });
  await draft.fill('尚未送出的工作內容');
  await task.getByRole('button', { name: '收合任務 實作頁面' }).click();
  await page.getByRole('button', { name: '收合職責 網站交付' }).click();
  await page.getByRole('button', { name: '收合職責與任務' }).click();
  const knowledge = page.getByRole('region', { name: '所需知識', exact: true });
  const reverse = knowledge.getByRole('link', { name: '網站交付／實作頁面', exact: true });
  await reverse.focus();
  await reverse.press('Enter');
  await expect(task).toBeFocused();
  await expect(task).toBeInViewport();
  await expect(draft).toBeVisible();
  await expect(draft).toHaveValue('尚未送出的工作內容');
  expect(await task.evaluate((element) => getComputedStyle(element).outlineStyle)).toBe('solid');
  await expect(page.getByRole('button', { name: '收合職責與任務' })).toHaveAttribute(
    'aria-expanded',
    'true',
  );
  await expect(page.getByRole('button', { name: '收合職責 網站交付' })).toHaveAttribute(
    'aria-expanded',
    'true',
  );
  await expect(task.getByRole('button', { name: '收合任務 實作頁面' })).toHaveAttribute(
    'aria-expanded',
    'true',
  );
  await knowledge.getByRole('button', { name: '收合所需知識' }).click();
  const forward = task.getByRole('link', { name: '資料介面', exact: true });
  await forward.focus();
  await forward.press('Enter');
  const capability = page.getByRole('article', { name: '知識：資料介面', exact: true });
  await expect(capability).toBeFocused();
  await expect(capability).toBeInViewport();
  await expect(page).toHaveURL(new RegExp(`#jd-capability-${capabilityId}$`));

  const interviewDraft = page.getByRole('textbox', { name: '訪談內容' });
  await interviewDraft.fill('尚未送出的訪談');
  await page.setViewportSize({ width: 899, height: 900 });
  await expect(page.getByRole('tabpanel', { name: '訪談', exact: true })).toBeVisible();
  const interviewTab = page.getByRole('tab', { name: '訪談', exact: true });
  await interviewTab.focus();
  await interviewTab.press('ArrowRight');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('tabpanel', { name: 'JD', exact: true })).toBeVisible();
  await expect(page.locator('#pane-interview')).toBeHidden();
  await expect(draft).toHaveValue('尚未送出的工作內容');
  await page.setViewportSize({ width: 900, height: 900 });
  await expect(page.getByRole('region', { name: '訪談區', exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: '職務說明書區', exact: true })).not.toHaveAttribute(
    'aria-labelledby',
  );
  await expect(interviewDraft).toHaveValue('尚未送出的訪談');
});
