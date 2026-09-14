import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { inspect, isDeepStrictEqual } from 'node:util';
import { editor, profile, capture, flush, clone, node, path, walk, allText, textOf } from './engine.mjs';

const stamp = new Date().toISOString().replaceAll(/[:.]/g, '-');
const directory = new URL(`./results/${stamp}/`, import.meta.url);
mkdirSync(directory, { recursive: true });
const fixture = JSON.parse(readFileSync(new URL('./fixture.json', import.meta.url), 'utf8'));
const original = JSON.parse(readFileSync(new URL('./fixture-original-f01.json', import.meta.url), 'utf8'));
const results = [], traces = {};
const json = (name, value) => writeFileSync(new URL(name, directory), JSON.stringify(value, null, 2));
const full = (name, value) => { json(`${name}.json`, value); writeFileSync(new URL(`${name}.inspect.txt`, directory), inspect(value, { depth: null, maxArrayLength: null, maxStringLength: null, compact: false })); };
const ids = value => walk(value).filter(n => n.children).map(n => n.id);
function assertIds(value) {
  const found = ids(value); assert(found.every(x => typeof x === 'string' && x.length)); assert.equal(new Set(found).size, found.length);
}
function forbidden(value, prefix = '$') {
  if (value === undefined || typeof value === 'number' && !Number.isFinite(value)) return [prefix];
  if (value && typeof value === 'object') return Object.keys(value).flatMap(k => forbidden(value[k], `${prefix}.${k}`));
  return [];
}
function leafSignature(value) {
  return walk(value).filter(n => typeof n.text === 'string' && n.text.length > 0).map(n => clone(n));
}
function fresh(name, value, mode = 'normalize') {
  json(`${name}-input.json`, value);
  const outputPath = fileURLToPath(new URL(`${name}-fresh.json`, directory));
  const proc = spawnSync(process.execPath, [fileURLToPath(new URL('./fresh-editor.mjs', import.meta.url)), fileURLToPath(new URL(`${name}-input.json`, directory)), outputPath, mode], { encoding: 'utf8', timeout: 30000 });
  const output = JSON.parse(readFileSync(outputPath, 'utf8'));
  output.processExit = proc.status; output.stderr = proc.stderr; output.stdout = proc.stdout;
  assert.equal(proc.status, 0, `fresh process failed: ${proc.stderr || output.error?.message}`);
  assert(output.ok); assert.notEqual(output.pid, process.pid);
  return output;
}
async function baseline() {
  const e = editor(fixture); e.tf.normalize({ force: true }); await flush(); return e;
}
async function group(id, description, action) {
  const trace = { id, description }, checks = [];
  traces[id] = trace;
  const check = (name, fn) => {
    try { fn(); checks.push({ name, passed: true }); }
    catch (error) { checks.push({ name, passed: false, message: error.message, actual: error.actual, expected: error.expected }); }
  };
  try { await action(trace, check); } catch (error) { trace.exception = { message: error.message, stack: error.stack }; checks.push({ name: 'execution', passed: false, message: error.message }); }
  const result = { id, description, passed: checks.length > 0 && checks.every(x => x.passed), checks };
  results.push(result); full(id, trace); json(`${id}-checks.json`, result);
  console.log(JSON.stringify({ id, passed: result.passed, failedChecks: checks.filter(x => !x.passed).map(x => ({ name: x.name, message: x.message })) }));
}

await group('F02-A', '官方 canonical 全 r2 與新程序 JSON 重開', async (t, check) => {
  t.originalF01 = original; t.input = fixture;
  const e = editor(fixture); t.initialBeforeForceNormalize = clone(e.children); const batches = capture(e);
  e.tf.normalize({ force: true }); await flush();
  t.canonical = clone(e.children); t.batches = batches;
  t.inputExactlyCanonical = isDeepStrictEqual(fixture, t.canonical);
  t.normalizationOperationTypes = batches.flatMap(b => b.operations).map(o => o.type);
  check('全部 r2 文字與非空 leaf 格式逐一保留', () => { assert.equal(allText(t.canonical), allText(original)); assert.deepEqual(leafSignature(t.canonical), leafSignature(original)); });
  check('所有輸入 Element ID 存在、唯一且來源未变', () => {
    assertIds(t.canonical); assert.deepEqual(ids(t.canonical).sort(), ids(fixture).sort());
    for (const n of walk(fixture).filter(n => n.source_refs)) assert.deepEqual(node(e, n.id).source_refs, n.source_refs);
  });
  check('原生官方 plugins 與形狀生效', () => {
    assert(e.plugins.listClassic); assert(e.plugins.table); assert(e.plugins.blockquote); assert(e.api.isVoid(node(e, walk(fixture).find(n => n.type === 'hr').id)));
    const elements = walk(e.children); assert.equal(elements.filter(n => n.type === 'table').length, 3); assert.equal(elements.filter(n => n.type === 'jd_task').length, 8);
    for (const li of elements.filter(n => n.type === 'li')) assert.equal(li.children[0].type, 'lic');
  });
  check('clean value 無 undefined 等 JSON 非值', () => assert.deepEqual(forbidden(t.canonical), []));
  t.reopened = fresh('F02-A-canonical', t.canonical);
  check('不同 Node PID／新 editor／normalization 後完整 JSON 相等', () => assert.deepEqual(t.reopened.value, t.canonical));
});

