/** Original-command recovery shared by manual writes; Query owns each network attempt. */
import { useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import type { PendingCommandStore } from './pending-command';
import { reportDiagnostic } from '../diagnostics';

type Acknowledgement = 'cleared' | 'changed' | 'unavailable';
export interface CommandRejection<Reason = 'refused'> {
  reason: Reason;
  refresh?: boolean;
}

export type CommandOutcome<R, Reason = 'refused'> =
  | { status: 'accepted'; data: R; acknowledgement: Acknowledgement; refreshFailed: boolean }
  | { status: 'rejected'; reason: Reason; acknowledgement: Acknowledgement; refreshFailed: boolean }
  | { status: 'unknown' };

export interface StoredCommand<C, R, Reason = 'refused'> {
  store: PendingCommandStore<C>;
  execute: (command: C) => Promise<R>;
  classifyRejection: (error: unknown, command: C) => CommandRejection<Reason> | null;
  refresh: () => void | Promise<unknown>;
}

interface LocalCommand<C> {
  pending: C | null;
  issue: 'restore' | 'invalid' | 'retain' | 'display' | null;
}

function restore<C>(store: PendingCommandStore<C>): LocalCommand<C> {
  try {
    return { pending: store.read(), issue: null };
  } catch {
    reportDiagnostic({ event: 'command_failure', kind: 'storage' });
    return { pending: null, issue: 'restore' };
  }
}

function acknowledge<C>(store: PendingCommandStore<C>, command: C): Acknowledgement {
  try {
    return store.acknowledge(command);
  } catch {
    reportDiagnostic({ event: 'command_failure', kind: 'storage' });
    return 'unavailable';
  }
}

async function refresh<C, R, Reason>(definition: StoredCommand<C, R, Reason>): Promise<boolean> {
  try {
    await definition.refresh();
    return false;
  } catch {
    reportDiagnostic({ event: 'command_failure', kind: 'refresh' });
    return true;
  }
}

async function execute<C, R, Reason>({
  command,
  definition,
}: {
  command: C;
  definition: StoredCommand<C, R, Reason>;
}): Promise<CommandOutcome<R, Reason>> {
  let data: R;
  try {
    data = await definition.execute(command);
  } catch (error) {
    const rejection = definition.classifyRejection(error, command);
    if (!rejection) return { status: 'unknown' };
    const refreshFailed = rejection.refresh ? await refresh(definition) : false;
    return {
      status: 'rejected',
      reason: rejection.reason,
      refreshFailed,
      acknowledgement: acknowledge(definition.store, command),
    };
  }
  // A local cleanup or cache error cannot turn the known server result into uncertainty.
  const refreshFailed = await refresh(definition);
  // Refresh may await another response. Compare the slot after that wait so a later
  // command cannot be mistaken for the one this attempt is allowed to retire.
  const acknowledgement = acknowledge(definition.store, command);
  return { status: 'accepted', data, acknowledgement, refreshFailed };
}

export function useStoredCommand<C, R, Reason = 'refused'>(
  definition: StoredCommand<C, R, Reason>,
  onAccepted?: (data: R) => void,
): StoredCommandState<C, R, Reason> {
  const [local, setLocal] = useState(() => restore(definition.store));
  const inFlight = useRef(false);
  const mutation = useMutation({ mutationFn: execute<C, R, Reason>, retry: false });
  const outcome = mutation.data;
  const changed = outcome?.status !== 'unknown' && outcome?.acknowledgement === 'changed';
  const blocked =
    local.issue === 'restore' ||
    local.issue === 'display' ||
    changed ||
    (outcome?.status !== 'unknown' && outcome?.refreshFailed === true);

  async function send(command: C): Promise<void> {
    if (inFlight.current || blocked) return;
    if (local.pending && !definition.store.matches(local.pending, command)) return;
    if (!definition.store.isCommand(command)) {
      setLocal({ ...local, issue: 'invalid' });
      return;
    }
    try {
      definition.store.retain(command);
    } catch {
      reportDiagnostic({ event: 'command_failure', kind: 'storage' });
      setLocal({ ...local, issue: 'retain' });
      return;
    }
    inFlight.current = true;
    setLocal({ pending: command, issue: null });
    try {
      await mutation.mutateAsync(
        { command, definition },
        {
          // Query drops this observer callback on unmount. The attempt above still retires
          // its own stored command and refreshes cache for any remaining observers.
          onSuccess(result) {
            if (result.status !== 'unknown' && result.acknowledgement === 'cleared') {
              setLocal({ pending: null, issue: null });
            }
            if (
              result.status === 'accepted' &&
              result.acknowledgement !== 'changed' &&
              !result.refreshFailed
            ) {
              try {
                onAccepted?.(result.data);
              } catch {
                reportDiagnostic({ event: 'command_failure', kind: 'display' });
                setLocal((current) => ({ ...current, issue: 'display' }));
              }
            }
          },
        },
      );
    } finally {
      inFlight.current = false;
    }
  }

  function reload(): boolean {
    const next = restore(definition.store);
    setLocal(next);
    mutation.reset();
    return next.pending === null && next.issue === null;
  }

  return {
    ...local,
    outcome,
    blocked,
    isSending: mutation.isPending,
    locked: mutation.isPending || local.pending !== null || blocked,
    send,
    reload,
  };
}

export interface StoredCommandState<C, R, Reason = 'refused'> extends LocalCommand<C> {
  outcome: CommandOutcome<R, Reason> | undefined;
  blocked: boolean;
  isSending: boolean;
  locked: boolean;
  send: (command: C) => Promise<void>;
  reload: () => boolean;
}
