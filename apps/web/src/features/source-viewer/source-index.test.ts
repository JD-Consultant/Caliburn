/** Item badges join citations to JD items by identity only; a label is never a key. */
import { expect, test } from 'vitest';
import type { Reference, Target } from '../../shared/api/generated/jd-sources-view';
import { buildSourceIndex, targetKey } from './source-index';

const taskA = '30000000-0000-4000-8000-00000000000a';
const taskB = '30000000-0000-4000-8000-00000000000b';
const detail = '40000000-0000-4000-8000-000000000004';

function task(id: string): Target {
  return { kind: 'task', field: null, item_id: id, task_id: null };
}

function reference(citationId: string, target?: Target, needsRecheck = false): Reference {
  const base = {
    citation_id: citationId,
    target_label: '任務：同名任務',
    source_kind: 'interview' as const,
    source_label: '訪談序號 2 · 員工',
    needs_recheck: needsRecheck,
    jd_changed: needsRecheck,
    source_changed: false,
  };
  return target ? { ...base, target } : base;
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

test('a server that predates target yields no summaries instead of guessing from the label', () => {
  expect(buildSourceIndex([reference('c1')]).size).toBe(0);
  expect(buildSourceIndex(undefined).size).toBe(0);
});

test('every part of a target takes part in its key', () => {
  const keys = new Set([
    targetKey({ kind: 'profile_field', field: 'purpose', item_id: null, task_id: null }),
    targetKey({ kind: 'profile_field', field: 'job_title', item_id: null, task_id: null }),
    targetKey({ kind: 'detail', field: null, item_id: detail, task_id: taskA }),
    targetKey({ kind: 'detail', field: null, item_id: detail, task_id: taskB }),
    targetKey({ kind: 'task', field: null, item_id: detail, task_id: null }),
  ]);
  expect(keys.size).toBe(5);
});
