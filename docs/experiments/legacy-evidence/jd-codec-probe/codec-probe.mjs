import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { inspect, isDeepStrictEqual } from 'node:util';
import { pathToFileURL } from 'node:url';
import SuperJSON from 'superjson';

const borrowedRequire = createRequire(new URL('../jd-editor-review-probe/package.json', import.meta.url));
const { createSlateEditor } = await import(pathToFileURL(borrowedRequire.resolve('platejs')).href);
const { BaseSuggestionPlugin, acceptSuggestion, rejectSuggestion, getSuggestionKey } = await import(pathToFileURL(borrowedRequire.resolve('@platejs/suggestion')).href);
const clone = structuredClone;
const hash = file => createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const flush = () => new Promise(resolve => setImmediate(resolve));
const p = (id, text, marks = {}) => ({ type: 'p', id, children: [{ text, ...marks }] });
const formatBaseline = [p('format', '保留必要的完成要求。', { bold: true })];
const oldMonthly = '僅有月檢約定的專案按月檢查。';
const runId = new Date().toISOString().replace(/[:.]/g, '-');
const directory = path.join('results', runId);
fs.mkdirSync(directory, { recursive: true });
const groups = [], traces = {};
const batches = new WeakMap();

function editor(value) {
  const e = createSlateEditor({
    value: clone(value), nodeId: { reuseId: true, initialValueIds: 'always' },
    plugins: [BaseSuggestionPlugin.configure({ options: { currentUserId: 'ai', isSuggesting: true } })],
  });
  const records = [], prior = e.onChange;
  e.onChange = options => { records.push({ operations: clone(e.operations), value: clone(e.children) }); prior(options); };
  batches.set(e, records);
  return e;
}
function entries(e, at = []) {
  const api = e.getApi(BaseSuggestionPlugin).suggestion;
  return api.nodes({ at }).flatMap(([node, nodePath]) => {
    const data = api.isBlockSuggestion(node) ? [api.suggestionData(node)] : api.dataList(node);
    return data.filter(Boolean).map(item => ({ path: nodePath, data: clone(item) }));
  });
}
function ids(e, at = []) { return [...new Set(entries(e, at).map(item => item.data.id))]; }
function rawSuggestionFields(e, at = []) {
  // Diagnostics only: detect raw keys even if the native suggestion flag is absent.
  return [...e.api.nodes({ at, match: node => Object.keys(node).some(key => key === 'suggestion' || key.startsWith('suggestion_')) })]
    .map(([node, nodePath]) => ({ path: nodePath, fields: clone(Object.fromEntries(Object.entries(node).filter(([key]) => key === 'suggestion' || key.startsWith('suggestion_')))) }));
}
function snapshot(e) { return { value: clone(e.children), selection: clone(e.selection), suggestionEntries: entries(e), rawSuggestionFields: rawSuggestionFields(e), batches: clone(batches.get(e)) }; }
function save(label, value) {
  const filename = path.join(directory, `${label}.json`);
  fs.writeFileSync(filename, JSON.stringify(value, null, 2) + '\n');
  fs.writeFileSync(path.join(directory, `${label}.inspect.txt`), inspect(value, { depth: null, maxArrayLength: null, compact: false }) + '\n');
  return filename;
}
function readJson(file) { return JSON.parse(fs.readFileSync(file, 'utf8')); }
function codecOpen(file) { return editor(SuperJSON.deserialize(readJson(file))); }
function check(g, name, action) {
  try { action(); g.checks.push({ name, pass: true }); }
  catch (error) { g.checks.push({ name, pass: false, error: error.message }); }
}
async function runGroup(id, title, execute) {
  const g = { id, title, checks: [] }; groups.push(g);
  const trace = traces[id] = {};
  try { await execute(g, trace); } catch (error) { g.executionError = error.stack; }
  g.status = g.executionError ? 'EXECUTION_ERROR' : g.checks.some(item => !item.pass) ? 'FAIL' : 'PASS';
}
async function resolve(e, id, action) {
  e.getApi(BaseSuggestionPlugin).suggestion.withoutSuggestions(() => {
    (action === 'accept' ? acceptSuggestion : rejectSuggestion)(e, { suggestionId: id, keyId: getSuggestionKey(id) });
  });
  await flush();
}
function formatPayload(e) {
  const data = e.getApi(BaseSuggestionPlugin).suggestion.dataList(e.children[0].children[0])[0];
  return { hasBoldOwnKey: Object.hasOwn(data.properties, 'bold'), boldIsUndefined: data.properties.bold === undefined, keys: Object.keys(data.properties), properties: clone(data.properties) };
}
let formatEnvelopePath, formatPending, formatId;

