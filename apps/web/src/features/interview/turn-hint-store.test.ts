/** The tab's tracked Turn identity is an external store: readers subscribe instead of copying it. */
import { beforeEach, expect, test, vi } from 'vitest';
import {
  clearTurnHint,
  readTurnHintSnapshot,
  retainTurnHint,
  subscribeTurnHint,
} from './interview-turn-api';

const fileId = '10000000-0000-4000-8000-000000000001';
const hint = {
  command_id: '60000000-0000-4000-8000-000000000006',
  execution_id: '50000000-0000-4000-8000-000000000005',
};

beforeEach(() => {
  localStorage.clear();
});

test('an empty store reads as null and an unchanged stored hint keeps one snapshot object', () => {
  expect(readTurnHintSnapshot(fileId)).toBeNull();
  retainTurnHint(fileId, hint);
  const first = readTurnHintSnapshot(fileId);
  expect(first).toEqual(hint);
  expect(readTurnHintSnapshot(fileId)).toBe(first);
});

test('writing or clearing the hint notifies subscribers; clearing another command does not', () => {
  const listener = vi.fn();
  const unsubscribe = subscribeTurnHint(listener);
  retainTurnHint(fileId, hint);
  expect(listener).toHaveBeenCalledTimes(1);
  clearTurnHint(fileId, '70000000-0000-4000-8000-000000000007');
  expect(listener).toHaveBeenCalledTimes(1);
  clearTurnHint(fileId, hint.command_id);
  expect(listener).toHaveBeenCalledTimes(2);
  expect(readTurnHintSnapshot(fileId)).toBeNull();
  unsubscribe();
  retainTurnHint(fileId, hint);
  expect(listener).toHaveBeenCalledTimes(2);
});

test('another tab writing the hint reaches subscribers through the storage event', () => {
  const listener = vi.fn();
  const unsubscribe = subscribeTurnHint(listener);
  window.dispatchEvent(new StorageEvent('storage', { key: `caliburn:interview-turn:${fileId}` }));
  expect(listener).toHaveBeenCalledTimes(1);
  unsubscribe();
});

test('a corrupt stored hint reads as null; the composer reports that corruption itself', () => {
  localStorage.setItem(`caliburn:interview-turn:${fileId}`, '{not json');
  expect(readTurnHintSnapshot(fileId)).toBeNull();
});
