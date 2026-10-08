/** Summaries only present a server-verified status; the JD lock follows active and paused only. */
import { expect, test } from 'vitest';
import type { ConsultantTurn } from '../../shared/api/generated/consultant-turn';
import { describeTurnBadge, isJdReadOnlyDuring } from './turn-summary';

function turn(status: ConsultantTurn['status'], pauseRequested = false): ConsultantTurn {
  return {
    job_file_id: '10000000-0000-4000-8000-000000000001',
    execution_id: '50000000-0000-4000-8000-000000000005',
    status,
    pause_requested: pauseRequested,
    input_text: '原輸入',
    commentary: [],
    plan_preview: null,
    candidate: null,
    allowed_controls: [],
  };
}

test('each status has its own badge, and a pause request is not yet a pause', () => {
  expect(describeTurnBadge(null)).toBeNull();
  expect(describeTurnBadge(turn('active'))).toEqual({ label: '顧問處理中', tone: 'info' });
  expect(describeTurnBadge(turn('active', true))).toEqual({
    label: '等待安全點暫停',
    tone: 'warning',
  });
  expect(describeTurnBadge(turn('paused', true))).toEqual({ label: '已暫停', tone: 'warning' });
  expect(describeTurnBadge(turn('completed'))).toEqual({ label: '已完成並保存', tone: 'success' });
  expect(describeTurnBadge(turn('cancelled'))).toEqual({ label: '已取消', tone: 'neutral' });
  expect(describeTurnBadge(turn('failed'))).toEqual({ label: '未完成', tone: 'error' });
});

test('the JD is read-only while a Turn is active or paused and open otherwise', () => {
  expect(isJdReadOnlyDuring(turn('active'))).toBe(true);
  expect(isJdReadOnlyDuring(turn('paused'))).toBe(true);
  for (const status of ['completed', 'cancelled', 'failed'] as const)
    expect(isJdReadOnlyDuring(turn(status))).toBe(false);
  expect(isJdReadOnlyDuring(null)).toBe(false);
});