await group('F02-B', '修改段落與清單文字、官方表格插入及刪除一列', async (t, check) => {
  const e = await baseline(); t.before = clone(e.children); const batches = capture(e);
  const purposeText = textOf(node(e, 'purpose')), task4 = node(e, 'task-4');
  const lic = task4.children[2].children[0].children[1].children[0].children[0];
  t.listTargetId = lic.id; t.listOriginalText = textOf(lic);
  const purposeSuffix = '【F02 合成附註：保留訪談更正】'; const listSuffix = '【F02 合成附註：先保留輸入】';
  e.tf.insertText(purposeSuffix, { at: e.api.end(path(e, 'purpose')) });
  e.tf.insertText(listSuffix, { at: e.api.end(path(e, lic.id)) });
  t.afterText = clone(e.children);
  const tableBefore = clone(node(e, 'basic-table')), tablePath = path(e, 'basic-table');
  e.tf.select(e.api.start([...tablePath, tableBefore.children.length - 1, 0]));
  e.tf.insert.tableRow({ at: tablePath, select: false });
  await flush(); t.afterInsert = clone(e.children);
  const tableAfterInsert = node(e, 'basic-table');
  check('官方插入一列，原來各列精確保留', () => {
    assert.equal(tableAfterInsert.children.length, tableBefore.children.length + 1);
    assert.deepEqual(tableAfterInsert.children.slice(0, tableBefore.children.length), tableBefore.children);
    const row = tableAfterInsert.children.at(-1); assert.equal(row.children.length, 2); assert.equal(textOf(row), ''); assertIds(e.children);
  });
  const rowIndex = tableBefore.children.length;
  e.tf.select(e.api.start([...path(e, 'basic-table'), rowIndex, 0]));
  e.tf.remove.tableRow();
  e.tf.normalize({ force: true }); await flush();
  t.after = clone(e.children); t.batches = batches;
  check('原生刪新列後整張表的全文／格式／ID 精確回原表', () => assert.deepEqual(node(e, 'basic-table'), tableBefore));
  check('两處固定文字更新且其餘全稿精確保留', () => {
    assert.equal(textOf(node(e, 'purpose')), purposeText + purposeSuffix);
    assert.equal(textOf(node(e, lic.id)), t.listOriginalText + listSuffix);
    const expected = clone(t.before);
    for (const n of walk(expected)) if (n.id === 'purpose' || n.id === lic.id) n.children.at(-1).text += n.id === 'purpose' ? purposeSuffix : listSuffix;
    assert.deepEqual(t.after, expected); assertIds(t.after);
  });
  check('確有原生 insert_node／remove_node，非整表替換', () => {
    const ops = batches.flatMap(b => b.operations); assert(ops.some(o => o.type === 'insert_node' && o.node.type === 'tr')); assert(ops.some(o => o.type === 'remove_node' && o.node.type === 'tr'));
    assert(!ops.some(o => ['insert_node', 'remove_node'].includes(o.type) && o.node.type === 'table'));
  });
});