await runGroup('C01', 'SuperJSON JSON 檔→新 editor→reject 恢復粗體，保留兩路控制', async (g, trace) => {
  const e = editor(formatBaseline); trace.before = snapshot(e);
  e.tf.select(e.api.range([0])); e.tf.removeMark('bold'); await flush();
  trace.nativePending = snapshot(e); trace.originalPayload = formatPayload(e);
  formatPending = clone(e.children);
  assert.equal(ids(e).length, 1); formatId = ids(e)[0]; trace.suggestionId = formatId;
  check(g, '原生重新生成 properties 自有 bold:undefined', () => { assert.equal(trace.originalPayload.hasBoldOwnKey, true); assert.equal(trace.originalPayload.boldIsUndefined, true); });
  const rawPath = save('format-pending-raw-json-control', formatPending);
  const memoryOpened = editor(clone(formatPending)); trace.memoryReopened = snapshot(memoryOpened);
  await resolve(memoryOpened, formatId, 'reject'); trace.memoryAfterReject = snapshot(memoryOpened);
  check(g, '記憶體控制組可恢復粗體', () => assert.deepEqual(memoryOpened.children, formatBaseline));
  const rawOpened = editor(readJson(rawPath)); trace.rawJsonReopened = snapshot(rawOpened); trace.rawJsonPayload = formatPayload(rawOpened);
  await resolve(rawOpened, formatId, 'reject'); trace.rawJsonAfterReject = snapshot(rawOpened);
  let controlDiff = null;
  try { assert.deepEqual(rawOpened.children, formatBaseline); } catch (error) { controlDiff = error.message; }
  trace.rawJsonControl = { restoredBold: isDeepStrictEqual(rawOpened.children, formatBaseline), knownR4FailureReproduced: !isDeepStrictEqual(rawOpened.children, formatBaseline), assertionDiff: controlDiff };
  check(g, '普通 JSON 控制仍重現原 R4 失敗，不改判為已修', () => { assert.equal(trace.rawJsonPayload.hasBoldOwnKey, false); assert.equal(trace.rawJsonControl.restoredBold, false); });
  const envelope = SuperJSON.serialize(formatPending);
  formatEnvelopePath = save('format-pending-superjson-envelope', envelope);
  const parsedEnvelope = readJson(formatEnvelopePath); trace.persistedEnvelope = parsedEnvelope;
  check(g, '完整 SuperJSON envelope 可普通 JSON roundtrip', () => assert.deepEqual(parsedEnvelope, envelope));
  const opened = codecOpen(formatEnvelopePath); trace.codecReopened = snapshot(opened); trace.codecPayload = formatPayload(opened);
  check(g, 'codec 新 editor 完整 pending value 與原生值相等', () => assert.deepEqual(opened.children, formatPending));
  check(g, 'codec 重開保留自有 bold:undefined', () => { assert.equal(trace.codecPayload.hasBoldOwnKey, true); assert.equal(trace.codecPayload.boldIsUndefined, true); });
  await resolve(opened, formatId, 'reject'); trace.codecAfterReject = snapshot(opened);
  check(g, '原生 reject 恢復原粗體及完整乾淨節點', () => assert.deepEqual(opened.children, formatBaseline));
  check(g, 'reject 後沒有任何 raw suggestion key 或 flag', () => assert.deepEqual(rawSuggestionFields(opened), []));
});

await runGroup('C02', '同一 pending codec 重開後 accept 正確移除粗體', async (g, trace) => {
  assert.ok(formatEnvelopePath);
  const e = codecOpen(formatEnvelopePath); trace.reopened = snapshot(e);
  check(g, '再次全新 editor 完整 pending 相等', () => assert.deepEqual(e.children, formatPending));
  await resolve(e, formatId, 'accept'); trace.afterAccept = snapshot(e);
  check(g, '正文保留且粗體正確移除', () => assert.deepEqual(e.children, [p('format', '保留必要的完成要求。')]));
  check(g, 'accept 後無原生 pending ID', () => assert.deepEqual(ids(e), []));
  check(g, 'accept 後沒有任何 raw suggestion key 或 flag', () => assert.deepEqual(rawSuggestionFields(e), []));
});

await runGroup('C03', '兩組原生 pending 經 codec 重開後拒絕 A 保留 fault', async (g, trace) => {
  const baseline = [p('monthly', oldMonthly), p('delivery', '交付版本與檢查結果一致。')];
  const e = editor(baseline); trace.before = snapshot(e);
  e.tf.select(e.api.range([0])); e.tf.insertText('所有專案都按月檢查。'); await flush();
  assert.equal(ids(e, [0]).length, 1); const monthlyId = ids(e, [0])[0];
  e.tf.insertNodes(p('fault', '記錄故障處理結果與未解事項。'), { at: [2] }); await flush();
  const faultId = e.getApi(BaseSuggestionPlugin).suggestion.nodeId(e.children[2]); assert.ok(faultId); assert.notEqual(monthlyId, faultId);
  const pending = clone(e.children), fault = clone(e.children[2]);
  trace.nativePending = snapshot(e); trace.monthlyId = monthlyId; trace.faultId = faultId;
  save('two-pending-native-raw-value', pending);
  const envelopePath = save('two-pending-superjson-envelope', SuperJSON.serialize(pending));
  const opened = codecOpen(envelopePath); trace.codecReopened = snapshot(opened);
  check(g, '兩組完整 pending 經 codec JSON 重開相等', () => assert.deepEqual(opened.children, pending));
  await resolve(opened, monthlyId, 'reject'); trace.afterRejectMonthly = snapshot(opened);
  check(g, '月檢恢復原文及乾淨節點', () => assert.deepEqual(opened.children[0], baseline[0]));
  check(g, '月檢無任何 raw suggestion key 或 flag', () => assert.deepEqual(rawSuggestionFields(opened, [0]), []));
  check(g, 'fault 全文及 pending metadata 整個節點相等', () => assert.deepEqual(opened.children[2], fault));
  check(g, '交付段保持原樣', () => assert.deepEqual(opened.children[1], baseline[1]));
  check(g, '整份只剩 fault 原生 pending ID', () => assert.deepEqual(ids(opened), [faultId]));
});

