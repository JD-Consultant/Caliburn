import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { createSlateEditor, NodeIdPlugin } from 'platejs';
import { createPlateEditor } from 'platejs/react';

// JD-R002/C03. A bounded synchronization/history observation; no production,
// framework modification, custom rebase/history, DOM/IME, or dependency install.
// Only these history-* outputs are written; original 13+3 probes are untouched.
const clone = structuredClone;
const flush = () => new Promise(resolve => setImmediate(resolve));
const p = (id, text, props = {}) => ({ type: 'p', id, ...props, children: [{ text }] });
function editor(value, react = false, nodeIdOptions = {}, idPrefix = 'history-new') {
  let nextId = 0;
  const create = react ? createPlateEditor : createSlateEditor;
  return create({ value: clone(value), plugins: [NodeIdPlugin.configure({ options: { ...nodeIdOptions, idCreator: () => `${idPrefix}-${++nextId}` } })] });
}
const state = e => ({ value: clone(e.children), selection: clone(e.selection), history: clone(e.history), operations: clone(e.operations), diagnosticFlags: { saving: e.api.isSaving() ?? null, merging: e.api.isMerging() ?? null, splittingOnce: e.api.isSplittingOnce() ?? null, normalizing: e.api.isNormalizing() } });
function observe(e) {
  const batches = [];
  const prior = e.onChange;
  e.onChange = options => { batches.push({ operations: clone(e.operations), value: clone(e.children) }); prior(options); };
  return batches;
}
async function selectEnd(e) { e.tf.select(e.api.end([])); await flush(); }
const text = e => e.children.map(node => e.api.string([e.children.indexOf(node)])).join('|');
const results = [];
const traces = {};
async function record(id, expectation, classification, run) {
  const trace = traces[id] = {};
  try { await run(trace); results.push({ id, expectation, classification, assertionPassed: true }); }
  catch (error) { results.push({ id, expectation, classification, assertionPassed: false, error: error.stack }); }
}
const originalPaths = ['probe.mjs', 'observe-native.mjs', 'results/native-results.json', 'results/native-observation.json'];
const digest = path => createHash('sha256').update(readFileSync(path)).digest('hex');
const originalHashes = Object.fromEntries(originalPaths.map(path => [path, digest(path)]));
const profiles = {
  H01_H08: { nodeIdEnabled: true, configuredVia: 'NodeIdPlugin.configure', idCreator: 'deterministic per-editor history-new-N (same initial counter)', reuseId: 'not supplied; falsey default in installed split implementation', initialValueIds: 'not supplied; resolved if-needed', shouldNormalizeEditor: 'not supplied; no forced initialization normalization', operationNormalization: 'normal native normalization; explicitly deferred inside bounded withoutNormalizing callbacks' },
  H09: { nodeIdEnabled: true, configuredVia: 'NodeIdPlugin.configure', idCreator: 'deliberately different deterministic streams history-source-N / history-target-N', reuseId: true, initialValueIds: 'always', shouldNormalizeEditor: 'not supplied; no forced initialization normalization', operationNormalization: 'normal native normalization; deferred while applying fixed batch', initialValueIdsGapCoverage: 'baseline already has IDs; missing-initial-ID fill is not experimentally covered' },
};