await group('F02-C', 'Task8 移動、Duty4 unwrap 保留完整工作後新程序重開', async (t, check) => {
  const e = await baseline(); t.before = clone(e.children); const batches = capture(e);
  const task8 = clone(node(e, 'task-8')), task4 = clone(node(e, 'task-4')), task7 = clone(node(e, 'task-7')), duty4Title = clone(node(e, 'duty-4').children[0]);
  e.tf.moveNodes({ at: path(e, 'task-8'), to: [...path(e, 'duty-1'), node(e, 'duty-1').children.length] });
  t.afterMove = clone(e.children);
  check('Task8 全 subtree／ID／來源保留且屬 Duty1', () => { assert.deepEqual(node(e, 'task-8'), task8); assert.deepEqual(path(e, 'task-8').slice(0, -1), path(e, 'duty-1')); });
  e.tf.unwrapNodes({ at: path(e, 'duty-4') }); e.tf.normalize({ force: true }); await flush();
  t.after = clone(e.children); t.batches = batches;
  check('unwrap 只取消 Duty4；Task4／7／8、原標題與八項工作保留', () => {
    assert.deepEqual(node(e, 'task-4'), task4); assert.deepEqual(node(e, 'task-7'), task7); assert.deepEqual(node(e, 'task-8'), task8); assert.deepEqual(node(e, duty4Title.id), duty4Title);
    assert(!walk(t.after).some(n => n.id === 'duty-4')); assert.equal(walk(t.after).filter(n => n.type === 'jd_task').length, 8); assertIds(t.after);
    const expected = clone(t.before), work = expected.find(n => n.id === 'section-work'), d1 = work.children.find(n => n.id === 'duty-1'), d4 = work.children.find(n => n.id === 'duty-4');
    d1.children.push(d4.children.pop()); work.children.splice(work.children.indexOf(d4), 1, ...d4.children);
    assert.deepEqual(t.after, expected);
  });
  t.reopened = fresh('F02-C-after', t.after);
  check('移動／unwrap 後檔案→不同 Node PID 新 editor 全等', () => assert.deepEqual(t.reopened.value, t.after));
});

await group('F02-D', '原生格式 operations 的普通 JSON 保存與 fresh apply', async (t, check) => {
  const e = await baseline(); t.before = clone(e.children); const batches = capture(e);
  const purpose = node(e, 'purpose'), task4Label = node(e, 'task-4').children[2].children[0].children[0];
  t.labelId = task4Label.id; t.labelBefore = clone(task4Label);
  e.tf.select(e.api.range(path(e, purpose.id))); e.tf.addMark('underline', true);
  e.tf.select(e.api.range(path(e, task4Label.id))); e.tf.removeMark('bold');
  e.tf.normalize({ force: true }); await flush();
  t.after = clone(e.children); t.batches = batches; t.operations = batches.flatMap(b => b.operations);
  t.undefinedPaths = forbidden(t.operations); full('F02-D-operations-memory', t.operations);
  const opsFile = new URL('F02-D-operations-memory.json', directory); t.operationsFromJsonFile = JSON.parse(readFileSync(opsFile, 'utf8'));
  t.setNodeOwnKeys = t.operations.filter(o => o.type === 'set_node').map(o => ({ properties: Object.keys(o.properties), newProperties: Object.keys(o.newProperties) }));
  check('原文不变；目的加底線、既有粗體 label 確實移除', () => {
    assert.equal(allText(t.after), allText(t.before)); assert(node(e, purpose.id).children.every(n => n.underline === true)); assert(walk([node(e, task4Label.id)]).filter(n => typeof n.text === 'string').every(n => !Object.hasOwn(n, 'bold')));
    assert(t.operations.some(o => o.type === 'set_node' && o.properties.bold === true && !Object.hasOwn(o.newProperties, 'bold')));
  });
  check('原生 operations 無 own undefined，普通 JSON 檔精確往返', () => { assert.deepEqual(t.undefinedPaths, []); assert.deepEqual(t.operationsFromJsonFile, t.operations); });
  t.replayed = fresh('F02-D-replay', { value: t.before, operations: t.operationsFromJsonFile }, 'apply');
  check('同基底全新 process 原生 apply 後完整 clean value 相等', () => assert.deepEqual(t.replayed.value, t.after));
});

const sha = name => createHash('sha256').update(readFileSync(new URL(name, import.meta.url))).digest('hex');
const report = { date: '2026-09-10', executedAt: new Date().toISOString(), pid: process.pid, node: process.version, profile, total: results.length, passed: results.filter(r => r.passed).length, failed: results.filter(r => !r.passed).length, results, sourceSha256: Object.fromEntries(['README.md', 'package.json', 'package-lock.json', 'prepare-fixture.mjs', 'engine.mjs', 'fresh-editor.mjs', 'probe.mjs', 'fixture.json', 'fixture-original-f01.json', 'fixture-mapping.json'].map(n => [n, sha(n)])) };
json('results.json', report); full('traces', traces);
writeFileSync(new URL('./latest-run.txt', import.meta.url), fileURLToPath(directory));
console.log(JSON.stringify({ directory: fileURLToPath(directory), total: report.total, passed: report.passed, failed: report.failed }));
process.exitCode = report.failed ? 1 : 0;
