import { describe, expect, it } from 'vitest';
import { isCreateJobFileRequest, isRenameJobFileRequest } from './validation';

const uuid = '12345678-1234-4234-8234-1234567890ab';

describe('canonical input formats', () => {
  it.each([uuid, uuid.toUpperCase()])('accepts a plain UUID: %s', (command_id) => {
    expect(
      isCreateJobFileRequest({ command_id, display_name: '工作', employee_name: '員工' }),
    ).toBe(true);
  });

  it.each([uuid.replaceAll('-', ''), `urn:uuid:${uuid}`, `${uuid}-`])(
    'rejects other UUID representations: %s',
    (command_id) => {
      expect(
        isCreateJobFileRequest({ command_id, display_name: '工作', employee_name: '員工' }),
      ).toBe(false);
    },
  );

  it.each([
    [1, true],
    [1.0, true],
    [Number.MAX_SAFE_INTEGER, true],
    [Number.MAX_SAFE_INTEGER + 1, false],
    [1e19, false],
    [true, false],
    ['1', false],
    [1.5, false],
  ])('validates a JSON integer before conversion: %s', (expected_name_revision, accepted) => {
    expect(
      isRenameJobFileRequest({ command_id: uuid, display_name: '工作', expected_name_revision }),
    ).toBe(accepted);
  });

  it.each([
    ['\u0085', false],
    ['\u001c', false],
    ['\ufeff', true],
    ['\n\t ', false],
    ['工作\n多行', true],
    ['工作\u0000', false],
  ])('uses the domain nonblank text policy: %j', (display_name, accepted) => {
    expect(isCreateJobFileRequest({ command_id: uuid, display_name, employee_name: '員工' })).toBe(
      accepted,
    );
  });
});
