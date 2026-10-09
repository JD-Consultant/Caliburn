import { createContext } from 'react';
export const DeletedJobFilesContext = createContext<{
  deleted: Set<string>;
  confirmDeleted: (jobFileId: string) => Promise<void>;
}>({
  deleted: new Set<string>(),
  confirmDeleted: (): Promise<void> => Promise.resolve(),
});
