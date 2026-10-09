/** A tab's original transport command; it never represents current server data. */
export interface PendingCommandStore<C> {
  isCommand: (value: unknown) => value is C;
  matches: (left: C, right: C) => boolean;
  read: () => C | null;
  retain: (command: C) => void;
  acknowledge: (command: C) => 'cleared' | 'changed';
  clear: () => void;
}

export function createPendingCommandStore<C>({
  key,
  isCommand,
  matches,
}: {
  key: string;
  isCommand: (value: unknown) => value is C;
  matches: (left: C, right: C) => boolean;
}): PendingCommandStore<C> {
  function read(): C | null {
    const raw = sessionStorage.getItem(key);
    if (raw === null) return null;
    const command: unknown = JSON.parse(raw);
    if (!isCommand(command)) throw new Error('Invalid pending command');
    return command;
  }

  function clear(): void {
    sessionStorage.removeItem(key);
  }

  return {
    isCommand,
    matches,
    read,
    retain: (command) => sessionStorage.setItem(key, JSON.stringify(command)),
    acknowledge(command) {
      const pending = read();
      if (!pending || !matches(pending, command)) return 'changed';
      clear();
      return 'cleared';
    },
    clear,
  };
}