await runGroup('C04', 'undefined、null、缺 key 區分與 envelope JSON 往返', async (g, trace) => {
  const original = { unset: undefined, nullable: null, nested: { unset: undefined, nullable: null } };
  trace.before = clone(original);
  const envelope = SuperJSON.serialize(original), envelopePath = save('undefined-null-missing-superjson-envelope', envelope);
  const parsed = readJson(envelopePath), restored = SuperJSON.deserialize(parsed);
  trace.envelope = parsed; trace.restored = clone(restored); trace.rawJsonControl = JSON.parse(JSON.stringify(original));
  check(g, 'envelope 本身完全可 JSON roundtrip', () => assert.deepEqual(parsed, envelope));
  check(g, 'deserialize 完整值相等', () => assert.deepEqual(restored, original));
  check(g, 'undefined 自有 key 保留，巢狀亦同', () => { assert.equal(Object.hasOwn(restored, 'unset'), true); assert.equal(restored.unset, undefined); assert.equal(Object.hasOwn(restored.nested, 'unset'), true); assert.equal(restored.nested.unset, undefined); });
  check(g, 'null 仍為自有 key 與 null，不變 undefined', () => { assert.equal(Object.hasOwn(restored, 'nullable'), true); assert.equal(restored.nullable, null); assert.equal(restored.nested.nullable, null); });
  check(g, '缺少的 key 維持不存在', () => { assert.equal(Object.hasOwn(restored, 'missing'), false); assert.equal(Object.hasOwn(restored.nested, 'missing'), false); });
  check(g, '普通 JSON 控制確實丟 undefined 但保留 null', () => { assert.equal(Object.hasOwn(trace.rawJsonControl, 'unset'), false); assert.equal(trace.rawJsonControl.nullable, null); });
});

const report = {
  topic: 'JD-R002/C03/codec', executedAt: new Date().toISOString(), node: process.version,
  versions: { superjson: JSON.parse(fs.readFileSync('node_modules/superjson/package.json', 'utf8')).version, 'copy-anything': JSON.parse(fs.readFileSync('node_modules/copy-anything/package.json', 'utf8')).version, ...Object.fromEntries(['platejs', '@platejs/core', '@platejs/slate', '@platejs/suggestion', 'slate', 'react', 'react-dom'].map(name => [name, JSON.parse(fs.readFileSync(`../jd-editor-review-probe/node_modules/${name}/package.json`, 'utf8')).version])) },
  borrowedPackageLock: '../jd-editor-review-probe/package-lock.json', borrowedPackageLockSha256: hash('../jd-editor-review-probe/package-lock.json'),
  profile: { nodeId: { reuseId: true, initialValueIds: 'always' }, currentUserId: 'ai', isSuggesting: true, normalization: 'native defaults', customCodecOrTransformer: false, customSuggestionMetadata: false },
  groups, passGroups: groups.filter(g => g.status === 'PASS').length, failGroups: groups.filter(g => g.status === 'FAIL').length, executionErrorGroups: groups.filter(g => g.executionError).length,
  rawJsonControl: traces.C01?.rawJsonControl,
  limits: ['Fixed 4 cases only; original R01/R01-F not modified.', 'Complete SuperJSON json+meta envelope required.', 'No DB/Python/model/DOM/IME/cross-version/all-type validation.', 'No vendor patch, custom transformer, before-image restore, codec or grouping engine.'],
};
save('codec-traces', traces);
fs.writeFileSync(path.join(directory, 'codec-results.json'), JSON.stringify(report, null, 2) + '\n');
fs.writeFileSync(path.join(directory, 'run-hashes.json'), JSON.stringify({ script: hash('codec-probe.mjs'), packageLock: hash('package-lock.json'), borrowedPackageLock: hash('../jd-editor-review-probe/package-lock.json'), results: hash(path.join(directory, 'codec-results.json')), traces: hash(path.join(directory, 'codec-traces.json')), tracesInspect: hash(path.join(directory, 'codec-traces.inspect.txt')) }, null, 2) + '\n');
console.log(JSON.stringify({ directory, ...report }, null, 2));
process.exitCode = report.failGroups || report.executionErrorGroups ? 1 : 0;
