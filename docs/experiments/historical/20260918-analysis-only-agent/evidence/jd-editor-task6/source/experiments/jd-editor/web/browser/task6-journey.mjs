import { chromium, expect } from '@playwright/test';
import { readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const evidence = resolve('../../../scratch');
const fixture = JSON.parse(await readFile(resolve('../fixtures/core-scenario.json'), 'utf8'));
const reopened = process.argv.includes('--reopened');
const previous = reopened ? JSON.parse(await readFile(resolve(evidence, 'task6-browser-initial.json'), 'utf8')) : null;
const browser = await chromium.launch({ channel: 'chrome', headless: false });
const context = await browser.newContext({ viewport: { width: 1500, height: 1050 } });
const page = await context.newPage();
const network = [], errors = [], cases = [];
const result = { phase: reopened ? 'reopened' : 'initial', browser: browser.version(), headed: true, OS_IME: 'NOT RUN', network, errors, cases };
page.on('request', r => network.push({ method: r.method(), url: r.url(), body: r.postData() }));
page.on('pageerror', error => errors.push(String(error)));
let document;
const api = async (path, body) => {
  const url = `http://127.0.0.1:8091/documents/${document}${path}`;
  const response = body === undefined ? await context.request.get(url) : await context.request.post(url, { data: body });
  expect(response.ok(), `${response.status()} ${await response.text()}`).toBeTruthy();
  return response.json();
};
const saved = () => api('/jd');
const editor = page.getByRole('textbox', { name: '職務說明書正文' });
const textOf = value => Array.isArray(value) ? value.map(textOf).join('') : typeof value === 'object' ? (value.text ?? textOf(value.children ?? [])) : '';
const elements = value => value.flatMap(n => n.type ? [n, ...elements(n.children)] : []);
const plain = value => Array.isArray(value) ? value.map(plain) : value && typeof value === 'object' ? Object.fromEntries(Object.entries(value).filter(([k]) => !['id','source_refs','knowledge_ids','skill_ids'].includes(k)).map(([k,v]) => [k,plain(v)])) : value;
async function send(key) {
  if (await page.getByRole('button', { name: '改為純聊天', exact: true }).isVisible()) await page.getByRole('button', { name: '改為純聊天', exact: true }).click();
  await page.getByLabel('補充或更正你的工作').fill(fixture.utterances[key]);
  const [response] = await Promise.all([
    page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/runs')),
    page.getByRole('button', { name: '送出', exact: true }).click(),
  ]);
  expect(response.status()).toBe(202);
  const run = await response.json();
  await expect.poll(async () => (await api(`/runs/${run.id}`)).status, { timeout: 45000 }).toBe('completed');
  await expect(editor).toBeEditable({ timeout: 15000 });
  return api(`/runs/${run.id}`);
}
async function capture() {
  const current = await saved(), histories = [], sources = {};
  let head = current;
  for (let i = 0; head.change_refs.length && i < 20; i++) {
    const change = await api('/jd/changes/read', { change_ref: head.change_refs[0] });
    histories.push(change);
    head = await api('/jd/read', { revision_ref: change.before_revision_ref });
  }
  expect(head.change_refs).toEqual([]);
  for (const ref of new Set(elements(current.fragment).flatMap(n => n.source_refs ?? []))) sources[ref] = await api(`/sources?reference=${encodeURIComponent(ref)}`);
  return { current, histories, sources, messages: await api('/messages') };
}
try {
  if (reopened) {
    document = previous.document;
    await page.goto(`http://127.0.0.1:3001/workspace/${document}`);
    await expect(editor).toBeEditable();
    result.recovered = await capture();
    expect(result.recovered).toEqual(previous.snapshot);
    for (const run of previous.runs) expect(await api(`/runs/${run.id}`)).toEqual(run);
    cases.push('new API process + fresh browser context recovered exact current, every history/source, messages and original run results');
  } else {
    await page.goto('http://127.0.0.1:3001');
    await page.getByLabel('文件名稱').fill('Task6 完整旅程 '+Date.now());
    await page.getByRole('button', { name: '建立文件', exact: true }).click();
    await page.waitForURL('**/workspace/**');
    document = page.url().split('/').at(-1);
    await expect(editor).toBeEditable();
    const initial = await saved();
    result.runs = [await send('intro')];
    expect((await saved()).revision_ref).toBe(initial.revision_ref);
    cases.push('create blank document and insufficient interview without JD revision');
    result.runs.push(await send('draft'));
    const draft = await saved();
    expect(plain(draft.fragment)).toEqual(fixture.expected_initial_content);
    expect(elements(draft.fragment).filter(n => n.type === 'jd_task')).toHaveLength(2);
    await expect(editor).toContainText(fixture.monthly_original);
    cases.push('same-page first draft through actual native writes and shared knowledge/skill links');
    result.runs.push(await send('correct'));
    await expect(editor).toContainText(fixture.monthly_corrected);
    await expect(editor).toContainText(fixture.fault_description);
    await page.getByRole('button', { name: '這次改動', exact: true }).click();
    const changes = page.getByRole('region', { name: '確切改動' });
    await expect(changes.locator(':scope > details').nth(0).getByText(fixture.monthly_original, { exact: true })).toBeVisible();
    await expect(changes.locator(':scope > details').nth(1).getByText(fixture.monthly_corrected, { exact: true })).toBeVisible();
    expect(await page.locator('[contenteditable=true]').count()).toBe(1);
    cases.push('correction and exact before/after visible alongside one editable JD');
    const correction = await saved();
    const requirement = elements(correction.fragment).find(n => textOf(n) === '未排除問題交接操作員');
    const leaf = page.locator(`.jd-editable [data-jd-id="${requirement.id}"] [data-slate-string]`).first();
    await leaf.evaluate(el => { const range = document.createRange(); range.selectNodeContents(el); const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range); });
    expect(await page.evaluate(() => window.getSelection().toString())).toBe('未排除問題交接操作員');
    await page.keyboard.insertText(fixture.manual_text);
    await expect(editor).toContainText(fixture.manual_text);
    await page.getByRole('button', { name: '保存', exact: true }).click();
    await expect.poll(async () => textOf((await saved()).fragment)).toContain(fixture.manual_text);
    await expect(page.getByRole('button', { name: '保存', exact: true })).toBeDisabled();
    result.runs.push(await send('continue'));
    await expect(editor).toContainText(fixture.manual_text);
    await expect(editor).toContainText(fixture.continued_purpose);
    const beforeThanks = await saved();
    result.runs.push(await send('thanks'));
    expect(await saved()).toEqual(beforeThanks);
    cases.push('actual DOM text edit/save -> AI continuation preserves manual text -> pure interview does not rewrite');
    result.snapshot = await capture();
    expect(result.snapshot.histories).toHaveLength(5);
  }
  result.document = document;
  await page.getByRole('button', { name: '讀取上一筆歷史', exact: true }).click();
  await expect(page.getByText('歷史 1・顧問修改', { exact: true })).toBeVisible();
  await page.locator('.jd-editable .source').first().click();
  await expect(page.getByText('依據・已保存的原問答', { exact: true })).toBeVisible();
  await expect(page.getByText(fixture.utterances.draft, { exact: true })).toHaveCount(2);
  expect(await page.locator('[contenteditable=true]').count()).toBe(1);
  cases.push('history and canonical source read in same page, no second editable document');
  result.ax = await page.locator('main').ariaSnapshot();
  await page.screenshot({ path: resolve(evidence, `task6-browser-${result.phase}.png`), fullPage: true });
  expect(errors).toEqual([]);
  expect(network.filter(r => !['http://127.0.0.1:3001','http://127.0.0.1:8091'].includes(new URL(r.url).origin))).toEqual([]);
  result.status = 'PASS';
} catch (error) {
  result.status = 'FAIL'; result.failure = String(error); result.document = document;
  result.ax = await page.locator('body').ariaSnapshot().catch(() => 'unavailable');
  await page.screenshot({ path: resolve(evidence, `task6-browser-${result.phase}-failure.png`), fullPage: true }).catch(() => {});
  throw error;
} finally {
  await writeFile(resolve(evidence, `task6-browser-${result.phase}.json`), JSON.stringify(result, null, 2));
  await context.close(); await browser.close();
}
console.log(JSON.stringify({ status: result.status, document, cases, headed: true }));
