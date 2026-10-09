/** Compile the shared Turn definition through the real guard and cross-file discovery ref. */
import { describe, expect, it } from 'vitest';
import type { ConsultantTurn } from './generated/consultant-turn';
import type { CurrentConsultantTurn } from './generated/current-consultant-turn';
import { isConsultantTurn, isCurrentConsultantTurn } from './validation';

const turn: ConsultantTurn = {
  job_file_id: '11111111-1111-4111-8111-111111111111',
  execution_id: '22222222-2222-4222-8222-222222222222',
  status: 'active',
  pause_requested: false,
  input_text: '合成訪談',
  allowed_controls: ['pause', 'cancel'],
  commentary: [{ response_id: 'response', message_id: 'message', text: '公開進度' }],
  plan_preview: null,
  candidate: {
    profile: { job_title: '工程師', organization_unit: null, reports_to: null, purpose: null },
    work: {
      revision_id: '33333333-3333-4333-8333-333333333333',
      areas: [],
      tasks: [],
      capabilities: [],
      task_links: [],
      collaborators: [],
      conditions: [],
    },
  },
};

describe('current consultant Turn contract', () => {
  it.each(['active', 'paused', 'completed', 'cancelled', 'failed'] as const)(
    'keeps the existing validation.ts guard working for %s',
    (status) => {
      expect(isConsultantTurn({ ...turn, status })).toBe(true);
    },
  );

  it('compiles the discovery ref and preserves the generated Turn type and nested candidate', () => {
    const discovery: CurrentConsultantTurn = { turn };
    expect(isCurrentConsultantTurn(discovery)).toBe(true);
    expect(isCurrentConsultantTurn({ turn: { ...turn, pause_requested: true } })).toBe(true);
    expect(isCurrentConsultantTurn({ turn: { ...turn, status: 'paused' } })).toBe(true);
    expect(isCurrentConsultantTurn({ turn: null })).toBe(true);
    expect(isCurrentConsultantTurn({})).toBe(false);
  });

  it.each([
    { ...turn, reasoning: 'private' },
    { ...turn, status: 'pause_requested' },
    { ...turn, candidate: { ...turn.candidate, checkpoint: 'private' } },
  ])('rejects private payloads or invented states in both guards', (invalid) => {
    expect(isConsultantTurn(invalid)).toBe(false);
    expect(isCurrentConsultantTurn({ turn: invalid })).toBe(false);
  });
});
