import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { execFileSync, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { checkDocuments, selectDocuments } from './check-docs.mjs';
import { findDocuments, parseDocument } from './documentation.mjs';

async function fixture(t, files) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'caliburn-docs-'));
  t.after(() => {
    assert.equal(path.dirname(root), path.resolve(os.tmpdir()));
    assert.ok(path.basename(root).startsWith('caliburn-docs-'));
    return rm(root, { recursive: true, force: true });
  });
  for (const [file, text] of Object.entries(files)) {
    await mkdir(path.dirname(path.join(root, file)), { recursive: true });
    await writeFile(path.join(root, file), text);
  }
  return root;
}

test('checks referenced Chinese and duplicate headings, explicit anchors and images', async t => {
  const root = await fixture(t, {
    'docs/README.md': '[一](detail.md#目前焦點) [二](detail.md#目前焦點-1) [舊](detail.md#old) ![圖](images/a.png)\n[參考][one]\n\n[one]: detail.md#目前焦點\n',
    'docs/detail.md': '# 目前焦點\n# 目前焦點\n<a id="old"></a>\n',
    'docs/images/a.png': 'fixture',
  });
  const result = await checkDocuments(root, ['docs/README.md']);
  assert.deepEqual(result.errors, []);
  assert.equal(result.links, 5);
});

test('reports missing files and anchors while ignoring code examples and external URLs', async t => {
  const root = await fixture(t, {
    'docs/README.md': '[缺檔](missing.md) [缺節](detail.md#missing)\n```md\n[示例](not-a-file.md)\n```\n`[示例](also-not-a-file.md)` [外部](https://example.com/#x)\n',
    'docs/detail.md': '# 實際標題\n',
  });
  const result = await checkDocuments(root, ['docs/README.md']);
  assert.deepEqual(result.errors.map(error => error.reason), ['missing file', 'missing anchor']);
  assert.equal(result.errors[0].line, 1);
});

test('parses GFM tables, escaped spaces and explicit HTML links', async t => {
  const root = await fixture(t, {
    'docs/README.md': '| 內容 |\n|---|\n| [參考](a%20b.md#工具) |\n<a href="a%20b.md#工具">工具</a>\n<img src="missing.png" alt="圖">\n',
    'docs/a b.md': '# 工具\n',
  });
  const result = await checkDocuments(root, ['docs/README.md']);
  assert.equal(result.links, 3);
  assert.equal(result.errors.length, 1);
  assert.equal(result.errors[0].target, 'missing.png');
});

test('rejects links outside the repository instead of reading host files', async t => {
  const root = await fixture(t, { 'docs/README.md': '[越界](../../outside.md)\n' });
  const result = await checkDocuments(root, ['docs/README.md']);
  assert.equal(result.errors[0].reason, 'outside repository');
});

test('default scope excludes frozen records but retains their maintained indexes', () => {
  assert.deepEqual(selectDocuments([
    'docs/README.md', 'docs/architecture/persistence.md', 'docs/adr/README.md',
    'docs/adr/0001-original.md', 'docs/archive/a.md',
    'docs/experiments/README.md', 'docs/experiments/product-validation/README.md',
    'docs/experiments/engineering/README.md', 'docs/experiments/case/source-snapshot/a.md',
    'docs/research/engineering/study.md', 'docs/plans/evidence/frozen.md',
  ]), [
    'docs/README.md', 'docs/architecture/persistence.md', 'docs/adr/README.md',
    'docs/experiments/README.md', 'docs/experiments/product-validation/README.md',
    'docs/experiments/engineering/README.md', 'docs/research/engineering/study.md',
  ]);
});

test('discovers real images with titles and references, excluding fenced examples', () => {
  const parsed = parseDocument('![A](a.png "圖名")\n![B][figure]\n\n[figure]: b.svg\n\n```md\n![範例](example.png)\n```\n\n~~~mermaid\nflowchart TD\n A --> B\n~~~\n');
  assert.deepEqual(parsed.images.map(image => image.target), ['a.png', 'b.svg']);
  assert.equal(parsed.inlineDiagram, true);
  assert.equal(parseDocument('```md\n~~~mermaid\nA --> B\n~~~\n```').inlineDiagram, false);
});

test('discovers existing maintained files after a tracked page is deleted without staging', async t => {
  const root = await fixture(t, {
    'docs/README.md': '# 文件\n[舊頁](removed.md)', 'docs/removed.md': '# 刪除頁',
    'docs/plans/evidence/frozen.md': '```mermaid\nflowchart TD\n A --> B\n```',
  });
  execFileSync('git', ['init', '-q'], { cwd: root });
  execFileSync('git', ['add', 'docs'], { cwd: root });
  await rm(path.join(root, 'docs/removed.md'));
  assert.deepEqual(await findDocuments(root), ['docs/README.md']);
  assert.equal((await checkDocuments(root, await findDocuments(root))).errors[0].reason, 'missing file');
  const result = await checkDocuments(root, ['docs/removed.md']);
  assert.equal(result.errors[0].reason, 'missing source file');
});

test('diagram inventory excludes PNG and SVG screenshots while retaining Mermaid sources', async t => {
  const root = await fixture(t, {
    'docs/README.md': '![設計](diagrams/architecture/flow.png)\n![截圖](diagrams/screenshots/product/list.png)\n![向量截圖](diagrams/screenshots/product/list.svg)\n',
    'docs/diagrams/architecture/flow.mmd': 'flowchart TD\n A --> B\n',
    'docs/diagrams/architecture/flow.png': 'generated diagram',
    'docs/diagrams/screenshots/product/list.png': 'screenshot',
    'docs/diagrams/screenshots/product/list.svg': '<svg></svg>',
  });
  execFileSync('git', ['init', '-q'], { cwd: root });
  const result = spawnSync(process.execPath, [fileURLToPath(new URL('./render-doc-diagrams.mjs', import.meta.url)), '--list'],
    { cwd: root, encoding: 'utf8', windowsHide: true });
  assert.equal(result.status, 0, result.stderr);
  const inventory = JSON.parse(result.stdout);
  assert.equal(inventory.discovered, 1);
  assert.deepEqual(inventory.diagrams.map(diagram => diagram.sourceFile), ['docs/diagrams/architecture/flow.mmd']);
});

test('diagram inventory still rejects a missing Mermaid source outside screenshots', async t => {
  const root = await fixture(t, {
    'docs/README.md': '![缺少圖源](diagrams/architecture/missing.png)\n',
    'docs/diagrams/architecture/missing.png': 'diagram without source',
  });
  execFileSync('git', ['init', '-q'], { cwd: root });
  const result = spawnSync(process.execPath, [fileURLToPath(new URL('./render-doc-diagrams.mjs', import.meta.url)), '--list'],
    { cwd: root, encoding: 'utf8', windowsHide: true });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /ENOENT/);
  assert.match(result.stderr, /missing\.mmd/);
});
