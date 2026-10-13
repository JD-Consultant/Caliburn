import { stubHttp } from '../../test-http';
import { QueryClient } from '@tanstack/react-query';
import { afterEach, expect, test, vi } from 'vitest';
import type { ConsultantTurn } from '../../shared/api/generated/http/types.gen';
import {
  consultantTurnByCommandQuery,
  consultantTurnQuery,
  controlConsultantTurn,
  currentConsultantTurnQuery,
  submitInterviewInput,
} from './interview-turn-api';
import { interviewPlanQuery } from './interview-plan-api';

const jobFileId = '10000000-0000-4000-8000-000000000001';
const executionId = '20000000-0000-4000-8000-000000000002';
const commandId = '30000000-0000-4000-8000-000000000003';
const foreignId = '40000000-0000-4000-8000-000000000004';
const requestId = '50000000-0000-4000-8000-000000000005';
const turn: ConsultantTurn = {
  job_file_id: jobFileId,
  execution_id: executionId,
  status: 'active',
  pause_requested: false,
  input_text: 'private interview',
  commentary: [],
  candidate: null,
  plan_preview: null,
  allowed_controls: ['pause', 'cancel'],
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test.each(['acceptance', 'control', 'command', 'execution', 'current', 'plan'] as const)(
  '%s rejects a foreign result with the original request and caller correlation',
  async (route) => {
    const diagnostic = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const foreignTurn = { ...turn, job_file_id: foreignId };
    const body =
      route === 'acceptance'
        ? {
            job_file_id: jobFileId,
            command_id: foreignId,
            source_id: foreignId,
            execution_id: executionId,
          }
        : route === 'plan'
          ? { job_file_id: foreignId, plan: 'private interview' }
          : route === 'current'
            ? { turn: foreignTurn }
            : foreignTurn;
    stubHttp(() =>
      Promise.resolve(Response.json(body, { headers: { 'X-Request-ID': requestId } })),
    );
    const client = new QueryClient();
    try {
      const response =
        route === 'acceptance'
          ? submitInterviewInput(jobFileId, { command_id: commandId, text: 'private interview' })
          : route === 'control'
            ? controlConsultantTurn(jobFileId, executionId, 'pause')
            : route === 'command'
              ? client.query(consultantTurnByCommandQuery(jobFileId, commandId))
              : route === 'execution'
                ? client.query(consultantTurnQuery(jobFileId, executionId))
                : route === 'plan'
                  ? client.query(interviewPlanQuery(jobFileId))
                  : client.query(currentConsultantTurnQuery(jobFileId));
      await expect(response).rejects.toMatchObject({ kind: 'invalid_response', requestId });
      expect(diagnostic).toHaveBeenCalledExactlyOnceWith('caliburn', {
        event: 'http_failure',
        kind: 'invalid_response',
        status: 200,
        requestId,
        jobFileId,
        ...(route === 'acceptance' || route === 'command' ? { commandId } : {}),
        ...(route === 'control' || route === 'execution' ? { executionId } : {}),
      });
      expect(JSON.stringify(diagnostic.mock.calls)).not.toContain('private interview');
    } finally {
      client.clear();
    }
  },
);
