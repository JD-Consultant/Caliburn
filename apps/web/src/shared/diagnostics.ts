/** Local diagnostics contain categories and opaque IDs, never content or raw exceptions. */
import { isCanonicalUuid } from './api/uuid';

export type FailureKind =
  | 'http'
  | 'network'
  | 'timeout'
  | 'cancelled'
  | 'invalid_json'
  | 'invalid_response'
  | 'stream_disconnected'
  | 'storage'
  | 'refresh'
  | 'display';
export interface DiagnosticScope {
  jobFileId?: string;
  commandId?: string;
  executionId?: string;
}
interface Diagnostic extends DiagnosticScope {
  event: 'http_failure' | 'stream_failure' | 'command_failure';
  kind: FailureKind;
  status?: number | undefined;
  requestId?: string | undefined;
}
const events = new Set(['http_failure', 'stream_failure', 'command_failure']);
const kinds = new Set<FailureKind>([
  'http',
  'network',
  'timeout',
  'cancelled',
  'invalid_json',
  'invalid_response',
  'stream_disconnected',
  'storage',
  'refresh',
  'display',
]);

export function reportDiagnostic(diagnostic: Diagnostic): void {
  if (
    !events.has(diagnostic.event) ||
    !kinds.has(diagnostic.kind) ||
    diagnostic.kind === 'cancelled'
  )
    return;
  const safe: Diagnostic = { event: diagnostic.event, kind: diagnostic.kind };
  if (
    typeof diagnostic.status === 'number' &&
    Number.isInteger(diagnostic.status) &&
    diagnostic.status >= 100 &&
    diagnostic.status <= 599
  )
    safe.status = diagnostic.status;
  for (const key of ['requestId', 'jobFileId', 'commandId', 'executionId'] as const) {
    const value = diagnostic[key];
    if (isCanonicalUuid(value)) safe[key] = value;
  }
  try {
    console.warn('caliburn', safe);
  } catch {
    // A failed diagnostic sink cannot change a command's result or recovery.
  }
}
