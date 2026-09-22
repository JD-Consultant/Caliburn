import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { inspect } from 'node:util';
import { createSlateEditor } from 'platejs';
import { BaseSuggestionPlugin, SkipSuggestionDeletes, acceptSuggestion, rejectSuggestion, getSuggestionKey } from '@platejs/suggestion';

// Fixed fixture facts, not an algorithm for discovering product review groups.
const SOURCE_RUN = 'results/2026-09-09T14-36-40-805Z';
const INPUT = path.join(SOURCE_RUN, 'ai-human-ai-pending-value.json');
const MONTHLY_IDS = [
  'ZGXJMoVuecTRW9aHmyE5d', // first AI
  '5IE5qwahRmkLHapfW5AEX', // human
  'm3B3MrQpdikPTtR3cTYVP', // second AI
];
const FAULT_ID = '5XwiFDd56xGxBbJcx_TD2';
const OLD = '僅有月檢約定的專案按月檢查。';
const LATEST = '僅有月檢約定的專案按月檢查，記錄結果並追蹤未解事項。';
const p = text => ({ type: 'p', id: 'monthly', children: [{ text }] });
const clone = structuredClone;
const flush = () => new Promise(resolve => setImmediate(resolve));
const hash = file => createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const runId = new Date().toISOString().replace(/[:.]/g, '-');
const directory = path.join('results', `order-followup-${runId}`);
fs.mkdirSync(directory, { recursive: true });
const batches = new WeakMap();
const groups = [];
const traces = {};
const inputValue = JSON.parse(fs.readFileSync(INPUT, 'utf8'));

function editor(value) {
  const e = createSlateEditor({
    value: clone(value),
    nodeId: { reuseId: true, initialValueIds: 'always' },
    plugins: [BaseSuggestionPlugin.configure({ options: { currentUserId: 'ai', isSuggesting: true } })],
  });
  const records = [];
  const prior = e.onChange;
  e.onChange = options => {
    records.push({ operations: clone(e.operations), value: clone(e.children) });
    prior(options);
  };
  batches.set(e, records);
  return e;
}
function entries(e, at = []) {
  const api = e.getApi(BaseSuggestionPlugin).suggestion;
  return api.nodes({ at }).flatMap(([node, nodePath]) => {
    const data = api.isBlockSuggestion(node) ? [api.suggestionData(node)] : api.dataList(node);
    return data.filter(Boolean).map(item => ({ path: nodePath, nodeId: node.id ?? null, data: clone(item) }));
  });
}
function ids(e, at = []) { return [...new Set(entries(e, at).map(entry => entry.data.id))]; }
function snapshot(e) {
  return {
    value: clone(e.children),
    selection: clone(e.selection),
    monthlyNativeTextProjection: SkipSuggestionDeletes(e, e.children[0]),
    monthlyAllStoredText: e.api.string([0]),
    suggestionEntries: entries(e),
    monthlyRemainingIds: ids(e, [0]),
    allRemainingIds: ids(e),
    batches: clone(batches.get(e)),
  };
}
function save(label, value) {
  const jsonPath = path.join(directory, `${label}.json`);
  fs.writeFileSync(jsonPath, JSON.stringify(value, null, 2) + '\n');
  fs.writeFileSync(path.join(directory, `${label}.inspect.txt`), inspect(value, { depth: null, maxArrayLength: null, compact: false }) + '\n');
  return jsonPath;
}
function reopen(file) { return editor(JSON.parse(fs.readFileSync(file, 'utf8'))); }
function check(g, name, fn) {
  try { fn(); g.checks.push({ name, pass: true }); }
  catch (error) { g.checks.push({ name, pass: false, error: error.message }); }
}
async function resolveOne(e, id, action) {
  e.getApi(BaseSuggestionPlugin).suggestion.withoutSuggestions(() => {
    (action === 'accept' ? acceptSuggestion : rejectSuggestion)(e, { suggestionId: id, keyId: getSuggestionKey(id) });
  });
  await flush();
}
const cases = [
  { id: 'R01-F1', action: 'accept', order: 'chronological', ids: [...MONTHLY_IDS] },
  { id: 'R01-F2', action: 'accept', order: 'reverse', ids: [...MONTHLY_IDS].reverse() },
  { id: 'R01-F3', action: 'reject', order: 'chronological', ids: [...MONTHLY_IDS] },
  { id: 'R01-F4', action: 'reject', order: 'reverse', ids: [...MONTHLY_IDS].reverse() },
];

