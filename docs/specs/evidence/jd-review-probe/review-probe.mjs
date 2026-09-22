import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { inspect } from 'node:util';
import { createSlateEditor } from 'platejs';
import { BaseSuggestionPlugin, acceptSuggestion, rejectSuggestion, getSuggestionKey } from '@platejs/suggestion';

const OLD = '僅有月檢約定的專案按月檢查。';
const AI_FIRST = '所有專案都按月檢查。';
const HUMAN = '僅有月檢約定的專案按月檢查，並記錄結果。';
const AI_LATEST = '僅有月檢約定的專案按月檢查，記錄結果並追蹤未解事項。';
const FAULT = '記錄故障處理結果與未解事項。';
const p = (id, text, marks = {}) => ({ type: 'p', id, children: [{ text, ...marks }] });
const baseline = [p('monthly', OLD), p('delivery', '交付版本與檢查結果一致。')];
const clone = structuredClone;
const flush = () => new Promise(resolve => setImmediate(resolve));
const runId = new Date().toISOString().replace(/[:.]/g, '-');
const directory = path.join('results', runId);
fs.mkdirSync(directory, { recursive: true });
const groups = [];
const traces = {};
const eBatches = new WeakMap();

function editor(value, userId = 'ai') {
  const e = createSlateEditor({
    value: clone(value),
    nodeId: { reuseId: true, initialValueIds: 'always' },
    plugins: [BaseSuggestionPlugin.configure({ options: { currentUserId: userId, isSuggesting: true } })],
  });
  const batches = [];
  const original = e.onChange;
  e.onChange = options => { batches.push({ operations: clone(e.operations), value: clone(e.children) }); original(options); };
  eBatches.set(e, batches);
  return e;
}
function dataEntries(e, at = []) {
  const api = e.getApi(BaseSuggestionPlugin).suggestion;
  return api.nodes({ at }).flatMap(([node, nodePath]) => {
    // Read only public plugin queries; no synthetic metadata or grouping.
    const list = api.isBlockSuggestion(node) ? [api.suggestionData(node)] : api.dataList(node);
    return list.filter(Boolean).map(item => ({ path: nodePath, nodeId: node.id ?? null, data: clone(item) }));
  });
}
function ids(e, at = []) { return [...new Set(dataEntries(e, at).map(entry => entry.data.id))]; }
function snapshot(e) { return { value: clone(e.children), selection: clone(e.selection), suggestionEntries: dataEntries(e), batches: clone(eBatches.get(e)) }; }
function save(label, value) {
  const jsonPath = path.join(directory, `${label}.json`);
  fs.writeFileSync(jsonPath, JSON.stringify(value, null, 2) + '\n');
  fs.writeFileSync(path.join(directory, `${label}.inspect.txt`), inspect(value, { depth: null, maxArrayLength: null, compact: false }) + '\n');
  return jsonPath;
}
function reopen(jsonPath) { return editor(JSON.parse(fs.readFileSync(jsonPath, 'utf8'))); }
function check(group, name, action) {
  try { action(); group.checks.push({ name, pass: true }); }
  catch (error) { group.checks.push({ name, pass: false, error: error.message }); }
}
async function group(id, title, run) {
  const result = { id, title, checks: [] }; groups.push(result);
  const trace = traces[id] = {};
  try { await run(result, trace); }
  catch (error) { result.executionError = error.stack; }
  result.status = result.executionError ? 'UNSUPPORTED_OR_EXECUTION_ERROR' : result.checks.some(c => !c.pass) ? 'FAIL' : 'PASS';
}
async function replaceLeafText(e, expectedText, nextText) {
  const entries = [...e.api.nodes({ at: [0], match: node => typeof node.text === 'string' && node.text === expectedText })];
  assert.equal(entries.length, 1, 'Fixed fixture must expose exactly one target text leaf.');
  e.tf.select(e.api.range(entries[0][1]));
  e.tf.insertText(nextText);
  await flush();
}
async function resolve(e, suggestionId, action) {
  // Authored accept/reject tests use these ID/key fields. They are resolution
  // arguments read from actual native data, never metadata injected into nodes.
  e.getApi(BaseSuggestionPlugin).suggestion.withoutSuggestions(() => {
    (action === 'accept' ? acceptSuggestion : rejectSuggestion)(e, { suggestionId, keyId: getSuggestionKey(suggestionId) });
  });
  await flush();
}
let pendingPath, originalMonthlyId, faultId, faultPending, pendingValue;

