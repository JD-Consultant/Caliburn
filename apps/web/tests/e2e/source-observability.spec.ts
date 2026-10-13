/** Real file/profile reads; controlled source failures exercise presentation, not source eligibility. */
import { expect, test } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { isJdProfileView, isJobFile } from '../../src/shared/api/validation';
import {
  isJdSourcesView,
  isJdSourceContentView,
  isJdSourceChangesView,
} from '../../src/shared/api/generated/http/validators.js';

test('來源讀取失敗可重試；背景失敗保留引用並明示尚未更新', async ({ page }, testInfo) => {
  const created = await page.request.post('/api/job-files', {
    data: { command_id: randomUUID(), display_name: '合成來源觀測', employee_name: '合成員工' },
  });
  expect(created.status()).toBe(201);
  const file: unknown = await created.json();
  if (!isJobFile(file)) throw new Error('Invalid synthetic file');
  const profileResponse = await page.request.get(`/api/job-files/${file.job_file_id}/jd/profile`);
  expect(profileResponse.status()).toBe(200);
  const profile: unknown = await profileResponse.json();
  if (!isJdProfileView(profile)) throw new Error('Invalid profile');
  let reads = 0;
  await page.route(`**/api/job-files/${file.job_file_id}/jd/sources`, async (route) => {
    reads += 1;
    if (reads === 1 || reads === 3) {
      await route.fulfill({ status: 503, json: { detail: { code: 'source_unavailable' } } });
      return;
    }
    await route.fulfill({
      json: {
        revision_id: profile.revision_id,
        references: [
          {
            citation_id: randomUUID(),
            target: { kind: 'profile_field', field: 'job_title', item_id: null },
            target_label: '職務名稱',
            source_kind: 'interview',
            source_label: '合成來源',
            needs_recheck: false,
            jd_changed: false,
            source_changed: false,
          },
        ],
      },
    });
  });
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto(`/job-files/${file.job_file_id}`);
  await expect(page.getByText('來源尚未讀取，暫時無法顯示引用。')).toBeVisible();
  await expect(page.getByRole('button', { name: '來源 1 筆' })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('source-first-read-failure.png') });
  await page.getByRole('button', { name: '重新讀取來源', exact: true }).click();
  await expect(page.getByRole('button', { name: '來源 1 筆' })).toBeVisible();
  await expect(page.getByText('來源尚未讀取，暫時無法顯示引用。')).toHaveCount(0);
  // Mounting the source sheet performs its normal stale-query re-read of the same cache.
  await page.getByRole('button', { name: '正式 JD 來源（唯讀）' }).click();
  await expect.poll(() => reads).toBe(3);
  await page.getByRole('button', { name: '關閉來源面板' }).click();
  await expect(page.getByText('來源尚未更新，目前顯示上次讀取的引用。')).toBeVisible();
  await expect(page.getByRole('button', { name: '來源 1 筆' })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('tab', { name: 'JD', exact: true }).click();
  await page.screenshot({ path: testInfo.outputPath('source-background-failure-mobile.png') });
  await page.getByRole('button', { name: '重新讀取來源', exact: true }).click();
  await expect(page.getByText('來源尚未更新，目前顯示上次讀取的引用。')).toHaveCount(0);
  await expect(page.getByRole('button', { name: '來源 1 筆' })).toBeVisible();
  expect(reads).toBe(4);
  expect(errors).toEqual([]);
});

test('正式 scripted A→B 發布的任務引用，可沿 HTTP 固定鏈讀回員工原話', async ({
  page,
}, testInfo) => {
  const fileId = process.env.CALIBURN_E2E_JOURNEY_FILE_ID;
  const taskId = process.env.CALIBURN_E2E_JOURNEY_TASK_ID;
  if (!fileId || !taskId) {
    throw new Error('Provide IDs from quality_journey.py scripted manual browser-binding.json.');
  }
  const path = `/api/job-files/${fileId}/jd/sources`;
  const overviewResponse = await page.request.get(path);
  expect(overviewResponse.status()).toBe(200);
  const overview: unknown = await overviewResponse.json();
  if (!isJdSourcesView(overview)) throw new Error('Invalid formal source overview');
  const candidates = overview.references.filter(
    (item) =>
      item.target.kind === 'task' &&
      item.target.item_id === taskId &&
      item.source_kind === 'work_understanding',
  );
  expect(candidates).toHaveLength(1);
  const citation = candidates[0];
  if (!citation)
    throw new Error('The scripted journey did not produce a unique task Memory citation');
  const endpoint = `${path}/${citation.citation_id}`;
  const readSource = async (sourceRef?: string) => {
    const response = await page.request.get(endpoint, {
      params: {
        revision_id: overview.revision_id,
        ...(sourceRef ? { source_ref: sourceRef } : {}),
      },
    });
    expect(response.status()).toBe(200);
    const value: unknown = await response.json();
    if (!isJdSourceContentView(value)) throw new Error('Invalid fixed source content');
    return value;
  };
  const root = await readSource();
  if (root.content.kind !== 'work_understanding')
    throw new Error('Expected the actual B2 publication');
  expect(root.content.references).toHaveLength(1);
  const situationLink = root.content.references[0];
  if (!situationLink) throw new Error('Missing fixed B2→B1 link');
  const situation = await readSource(situationLink.source_ref);
  if (situation.content.kind !== 'work_situation')
    throw new Error('Expected the actual B1 publication');
  expect(situation.content.references).toHaveLength(1);
  const interviewLink = situation.content.references[0];
  if (!interviewLink) throw new Error('Missing fixed B1→interview link');
  const interview = await readSource(interviewLink.source_ref);
  if (interview.content.kind !== 'interview') throw new Error('Expected the formal employee input');
  expect(interview.content.speaker).toBe('employee');
  const changesResponse = await page.request.get(`${endpoint}/changes`, {
    params: { revision_id: overview.revision_id },
  });
  expect(changesResponse.status()).toBe(200);
  const changes: unknown = await changesResponse.json();
  if (!isJdSourceChangesView(changes)) throw new Error('Invalid actual source comparison');
  const reads: { url: string; status: number }[] = [];
  page.on('response', (response) => {
    if (response.url().includes(endpoint))
      reads.push({ url: response.url(), status: response.status() });
  });
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto(`/job-files/${fileId}`);
  await page.getByRole('button', { name: '正式 JD 來源（唯讀）' }).click();
  await page
    .locator(`[data-citation-id="${citation.citation_id}"]`)
    .getByRole('button', { name: citation.source_label, exact: true })
    .click();
  await expect(page.getByRole('heading', { name: root.content.title, exact: true })).toBeVisible();
  await page.getByRole('button', { name: situationLink.label, exact: true }).click();
  await expect(
    page.getByRole('heading', { name: situation.content.title, exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: interviewLink.label, exact: true }).click();
  await expect(page.locator('.source-quote blockquote')).toHaveText(
    interview.content.interview_text,
  );
  await page.screenshot({ path: testInfo.outputPath('formal-published-source-chain.png') });
  const afterResponse = await page.request.get(path);
  expect(afterResponse.status()).toBe(200);
  const after: unknown = await afterResponse.json();
  expect(after).toEqual(overview);
  expect(reads).toHaveLength(3);
  expect(reads.every((item) => item.status === 200)).toBe(true);
  expect(errors).toEqual([]);
  await testInfo.attach('formal-published-source-reads', {
    body: JSON.stringify({ overview, root, situation, interview, changes, after, reads }),
    contentType: 'application/json',
  });
});
