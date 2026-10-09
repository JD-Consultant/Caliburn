/** File-owned pending commands; confirmed deletion is composed by the app. */
import { pendingProfile, pendingWork } from './jd-commands';

export function clearDeletedJdCommands(jobFileId: string): void {
  const failures: unknown[] = [];
  for (const store of [pendingProfile(jobFileId), pendingWork(jobFileId)]) {
    try {
      store.clear();
    } catch (error) {
      failures.push(error);
    }
  }
  if (failures.length) throw new AggregateError(failures, 'Unable to clear deleted JD commands');
}