await group('R01-1', '兩組 pending 保存重開後取消月檢，保留故障 pending', async (g, trace) => {
  const e = editor(baseline); trace.before = snapshot(e);
  await replaceLeafText(e, OLD, AI_FIRST); trace.afterMonthly = snapshot(e);
  const monthlyIds = ids(e, [0]); assert.equal(monthlyIds.length, 1); originalMonthlyId = monthlyIds[0];
  e.tf.insertNodes(p('fault', FAULT), { at: [2] }); await flush();
  faultId = e.getApi(BaseSuggestionPlugin).suggestion.nodeId(e.children[2]);
  assert.ok(faultId); assert.notEqual(faultId, originalMonthlyId);
  pendingValue = clone(e.children); faultPending = clone(e.children[2]);
  trace.beforeSave = snapshot(e); trace.monthlyId = originalMonthlyId; trace.faultId = faultId;
  pendingPath = save('two-pending-value', pendingValue);
  const opened = reopen(pendingPath); trace.afterReopen = snapshot(opened);
  check(g, 'JSON→全新 editor 完整 pending value 相等', () => assert.deepEqual(opened.children, pendingValue));
  await resolve(opened, originalMonthlyId, 'reject'); trace.afterReject = snapshot(opened);
  check(g, '月檢回到原始正文及乾淨節點', () => assert.deepEqual(opened.children[0], baseline[0]));
  check(g, '故障正文及 pending metadata 完整保留', () => assert.deepEqual(opened.children[2], faultPending));
  check(g, '別處交付內容不變', () => assert.deepEqual(opened.children[1], baseline[1]));
  check(g, '只剩故障 ID 待審', () => assert.deepEqual(ids(opened), [faultId]));
});

await group('R01-2', '同一 pending fixture 重開後接受月檢，保留故障 pending', async (g, trace) => {
  assert.ok(pendingPath, 'Group 1 must produce a real native pending fixture.');
  const e = reopen(pendingPath); trace.beforeAccept = snapshot(e);
  await resolve(e, originalMonthlyId, 'accept'); trace.afterAccept = snapshot(e);
  check(g, '接受當下月檢新文，不回到原文', () => assert.deepEqual(e.children[0], p('monthly', AI_FIRST)));
  check(g, '故障正文及 pending metadata 完整保留', () => assert.deepEqual(e.children[2], faultPending));
  check(g, '別處交付內容不變', () => assert.deepEqual(e.children[1], baseline[1]));
  check(g, '月檢已結算，只剩故障待審', () => assert.deepEqual(ids(e), [faultId]));
});

await group('R01-3', 'AI→人工→AI 後原始待審組 accept/reject 的實際範圍', async (g, trace) => {
  assert.ok(pendingPath);
  const e = reopen(pendingPath); trace.afterFirstAI = snapshot(e);
  e.setOption(BaseSuggestionPlugin, 'currentUserId', 'human');
  await replaceLeafText(e, AI_FIRST, HUMAN); trace.afterHuman = snapshot(e);
  e.setOption(BaseSuggestionPlugin, 'currentUserId', 'ai');
  await replaceLeafText(e, HUMAN, AI_LATEST); trace.afterSecondAI = snapshot(e);
  trace.monthlyIdsByStage = { afterFirstAI: [originalMonthlyId], afterHuman: [...new Set(trace.afterHuman.suggestionEntries.filter(x => x.path[0] === 0).map(x => x.data.id))], afterSecondAI: ids(e, [0]) };
  check(g, '續編仍是原生同一月檢 ID（不造共組）', () => assert.deepEqual(ids(e, [0]), [originalMonthlyId]));
  const chainValue = clone(e.children); const chainPath = save('ai-human-ai-pending-value', chainValue);
  const accepted = reopen(chainPath); trace.acceptReopened = snapshot(accepted);
  check(g, 'AI→人→AI JSON 重開不丟原生 metadata', () => assert.deepEqual(accepted.children, chainValue));
  await resolve(accepted, originalMonthlyId, 'accept'); trace.afterAcceptOriginalId = snapshot(accepted);
  check(g, '接受原始月檢組得到最新版完整正文且該組結清', () => assert.deepEqual(accepted.children[0], p('monthly', AI_LATEST)));
  check(g, '接受月檢不動故障 pending', () => assert.deepEqual(accepted.children[2], faultPending));
  const rejected = reopen(chainPath);
  await resolve(rejected, originalMonthlyId, 'reject'); trace.afterRejectOriginalId = snapshot(rejected);
  check(g, '拒絕原始月檢組恢復組前完整內容', () => assert.deepEqual(rejected.children[0], baseline[0]));
  check(g, '拒絕月檢不動故障 pending', () => assert.deepEqual(rejected.children[2], faultPending));
  trace.remainingIdsAfterAccept = ids(accepted); trace.remainingIdsAfterReject = ids(rejected);
});

