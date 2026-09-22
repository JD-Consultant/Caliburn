import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { Schema } from 'prosemirror-model';
import { EditorState } from 'prosemirror-state';
import {
  addSuggestionMarks,
  suggestionModePlugin,
  suggestionTransactionKey,
  rejectSuggestionsInRange,
  acceptSuggestionsInRange,
} from 'prosemirror-suggestion-mode';

const root = path.dirname(fileURLToPath(import.meta.url));
const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
const dir = path.join(root, 'results', `run-${stamp}`);
fs.mkdirSync(dir, { recursive: true });
const schema = new Schema({
  nodes: {
    doc: { content: 'paragraph+' },
    paragraph: {
      content: 'text*', group: 'block',
      attrs: { id: { default: null }, scope: { default: null }, sourceRefs: { default: [] } },
    },
    text: { group: 'inline' },
  },
  marks: addSuggestionMarks({
    strong: {},
    link: { attrs: { href: {}, title: { default: null } }, inclusive: false },
  }),
});
const plain = text => [{ type: 'text', text }];
const fixture = {
  type: 'doc', content: [
    { type: 'paragraph', attrs: { id: 'task-A', scope: '例行設備檢查', sourceRefs: ['utterance-1'] }, content: plain('每月檢查一次，記錄結果。') },
    { type: 'paragraph', attrs: { id: 'task-B', scope: '故障通報', sourceRefs: ['utterance-2'] }, content: plain('故障時通報主管，記錄原因。') },
    { type: 'paragraph', attrs: { id: 'task-C', scope: '所有班別', sourceRefs: ['utterance-3'] }, content: [
      { type: 'text', text: '參閱' },
      { type: 'text', text: '設備手冊', marks: [{ type: 'link', attrs: { href: 'https://example.invalid/manual-v1', title: '原版手冊' } }] },
      { type: 'text', text: '。' },
    ] },
  ],
};
const report = {
  startedAt: new Date().toISOString(), nodeVersion: process.version,
  scope: 'Three fixed native transaction / doc JSON / new EditorState observations. No DOM, history, model, DB, before-image reconstruction or vendor patch.',
  packageVersion: 'prosemirror-suggestion-mode@1.0.79',
  licenseCaveat: 'package/README declares MIT; independently downloaded source has no separate LICENSE; author README states WIP. Not adoption clearance.',
  groups: [], firstGap: null,
};
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const sha = filename => crypto.createHash('sha256').update(fs.readFileSync(filename)).digest('hex');
function save(name, data) {
  const file = path.join(dir, name);
  fs.writeFileSync(file, JSON.stringify(data, null, 2) + '\n');
  return { file: path.relative(root, file).replaceAll('\\', '/'), sha256: sha(file) };
}
function fresh(json) {
  return EditorState.create({
    schema, doc: schema.nodeFromJSON(json),
    plugins: [suggestionModePlugin({ inSuggestionMode: false, username: 'default-unused', data: {} })],
  });
}
function errorInfo(error) { return { name: error.name, message: error.message, stack: error.stack }; }
function block(state, id) {
  const found = [];
  state.doc.descendants((node, pos) => {
    if (node.type.name === 'paragraph' && node.attrs.id === id) found.push({ node, pos });
  });
  if (found.length !== 1) throw new Error(`Expected exactly one fixed fixture block ${id}, got ${found.length}`);
  return found[0];
}
function pending(state) {
  const result = [];
  state.doc.descendants((node, pos) => {
    for (const mark of node.marks) {
      if (mark.type.name === 'suggestion_insert' || mark.type.name === 'suggestion_delete') {
        result.push({ from: pos, to: pos + node.nodeSize, text: node.text ?? null, mark: mark.toJSON(), allMarks: node.marks.map(m => m.toJSON()) });
      }
    }
  });
  return result;
}
function snapshot(state) { return { doc: state.doc.toJSON(), pending: pending(state) }; }
function traceApply(state, transaction, label, traces) {
  const trace = { label, before: snapshot(state), requestedSteps: transaction.steps.map(s => s.toJSON()), requestedStepClasses: transaction.steps.map(s => s.constructor.name), requestedDoc: transaction.doc.toJSON() };
  traces.push(trace);
  try {
    const output = state.applyTransaction(transaction);
    trace.transactions = output.transactions.map(t => ({ steps: t.steps.map(s => s.toJSON()), stepClasses: t.steps.map(s => s.constructor.name), doc: t.doc.toJSON() }));
    trace.after = snapshot(output.state);
    return output.state;
  } catch (error) {
    trace.error = errorInfo(error);
    trace.callerStateAfterThrow = snapshot(state);
    throw error;
  }
}
function proposal(transaction, groupId, username, stage) {
  return transaction.setMeta(suggestionTransactionKey, { inSuggestionMode: true, username, data: { groupId, stage } });
}
// Fixed fixture helper only: exact known substring in one known paragraph.
// Existing pending insertions are addressed by their current marked text, not an AI text locator.
function knownRange(state, id, expected, groupId = null) {
  const { node, pos } = block(state, id);
  const matches = [];
  node.descendants((child, offset) => {
    if (!child.isText) return;
    if (groupId && !child.marks.some(m => m.type.name === 'suggestion_insert' && m.attrs.data?.groupId === groupId)) return;
    let start = child.text.indexOf(expected);
    while (start !== -1) {
      matches.push({ from: pos + 1 + offset + start, to: pos + 1 + offset + start + expected.length });
      start = child.text.indexOf(expected, start + 1);
    }
  });
  if (matches.length !== 1) throw new Error(`Fixed fixture substring ${expected} in ${id}/${groupId} matched ${matches.length} ranges`);
  return matches[0];
}
function replace(state, id, oldText, newText, groupId, username, stage, traces, insidePending = false) {
  const range = knownRange(state, id, oldText, insidePending ? groupId : null);
  return traceApply(state, proposal(state.tr.insertText(newText, range.from, range.to), groupId, username, stage), stage, traces);
}
function roundtrip(state, label, traces) {
  const artifact = save(`${label}.doc.json`, state.doc.toJSON());
  const reopened = fresh(JSON.parse(fs.readFileSync(path.join(root, artifact.file), 'utf8')));
  traces.push({ label: `${label}:new-EditorState-from-file`, artifact, documentEqual: equal(state.doc.toJSON(), reopened.doc.toJSON()), pendingEqual: equal(pending(state), pending(reopened)), after: snapshot(reopened) });
  return reopened;
}
// This does not implement a grouping engine. It calls the vendor range command for
// one disjoint contiguous fixture group and refuses a bounding range touching another group.
function reviewRange(state, groupId) {
  const marks = pending(state);
  const selected = marks.filter(x => x.mark.attrs.data?.groupId === groupId);
  if (!selected.length) throw new Error(`No pending marks for fixture group ${groupId}`);
  const range = { from: Math.min(...selected.map(x => x.from)), to: Math.max(...selected.map(x => x.to)) };
  const other = marks.filter(x => x.from < range.to && x.to > range.from && x.mark.attrs.data?.groupId !== groupId);
  if (other.length) throw new Error('Fixture group bounding range includes another group; no group engine is permitted');
  return range;
}
function review(state, groupId, action, traces) {
  const range = reviewRange(state, groupId);
  let output = state;
  let dispatchCount = 0;
  const command = action === 'reject' ? rejectSuggestionsInRange(range.from, range.to) : acceptSuggestionsInRange(range.from, range.to);
  const returned = command(state, tr => { dispatchCount++; output = traceApply(state, tr, `${action}:${groupId}`, traces); });
  traces.push({ label: 'vendor-range-command-result', action, groupId, range, returned, dispatchCount });
  if (!returned || dispatchCount !== 1) throw new Error(`Vendor review did not dispatch exactly once: ${returned}/${dispatchCount}`);
  return output;
}
function check(group, name, passed, detail) {
  group.checks.push({ name, passed, detail });
  if (!passed && !report.firstGap) report.firstGap = { group: group.id, name, detail };
}
function runGroup(id, execute) {
  const group = { id, checks: [], traces: [] };
  report.groups.push(group);
  try { execute(group); } catch (error) {
    group.error = errorInfo(error);
    check(group, 'complete fixed observation without exception', false, group.error);
  }
  group.status = group.checks.length && group.checks.every(c => c.passed) && !group.error ? 'PASS_FIXED_CASE' : 'GAP_OBSERVED';
  group.artifact = save(`${id}.json`, group);
  console.log(`${id}: ${group.status}`);
}

