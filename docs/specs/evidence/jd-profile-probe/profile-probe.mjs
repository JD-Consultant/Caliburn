import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fixture, source, clone, unwrappedOracle, allText, paragraph } from './fixture.mjs';
import { editor, entry, node, path, flush } from './engine.mjs';

const directory = new URL('./results/', import.meta.url);
mkdirSync(directory, { recursive: true });
const results = [], traces = {};
const everyNode = value => value.flatMap(n => [n, ...(n.children ? everyNode(n.children) : [])]);
const ids = value => everyNode(value).filter(n => n.children).map(n => n.id);
const assertIds = value => { const list = ids(value); assert(list.every(x => typeof x === 'string' && x.length)); assert.equal(new Set(list).size, list.length); };
const taskCount = value => everyNode(value).filter(n => n.type === 'jd_task').length;
async function run(id, description, action) {
  const e = editor(fixture), operations = [];
  const previous = e.onChange;
  e.onChange = options => { operations.push(...clone(e.operations)); previous(options); };
  const trace = traces[id] = { before: clone(e.children), operations };
  try { const detail = await action(e, trace); await flush(); results.push({ id, description, passed: true, detail }); }
  catch (error) { await flush(); results.push({ id, description, passed: false, error: error.message }); }
  finally { trace.after = clone(e.children); }
}

await run('F01-A', '完整 r2 容器 normalization、JSON 存檔及新 editor 重開', async (e, trace) => {
  assert.deepEqual(unwrappedOracle(fixture), source);
  e.tf.normalize({ force: true });
  const normalized = clone(e.children);
  trace.normalizationObservations = {
    rawJsonExact: JSON.stringify(normalized) === JSON.stringify(fixture),
    visibleTextExact: allText(normalized) === allText(fixture),
  };
  // Characterize the observed native removal without changing the input or
  // repairing the editor. This is one fixed test oracle, not a normalizer.
  const expectedNative = clone(fixture);
  const requirementLabel = everyNode(expectedNative).find(n => n.id === 'r2-51');
  assert.deepEqual(requirementLabel.children.at(-1), { text: '' });
  requirementLabel.children.pop();
  assert.deepEqual(normalized, expectedNative);
  trace.normalizationObservations.onlyUnformattedEmptyLeafRemoved = true;
  writeFileSync(new URL('saved-profile.json', directory), JSON.stringify(e.children, null, 2));
  const reopened = editor(JSON.parse(readFileSync(new URL('saved-profile.json', directory), 'utf8')));
  reopened.tf.normalize({ force: true });
  trace.reopened = clone(reopened.children);
  assert.deepEqual(reopened.children, normalized);
  trace.normalizationObservations.canonicalJsonRoundtripExact = true;
  assertIds(reopened.children);
  // Preserve the original strict raw-JSON failure; the observations above have
  // narrower, separately named scope and do not turn this assertion green.
  assert.deepEqual(e.children, fixture);
  return { tasks: taskCount(e.children), originalNodesAndTextExact: true, idCount: ids(e.children).length };
});

await run('F01-B', 'Task8 原生移動保留完整適用條件與來源', async (e, trace) => {
  const originalTask = clone(node(e, 'task-8')), unrelated = clone(node(e, 'task-4'));
  const destination = path(e, 'duty-1');
  e.tf.moveNodes({ at: path(e, 'task-8'), to: [...destination, node(e, 'duty-1').children.length] });
  assert.deepEqual(node(e, 'task-8'), originalTask);
  assert.deepEqual(node(e, 'task-4'), unrelated);
  assert.deepEqual(path(e, 'task-8').slice(0, -1), path(e, 'duty-1'));
  assertIds(e.children);
  trace.movedTask = clone(node(e, 'task-8'));
  return { taskSubtreeExact: true, independentTaskExact: true };
});

await run('F01-C', 'unwrap Duty 保留標題與其全部工作', async e => {
  const beforeText = allText(e.children), children = clone(node(e, 'duty-4').children);
  e.tf.unwrapNodes({ at: path(e, 'duty-4') });
  assert.equal(allText(e.children), beforeText);
  for (const child of children) assert.deepEqual(node(e, child.id), child);
  assert.equal(taskCount(e.children), 8);
  assertIds(e.children);
  return { childSubtreesExact: true, taskCount: 8 };
});