await record('H01', '同基底原生批次重播至第二個 React Plate editor，JSON／ID 與 undo／redo 往返一致', 'positive-with-fixed-baseline', async out => {
  const baseline = [p('a', '確認需求。', { sourceRefs: ['source:a'] }), p('b', '維護僅限約定範圍。')];
  const source = editor(baseline);
  const target = editor(baseline, true);
  const observed = observe(source);
  out.baseline = clone(baseline);
  source.tf.withNewBatch(() => source.tf.withoutNormalizing(() => {
    source.tf.insertText('先', { at: { path: [0, 0], offset: 0 } });
    source.tf.setNodes({ scope: { covered: ['客戶網站'], approved: false } }, { at: [0] });
    source.tf.setNodes({ bold: true }, { at: [0, 0] });
    source.tf.insertNodes(p('c', '保留未解事項。'), { at: [2] });
    source.tf.moveNodes({ at: [2], to: [1] });
    source.tf.splitNodes({ at: { path: [2, 0], offset: 2 } });
  }));
  await flush();
  const operations = JSON.parse(JSON.stringify(observed.flatMap(batch => batch.operations)));
  out.sourceAfter = state(source);
  out.operationsJsonRoundtrip = clone(operations);
  target.tf.withNewBatch(() => target.tf.withoutNormalizing(() => { for (const operation of operations) target.tf.apply(clone(operation)); }));
  await flush();
  out.targetAfter = state(target);
  assert.deepEqual(target.children, source.children);
  assert.equal(target.history.undos.length, 1);
  assert.deepEqual(target.children.map(n => n.id), source.children.map(n => n.id));
  target.tf.undo(); await flush(); out.targetUndo = state(target);
  assert.deepEqual(target.children, baseline);
  target.tf.redo(); await flush(); out.targetRedo = state(target);
  assert.deepEqual(target.children, source.children);
  assert.deepEqual(out.baseline, baseline);
});

await record('H02', 'withNewBatch 只隔開 AI 前方；相鄰人改仍與 AI 合併，第一次 undo 一起移除', 'confirmed-counterexample', async out => {
  const baseline = [p('p', '本')]; const e = editor(baseline); await selectEnd(e);
  e.tf.insertText('前'); await flush(); out.beforeAI = state(e);
  e.tf.withNewBatch(() => e.tf.withoutNormalizing(() => { e.tf.insertText('A'); e.tf.insertText('I'); }));
  await flush(); out.afterAI = state(e);
  e.tf.insertText('人'); await flush(); out.afterHuman = state(e);
  assert.equal(text(e), '本前AI人');
  e.tf.undo(); await flush(); out.firstUndo = state(e);
  assert.equal(text(e), '本前');
  e.tf.undo(); await flush(); out.secondUndo = state(e);
  assert.deepEqual(e.children, baseline);
  e.tf.redo(); await flush(); out.firstRedo = state(e); assert.equal(text(e), '本前');
  e.tf.redo(); await flush(); out.secondRedo = state(e); assert.equal(text(e), '本前AI人');
});

await record('H03', 'AI 後 setSplittingOnce(true) 使緊接人改獨立；原生 undo／redo 三批內容正確', 'positive-headless-only', async out => {
  const baseline = [p('p', '本')]; const e = editor(baseline); await selectEnd(e);
  e.tf.insertText('前'); await flush(); out.beforeAI = state(e);
  e.tf.withNewBatch(() => e.tf.withoutNormalizing(() => { e.tf.insertText('A'); e.tf.insertText('I'); }));
  await flush(); out.afterAI = state(e);
  e.tf.setSplittingOnce(true);
  e.tf.insertText('人'); await flush(); e.tf.insertText('改'); await flush(); out.afterHuman = state(e);
  assert.equal(text(e), '本前AI人改');
  const expectedUndo = ['本前AI', '本前', '本']; out.undos = [];
  for (const expected of expectedUndo) { e.tf.undo(); await flush(); out.undos.push(state(e)); assert.equal(text(e), expected); }
  assert.deepEqual(e.children, baseline);
  const expectedRedo = ['本前', '本前AI', '本前AI人改']; out.redos = [];
  for (const expected of expectedRedo) { e.tf.redo(); await flush(); out.redos.push(state(e)); assert.equal(text(e), expected); }
  assert.deepEqual(e.children, out.afterHuman.value);
});

await record('H04', 'setValue 是可 undo 的根節點替換；保留舊 undo、清掉既有 redo', 'confirmed-setter-limitation', async out => {
  const baseline = [p('original', '原')]; const replacement = [p('replacement', '另一份')];
  const e = editor(baseline); await selectEnd(e);
  e.tf.insertText('A'); await flush();
  e.tf.withNewBatch(() => e.tf.insertText('B')); await flush();
  e.tf.undo(); await flush(); out.beforeSetValue = state(e);
  assert.equal(text(e), '原A'); assert.equal(e.history.redos.length, 1);
  e.tf.setValue(clone(replacement)); await flush(); out.afterSetValue = state(e);
  assert.deepEqual(e.children, replacement); assert.equal(e.history.redos.length, 0);
  e.tf.undo(); await flush(); out.undoSetValue = state(e); assert.equal(text(e), '原A');
  e.tf.undo(); await flush(); out.undoEarlierHuman = state(e); assert.deepEqual(e.children, baseline);
  e.tf.redo(); await flush(); assert.equal(text(e), '原A');
  e.tf.redo(); await flush(); out.redoSetValue = state(e); assert.deepEqual(e.children, replacement);
});