save('fixture.doc.json', fixture);
runGroup('A-independent-pending', g => {
  let state = fresh(fixture);
  state = replace(state, 'task-A', '每月檢查一次', '每週檢查一次', 'A', 'AI', 'A:AI-initial', g.traces);
  state = replace(state, 'task-B', '通報主管', '先隔離設備再通報主管', 'B', 'AI', 'B:AI-independent', g.traces);
  check(g, 'both A and B contain pending deletion and insertion', ['A', 'B'].every(id => ['suggestion_insert', 'suggestion_delete'].every(type => pending(state).some(x => x.mark.attrs.data?.groupId === id && x.mark.type === type))), pending(state));
  const before = state;
  state = roundtrip(state, 'A-before-reject', g.traces);
  check(g, 'doc and pending survive file JSON and new EditorState', equal(snapshot(state), snapshot(before)));
  const bBefore = block(state, 'task-B').node.toJSON();
  state = review(state, 'A', 'reject', g.traces);
  check(g, 'A exactly restored including attrs and sourceRefs', equal(block(state, 'task-A').node.toJSON(), fixture.content[0]), block(state, 'task-A').node.toJSON());
  check(g, 'B text and pending marks exactly unchanged', equal(block(state, 'task-B').node.toJSON(), bBefore), block(state, 'task-B').node.toJSON());
  check(g, 'only B remains pending', pending(state).length > 0 && pending(state).every(x => x.mark.attrs.data?.groupId === 'B'), pending(state));
  save('A-after-reject.doc.json', state.doc.toJSON());
});