await run('F01-D', '未完整與未歸屬內容可保存；空容器另作觀測', async (e, trace) => {
  const workPath = path(e, 'section-work');
  const additions = [
    { type: 'jd_task', id: 'task-incomplete', children: [paragraph('incomplete-body', 'F01 虛構資料：協助處理問題；責任範圍尚待釐清。')] },
    paragraph('unassigned-output', 'F01 虛構資料：先保留交接說明，尚未確定歸屬哪項工作。'),
    { type: 'jd_task', id: 'task-empty-paragraph', children: [paragraph('empty-body', '')] },
  ];
  // NodeId may mutate the command's input with temporary _id history data.
  // Keep the test oracle independent from the mutable command argument.
  e.tf.insertNodes(clone(additions), { at: [...workPath, node(e, 'section-work').children.length] });
  const reopened = editor(JSON.parse(JSON.stringify(e.children)));
  reopened.tf.normalize({ force: true });
  for (const addition of additions) assert.deepEqual(node(reopened, addition.id), addition);
  assertIds(reopened.children);
  const invalid = editor([{ type: 'jd_task', id: 'empty-container', children: [] }]);
  invalid.tf.normalize({ force: true });
  trace.emptyContainerObservation = clone(invalid.children);
  return { additionsPreserved: 3, emptyContainerIsProductValidated: false, emptyContainerNativeValue: clone(invalid.children) };
});

await run('F01-E', '正文 insertBreak 的實際範圍與 Task 身分', async e => {
  const beforeText = allText(e.children), beforeTask = clone(node(e, 'task-4'));
  e.tf.select({ path: [...path(e, 'task4-description'), 0], offset: 6 });
  e.tf.insertBreak();
  assert.equal(taskCount(e.children), 8);
  assert.equal(allText(e.children), beforeText);
  assert.deepEqual(node(e, 'task-4').source_refs, beforeTask.source_refs);
  assert.equal(node(e, 'task-4').children.length, beforeTask.children.length + 1);
  assertIds(e.children);
  return { taskCount: 8, sameTaskIdentity: true, notDomEnterOrIme: true };
});

await run('F01-F', '固定 Task fragment 插入的內容、層級及 ID', async (e, trace) => {
  const copied = clone(node(e, 'task-4'));
  const workPath = path(e, 'section-work');
  e.tf.insertNodes(paragraph('fragment-destination', ''), { at: [...workPath, node(e, 'section-work').children.length] });
  e.tf.select(e.api.start(path(e, 'fragment-destination')));
  e.tf.insertFragment([copied]);
  trace.fragmentInput = copied;
  const matches = everyNode(e.children).filter(n => n.type === 'jd_task' && allText([n]) === allText([copied]));
  assert.equal(matches.length, 2, '原 Task 與貼入 Task 皆完整存在');
  assertIds(e.children);
  assert.notEqual(matches[0].id, matches[1].id);
  assert.deepEqual(matches[1].source_refs, copied.source_refs);
  return { fullCopies: 2, uniqueIds: true, clipboardOrCrossDocumentPolicyVerified: false };
});

const hashes = Object.fromEntries(['profile-probe.mjs', 'fixture.mjs', 'engine.mjs', 'README.md'].map(name => [name, createHash('sha256').update(readFileSync(new URL(name, import.meta.url))).digest('hex')]));
const report = { date: '2026-09-09', node: process.version, profile: 'platejs53.3.11; ordinary elements; reuseId true; initialValueIds always', sourceSha256: hashes, total: results.length, passed: results.filter(x => x.passed).length, failed: results.filter(x => !x.passed).length, results };
const stamp = new Date().toISOString().replaceAll(/[:.]/g, '-');
writeFileSync(new URL(`profile-${stamp}.json`, directory), JSON.stringify(report, null, 2));
writeFileSync(new URL(`profile-${stamp}-traces.json`, directory), JSON.stringify(traces, null, 2));
console.log(JSON.stringify(report, null, 2));
process.exitCode = report.failed ? 1 : 0;
