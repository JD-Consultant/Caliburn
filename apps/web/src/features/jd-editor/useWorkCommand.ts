/** The collections' manual command: areas, tasks, capabilities, collaborators and conditions. */
import { useQueryClient } from '@tanstack/react-query';
import { jdProfileQuery } from './jd-profile-api';
import { editJdWork, isWorkCommand, jdWorkQuery } from './jd-work-api';
import type { WorkCommand } from './jd-work-api';
import { usePendingCommand } from './usePendingCommand';

export function useWorkCommand(jobFileId: string, onSaved: () => void) {
  const queryClient = useQueryClient();
  return usePendingCommand<WorkCommand>(
    {
      storageKey: `caliburn.pending-jd-work.${jobFileId}`,
      isCommand: isWorkCommand,
      post: (command) => editJdWork(jobFileId, command),
      refresh: () => {
        void queryClient.invalidateQueries({ queryKey: jdWorkQuery(jobFileId).queryKey });
        void queryClient.invalidateQueries({ queryKey: jdProfileQuery(jobFileId).queryKey });
      },
      invalidMessage: '名稱或內容至少填一項，欄位不能只有空白或包含無法儲存的字元。',
      restoredMessage: '有尚未確認的 JD 集合修改，請先取得原結果。',
    },
    onSaved,
  );
}
