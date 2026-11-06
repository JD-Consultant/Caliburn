import { randomUUID } from 'node:crypto';
import { mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import type { Locator, Page, TestInfo } from '@playwright/test';
import type { JobDescriptionResponse } from '../../src/shared/api/generated/types.gen';
import {
  validateJobDescriptionResponse,
  validateWorkspaceResponse,
} from '../../src/shared/api/generated/validators';
import { expect, test, type SyntheticApi } from './fixtures';

test.beforeEach(({ page }) => {
  page.setDefaultTimeout(15_000);
});

function detail(page: Page, name: string) {
  return page
    .locator('.jd-edit-duty, .jd-edit-task')
    .filter({ has: page.getByRole('heading', { name, exact: true }) })
    .last();
}

async function write(page: Page, action: () => Promise<unknown>) {
  const response = page.waitForResponse(
    (result) =>
      ['POST', 'PUT', 'PATCH', 'DELETE'].includes(result.request().method()) &&
      result.url().includes('/job-descriptions/'),
  );
  await action();
  const result = await response;
  expect(result.ok(), await result.text()).toBe(true);
  const body: unknown = await result.json();
  if (!validateJobDescriptionResponse(body)) throw new Error('Invalid saved JD');
  await expect(page.locator('.jd-document-meta')).toContainText(
    `版本 ${String(body.version)}`,
  );
  return body;
}

async function openInlineEditor(trigger: Locator) {
  await expect(trigger).toHaveAttribute('aria-disabled', 'false');
  await trigger.press('Enter');
}

async function edit(page: Page, trigger: Locator, value: string) {
  const label = (await trigger.getAttribute('aria-label'))?.replace(/^修改/, '');
  if (!label) throw new Error('Missing inline edit label');
  await openInlineEditor(trigger);
  const field = page.getByRole('textbox', { name: label, exact: true });
  await field.fill(value);
  const multiline = await field.evaluate((element) => element.tagName === 'TEXTAREA');
  return write(page, () => field.press(multiline ? 'Control+Enter' : 'Enter'));
}

async function showDocument(page: Page) {
  await page.locator('#pane-jd').waitFor({ state: 'attached' });
  if ((page.viewportSize()?.width ?? 1440) < 900)
    await page.getByRole('tab', { name: 'JD', exact: true }).click();
}

async function read(synthetic: SyntheticApi, workspaceId: string) {
  const response = await synthetic.request.get(
    `/workspaces/${workspaceId}/job-description`,
  );
  expect(response.ok(), await response.text()).toBe(true);
  const result: unknown = await response.json();
  if (!validateJobDescriptionResponse(result)) throw new Error('Invalid JD readback');
  return result;
}

async function capture(page: Page, testInfo: TestInfo, name: string) {
  const directory = process.env.CALIBURN_E2E_SCREENSHOT_DIR;
  if (directory) await mkdir(directory, { recursive: true });
  const path = directory
    ? join(directory, `${name}.png`)
    : testInfo.outputPath(`${name}.png`);
  await page.screenshot({ path, animations: 'disabled' });
  await testInfo.attach(name, { path, contentType: 'image/png' });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(await page.evaluate(() => innerWidth));
}

async function confirmDelete(page: Page, opener: Locator, explanation: string) {
  await opener.click();
  await expect(page.getByRole('dialog')).toContainText(explanation);
  return write(page, () =>
    page.getByRole('button', { name: '確認刪除', exact: true }).click(),
  );
}

async function expectFocusedInViewport(heading: Locator) {
  await expect(heading).toBeFocused();
  await expect
    .poll(() =>
      heading.evaluate((element) => {
        const bounds = element.getBoundingClientRect();
        const headerBottom =
          document.querySelector('header')?.getBoundingClientRect().bottom ?? 0;
        return bounds.top >= headerBottom && bounds.bottom <= innerHeight;
      }),
    )
    .toBe(true);
}

for (const width of [1440, 390, 320]) {
  for (const theme of ['light', 'forced-colors'] as const) {
    test(`complete document fits ${String(width)}px in ${theme} mode`, async ({
      page,
      synthetic,
    }, testInfo) => {
      await page.setViewportSize({ width, height: 1000 });
      const { workspace, jd } = await synthetic.createCompleteDocument();
      await page.goto(`/workspaces/${workspace.workspace_id}/jd`);
      await showDocument(page);
      await expect(
        page.getByText('營運規劃與流程改善專員', { exact: true }),
      ).toBeVisible();
      await page.emulateMedia({
        forcedColors: theme === 'forced-colors' ? 'active' : 'none',
        reducedMotion: 'reduce',
      });
      await expect(
        page
          .getByRole('group', { name: '基準職能級別', exact: true })
          .getByRole('radio', { name: '第 3 級', exact: true }),
      ).toBeChecked();
      await openInlineEditor(
        page.getByRole('button', { name: '修改職務目的', exact: true }),
      );
      await expect
        .poll(() =>
          page
            .locator('textarea:not([aria-hidden="true"])')
            .evaluateAll((fields) =>
              fields
                .filter((field) => field.scrollHeight > field.clientHeight + 1)
                .map((field) => field.getAttribute('aria-label')),
            ),
        )
        .toEqual([]);
      await page.getByRole('textbox', { name: '職務目的', exact: true }).press('Escape');
      await capture(page, testInfo, `editor-basic-${String(width)}-${theme}`);

      const task = detail(page, '營運資訊分析：整理現況與辨識差異');
      await expect(
        task.getByRole('list', { name: '工作成果', exact: true }).getByRole('listitem'),
      ).toHaveCount(3);
      await expect(
        task.getByRole('list', { name: '工作要求', exact: true }).getByRole('listitem'),
      ).toHaveCount(5);
      await task
        .getByRole('group', { name: '任務職能級別', exact: true })
        .scrollIntoViewIfNeeded();
      await capture(page, testInfo, `editor-task-controls-${String(width)}-${theme}`);
      await task
        .getByRole('list', { name: '工作要求', exact: true })
        .scrollIntoViewIfNeeded();
      await capture(page, testInfo, `editor-task-content-${String(width)}-${theme}`);
      for (const [section, name] of [
        ['知識與技能', 'catalog'],
        ['協作與條件', 'conditions'],
      ] as const) {
        await page.getByRole('button', { name: section, exact: true }).click();
        await capture(page, testInfo, `editor-${name}-${String(width)}-${theme}`);
      }
      expect((await read(synthetic, workspace.workspace_id)).version).toBe(jd.version);
    });
  }
}

test.describe('touch input', () => {
  test.use({ hasTouch: true, viewport: { width: 320, height: 1000 } });

  test('coarse pointer keeps all competency levels touchable at 320px', async ({
    page,
    synthetic,
  }, testInfo) => {
    const { workspace } = await synthetic.createCompleteDocument();
    await page.goto(`/workspaces/${workspace.workspace_id}/jd`);
    await showDocument(page);
    expect(await page.evaluate(() => matchMedia('(pointer: coarse)').matches)).toBe(true);
    expect(await page.evaluate(() => navigator.maxTouchPoints)).toBeGreaterThan(0);
    const task = detail(page, '營運資訊分析：整理現況與辨識差異');
    for (const group of [
      page.getByRole('group', { name: '基準職能級別', exact: true }),
      task.getByRole('group', { name: '任務職能級別', exact: true }),
    ]) {
      await group.scrollIntoViewIfNeeded();
      const radios = group.getByRole('radio');
      await expect(radios).toHaveCount(7);
      for (const radio of await radios.all()) {
        await expect(radio).toBeInViewport({ ratio: 1 });
        const target = await radio.boundingBox();
        expect(target?.width).toBeGreaterThanOrEqual(24);
        expect(target?.height).toBeGreaterThanOrEqual(40);
      }
      const level = group.getByRole('radio', { name: '第 6 級', exact: true });
      await write(page, () => level.tap());
      await expect(level).toBeChecked();
    }
    await capture(page, testInfo, 'editor-task-controls-touch320-light');
    const taskContent = task.locator('.jd-task-content');
    const contentBounds = await taskContent.boundingBox();
    const levelBounds = await task.locator('.jd-level-options').boundingBox();
    if (!contentBounds || !levelBounds) throw new Error('Missing task layout bounds');
    const paddingRight = await taskContent.evaluate((element) =>
      Number.parseFloat(getComputedStyle(element).paddingRight),
    );
    expect(levelBounds.x + levelBounds.width).toBeLessThanOrEqual(
      contentBounds.x + contentBounds.width - paddingRight,
    );
    const lastRadio = await task
      .getByRole('group', { name: '任務職能級別', exact: true })
      .getByRole('radio')
      .last()
      .boundingBox();
    if (!lastRadio) throw new Error('Missing last competency level bounds');
    expect(lastRadio.x + lastRadio.width).toBeLessThanOrEqual(
      contentBounds.x + contentBounds.width - paddingRight,
    );
    await page.emulateMedia({ forcedColors: 'active', reducedMotion: 'reduce' });
    await task
      .getByRole('group', { name: '任務職能級別', exact: true })
      .evaluate((element) => element.scrollIntoView({ block: 'center' }));
    await capture(page, testInfo, 'editor-task-controls-touch320-forced-colors');
    const saved = await read(synthetic, workspace.workspace_id);
    expect(saved.baseline_competency_level).toBe(6);
    expect(
      saved.tasks.find((item) => item.name === '營運資訊分析：整理現況與辨識差異')
        ?.competency_level,
    ).toBe(6);
  });
});

test('keyboard focus survives saved levels and ordering boundaries without stealing moved focus', async ({
  page,
  synthetic,
}) => {
  const { workspace, jd } = await synthetic.createCompleteDocument();
  await page.goto(`/workspaces/${workspace.workspace_id}/jd`);
  await showDocument(page);
  const baseline = page.getByRole('group', { name: '基準職能級別', exact: true });
  const level = (value: number) =>
    baseline.getByRole('radio', { name: `第 ${String(value)} 級`, exact: true });
  await level(3).focus();
  await write(page, () => page.keyboard.press('ArrowRight'));
  await expect(level(4)).toBeChecked();
  await expect(level(4)).toBeEnabled();
  await expect(level(4)).toBeFocused();

  async function saveWhileMovingFocus(path: string, target: Locator, key: string) {
    const editLabel = await target.getAttribute('aria-label');
    let signalReceived: () => void = () => undefined;
    let releaseResponse: () => void = () => undefined;
    const received = new Promise<void>((resolve) => {
      signalReceived = resolve;
    });
    const released = new Promise<void>((resolve) => {
      releaseResponse = resolve;
    });
    // 延後真 API 的回覆，讓使用者在保存期間有機會改變焦點。
    await page.route(
      (url) => url.pathname.endsWith(path),
      async (route) => {
        const response = await route.fetch();
        signalReceived();
        await released;
        await route.fulfill({ response });
      },
      { times: 1 },
    );
    try {
      await write(page, async () => {
        await page.keyboard.press(key);
        await received;
        if (editLabel?.startsWith('修改')) await openInlineEditor(target);
        else await target.click();
        releaseResponse();
      });
      if (editLabel?.startsWith('修改')) {
        const input = page.getByRole('textbox', {
          name: editLabel.slice(2),
          exact: true,
        });
        await expect(input).toBeFocused();
        await input.press('Escape');
      } else await expect(target).toBeFocused();
    } finally {
      releaseResponse();
    }
  }

  const documentPath = `/workspaces/${workspace.workspace_id}/job-descriptions/${jd.job_description_id}`;
  await saveWhileMovingFocus(
    documentPath,
    page.getByRole('button', { name: '修改職務名稱', exact: true }),
    'ArrowRight',
  );
  await expect(level(5)).toBeChecked();

  const task = detail(page, '營運資訊分析：整理現況與辨識差異');
  const outcomes = task.getByRole('list', { name: '工作成果', exact: true });
  const outcomeText = '責任、完成期限與驗收方式清楚的改善追蹤表。';
  const controls = outcomes.getByRole('group', {
    name: `排序：${outcomeText}`,
    exact: true,
  });
  const up = controls.getByRole('button', { name: `上移${outcomeText}`, exact: true });
  const down = controls.getByRole('button', {
    name: `下移${outcomeText}`,
    exact: true,
  });
  await up.focus();
  await write(page, () => page.keyboard.press('Enter'));
  await expect(outcomes.locator('.inline-text__value').first()).toHaveText(outcomeText);
  await expect(up).toBeDisabled();
  await expect(down).toBeEnabled();
  await expect(down).toBeFocused();
  for (let move = 0; move < 2; move += 1)
    await write(page, () => page.keyboard.press('Enter'));
  await expect(outcomes.locator('.inline-text__value').last()).toHaveText(outcomeText);
  await expect(down).toBeDisabled();
  await expect(up).toBeEnabled();
  await expect(up).toBeFocused();

  const taskFixture = jd.tasks.find(
    (item) => item.name === '營運資訊分析：整理現況與辨識差異',
  );
  const outcomeFixture = taskFixture?.outcomes.find((item) => item.text === outcomeText);
  if (!taskFixture || !outcomeFixture) throw new Error('Missing task outcome fixture');
  await saveWhileMovingFocus(
    `${documentPath}/tasks/${taskFixture.id}`,
    task.getByRole('button', { name: '修改任務說明', exact: true }),
    'Enter',
  );
  await expect(outcomes.locator('.inline-text__value').nth(1)).toHaveText(outcomeText);
  const saved = await read(synthetic, workspace.workspace_id);
  expect(saved.baseline_competency_level).toBe(5);
  expect(saved.tasks.find((item) => item.id === taskFixture.id)?.outcomes[1]?.id).toBe(
    outcomeFixture.id,
  );
});

test('existing task creates and links each new definition in one saved version', async ({
  page,
  synthetic,
}) => {
  const { workspace, jd } = await synthetic.createCompleteDocument();
  const task = jd.tasks[0];
  if (!task) throw new Error('Missing task fixture');
  await page.goto(`/workspaces/${workspace.workspace_id}/jd`);
  await showDocument(page);
  let current = jd;
  for (const [label, kind, referenceField] of [
    ['知識', 'knowledge', 'knowledge_ids'],
    ['技能', 'skills', 'skill_ids'],
  ] as const) {
    const references = detail(page, task.name).getByRole('region', {
      name: `${task.name}的${label}`,
      exact: true,
    });
    await references
      .getByRole('button', { name: `建立並引用新${label}`, exact: true })
      .click();
    const name = `同次建立的${label}`;
    await references.getByLabel(`${label}名稱`, { exact: true }).fill(name);
    await references
      .getByLabel(`${label}說明（選填）`, { exact: true })
      .fill('合成的能力說明');
    const saved = await write(page, () =>
      references
        .getByRole('button', {
          name: `建立並引用${label}`,
          exact: true,
        })
        .click(),
    );
    expect(saved.version).toBe(current.version + 1);
    const definition = saved[kind].find((item) => item.name === name);
    expect(definition).toMatchObject({ name, description: '合成的能力說明' });
    expect(saved.tasks.find((item) => item.id === task.id)?.[referenceField]).toContain(
      definition?.id,
    );
    await expect(references.getByRole('link', { name, exact: true })).toBeVisible();
    current = saved;
  }
  expect(await read(synthetic, workspace.workspace_id)).toEqual(current);
});

for (const width of [1440, 390]) {
  test(`complete authoring journey at ${String(width)}px preserves atomic task content and shared definitions`, async ({
    page,
    synthetic,
  }, testInfo) => {
    test.setTimeout(180_000);
    await page.setViewportSize({ width, height: 1000 });
    const name = `完整旅程 ${randomUUID().slice(0, 8)}`;
    await page.goto('/workspaces');
    await page.getByRole('button', { name: '建立工作區', exact: true }).click();
    await page.getByRole('textbox', { name: '受訪者姓名', exact: true }).fill(name);
    const created = page.waitForResponse(
      (response) =>
        response.request().method() === 'POST' &&
        response.url().endsWith('/api/workspaces'),
    );
    await page.getByRole('button', { name: '建立並開啟', exact: true }).click();
    const workspace: unknown = await (await created).json();
    if (!validateWorkspaceResponse(workspace)) throw new Error('Invalid workspace');
    synthetic.track(workspace.workspace_id);
    await showDocument(page);
    expect((await read(synthetic, workspace.workspace_id)).version).toBe(1);
    await expect(page.locator('#jd-title')).toBeVisible();
    await edit(
      page,
      page.getByRole('button', { name: '修改職務名稱', exact: true }),
      '合成流程分析師',
    );
    await edit(
      page,
      page.getByRole('button', { name: '修改職務目的', exact: true }),
      '核對來源與作業差異。\n讓下一位接手者可以追蹤成果。',
    );
    await edit(
      page,
      page.getByRole('button', { name: '修改組織單位', exact: true }),
      '合成營運處',
    );
    await edit(
      page,
      page.getByRole('button', { name: '修改直屬主管', exact: true }),
      '合成主管',
    );
    const baselineLevel = page
      .getByRole('group', { name: '基準職能級別', exact: true })
      .getByRole('radio', { name: '第 3 級', exact: true });
    await write(page, () => baselineLevel.click());
    await expect(baselineLevel).toBeChecked();

    for (const dutyName of ['來源核對', '成果追蹤']) {
      await page.getByRole('button', { name: '新增職責', exact: true }).click();
      const form = page
        .locator('form')
        .filter({ has: page.getByRole('button', { name: '建立職責', exact: true }) });
      await form.getByLabel('職責名稱', { exact: true }).fill(dutyName);
      await write(page, () =>
        form.getByRole('button', { name: '建立職責', exact: true }).click(),
      );
      await expect(
        page.getByRole('heading', { name: dutyName, exact: true }),
      ).toBeVisible();
    }
    await detail(page, '來源核對')
      .getByRole('button', { name: '新增任務', exact: true })
      .click();
    const taskForm = page
      .locator('form')
      .filter({ has: page.getByRole('button', { name: '建立任務', exact: true }) });
    await taskForm.getByLabel('任務名稱', { exact: true }).fill('比對交接資料');
    await taskForm
      .getByLabel('任務說明（選填）', { exact: true })
      .fill('先核對定義，再確認差異。');
    await taskForm.getByText('一併加入成果、要求與知識技能', { exact: true }).click();
    for (const [label, texts] of [
      ['工作成果', ['附來源的分析報告', '差異追蹤清單']],
      ['工作要求', ['保留資料日期', '交叉核對定義', '列出待確認項目']],
    ] as const) {
      for (const [index, text] of texts.entries()) {
        await taskForm.getByRole('button', { name: `加入${label}`, exact: true }).click();
        await taskForm
          .getByLabel(`${label} ${String(index + 1)}`, { exact: true })
          .fill(text);
      }
    }
    await taskForm.getByRole('button', { name: '加入新知識', exact: true }).click();
    await taskForm.getByLabel('新知識名稱 1', { exact: true }).fill('資料定義');
    await taskForm.getByRole('button', { name: '加入新技能', exact: true }).click();
    await taskForm.getByLabel('新技能名稱 1', { exact: true }).fill('交叉核對');
    await capture(page, testInfo, `task-create-${String(width)}`);
    const added = await write(page, () =>
      taskForm.getByRole('button', { name: '建立任務', exact: true }).click(),
    );
    const task = detail(page, '比對交接資料');
    await expect(
      task.getByRole('list', { name: '工作成果', exact: true }).getByRole('listitem'),
    ).toHaveCount(2);
    await expect(
      task.getByRole('list', { name: '工作要求', exact: true }).getByRole('listitem'),
    ).toHaveCount(3);
    expect(added.tasks[0]).toMatchObject({
      knowledge_ids: [added.knowledge[0]?.id],
      skill_ids: [added.skills[0]?.id],
    });
    await expect(
      page
        .getByRole('list', { name: '知識定義', exact: true })
        .getByRole('link', { name: '比對交接資料', exact: true }),
    ).toBeVisible();

    await edit(
      page,
      task.getByRole('button', { name: '修改任務說明', exact: true }),
      '先核對定義，再確認並記錄差異。',
    );
    const taskLevel = task
      .getByRole('group', { name: '任務職能級別', exact: true })
      .getByRole('radio', { name: '第 4 級', exact: true });
    await write(page, () => taskLevel.click());
    await expect(taskLevel).toBeChecked();
    const outcomes = task.getByRole('list', { name: '工作成果', exact: true });
    await write(page, () =>
      outcomes.getByRole('button', { name: '上移差異追蹤清單', exact: true }).click(),
    );
    await expect(outcomes.locator('.inline-text__value').first()).toHaveText(
      '差異追蹤清單',
    );
    await edit(
      page,
      outcomes.getByRole('button', { name: '修改工作成果', exact: true }).first(),
      '已確認差異追蹤清單',
    );
    await task.getByRole('button', { name: '新增工作成果', exact: true }).click();
    const outcomeForm = task
      .locator('form')
      .filter({ has: page.getByRole('button', { name: '建立工作成果', exact: true }) });
    await outcomeForm.getByLabel('工作成果', { exact: true }).fill('驗收紀錄');
    await write(page, () =>
      outcomeForm.getByRole('button', { name: '建立工作成果', exact: true }).click(),
    );
    await confirmDelete(
      page,
      outcomes
        .getByRole('listitem')
        .last()
        .getByRole('button', { name: '刪除工作成果', exact: true }),
      '其他項目不受影響',
    );
    await expect(outcomes.getByRole('listitem')).toHaveCount(2);

    const references = task.getByRole('region', {
      name: '比對交接資料的知識',
      exact: true,
    });
    await write(page, () =>
      references
        .getByRole('button', { name: '解除知識「資料定義」的引用', exact: true })
        .click(),
    );
    await expect(
      references.getByRole('link', { name: '資料定義', exact: true }),
    ).toHaveCount(0);
    await expect(
      page
        .getByRole('list', { name: '知識定義', exact: true })
        .getByText('資料定義', { exact: true }),
    ).toBeVisible();
    await references.getByRole('button', { name: '引用既有知識', exact: true }).click();
    await references
      .getByRole('combobox', { name: '選取知識', exact: true })
      .selectOption({ label: '資料定義' });
    await write(page, () =>
      references.getByRole('button', { name: '引用知識', exact: true }).click(),
    );

    await write(page, () =>
      task
        .getByRole('combobox', { name: '移至職責', exact: true })
        .selectOption({ label: '成果追蹤' }),
    );
    await expect(
      detail(page, '成果追蹤').getByRole('heading', {
        name: '比對交接資料',
        exact: true,
      }),
    ).toBeVisible();
    await write(page, () =>
      page.getByRole('button', { name: '上移成果追蹤', exact: true }).click(),
    );
    await expect(
      page.locator('.jd-edit-duty > .jd-item-heading > [role="heading"]').first(),
    ).toHaveText('成果追蹤');
    await page.reload();
    await showDocument(page);
    await expect(
      detail(page, '成果追蹤').getByRole('heading', {
        name: '比對交接資料',
        exact: true,
      }),
    ).toBeVisible();
    const saved = await read(synthetic, workspace.workspace_id);
    expect(saved.baseline_competency_level).toBe(3);
    expect(saved.tasks[0]?.competency_level).toBe(4);
    expect(saved.tasks[0]?.outcomes.map((item) => item.text)).toEqual([
      '已確認差異追蹤清單',
      '附來源的分析報告',
    ]);
    expect(saved.tasks[0]?.requirements).toHaveLength(3);
    await task.scrollIntoViewIfNeeded();
    await capture(page, testInfo, `task-saved-${String(width)}`);

    await confirmDelete(
      page,
      page.getByRole('button', { name: '刪除職責「成果追蹤」', exact: true }),
      '任務與內容會保留',
    );
    await expect(
      detail(page, '未分類任務').getByRole('heading', {
        name: '比對交接資料',
        exact: true,
      }),
    ).toBeVisible();
    await confirmDelete(
      page,
      task.getByRole('button', { name: '刪除任務「比對交接資料」', exact: true }),
      '共用知識與技能定義會保留',
    );
    await expect(
      page.getByRole('heading', { name: '比對交接資料', exact: true }),
    ).toHaveCount(0);
    await expect(
      page
        .getByRole('list', { name: '知識定義', exact: true })
        .getByText('資料定義', { exact: true }),
    ).toBeVisible();
    await page.getByRole('link', { name: '工作區', exact: true }).click();
    await page.getByRole('button', { name: `變更 ${name} 的姓名`, exact: true }).click();
    await page
      .getByRole('textbox', { name: '受訪者姓名', exact: true })
      .fill(`${name} 已完成`);
    await page.getByRole('button', { name: '確認', exact: true }).click();
    await page
      .getByRole('button', { name: `刪除 ${name} 已完成 的工作區`, exact: true })
      .click();
    await page.getByRole('button', { name: '永久刪除', exact: true }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    expect(
      (await synthetic.request.get(`/workspaces/${workspace.workspace_id}`)).status(),
    ).toBe(404);
  });
}

test('shared catalog, collaboration and five condition families remain independently editable', async ({
  page,
  synthetic,
}, testInfo) => {
  test.setTimeout(180_000);
  const { workspace } = await synthetic.createCompleteDocument();
  await page.goto(`/workspaces/${workspace.workspace_id}/jd`);
  await showDocument(page);
  for (const label of ['知識', '技能']) {
    await page.getByRole('button', { name: `新增${label}`, exact: true }).click();
    const form = page
      .locator('form')
      .filter({ has: page.getByRole('button', { name: `建立${label}`, exact: true }) });
    await form.getByLabel(`${label}名稱`, { exact: true }).fill(`合成新${label}`);
    await write(page, () =>
      form.getByRole('button', { name: `建立${label}`, exact: true }).click(),
    );
    const list = page.getByRole('list', { name: `${label}定義`, exact: true });
    const item = list.getByRole('listitem').last();
    await edit(
      page,
      item.getByRole('button', { name: `修改${label}說明`, exact: true }),
      '可由兩個任務共用。',
    );
    await write(page, () =>
      item.getByRole('button', { name: `上移合成新${label}`, exact: true }).click(),
    );
    await expect(
      list.getByRole('listitem').nth(2).getByText(`合成新${label}`, { exact: true }),
    ).toBeVisible();
    const task = detail(page, '未分類：長字串與特殊內容核對');
    const references = task.getByRole('region', {
      name: `未分類：長字串與特殊內容核對的${label}`,
      exact: true,
    });
    await references
      .getByRole('button', { name: `引用既有${label}`, exact: true })
      .click();
    await references
      .getByRole('combobox', { name: `選取${label}`, exact: true })
      .selectOption({ label: `合成新${label}` });
    await write(page, () =>
      references.getByRole('button', { name: `引用${label}`, exact: true }).click(),
    );
    await confirmDelete(
      page,
      page.getByRole('button', { name: `刪除${label}「合成新${label}」`, exact: true }),
      '會解除 1 個任務的引用',
    );
    await expect(
      references.getByRole('link', { name: `合成新${label}`, exact: true }),
    ).toHaveCount(0);
    await expect(
      task.getByRole('heading', { name: '未分類：長字串與特殊內容核對', exact: true }),
    ).toBeVisible();
  }
  await page.getByRole('button', { name: '新增協作對象', exact: true }).click();
  const collaborationForm = page
    .locator('form')
    .filter({ has: page.getByRole('button', { name: '建立協作對象', exact: true }) });
  await collaborationForm
    .getByLabel('協作對象名稱', { exact: true })
    .fill('合成稽核窗口');
  await write(page, () =>
    collaborationForm.getByRole('button', { name: '建立協作對象', exact: true }).click(),
  );
  const collaborations = page.getByRole('list', { name: '協作對象', exact: true });
  await edit(
    page,
    collaborations
      .getByRole('listitem')
      .last()
      .getByRole('button', { name: '修改協作範圍', exact: true }),
    '確認缺漏與例外原因',
  );
  await write(page, () =>
    collaborations.getByRole('button', { name: '上移合成稽核窗口', exact: true }).click(),
  );
  await expect(
    collaborations
      .getByRole('listitem')
      .first()
      .getByText('合成稽核窗口', { exact: true }),
  ).toBeVisible();
  await confirmDelete(
    page,
    collaborations.getByRole('button', {
      name: '刪除協作對象「合成稽核窗口」',
      exact: true,
    }),
    '將刪除此協作對象及其範圍',
  );
  for (const label of ['工作環境', '工時與出差', '共通權限', '共通協作', '資格條件']) {
    await page.getByRole('button', { name: `新增${label}`, exact: true }).click();
    const form = page
      .locator('form')
      .filter({ has: page.getByRole('button', { name: `建立${label}`, exact: true }) });
    await form.getByLabel(label, { exact: true }).fill(`合成${label}補充`);
    await write(page, () =>
      form.getByRole('button', { name: `建立${label}`, exact: true }).click(),
    );
    await expect(
      page.getByRole('list', { name: label, exact: true }).getByRole('listitem'),
    ).toHaveCount(2);
  }
  const environment = page.getByRole('list', { name: '工作環境', exact: true });
  await edit(
    page,
    environment.getByRole('button', { name: '修改工作環境', exact: true }).last(),
    '合成工作環境修訂',
  );
  await write(page, () =>
    environment
      .getByRole('button', { name: '上移合成工作環境修訂', exact: true })
      .click(),
  );
  await expect(environment.locator('.inline-text__value').first()).toHaveText(
    '合成工作環境修訂',
  );
  await write(page, () =>
    environment
      .getByRole('combobox', { name: '條件分類', exact: true })
      .first()
      .selectOption('schedule_travel'),
  );
  const schedule = page.getByRole('list', { name: '工時與出差', exact: true });
  await expect(schedule.locator('.inline-text__value').last()).toHaveText(
    '合成工作環境修訂',
  );
  await confirmDelete(
    page,
    schedule
      .getByRole('listitem')
      .last()
      .getByRole('button', { name: '刪除工時與出差', exact: true }),
    '合成工作環境修訂',
  );
  await page.reload();
  await showDocument(page);
  await expect(environment.getByRole('listitem')).toHaveCount(1);
  await expect(schedule.getByRole('listitem')).toHaveCount(2);
  await page.getByRole('button', { name: '協作與條件', exact: true }).click();
  await capture(page, testInfo, 'conditions-edited-desktop');
});

for (const width of [1440, 390]) {
  test(`history pagination, read-only preview, arbitrary diff and restoration at ${String(width)}px`, async ({
    page,
    synthetic,
  }, testInfo) => {
    test.setTimeout(120_000);
    await page.setViewportSize({ width, height: 1000 });
    const { workspace, jd } = await synthetic.createCompleteDocument();
    await page.goto(`/workspaces/${workspace.workspace_id}/jd`);
    await showDocument(page);
    let saved: JobDescriptionResponse = jd;
    for (let index = 0; index < 4; index += 1)
      saved = await edit(
        page,
        page.getByRole('button', { name: '修改職務名稱', exact: true }),
        `歷史測試職務 ${String(index + 1)}`,
      );
    await page.getByRole('button', { name: '版本歷史', exact: true }).click();
    await expect(
      page.getByRole('heading', { name: '版本歷史', exact: true }),
    ).toBeVisible();
    await expect(page.getByRole('textbox')).toHaveCount(0);
    await page.getByRole('button', { name: '載入較早版本', exact: true }).click();
    await expect(
      page.getByRole('button', { name: '預覽版本 1', exact: true }),
    ).toBeVisible();
    await page
      .getByRole('button', { name: `預覽版本 ${String(jd.version)}`, exact: true })
      .click();
    await expect(
      page
        .locator('.history-preview')
        .getByRole('heading', { name: '營運規劃與流程改善專員', level: 1, exact: true }),
    ).toBeVisible();
    const returnToVersions = page.getByRole('button', {
      name: '返回版本清單',
      exact: true,
    });
    if (width === 390) {
      const contentHeading = page
        .getByRole('region', { name: '版本內容', exact: true })
        .getByRole('heading', { name: `版本 ${String(jd.version)}`, exact: true });
      await expectFocusedInViewport(contentHeading);
      const listDimensions = await page
        .getByRole('complementary', { name: '歷史版本', exact: true })
        .getByRole('list')
        .evaluate((element) => ({
          height: element.clientHeight,
          contentHeight: element.scrollHeight,
        }));
      expect(listDimensions.height).toBeLessThanOrEqual(280);
      expect(listDimensions.contentHeight).toBeGreaterThan(listDimensions.height);
      await returnToVersions.click();
      await expectFocusedInViewport(
        page.getByRole('heading', { name: '全部版本', exact: true }),
      );
      await page
        .getByRole('button', { name: `預覽版本 ${String(jd.version)}`, exact: true })
        .click();
      await expectFocusedInViewport(contentHeading);
    } else {
      await expect(returnToVersions).toBeHidden();
    }
    await page.getByRole('button', { name: '比較版本', exact: true }).click();
    await expect(
      page.locator('.history-difference').getByText('歷史測試職務 4', { exact: true }),
    ).toBeVisible();
    await page
      .getByRole('combobox', { name: '比較起始版本', exact: true })
      .selectOption(String(jd.version + 1));
    await page
      .getByRole('combobox', { name: '比較目標版本', exact: true })
      .selectOption(String(jd.version + 2));
    await expect(
      page.locator('.history-difference').getByText('歷史測試職務 1', { exact: true }),
    ).toBeVisible();
    await expect(
      page.locator('.history-difference').getByText('歷史測試職務 2', { exact: true }),
    ).toBeVisible();
    if (width === 390) await capture(page, testInfo, 'history-diff-390');
    await page
      .getByRole('combobox', { name: '比較起始版本', exact: true })
      .selectOption(String(jd.version + 2));
    await expect(page.getByText(/沒有內容差異|無內容差異/)).toBeVisible();
    await page
      .getByRole('button', { name: `預覽版本 ${String(jd.version)}`, exact: true })
      .click();
    await page.getByRole('button', { name: '恢復此版本', exact: true }).click();
    await expect(page.getByRole('dialog')).toContainText(
      `取代目前版本 ${String(saved.version)}`,
    );
    await page.getByRole('button', { name: '確認恢復', exact: true }).click();
    await showDocument(page);
    await expect(
      page.locator('#pane-jd').getByText('營運規劃與流程改善專員', { exact: true }),
    ).toBeVisible();
    const restored = await read(synthetic, workspace.workspace_id);
    expect(restored.version).toBe(saved.version + 1);
    expect(restored.tasks).toEqual(jd.tasks);
    await page.getByRole('button', { name: '版本歷史', exact: true }).click();
    await expect(
      page.getByRole('button', {
        name: `預覽版本 ${String(restored.version)}`,
        exact: true,
      }),
    ).toContainText(`恢復自版本 ${String(jd.version)}`);
    await expect(
      page.getByRole('button', {
        name: `預覽版本 ${String(saved.version)}`,
        exact: true,
      }),
    ).toBeVisible();
  });
}

test('refresh retains unsubmitted text and task draft without replay, and protects history restore', async ({
  page,
  synthetic,
}, testInfo) => {
  const { workspace, jd } = await synthetic.createCompleteDocument();
  const other = await synthetic.createWorkspace('隔離核對');
  await page.goto(`/workspaces/${workspace.workspace_id}/jd`);
  await showDocument(page);
  const title = page.getByRole('textbox', { name: '職務名稱', exact: true });
  await openInlineEditor(page.getByRole('button', { name: '修改職務名稱', exact: true }));
  await title.fill('重新整理後決定的名稱');
  page.on('dialog', (dialog) => dialog.accept());
  await page.reload();
  await showDocument(page);
  await openInlineEditor(page.getByRole('button', { name: '修改職務名稱', exact: true }));
  await expect(title).toHaveValue('重新整理後決定的名稱');
  expect((await read(synthetic, workspace.workspace_id)).version).toBe(jd.version);
  await expect(page.getByRole('alert')).toContainText('輸入');
  await page.getByRole('button', { name: '版本歷史', exact: true }).click();
  await expect(
    page.getByRole('status').filter({ hasText: '請先處理保留的輸入' }),
  ).toBeVisible();
  await page.goto(`/workspaces/${workspace.workspace_id}/jd/history`);
  await expect(page.getByRole('alert')).toContainText('未確認輸入');
  await expect(page.getByRole('button', { name: '恢復此版本', exact: true })).toHaveCount(
    0,
  );
  await page.getByRole('link', { name: '返回編輯頁處理輸入', exact: true }).click();
  await showDocument(page);
  await openInlineEditor(page.getByRole('button', { name: '修改職務名稱', exact: true }));
  await page.getByRole('button', { name: '重新讀取', exact: true }).click();
  await page.getByRole('button', { name: '已核對，繼續編輯', exact: true }).click();
  await write(page, () =>
    page.getByRole('button', { name: '套用輸入', exact: true }).click(),
  );
  await expect(page.getByText('重新整理後決定的名稱', { exact: true })).toBeVisible();
  const unclassified = detail(page, '未分類任務');
  await unclassified.getByRole('button', { name: '新增任務', exact: true }).click();
  const form = unclassified.locator('form');
  await form.getByLabel('任務名稱', { exact: true }).fill('刷新保留的新任務');
  await page.reload();
  await showDocument(page);
  await expect(form.getByLabel('任務名稱', { exact: true })).toHaveValue(
    '刷新保留的新任務',
  );
  expect((await read(synthetic, workspace.workspace_id)).tasks).toHaveLength(
    jd.tasks.length,
  );
  await capture(page, testInfo, 'recovered-task-draft');
  await page.goto(`/workspaces/${other.workspace_id}/jd`);
  await showDocument(page);
  await expect(page.locator('#jd-title')).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await page.goto(`/workspaces/${workspace.workspace_id}/jd`);
  await showDocument(page);
  await expect(form.getByLabel('任務名稱', { exact: true })).toHaveValue(
    '刷新保留的新任務',
  );
  await page.getByRole('button', { name: '重新讀取', exact: true }).click();
  await page.getByRole('button', { name: '已核對，繼續編輯', exact: true }).click();
  await write(page, () =>
    form.getByRole('button', { name: '建立任務', exact: true }).click(),
  );
  await expect(
    page.getByRole('heading', { name: '刷新保留的新任務', exact: true }),
  ).toBeVisible();
  await page.reload();
  await showDocument(page);
  await expect(page.getByRole('alert')).toHaveCount(0);
  expect((await read(synthetic, workspace.workspace_id)).tasks).toHaveLength(
    jd.tasks.length + 1,
  );
});

test('real version conflict preserves local text until reviewed and explicitly reapplied', async ({
  page,
  synthetic,
}, testInfo) => {
  const { workspace, jd } = await synthetic.createCompleteDocument();
  const task = jd.tasks.at(-1);
  if (!task) throw new Error('Missing task fixture');
  const taskPath = `/workspaces/${workspace.workspace_id}/job-descriptions/${jd.job_description_id}/tasks/${task.id}`;
  const browserWrites: number[] = [];
  page.on('request', (request) => {
    if (request.method() === 'PATCH' && request.url().endsWith(taskPath)) {
      const body = request.postDataJSON() as { expected_version: number };
      browserWrites.push(body.expected_version);
    }
  });
  await page.goto(`/workspaces/${workspace.workspace_id}/jd`);
  await showDocument(page);
  const taskEditor = page.locator(`#jd-task-${task.id}`);
  const description = taskEditor.getByRole('textbox', { name: '任務說明', exact: true });
  const localText = '本人核對後補上的交接說明';
  await openInlineEditor(
    taskEditor.getByRole('button', { name: '修改任務說明', exact: true }),
  );
  await description.fill(localText);
  expect(
    await page.locator('#pane-jd .pane-scroll').evaluate((element) => element.scrollTop),
  ).toBeGreaterThan(0);

  // Independent HTTP client commits after this browser loaded its version.
  const remote = await synthetic.request.patch(taskPath, {
    data: {
      expected_version: jd.version,
      name: '另一位顧問更新的任務名稱',
      description: '另一位顧問已保存的說明',
    },
  });
  expect(remote.status(), await remote.text()).toBe(200);
  const remoteDocument: unknown = await remote.json();
  if (!validateJobDescriptionResponse(remoteDocument))
    throw new Error('Invalid remote JD');
  const conflictResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'PATCH' && response.url().endsWith(taskPath),
  );
  await description.press('Control+Enter');
  expect((await conflictResponse).status()).toBe(409);
  await expect(description).toHaveValue(localText);
  const notice = page.getByRole('alert');
  await expect(notice).toContainText('本次未保存');
  await expect(notice).toBeInViewport({ ratio: 1 });
  expect(browserWrites).toEqual([jd.version]);
  expect((await read(synthetic, workspace.workspace_id)).tasks.at(-1)?.description).toBe(
    '另一位顧問已保存的說明',
  );
  await capture(page, testInfo, 'version-conflict-deep-page');

  await notice.getByRole('button', { name: '重新讀取', exact: true }).click();
  await expect(notice).toContainText('已讀取目前內容');
  await expect(description).toHaveValue(localText);
  await expect(taskEditor).toContainText('目前內容：另一位顧問已保存的說明');
  await notice.getByRole('button', { name: '已核對，繼續編輯', exact: true }).click();
  expect(browserWrites).toEqual([jd.version]);
  expect((await read(synthetic, workspace.workspace_id)).version).toBe(
    remoteDocument.version,
  );
  await write(page, () =>
    taskEditor.getByRole('button', { name: '套用輸入', exact: true }).click(),
  );
  expect(browserWrites).toEqual([jd.version, remoteDocument.version]);
  await expect(notice).toHaveCount(0);
  await page.reload();
  await showDocument(page);
  await expect(taskEditor.getByText(localText, { exact: true })).toBeVisible();
  await expect(
    taskEditor.getByRole('heading', { name: '另一位顧問更新的任務名稱', exact: true }),
  ).toBeVisible();
  const finalDocument = await read(synthetic, workspace.workspace_id);
  expect(finalDocument.version).toBe(remoteDocument.version + 1);
  expect(finalDocument.tasks.at(-1)).toMatchObject({
    name: '另一位顧問更新的任務名稱',
    description: localText,
  });
});