runGroup('B-ai-human-ai', g => {
  let state = fresh(fixture);
  state = replace(state, 'task-A', '每月檢查一次', '每週檢查一次', 'A', 'AI', 'AI-initial', g.traces);
  state = replace(state, 'task-A', '一次', '兩次', 'A', 'employee', 'human-continues-A', g.traces, true);
  state = replace(state, 'task-A', '檢查', '巡檢', 'A', 'AI', 'AI-continues-A', g.traces, true);
  check(g, 'continued insertion contains latest wording', pending(state).filter(x => x.mark.type === 'suggestion_insert' && x.mark.attrs.data?.groupId === 'A').map(x => x.text).join('') === '每週巡檢兩次', pending(state));
  const before = state;
  state = roundtrip(state, 'B-before-review', g.traces);
  check(g, 'continued pending survives doc JSON reopen', equal(snapshot(state), snapshot(before)));
  const rejected = review(state, 'A', 'reject', g.traces);
  check(g, 'reject latest A restores original wording and attrs', equal(block(rejected, 'task-A').node.toJSON(), fixture.content[0]), block(rejected, 'task-A').node.toJSON());
  check(g, 'reject clears pending', pending(rejected).length === 0, pending(rejected));
  const accepted = review(fresh(JSON.parse(fs.readFileSync(path.join(dir, 'B-before-review.doc.json'), 'utf8'))), 'A', 'accept', g.traces);
  const expected = { ...fixture.content[0], content: plain('每週巡檢兩次，記錄結果。') };
  check(g, 'accept retains latest AI-human-AI wording and attrs', equal(block(accepted, 'task-A').node.toJSON(), expected), block(accepted, 'task-A').node.toJSON());
  check(g, 'accept clears pending', pending(accepted).length === 0, pending(accepted));
  save('B-after-reject.doc.json', rejected.doc.toJSON());
  save('B-after-accept.doc.json', accepted.doc.toJSON());
});

