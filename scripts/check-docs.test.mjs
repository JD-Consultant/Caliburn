import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { execFileSync } from 'node:child_process';
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

test('selects Markdown across public root, component and documentation paths', () => {
  assert.deepEqual(selectDocuments([
    'README.md', 'AGENTS.md', 'CONTRIBUTING.md', 'apps/api/README.md',
    'packages/ocs-contract/README.md', 'docs/README.md', 'docs/diagrams/flow.png',
  ]), [
    'README.md', 'AGENTS.md', 'CONTRIBUTING.md', 'apps/api/README.md',
    'packages/ocs-contract/README.md', 'docs/README.md',
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
    '.gitignore': 'docs-local/\n',
    'docs-local/evidence/frozen.md': '```mermaid\nflowchart TD\n A --> B\n```',
  });
  execFileSync('git', ['init', '-q'], { cwd: root });
  execFileSync('git', ['add', 'docs'], { cwd: root });
  await rm(path.join(root, 'docs/removed.md'));
  assert.deepEqual(await findDocuments(root), ['docs/README.md']);
  assert.equal((await checkDocuments(root, await findDocuments(root))).errors[0].reason, 'missing file');
  const result = await checkDocuments(root, ['docs/removed.md']);
  assert.equal(result.errors[0].reason, 'missing source file');
});


test('default discovery reports broken root and component links, including untracked public pages', async t => {
  const root = await fixture(t, {
    '.gitignore': 'docs-local/\n',
    'README.md': '[missing](root-missing.md)\n',
    'apps/api/README.md': '[missing](component-missing.md)\n',
    'docs-local/private.md': '[ignored](does-not-exist.md)\n',
  });
  execFileSync('git', ['init', '-q'], { cwd: root });
  execFileSync('git', ['add', 'README.md', '.gitignore'], { cwd: root });
  const files = await findDocuments(root);
  assert.deepEqual(files, ['README.md', 'apps/api/README.md']);
  const result = await checkDocuments(root, files);
  assert.deepEqual(result.errors.map(error => error.file), ['README.md', 'apps/api/README.md']);
});

test('public checking rejects ignored targets that exist and accepts public directories', async t => {
  const root = await fixture(t, {
    '.gitignore': 'docs-local/\n',
    'README.md': '[private](docs-local/private.md#內容) [private directory](docs-local/) [public directory](apps/api/)\n',
    'apps/api/README.md': '# API\n',
    'docs-local/private.md': '# 內容\n',
  });
  execFileSync('git', ['init', '-q'], { cwd: root });
  const publishedFiles = execFileSync('git', ['ls-files', '--cached', '--others', '--exclude-standard', '-z'],
    { cwd: root, encoding: 'utf8' }).split('\0').filter(Boolean);
  const result = await checkDocuments(root, ['README.md'], { publishedFiles });
  assert.deepEqual(result.errors.map(error => [error.target, error.reason]), [
    ['docs-local/private.md#內容', 'not a public file or directory'],
    ['docs-local/', 'not a public file or directory'],
  ]);
});

test('explicit local checking preserves access to ignored local targets', async t => {
  const root = await fixture(t, {
    '.gitignore': 'docs-local/\n',
    'docs-local/README.md': '[private](private.md#內容)\n',
    'docs-local/private.md': '# 內容\n',
  });
  execFileSync('git', ['init', '-q'], { cwd: root });
  const result = await checkDocuments(root, ['docs-local/README.md']);
  assert.deepEqual(result.errors, []);
});
