import fs from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { createSlateEditor, createSlatePlugin } from 'platejs';
import { before, nodeTypes } from './fixture.mjs';

const clone = structuredClone;
const plugins = nodeTypes.map(key => createSlatePlugin({ key, node: { isElement: true } }));
// Fixed fixture path lookup only. No runtime/LLM locator service is exposed.
function fixturePath(nodes, id, prefix = []) {
  for (let i = 0; i < nodes.length; i++) {
    const path = [...prefix, i];
    if (nodes[i].id === id) return path;
    if (nodes[i].children) { const child = fixturePath(nodes[i].children, id, path); if (child) return child; }
  }
}
async function capture(id, title, value, mutate, note) {
  const editor = createSlateEditor({ plugins, nodeId: false, value: clone(value) });
  const batches = [];
  const prior = editor.onChange;
  editor.onChange = options => {
    batches.push({ operations: clone(editor.operations), value: clone(editor.children) });
    prior(options);
  };
  const initial = clone(editor.children);
  mutate(editor);
  await new Promise(resolve => setImmediate(resolve));
  return { id, title, note, before: initial, after: clone(editor.children), batches, operationsClearedAfterCallback: editor.operations.length === 0 };
}
const full = await capture('full-r2', '完整 r2 與固定改動', before, editor => {
  const at = id => fixturePath(editor.children, id);
  editor.tf.insertText('（固定驗證新增：交付前確認接收窗口。）', { at: { path: [...at('purpose'), 0], offset: editor.api.string(at('purpose')).length } });
  editor.tf.setNodes({ bold: true }, { at: [...at('task1-description'), 0] });
  editor.tf.setNodes({ score: 0, approved: false, provenance: { source: 'fixture-after', revision: 2 }, obsolete: null }, { at: at('task2-description') });
  editor.tf.setNodes({ scope: '固定雙改案例' }, { at: at('task3-description') });
  editor.tf.insertText('（固定驗證：同 ID 正文也已更新。）', { at: { path: [...at('task3-description'), 0], offset: editor.api.string(at('task3-description')).length } });
  // The final basic-table row, second cell, paragraph, text.
  const cell = [...at('basic-table'), 4, 1, 0, 0];
  editor.tf.insertText('（含驗證窗口）', { at: { path: cell, offset: editor.api.node(cell)[0].text.length } });
  const fourthIndex = at('task4-description')[0];
  const nestedLeaf = [fourthIndex + 1, 0, 1, 0, 0, 0];
  editor.tf.insertText('（固定驗證：重試保留查詢條件。）', { at: { path: nestedLeaf, offset: editor.api.node(nestedLeaf)[0].text.length } });
}, 'r2 全文；僅加入明列的合成改動。element score／approved／provenance／obsolete 是研究 metadata，不是 JD 產品 schema。');
const score = await capture('leaf-score-zero', '已知反例：文字屬性 1 → 0', [{ id: 'score-p', type: 'p', children: [{ text: '原生比較不應把 0 當作沒有值。', score: 1 }] }], editor => {
  editor.tf.setNodes({ score: 0 }, { at: [0, 0] });
}, '乾淨後版有 score:0；原生 diff 卻把新值表示成 undefined。這個缺口沒有修補。');
const empty = await capture('empty-mark', '已知反例：空文字粗體 → 斜體', [{ id: 'empty-p', type: 'p', children: [{ text: '', bold: true }] }], editor => {
  editor.tf.setNodes({ bold: null, italic: true }, { at: [0, 0] });
}, '空文字沒有可見字形；原生 diff 沒有 diffOperation。旁列真實 JSON 與 set_node，不能把它算成高亮通過。');

const sourcePath = process.argv[2] ?? new URL('../../docs/specs/2026-09-09-frontend-engineer-jd-sample.md', import.meta.url);
const source = await fs.readFile(sourcePath, 'utf8');
const materials = { schema: 'bounded-ui-fixture-v1', source: { path: 'docs/specs/2026-09-09-frontend-engineer-jd-sample.md', sha256: createHash('sha256').update(source).digest('hex'), referenceLink: '2026-09-09-jd-sample-basis-and-review.md#10-完整閱讀版-r2-與核心文檔一致性審核' }, versions: { platejs: '53.3.11', diff: '53.0.0', react: '19.2.4' }, cases: [full, score, empty] };
await fs.mkdir('public', { recursive: true });
await fs.mkdir('results', { recursive: true });
await fs.writeFile('public/materials.json', JSON.stringify(materials, null, 2) + '\n');
await fs.writeFile('results/r2-source.md', source);
console.log(JSON.stringify({ cases: materials.cases.map(c => ({ id: c.id, batches: c.batches.length, operations: c.batches.reduce((n, b) => n + b.operations.length, 0), callbackFlushed: c.operationsClearedAfterCallback })) }, null, 2));
