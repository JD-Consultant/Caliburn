/** Item badges join citations to JD items by identity only; a label is never a key. */
import { expect, test } from 'vitest';
import type { Reference, Target } from '../../shared/api/generated/http/types.gen';
import { buildSourceIndex, targetKey } from './source-index';

const taskA = '30000000-0000-4000-8000-00000000000a';
const taskB = '30000000-0000-4000-8000-00000000000b';
const detail = '40000000-0000-4000-8000-000000000004';

function task(id: string): Target {
  return { kind: 'task', field: null, item_id: id };
}

function reference(citationId: string, target: Target, needsRecheck = false): Reference {
  const base = {
    citation_id: citationId,
    target_label: '任務：同名任務',
    source_kind: 'interview' as const,
    source_label: '訪談序號 2 · 員工',
    needs_recheck: needsRecheck,
    jd_changed: needsRecheck,
    source_changed: false,
  };
  return { ...base, target };
}

test('two items that share one label stay separate because they are joined by identity', () => {
  const index = buildSourceIndex([reference('c1', task(taskA)), reference('c2', task(taskB))]);
  expect(index.size).toBe(2);
  expect(index.get(targetKey(task(taskA)))?.citationIds).toEqual(['c1']);
  expect(index.get(targetKey(task(taskB)))?.citationIds).toEqual(['c2']);
});

test('an item counts every citation and needs recheck when any one of them does', () => {
  const index = buildSourceIndex([
    reference('c1', task(taskA), false),
    reference('c2', task(taskA), true),
    reference('c3', task(taskA), false),
  ]);
  expect(index.get(targetKey(task(taskA)))).toEqual({
    count: 3,
    needsRecheck: true,
    citationIds: ['c1', 'c2', 'c3'],
  });
});

test('an unloaded overview has no summaries', () => {
  expect(buildSourceIndex(undefined).size).toBe(0);
});

test('task children resolve to task evidence while shared capability keeps its own evidence', () => {
  const capability: Target = { kind: 'capability', field: null, item_id: detail };
  const index = buildSourceIndex([
    reference('task-source', task(taskA), true),
    reference('capability-source', capability),
  ]);
  expect(index.get(targetKey(task(taskA)))).toEqual({
    count: 1,
    needsRecheck: true,
    citationIds: ['task-source'],
  });
  expect(index.get(targetKey(capability))).toEqual({
    count: 1,
    needsRecheck: false,
    citationIds: ['capability-source'],
  });
});

test('every part of a target takes part in its key', () => {
  const keys = new Set([
    targetKey({ kind: 'profile_field', field: 'purpose', item_id: null }),
    targetKey({ kind: 'profile_field', field: 'job_title', item_id: null }),
    targetKey({ kind: 'task', field: null, item_id: taskA }),
    targetKey({ kind: 'capability', field: null, item_id: detail }),
    targetKey({ kind: 'task', field: null, item_id: detail }),
  ]);
  expect(keys.size).toBe(5);
});
