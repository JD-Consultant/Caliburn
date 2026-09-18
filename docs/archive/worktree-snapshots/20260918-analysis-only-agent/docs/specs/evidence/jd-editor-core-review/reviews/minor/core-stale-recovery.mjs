import { chromium, expect } from '@playwright/test';
import { writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const browser = await chromium.launch({ channel: 'chrome', headless: false });
const context = await browser.newContext({ viewport: { width: 1500, height: 1050 } });
const page = await context.newPage();
const result = { status: 'RUNNING', browser: browser.version(), headed: true, OS_IME: 'NOT RUN', product_provider_calls: 0, requests: [], errors: [] };
page.on('request', r => result.requests.push({ method: r.method(), url: r.url(), body: r.postData() }));
page.on('pageerror', e => result.errors.push(String(e)));
const evidence = resolve('../../../scratch/core-stale-browser');
const editor = page.getByRole('textbox', { name: '職務說明書正文' });
let document;
async function api(path, body) {
  const url = `http://127.0.0.1:8091/documents/${document}${path}`;
  const response = body === undefined ? await context.request.get(url) : await context.request.post(url, { data: body });
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}
try {
  await page.goto('http://127.0.0.1:3001');
  await page.getByLabel('文件名稱').fill('核心審查・舊版手改恢復 ' + Date.now());
  await page.getByRole('button', { name: '建立文件', exact: true }).click();
  await page.waitForURL('**/workspace/**');
  document = page.url().split('/').at(-1);
  result.document = document;
  await expect(editor).toBeEditable();
  result.before = await api('/jd');
  await page.getByLabel('補充或更正你的工作').fill('這段補充先不要送出');
  await editor.click();
  await page.keyboard.insertText('員工尚未保存的更正');
  await expect(editor).toContainText('員工尚未保存的更正');
  const other = structuredClone(result.before.fragment);
  const firstText = nodes => { for (const n of nodes) { if ('text' in n) return n; const found = firstText(n.children ?? []); if (found) return found; } };
  firstText(other).text = '伺服器已保存的新工作';
  const otherKey = crypto.randomUUID();
  result.other = await api('/jd/manual-save', { request_key: otherKey, base_revision_ref: result.before.revision_ref, value: other });
  expect(result.other.status).toBe('committed');
  const [failed] = await Promise.all([
    page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/jd/manual-save')),
    page.getByRole('button', { name: '保存', exact: true }).click(),
  ]);
  result.failed = await failed.json();
  expect(result.failed.status).toBe('stale_base');
  expect(result.failed.receipt_durability).toBe('confirmed');
  await expect(page.getByText('尚待處理的送出候選', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '再次送出同一份', exact: true })).toBeDisabled();
  await expect(page.getByText(/這份候選未保存，已保留供查看/)).toBeVisible();
  await expect(editor).toContainText('員工尚未保存的更正');
  result.candidateBefore = await page.evaluate(id => localStorage.getItem('caliburn:jd-plate-clean-v2:submission:' + id), document);
  page.once('dialog', d => d.accept());
  await page.getByRole('button', { name: '捨棄畫面修改並載入最新稿', exact: true }).click();
  await expect(editor).toContainText('伺服器已保存的新工作');
  await expect(page.getByLabel('補充或更正你的工作')).toHaveValue('這段補充先不要送出');
  expect(await page.evaluate(id => localStorage.getItem('caliburn:jd-plate-clean-v2:submission:' + id), document)).toBe(result.candidateBefore);
  expect(await page.locator('[contenteditable=true]').count()).toBe(1);
  await page.screenshot({ path: evidence + '.png', fullPage: true });
  result.recoveredAX = await page.locator('main').ariaSnapshot();
  // Enter the needed candidate text into the current editor; OS clipboard and
  // human IME are separate evidence, not claimed by keyboard.insertText.
  const leaf = editor.locator('[data-slate-string]').first();
  await leaf.evaluate(el => { const range = document.createRange(); range.selectNodeContents(el); range.collapse(false); const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range); });
  await page.keyboard.insertText('；員工尚未保存的更正');
  await expect(editor).toContainText('伺服器已保存的新工作；員工尚未保存的更正');
  page.once('dialog', d => d.accept());
  await page.getByRole('button', { name: '捨棄這份候選', exact: true }).click();
  const [saved] = await Promise.all([
    page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/jd/manual-save')),
    page.getByRole('button', { name: '保存', exact: true }).click(),
  ]);
  result.saved = await saved.json();
  expect(result.saved.status).toBe('committed');
  await expect(page.getByRole('button', { name: '保存', exact: true })).toBeDisabled();
  result.after = await api('/jd');
  expect(firstText(result.after.fragment).text).toBe('伺服器已保存的新工作；員工尚未保存的更正');
  expect(await page.evaluate(id => localStorage.getItem('caliburn:jd-plate-clean-v2:submission:' + id), document)).toBeNull();
  await expect(page.getByLabel('補充或更正你的工作')).toHaveValue('這段補充先不要送出');
  expect(result.requests.filter(r => r.method === 'POST' && r.url.endsWith('/runs'))).toEqual([]);
  expect(result.requests.filter(r => !['http://127.0.0.1:3001', 'http://127.0.0.1:8091'].includes(new URL(r.url).origin))).toEqual([]);
  expect(result.errors).toEqual([]);
  result.status = 'PASS';
} catch (error) {
  result.status = 'FAIL'; result.failure = String(error);
  result.failureAX = await page.locator('body').ariaSnapshot().catch(() => 'unavailable');
  await page.screenshot({ path: evidence + '-failure.png', fullPage: true }).catch(() => {});
  throw error;
} finally {
  await writeFile(evidence + '.json', JSON.stringify(result, null, 2));
  await context.close(); await browser.close();
}
console.log(JSON.stringify({ status: result.status, document, product_provider_calls: 0 }));
