/** Compile the shared Turn definition through the real guard and cross-file discovery ref. */
import { Ajv2020 } from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import interviewPlanSchema from '../../../../api/contracts/tools/interview-plan.schema.json' with { type: 'json' };
import { describe, expect, it } from 'vitest';
import consultantTurnSchema from '../../../../api/contracts/http/consultant-turn.schema.json' with { type: 'json' };
import currentTurnSchema from '../../../../api/contracts/http/current-consultant-turn.schema.json' with { type: 'json' };
import jdAreasSchema from '../../../../api/contracts/http/jd-areas-view.schema.json' with { type: 'json' };
import jdCapabilitiesSchema from '../../../../api/contracts/http/jd-capabilities-view.schema.json' with { type: 'json' };
import jdCollaboratorsSchema from '../../../../api/contracts/http/jd-collaborators-view.schema.json' with { type: 'json' };
import jdConditionsSchema from '../../../../api/contracts/http/jd-conditions-view.schema.json' with { type: 'json' };
import jdProfileSchema from '../../../../api/contracts/http/jd-profile-view.schema.json' with { type: 'json' };
import jdTasksSchema from '../../../../api/contracts/http/jd-tasks-view.schema.json' with { type: 'json' };
import jdWorkSchema from '../../../../api/contracts/http/jd-work-view.schema.json' with { type: 'json' };
import type { ConsultantTurn } from './generated/consultant-turn';
import type { CurrentConsultantTurn } from './generated/current-consultant-turn';
import { isConsultantTurn } from './validation';

const validator = new Ajv2020();
addFormats(validator);
validator.addSchema(interviewPlanSchema, 'tools/interview-plan.schema.json');
for (const [name, schema] of Object.entries({
  'consultant-turn.schema.json': consultantTurnSchema,
  'jd-areas-view.schema.json': jdAreasSchema,
  'jd-capabilities-view.schema.json': jdCapabilitiesSchema,
  'jd-collaborators-view.schema.json': jdCollaboratorsSchema,
  'jd-conditions-view.schema.json': jdConditionsSchema,
  'jd-profile-view.schema.json': jdProfileSchema,
  'jd-tasks-view.schema.json': jdTasksSchema,
  'jd-work-view.schema.json': jdWorkSchema,
})) {
  validator.addSchema(schema, name);
}
const isCurrentConsultantTurn = validator.compile<CurrentConsultantTurn>(currentTurnSchema);

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
