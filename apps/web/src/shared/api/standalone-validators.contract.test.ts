/** OpenAPI-generated standalone guards preserve the established HTTP acceptance policy. */
import { describe, expect, it } from 'vitest';
import { isCreateJobFileRequest, isJobFile, isJobFileList } from './generated/http/validators.js';

const uuid = '123e4567-e89b-12d3-a456-426614174000';
describe('standalone HTTP guards', () => {
  it.each([
    [uuid, true],
    [uuid.toUpperCase(), true],
    [`urn:uuid:${uuid}`, false],
    [`${uuid}\n`, false],
    [`${uuid}\r\n`, false],
    [`${uuid} `, false],
    ['bad', false],
    [null, false],
  ])('preserves plain HTTP UUID policy: %j', (command_id, accepted) => {
    expect(
      isCreateJobFileRequest({ command_id, display_name: '合成', employee_name: '合成' }),
    ).toBe(accepted);
  });
  it.each([
    ['2026-10-10T01:02:03Z', true],
    ['2026-10-10T09:02:03+08:00', true],
    ['2024-02-29T00:00:00Z', true],
    ['2025-02-29T00:00:00Z', false],
    ['2026-10-10', false],
    ['not-a-date', false],
    [null, false],
  ])('validates date-time for the public JobFile value: %j', (created_at, accepted) => {
    const value = {
      job_file_id: uuid,
      display_name: '合成',
      employee_name: '合成',
      name_revision: 1,
      created_at,
      active_usage_seconds: 0,
    };
    expect(isJobFile(value)).toBe(accepted);
    expect(isJobFileList({ job_files: [value] })).toBe(accepted);
  });
  it('rejects remote extra fields and missing required fields', () => {
    const value = { command_id: uuid, display_name: '合成', employee_name: '合成' };
    expect(isCreateJobFileRequest({ ...value, private_extra: '合成' })).toBe(false);
    expect(isCreateJobFileRequest({ command_id: uuid, display_name: '合成' })).toBe(false);
  });
});
