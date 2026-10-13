/** Read-only comparisons share one request but keep their distinct baselines visible. */
import { useQuery } from '@tanstack/react-query';
import { Alert } from '@mui/material';
import type { SourceScope } from './source-api';
import { describeSourceError, jdSourceChangesQuery } from './source-api';
import { SafeMarkdown } from '../../shared/ui/SafeMarkdown';

export function SourceChanges({ scope }: { scope: SourceScope }) {
  const changes = useQuery(jdSourceChangesQuery(scope));
  return (
    <div className="source-body">
      <p className="source-note">
        JD 比較此項目上次核對時與所選正式修訂；來源比較原引用與讀取當時最新已發布的
        Memory。閱讀不會解除待核對。
      </p>
      {changes.isFetching ? (
        <p role="status">正在讀取差異…</p>
      ) : changes.isError ? (
        <Alert severity="error">{describeSourceError(changes.error)}</Alert>
      ) : (
        changes.data && (
          <>
            {changes.data.source_version && changes.data.comparison_version && (
              <p className="source-note">
                原引用 Memory 涵蓋至訪談序號 {changes.data.source_version.covered_through_sequence}
                ； 本次比較 Memory 涵蓋至訪談序號{' '}
                {changes.data.comparison_version.covered_through_sequence}。
              </p>
            )}
            <ChangeSection title="JD 內容變更" markdown={changes.data.jd_markdown} />
            {changes.data.source_markdown !== null && (
              <ChangeSection title="來源變更" markdown={changes.data.source_markdown} />
            )}
          </>
        )
      )}
    </div>
  );
}

function ChangeSection({ title, markdown }: { title: string; markdown: string }) {
  return (
    <div className="source-change">
      <h5 className="source-change__title">{title}</h5>
      <div className="source-prose">
        <SafeMarkdown markdown={markdown} />
      </div>
    </div>
  );
}