await group('R01-4', '取消 bold 的待審變更 JSON 重開後拒絕', async (g, trace) => {
  const boldBaseline = [p('format', '保留必要的完成要求。', { bold: true })];
  const e = editor(boldBaseline); trace.before = snapshot(e);
  e.tf.select(e.api.range([0])); e.tf.removeMark('bold'); await flush(); trace.afterRemoveMark = snapshot(e);
  const updateIds = ids(e); assert.equal(updateIds.length, 1); const updateId = updateIds[0];
  const data = e.getApi(BaseSuggestionPlugin).suggestion.dataList(e.children[0].children[0])[0];
  trace.originalPayload = { hasBoldKey: Object.hasOwn(data.properties, 'bold'), keys: Object.keys(data.properties), boldIsUndefined: data.properties.bold === undefined };
  const memoryValue = clone(e.children); const jsonPath = save('remove-bold-pending-value', memoryValue);
  const memoryOpened = editor(memoryValue); trace.memoryReopened = snapshot(memoryOpened);
  await resolve(memoryOpened, updateId, 'reject'); trace.memoryReject = snapshot(memoryOpened);
  check(g, '保留 undefined 的記憶體控制組 reject 恢復粗體', () => assert.deepEqual(memoryOpened.children, boldBaseline));
  const jsonOpened = reopen(jsonPath); trace.jsonReopened = snapshot(jsonOpened);
  const jsonData = jsonOpened.getApi(BaseSuggestionPlugin).suggestion.dataList(jsonOpened.children[0].children[0])[0];
  trace.jsonPayload = { hasBoldKey: Object.hasOwn(jsonData.properties, 'bold'), keys: Object.keys(jsonData.properties) };
  await resolve(jsonOpened, updateId, 'reject'); trace.jsonReject = snapshot(jsonOpened);
  check(g, '標準 JSON 重開後 reject 仍恢復原粗體', () => assert.deepEqual(jsonOpened.children, boldBaseline));
  check(g, '格式正文不丟失', () => assert.equal(jsonOpened.api.string([0]), '保留必要的完成要求。'));
});

const packages = ['platejs', '@platejs/core', '@platejs/slate', '@platejs/suggestion', '@platejs/diff', 'slate', 'react', 'react-dom'];
const versions = Object.fromEntries(packages.map(name => [name, JSON.parse(fs.readFileSync(`node_modules/${name}/package.json`, 'utf8')).version]));
const report = { topic: 'JD-R002/C03/R01', executedAt: new Date().toISOString(), node: process.version, versions, profile: { currentUserIds: ['ai', 'human'], isSuggesting: true, nodeId: { reuseId: true, initialValueIds: 'always' }, normalization: 'native defaults; suggestion wrappers normalize normally', customSuggestionMetadataWritten: false, aiHelpersUsed: false }, groups, passGroups: groups.filter(g => g.status === 'PASS').length, failGroups: groups.filter(g => g.status === 'FAIL').length, executionErrorGroups: groups.filter(g => g.executionError).length, limitations: ['No DOM/IME/UI/LLM/DB.', 'Only fixed unconfirmed suggestions; no accepted-history rollback.', 'No custom codec/grouping/review/rollback engine.', 'Different author profile is one tested policy, not an adopted product requirement.'] };
save('review-traces', traces);
fs.writeFileSync(path.join(directory, 'review-results.json'), JSON.stringify(report, null, 2) + '\n');
fs.writeFileSync('results/latest-run.txt', directory + '\n');
const hash = file => createHash('sha256').update(fs.readFileSync(file)).digest('hex');
fs.writeFileSync(path.join(directory, 'run-hashes.json'), JSON.stringify({ script: hash('review-probe.mjs'), packageLock: hash('package-lock.json'), results: hash(path.join(directory, 'review-results.json')), traces: hash(path.join(directory, 'review-traces.json')) }, null, 2) + '\n');
console.log(JSON.stringify({ directory, ...report }, null, 2));
process.exitCode = report.failGroups || report.executionErrorGroups ? 1 : 0;
