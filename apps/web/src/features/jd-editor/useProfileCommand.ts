/** The profile's manual command: the four basic-data fields. Same rule as the collections, own endpoint and key. */
import { useQueryClient } from '@tanstack/react-query';
import type { ReviseJdProfileRequest } from '../../shared/api/generated/revise-jd-profile-request';
import { isReviseJdProfileRequest } from '../../shared/api/validation';
import { jdProfileQuery, reviseJdProfile } from './jd-profile-api';
import { jdWorkQuery } from './jd-work-api';
import { usePendingCommand } from './usePendingCommand';

export function useProfileCommand(jobFileId: string, onSaved: () => void) {
  const queryClient = useQueryClient();
  return usePendingCommand<ReviseJdProfileRequest>(
    {
      storageKey: `caliburn.pending-jd-profile.${jobFileId}`,
      isCommand: isReviseJdProfileRequest,
      post: (command) => reviseJdProfile(jobFileId, command),
      refresh: () => {
        void queryClient.invalidateQueries({ queryKey: jdProfileQuery(jobFileId).queryKey });
        void queryClient.invalidateQueries({ queryKey: jdWorkQuery(jobFileId).queryKey });
      },
      invalidMessage: '欄位不能只有空白或包含無法儲存的字元；若要清空，請刪除全部文字。',
      restoredMessage: '有尚未確認的 JD 修改，請先取得原結果。',
    },
    onSaved,
  );
}