await record('H05', 'reset 預設清內容與兩個 history stacks；undo／redo 都不還原先前文件', 'confirmed-reset-limitation', async out => {
  const baseline = [p('original', '原')]; const e = editor(baseline); await selectEnd(e);
  e.tf.insertText('A'); await flush(); e.tf.withNewBatch(() => e.tf.insertText('B')); await flush(); e.tf.undo(); await flush();
  out.beforeReset = state(e);
  e.tf.reset(); await flush(); out.afterReset = state(e);
  assert.equal(e.children.length, 1); assert.equal(e.children[0].type, 'p'); assert.equal(text(e), '');
  assert.deepEqual(e.children[0].children, [{ text: '' }]); assert.ok(e.children[0].id);
  assert.deepEqual(e.history, { undos: [], redos: [] });
  e.tf.undo(); await flush(); out.afterUndo = state(e); assert.deepEqual(e.children, out.afterReset.value);
  e.tf.redo(); await flush(); out.afterRedo = state(e); assert.deepEqual(e.children, out.afterReset.value);
});

await record('H06', 'withoutSaving(setValue) 不重算舊 undo；undo 在新文件錯位刪字，redo 也不復原外部稿', 'confirmed-counterexample', async out => {
  const e = editor([p('original', '原')]); await selectEnd(e); e.tf.insertText('人'); await flush(); out.savedHuman = state(e);
  const external = [p('external', '完全不同')];
  e.tf.withoutSaving(() => e.tf.setValue(clone(external))); await flush(); out.afterUnsavedReplacement = state(e);
  assert.deepEqual(e.children, external);
  assert.deepEqual(e.history, out.savedHuman.history);
  e.tf.undo(); await flush(); out.afterStaleUndo = state(e);
  assert.deepEqual(e.children, [p('external', '完不同')]);
  e.tf.redo(); await flush(); out.afterStaleRedo = state(e);
  assert.deepEqual(e.children, [p('external', '完人不同')]);
});

await record('H07', '原生 apply 中途無效 path 拋錯留下部分 AI 與無效 history，undo 再拋錯不能回復', 'confirmed-counterexample-disposable-editor', async out => {
  const e = editor([p('original', '原')]); await selectEnd(e); e.tf.insertText('人'); await flush(); out.beforeAI = state(e);
  const batches = observe(e);
  try {
    e.tf.withNewBatch(() => e.tf.withoutNormalizing(() => {
      e.tf.insertText('AI');
      e.tf.apply({ type: 'insert_text', path: [99, 0], offset: 0, text: '錯' });
    }));
  } catch (error) { out.applyError = error.message; }
  await flush(); out.afterThrow = state(e); out.observedBatches = clone(batches);
  assert.ok(out.applyError); assert.equal(text(e), '原人AI');
  assert.ok(e.history.undos.at(-1).operations.some(op => op.path?.[0] === 99));
  try { e.tf.undo(); } catch (error) { out.undoError = error.message; }
  await flush(); out.afterFailedUndo = state(e);
  assert.ok(out.undoError); assert.equal(text(e), '原人AI');
  assert.notDeepEqual(e.children, out.beforeAI.value);
  // This corrupted throwaway editor is deliberately discarded, not repaired.
});

