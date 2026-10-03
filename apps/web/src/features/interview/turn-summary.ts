/** Presentation-only summaries of a server-verified Turn; never a substitute for its status. */
import type { ConsultantTurn } from '../../shared/api/generated/consultant-turn';

export interface TurnBadge {
  label: string;
  tone: 'info' | 'warning' | 'success' | 'error' | 'neutral';
}

export function describeTurnBadge(turn: ConsultantTurn | null): TurnBadge | null {
  if (!turn) return null;
  switch (turn.status) {
    case 'active':
      return turn.pause_requested
        ? { label: '等待安全點暫停', tone: 'warning' }
        : { label: '顧問處理中', tone: 'info' };
    case 'paused':
      return { label: '已暫停', tone: 'warning' };
    case 'completed':
      return { label: '已完成並保存', tone: 'success' };
    case 'cancelled':
      return { label: '已取消', tone: 'neutral' };
    case 'failed':
      return { label: '未完成', tone: 'error' };
  }
}

/** Active or paused Turns own the JD: readers may read, manual writes are refused by the App. */
export function isJdReadOnlyDuring(turn: ConsultantTurn | null): boolean {
  return turn?.status === 'active' || turn?.status === 'paused';
}