runGroup('C-link-and-node-attrs', g => {
  // Independent observations stay in this one predeclared capabilities group.
  const observations = [
    ['link-href-title', initial => {
      const { from, to } = knownRange(initial, 'task-C', '設備手冊');
      return proposal(initial.tr.addMark(from, to, schema.marks.link.create({ href: 'https://example.invalid/manual-v2', title: '新版手冊' })), 'C-link', 'AI', 'link-href-title');
    }, 'C-link', state => {
      const links = [];
      block(state, 'task-C').node.descendants(node => { for (const mark of node.marks) if (mark.type.name === 'link') links.push(mark.attrs); });
      return links.length === 1 && links[0].href === 'https://example.invalid/manual-v2' && links[0].title === '新版手冊';
    }],
    ['node-scope-attr', initial => proposal(initial.tr.setNodeAttribute(block(initial, 'task-C').pos, 'scope', '僅白班'), 'C-attrs', 'AI', 'node-scope-attr'), 'C-attrs', state => block(state, 'task-C').node.attrs.scope === '僅白班'],
  ];
  for (const [label, make, groupId, latest] of observations) {
    try {
      const initial = fresh(fixture);
      const transaction = make(initial);
      const stepTypes = transaction.steps.map(s => ({ class: s.constructor.name, json: s.toJSON() }));
      g.traces.push({ label: `${label}:actual-step-types`, stepTypes });
      let state = traceApply(initial, transaction, label, g.traces);
      check(g, `${label}: vendor produces pending metadata`, pending(state).some(x => x.mark.attrs.data?.groupId === groupId), { stepTypes, pending: pending(state) });
      const before = state;
      state = roundtrip(state, `C-${label}-before-review`, g.traces);
      check(g, `${label}: JSON doc and pending preserved`, equal(snapshot(state), snapshot(before)));
      const rejected = review(state, groupId, 'reject', g.traces);
      check(g, `${label}: reject restores original attrs and marks`, equal(block(rejected, 'task-C').node.toJSON(), fixture.content[2]), block(rejected, 'task-C').node.toJSON());
      const accepted = review(fresh(before.doc.toJSON()), groupId, 'accept', g.traces);
      check(g, `${label}: accept keeps latest attrs`, latest(accepted), block(accepted, 'task-C').node.toJSON());
      check(g, `${label}: both reviews clear pending`, pending(rejected).length === 0 && pending(accepted).length === 0);
      save(`C-${label}-after-reject.doc.json`, rejected.doc.toJSON());
      save(`C-${label}-after-accept.doc.json`, accepted.doc.toJSON());
    } catch (error) {
      check(g, `${label}: complete without exception`, false, errorInfo(error));
    }
  }
});

report.completedAt = new Date().toISOString();
report.status = report.groups.every(g => g.status === 'PASS_FIXED_CASE') ? 'ALL_FIXED_CASES_PASS' : 'GAPS_PRESERVED';
report.evidenceHashes = ['README.md', 'package.json', 'package-lock.json', 'probe.mjs'].map(name => ({ name, sha256: sha(path.join(root, name)) }));
report.artifacts = fs.readdirSync(dir).filter(name => name.endsWith('.json')).map(name => ({ name, sha256: sha(path.join(dir, name)) }));
const reportFile = save('report.json', report);
console.log(JSON.stringify({ status: report.status, firstGap: report.firstGap, reportFile }, null, 2));
process.exitCode = report.status === 'ALL_FIXED_CASES_PASS' ? 0 : 2;
