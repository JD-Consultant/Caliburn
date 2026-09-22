import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { inspect } from 'node:util';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createSlateEditor, createSlatePlugin } from 'platejs';
import { before as fixture, nodeTypes, textOf } from './fixture.mjs';
import { nativeDiff, nativeOperations, ReadOnlyDocument, updateText } from './results/render-server.mjs';

// Separate process from prepare.mjs; all dynamic before/after/op data read from disk.
const materialsBytes = await fs.readFile('public/materials.json', 'utf8');
const materials = JSON.parse(materialsBytes);
const full = materials.cases[0];
const source = await fs.readFile('results/r2-source.md', 'utf8');
const checks = [];
function check(name, action) { try { action(); checks.push({ name, pass: true }); } catch (error) { checks.push({ name, pass: false, error: error.message }); } }
const walk = nodes => nodes.flatMap(n => [n, ...(n.children ? walk(n.children) : [])]);
const compact = text => text.replace(/\s/g, '');
// Validation-only normalization of the source sample's literal Markdown syntax;
// never generates editor nodes and is not used by App/runtime.
const expectedText = source.split(/\r?\n/).filter(line => line.trim() && !/^\|[-|]+\|$/.test(line.trim()) && line.trim() !== '---').map(line => line.replace(/^[#>]+\s*/, '').replace(/^\s*-\s+/, '').replace(/\*\*/g, '').replace(/\[([^\]]+)\]\([^)]*\)/g, '$1').replace(/\|/g, '')).join('');
check('完整 r2 原文逐字保留（只移除原稿 Markdown 標記及空白）', () => assert.equal(compact(full.before.map(textOf).join('')), compact(expectedText)));
check('手寫 fixture 經原生初始化仍保持完整乾淨值', () => assert.deepEqual(full.before, fixture));
check('包含 3 張真表格與至少一層 ul/li 子清單', () => { assert.equal(walk(full.before).filter(n => n.type === 'table').length, 3); assert.ok(walk(full.before).some(n => n.type === 'li' && n.children.some(c => c.type === 'ul'))); });
const diffs = [];
const htmls = [];
for (const entry of materials.cases) {
  const originalBefore = structuredClone(entry.before);
  const originalAfter = structuredClone(entry.after);
  const editor = createSlateEditor({ plugins: nodeTypes.map(key => createSlatePlugin({ key, node: { isElement: true } })), nodeId: false, value: structuredClone(entry.after) });
  check(`${entry.id}：保存後全新程序/editor 重開精確相等`, () => assert.deepEqual(editor.children, entry.after));
  const diff = nativeDiff(entry.before, entry.after);
  diffs.push({ id: entry.id, diff });
  check(`${entry.id}：原生 computeDiff 未改動乾淨快照`, () => { assert.deepEqual(entry.before, originalBefore); assert.deepEqual(entry.after, originalAfter); assert.ok(!walk(entry.after).some(n => n.diff || n.diffOperation)); });
  check(`${entry.id}：真實 operation 批次保存且回呼後清空`, () => { assert.ok(entry.operationsClearedAfterCallback); assert.ok(entry.batches.flatMap(b => b.operations).length > 0); assert.deepEqual(entry.batches.at(-1).value, entry.after); });
  for (const [label, value] of [['before', entry.before], ['after', entry.after], ['diff', diff]]) {
    const html = renderToStaticMarkup(React.createElement(ReadOnlyDocument, { value, name: `${entry.id}-${label}` }));
    htmls.push({ id: entry.id, label, html });
    await fs.writeFile(`results/${entry.id}-${label}.html`, html);
    check(`${entry.id}/${label}：真正 React Plate SSR 有 Slate readonly editor`, () => { assert.ok(html.includes('data-slate-editor="true"')); assert.ok(html.includes('contentEditable="false"') || html.includes('contenteditable="false"')); });
  }
}
const fullDiff = diffs[0].diff;
check('同 ID 屬性＋文字雙改：原生刪／增兩節點均保留', () => { const nodes = walk(fullDiff).filter(n => n.id === 'task3-description'); assert.equal(nodes.length, 2); assert.deepEqual(nodes.map(n => n.diffOperation.type), ['delete', 'insert']); assert.ok(textOf(nodes[1]).includes('同 ID 正文也已更新')); });
const fullDiffHtml = htmls.find(x => x.id === 'full-r2' && x.label === 'diff').html;
check('SSR 同 ID：兩個 data-fixture-id 與新舊正文均輸出', () => { assert.equal((fullDiffHtml.match(/data-fixture-id="task3-description"/g) || []).length, 2); assert.ok(fullDiffHtml.includes('同 ID 正文也已更新')); assert.ok(fullDiffHtml.includes('data-diff-type="delete"')); assert.ok(fullDiffHtml.includes('data-diff-type="insert"')); });
check('SSR before/after 全部文字節點均實際輸出，不只是資料留存', () => {
  for (const label of ['before', 'after']) {
    const html = htmls.find(x => x.id === 'full-r2' && x.label === label).html;
    const visible = html.replace(/<[^>]*>/g, '').replace(/&#xFEFF;|&#65279;|\uFEFF/g, '').replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#x27;/g, "'");
    assert.equal(compact(visible), compact(full[label].map(textOf).join('')));
  }
});
check('SSR before/after/diff 全部有 3 張 table/tbody、tr/td 及真子清單', () => {
  for (const { html } of htmls.filter(x => x.id === 'full-r2')) {
    assert.equal((html.match(/<table\b/g) || []).length, 3);
    assert.equal((html.match(/<tbody>/g) || []).length, 3);
    assert.ok(html.includes('<tr ')); assert.ok(html.includes('<td '));
    assert.match(html, /<li\b[^>]*>[\s\S]*?<ul\b/);
    assert.ok(!/<tbody>\s*<div/.test(html));
    assert.ok(!/<tr\b[^>]*>\s*<div/.test(html));
  }
});
const attrs = nativeOperations(fullDiff).find(x => x.id === 'task2-description').operation;
check('原生 element 更新保留 0/false/object/移除；說明輸出不丟 undefined', () => { assert.equal(attrs.newProperties.score, 0); assert.equal(attrs.newProperties.approved, false); assert.deepEqual(attrs.newProperties.provenance, { source: 'fixture-after', revision: 2 }); assert.ok(Object.hasOwn(attrs.newProperties, 'obsolete')); assert.equal(attrs.newProperties.obsolete, undefined); const text = updateText(attrs); assert.ok(text.includes('obsolete:')); assert.ok(text.includes('undefined')); assert.ok(text.includes('fixture-after')); assert.ok(!text.includes('[object Object]')); });
const score = materials.cases.find(c => c.id === 'leaf-score-zero');
const scoreDiff = diffs.find(c => c.id === 'leaf-score-zero').diff;
check('已知反例仍成立：leaf 0 在乾淨值與 set_node 都精確，diff 卻是 undefined', () => { assert.equal(score.after[0].children[0].score, 0); const op = score.batches[0].operations.find(op => op.type === 'set_node'); assert.equal(op.properties.score, 1); assert.equal(op.newProperties.score, 0); const d = nativeOperations(scoreDiff).find(x => x.operation.type === 'update').operation; assert.equal(d.newProperties.score, undefined); });
const empty = materials.cases.find(c => c.id === 'empty-mark');
check('已知反例仍成立：empty bold→italic 有保存的 set_node，diff 沒有 operation', () => { assert.equal(empty.before[0].children[0].bold, true); assert.equal(empty.after[0].children[0].italic, true); assert.ok(!Object.hasOwn(empty.after[0].children[0], 'bold')); assert.ok(empty.batches[0].operations.some(op => op.type === 'set_node' && op.newProperties.italic === true)); assert.equal(nativeOperations(diffs.find(c => c.id === 'empty-mark').diff).length, 0); });
const bytesAfterRecompute = await fs.readFile('public/materials.json', 'utf8');
check('重算前後重新讀取的磁碟保存材料位元未變', () => assert.equal(createHash('sha256').update(materialsBytes).digest('hex'), createHash('sha256').update(bytesAfterRecompute).digest('hex')));

// This text file is diagnostic only, not a diff persistence format. inspect preserves undefined.
await fs.writeFile('results/recomputed-native-diff.txt', inspect(diffs, { depth: null, maxArrayLength: null, compact: false }));
const report = { executedAt: new Date().toISOString(), node: process.version, newProcessReadFromDisk: true, passed: checks.filter(c => c.pass).length, failed: checks.filter(c => !c.pass).length, knownNativeDiffFailures: 2, checks, limitations: ['SSR is not browser DOM/visual acceptance.', 'Two known native diff failures remain unrepaired.', 'Finite readonly renderer only; no general editor/schema/diff/rollback.', 'Saved files are research fixture materials, not production durable authority.'] };
await fs.writeFile('results/ui-node-results.json', JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
process.exitCode = report.failed ? 1 : 0;