await record('H08', 'withoutSaving callback 拋錯後續人改仍無 undo 紀錄；undo 只撤銷舊字', 'confirmed-counterexample-disposable-editor', async out => {
  const e = editor([p('original', '原')]); await selectEnd(e); e.tf.insertText('人'); await flush(); out.savedHuman = state(e);
  try { e.tf.withoutSaving(() => { e.tf.insertText('暫'); throw new Error('固定 probe：callback 中途停止'); }); }
  catch (error) { out.callbackError = error.message; }
  await flush(); out.afterThrow = state(e);
  e.tf.insertText('後'); await flush(); out.afterLaterHuman = state(e); assert.equal(text(e), '原人暫後');
  e.tf.undo(); await flush(); out.afterUndo = state(e);
  assert.deepEqual(e.children, [p('original', '原暫後')]);
  assert.ok(out.callbackError);
  // No flag repair or history patch is attempted.
});

await record('H09', '明列 reuseId:true profile、不同 ID streams；split 同 operations 同步與 undo／redo 保留精確 JSON／ID', 'positive-explicit-profile-only', async out => {
  const baseline = [p('split-base', '確認範圍。', { sourceRefs: ['source:split'] })];
  const profile = { reuseId: true, initialValueIds: 'always' };
  const source = editor(baseline, false, profile, 'history-source');
  const target = editor(baseline, true, profile, 'history-target');
  const batches = observe(source); out.baseline = clone(baseline); out.profile = clone(profiles.H09);
  source.tf.withNewBatch(() => source.tf.withoutNormalizing(() => source.tf.splitNodes({ at: { path: [0, 0], offset: 2 } })));
  await flush(); out.sourceAfter = state(source);
  const operations = JSON.parse(JSON.stringify(batches.flatMap(batch => batch.operations))); out.operations = clone(operations);
  assert.deepEqual(source.children.map(n => n.id), ['split-base', 'history-source-1']);
  target.tf.withNewBatch(() => target.tf.withoutNormalizing(() => { for (const operation of operations) target.tf.apply(clone(operation)); }));
  await flush(); out.targetAfter = state(target); assert.deepEqual(target.children, source.children);
  target.tf.undo(); await flush(); out.targetUndo = state(target); assert.deepEqual(target.children, baseline);
  target.tf.redo(); await flush(); out.targetRedo = state(target); assert.deepEqual(target.children, source.children);
  assert.deepEqual(target.children.map(n => n.sourceRefs), [['source:split'], ['source:split']]);
  source.tf.undo(); await flush(); out.sourceUndo = state(source); assert.deepEqual(source.children, baseline);
  source.tf.redo(); await flush(); out.sourceRedo = state(source); assert.deepEqual(source.children, out.sourceAfter.value);
});

const hashesAfter = Object.fromEntries(originalPaths.map(path => [path, digest(path)]));
assert.deepEqual(hashesAfter, originalHashes, 'Original 13+3 script/results must remain unchanged');
const versions = Object.fromEntries(['platejs', '@platejs/core', '@platejs/slate', 'slate', 'react'].map(name => { const pkg = JSON.parse(readFileSync(`node_modules/${name}/package.json`, 'utf8')); return [name, pkg.version]; }));
const report = { topic: 'JD-R002/C03', executedAt: new Date().toISOString(), node: process.version, versions, nodeEnv: process.env.NODE_ENV ?? null, profiles, installedDependencies: false, passedAssertions: results.filter(r => r.assertionPassed).length, failedAssertions: results.filter(r => !r.assertionPassed).length, countsAreCharacterizationNotUniversalCapability: true, results, originalEvidenceHashesUnchanged: originalHashes, limitations: ['Same fixed baseline/schema only; no stale state, rebasing, transport retries, or database.', 'H01 matching generators can accidentally make initial replay IDs equal; falsey reuseId still regenerates IDs on split.', 'H09 is one explicit-profile split case; no duplicate-ID/copy-paste or arbitrary schema guarantee.', 'React Plate editor is instantiated headlessly; no DOM/selection/IME acceptance.', 'History is session-local; no history persistence claimed.', 'Confirmed counterexamples remain; no framework or history repair.'] };
mkdirSync('results', { recursive: true });
writeFileSync('results/history-native-results.json', JSON.stringify(report, null, 2) + '\n');
writeFileSync('results/history-native-traces.json', JSON.stringify(traces, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
process.exitCode = report.failedAssertions ? 1 : 0;