for (const testCase of cases) {
  const g = { ...testCase, checks: [] }; groups.push(g);
  const trace = traces[testCase.id] = { fixedResolutionIds: [...testCase.ids], steps: [] };
  try {
    // Each case begins with its own standard JSON round trip and new editor.
    const inputPath = save(`${testCase.id}-input-value`, inputValue);
    const e = reopen(inputPath);
    await flush();
    trace.before = snapshot(e);
    check(g, 'JSON→全新 editor 保留原 R3 完整 pending value', () => assert.deepEqual(e.children, inputValue));
    check(g, '固定月檢範圍恰含已明列三個原生 ID', () => assert.deepEqual(ids(e, [0]).sort(), [...MONTHLY_IDS].sort()));
    check(g, '初始原生目前文字投影為最新版', () => assert.equal(SkipSuggestionDeletes(e, e.children[0]), LATEST));
    for (const suggestionId of testCase.ids) {
      await resolveOne(e, suggestionId, testCase.action);
      trace.steps.push({ resolvedId: suggestionId, action: testCase.action, after: snapshot(e) });
    }
    const finalSnapshot = snapshot(e); trace.after = finalSnapshot;
    const expectedText = testCase.action === 'accept' ? LATEST : OLD;
    check(g, '原生目前文字投影得到預期完整正文', () => assert.equal(finalSnapshot.monthlyNativeTextProjection, expectedText));
    check(g, '月檢為預期乾淨節點，無額外正文或 metadata', () => assert.deepEqual(e.children[0], p(expectedText)));
    check(g, '月檢沒有剩餘原生修訂 ID', () => assert.deepEqual(ids(e, [0]), []));
    check(g, '組外交付段完全不變', () => assert.deepEqual(e.children[1], inputValue[1]));
    check(g, '組外故障全文及 pending metadata 完全不變', () => assert.deepEqual(e.children[2], inputValue[2]));
    check(g, '整份只剩故障 pending ID', () => assert.deepEqual(ids(e), [FAULT_ID]));
    check(g, '整份根節點數不變', () => assert.equal(e.children.length, inputValue.length));
    const finalPath = save(`${testCase.id}-final-value`, e.children);
    const reopened = reopen(finalPath); await flush(); trace.afterFinalReopen = snapshot(reopened);
    check(g, '最終 value 再 JSON→全新 editor 完全相等', () => assert.deepEqual(reopened.children, finalSnapshot.value));
    check(g, '最終重開後原生文字投影仍是預期正文', () => assert.equal(SkipSuggestionDeletes(reopened, reopened.children[0]), expectedText));
    g.observation = {
      nativeTextProjection: finalSnapshot.monthlyNativeTextProjection,
      allStoredText: finalSnapshot.monthlyAllStoredText,
      monthlyRemainingIds: finalSnapshot.monthlyRemainingIds,
      allRemainingIds: finalSnapshot.allRemainingIds,
    };
  } catch (error) { g.executionError = error.stack; }
  g.status = g.executionError ? 'EXECUTION_ERROR' : g.checks.some(item => !item.pass) ? 'FAIL' : 'PASS';
}

const packageNames = ['platejs', '@platejs/core', '@platejs/slate', '@platejs/suggestion', '@platejs/diff', 'slate', 'react', 'react-dom'];
const versions = Object.fromEntries(packageNames.map(name => [name, JSON.parse(fs.readFileSync(`node_modules/${name}/package.json`, 'utf8')).version]));
const report = {
  topic: 'JD-R002/C03/R01-F', executedAt: new Date().toISOString(), node: process.version, versions,
  sourceInput: INPUT, sourceInputSha256: hash(INPUT),
  fixedMonthlyIds: MONTHLY_IDS, fixedFaultId: FAULT_ID,
  profile: { nodeId: { reuseId: true, initialValueIds: 'always' }, currentUserId: 'ai', isSuggesting: true, normalization: 'native defaults', visibleTextObservation: 'native SkipSuggestionDeletes projection; not DOM/React verification' },
  groups, passGroups: groups.filter(g => g.status === 'PASS').length, failGroups: groups.filter(g => g.status === 'FAIL').length, executionErrorGroups: groups.filter(g => g.executionError).length,
  limitations: ['Known fixture members and two explicit orders only; no grouping/dependency algorithm.', 'No metadata writes, before-image restore, vendor fixes, codec, or custom review engine.', 'Original R01 four groups and 2 PASS/2 FAIL results are unchanged.', 'No DOM/IME/React UI, LLM, production, DB, or dependency installation.'],
};
save('review-order-traces', traces);
fs.writeFileSync(path.join(directory, 'review-order-results.json'), JSON.stringify(report, null, 2) + '\n');
const sourceFile = '../jd-oss/plate/packages/suggestion/src/lib/utils/SkipSuggestionDeletes.ts';
const sourceCopy = path.join(directory, 'SkipSuggestionDeletes.source.ts');
fs.copyFileSync(sourceFile, sourceCopy);
const previous = JSON.parse(fs.readFileSync(path.join(SOURCE_RUN, 'run-hashes.json'), 'utf8'));
const originalPreserved = {
  script: hash('review-probe.mjs') === previous.script,
  packageLock: hash('package-lock.json') === previous.packageLock,
  results: hash(path.join(SOURCE_RUN, 'review-results.json')) === previous.results,
  traces: hash(path.join(SOURCE_RUN, 'review-traces.json')) === previous.traces,
};
const runHashes = {
  script: hash('review-order-followup.mjs'), packageLock: hash('package-lock.json'), sourceInput: hash(INPUT),
  results: hash(path.join(directory, 'review-order-results.json')),
  traces: hash(path.join(directory, 'review-order-traces.json')),
  tracesInspect: hash(path.join(directory, 'review-order-traces.inspect.txt')),
  installedImplementation: { file: 'node_modules/@platejs/suggestion/dist/src-CMqLOrDd.js', sha256: hash('node_modules/@platejs/suggestion/dist/src-CMqLOrDd.js') },
  source: { url: 'https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/utils/SkipSuggestionDeletes.ts', license: 'MIT', accessed: '2026-09-09', originalSha256: hash(sourceFile), copySha256: hash(sourceCopy) },
  originalR01HashesStillMatch: originalPreserved,
};
fs.writeFileSync(path.join(directory, 'run-hashes.json'), JSON.stringify(runHashes, null, 2) + '\n');
console.log(JSON.stringify({ directory, ...report, originalR01HashesStillMatch: originalPreserved }, null, 2));
process.exitCode = report.failGroups || report.executionErrorGroups || Object.values(originalPreserved).some(v => !v) ? 1 : 0;
