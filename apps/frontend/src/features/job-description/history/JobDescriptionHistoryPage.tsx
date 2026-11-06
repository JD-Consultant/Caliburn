import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { ArrowLeft, History } from 'lucide-react';
import { useRef, useState } from 'react';
import { Link } from 'react-router';
import { Button } from '@mui/material';
import type {
  HistoryEntryResponse,
  JobDescriptionResponse,
} from '../../../shared/api/generated/types.gen';
import { ErrorNotice, LoadingState } from '../../../shared/ui/Feedback';
import { hasStoredDrafts } from '../editing/drafts';
import { compareVersions, getSnapshot, listHistory } from '../history-api';
import { JobDescriptionDocument } from '../JobDescriptionDocument';
import { jobDescriptionOptions } from '../queries';
import { JobDescriptionDifference } from './JobDescriptionDifference';
import { RestoreVersionDialog } from './RestoreVersionDialog';
import { JobDescriptionSourcesProvider } from '../sources/JobDescriptionSourcesProvider';
import { JobDescriptionSources } from '../sources/JobDescriptionSources';
import './history.css';

const historyKindLabels: Record<HistoryEntryResponse['kind'], string> = {
  created: '建立',
  edited: '編輯',
  restored: '恢復',
};
const dateFormat = new Intl.DateTimeFormat('zh-TW', {
  dateStyle: 'medium',
  timeStyle: 'short',
});

export function JobDescriptionHistoryPage({
  workspaceId,
  intervieweeName,
  readOnly = false,
}: {
  workspaceId: string;
  intervieweeName: string;
  readOnly?: boolean;
}) {
  const current = useQuery(jobDescriptionOptions(workspaceId));
  const returnPath = `/workspaces/${encodeURIComponent(workspaceId)}/jd`;
  return (
    <div className="history-page page-enter">
      <header className="history-page-heading">
        <Link className="text-button" to={returnPath}>
          <ArrowLeft size={17} aria-hidden="true" /> 返回職務說明書
        </Link>
        <p className="eyebrow">{intervieweeName}</p>
        <h1>
          <History size={24} aria-hidden="true" /> 版本歷史
        </h1>
        <p>預覽過去內容，或選擇兩個版本比較。</p>
      </header>
      {current.isPending ? (
        <LoadingState />
      ) : current.isError && !current.data ? (
        <ErrorNotice
          message="無法讀取目前職務說明書，請重新讀取。"
          onRetry={() => {
            void current.refetch();
          }}
        />
      ) : current.data ? (
        <HistoryBrowser
          key={`${workspaceId}-${current.data.job_description_id}`}
          current={current.data}
          readOnly={readOnly}
        />
      ) : (
        <p className="history-empty">這份工作區還沒有職務說明書。</p>
      )}
    </div>
  );
}

function HistoryBrowser({
  current,
  readOnly,
}: {
  current: JobDescriptionResponse;
  readOnly: boolean;
}) {
  const contentHeading = useRef<HTMLHeadingElement>(null);
  const versionsHeading = useRef<HTMLHeadingElement>(null);
  const workspaceId = current.workspace_id;
  const jdId = current.job_description_id;
  const baseKey = [...jobDescriptionOptions(workspaceId).queryKey, jdId, 'history'];
  const [selection, setSelection] = useState<number | undefined>();
  const [comparisonTarget, setComparisonTarget] = useState<number | undefined>();
  const [mode, setMode] = useState<'preview' | 'compare'>('preview');
  const [restoreTarget, setRestoreTarget] = useState<number | null>(null);
  const [verificationRequired, setVerificationRequired] = useState(false);
  const [draftsBlocked, setDraftsBlocked] = useState(() =>
    hasStoredDrafts(workspaceId, jdId),
  );
  const history = useInfiniteQuery({
    queryKey: [...baseKey, 'list'],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam, signal }) =>
      listHistory(
        workspaceId,
        jdId,
        {
          page_size: '20',
          ...(pageParam === undefined ? {} : { page_token: pageParam }),
        },
        signal,
      ),
    getNextPageParam: (page) => page.next_page_token ?? undefined,
  });
  const entries = history.data?.pages.flatMap((page) => page.items) ?? [];
  const selectedVersion =
    selection ??
    entries.find((entry) => entry.version !== current.version)?.version ??
    entries[0]?.version;
  const targetVersion = comparisonTarget ?? current.version;
  const versions = Array.from(
    new Set([current.version, ...entries.map((entry) => entry.version)]),
  ).sort((a, b) => b - a);
  const snapshot = useQuery({
    queryKey: [...baseKey, 'snapshot', selectedVersion],
    queryFn: ({ signal }) =>
      getSnapshot(workspaceId, jdId, selectedVersion ?? current.version, signal),
    enabled: selectedVersion !== undefined,
    staleTime: Infinity,
  });
  const targetSnapshot = useQuery({
    queryKey: [...baseKey, 'snapshot', targetVersion],
    queryFn: ({ signal }) => getSnapshot(workspaceId, jdId, targetVersion, signal),
    enabled: mode === 'compare' && selectedVersion !== undefined,
    staleTime: Infinity,
  });
  const difference = useQuery({
    queryKey: [...baseKey, 'compare', selectedVersion, targetVersion],
    queryFn: ({ signal }) =>
      compareVersions(
        workspaceId,
        jdId,
        selectedVersion ?? current.version,
        targetVersion,
        signal,
      ),
    enabled: mode === 'compare' && selectedVersion !== undefined,
    staleTime: Infinity,
  });
  const returnPath = `/workspaces/${encodeURIComponent(workspaceId)}/jd`;
  const retryComparison = () => {
    void snapshot.refetch();
    void targetSnapshot.refetch();
    void difference.refetch();
  };
  return (
    <>
      {verificationRequired && restoreTarget === null && (
        <div className="history-draft-guard">
          <ErrorNotice message="上次恢復結果需要核對，請返回目前 JD 確認內容後再繼續。" />
          <Link className="text-button" to={returnPath}>
            返回目前 JD 核對
          </Link>
        </div>
      )}
      {draftsBlocked && (
        <div className="history-draft-guard">
          <ErrorNotice message="這份 JD 還有未確認輸入。請先返回編輯頁，核對並處理輸入，再恢復歷史版本。" />
          <Link className="text-button" to={returnPath}>
            返回編輯頁處理輸入
          </Link>
        </div>
      )}
      <div className="history-layout">
        <aside className="history-versions" aria-label="歷史版本">
          <div className="history-list-heading">
            <h2 ref={versionsHeading} tabIndex={-1}>
              全部版本
            </h2>
            <span>目前版本 {current.version}</span>
          </div>
          {history.isPending && <LoadingState />}
          <ol className="history-version-list">
            {entries.map((entry) => (
              <li key={entry.version}>
                <Button
                  aria-label={`預覽版本 ${String(entry.version)}`}
                  aria-pressed={selectedVersion === entry.version}
                  className="history-version-button"
                  onClick={() => {
                    setSelection(entry.version);
                    if (window.matchMedia('(max-width: 720px)').matches) {
                      requestAnimationFrame(() => {
                        contentHeading.current?.scrollIntoView({ block: 'start' });
                        contentHeading.current?.focus({ preventScroll: true });
                      });
                    }
                  }}
                >
                  <span className="history-version-title">
                    版本 {entry.version}
                    {entry.version === current.version && (
                      <span className="history-current-marker">目前</span>
                    )}
                  </span>
                  <span>
                    {historyKindLabels[entry.kind]}
                    {entry.restored_from_version !== null &&
                      `自版本 ${String(entry.restored_from_version)}`}
                  </span>
                  <time dateTime={entry.recorded_at}>
                    {dateFormat.format(new Date(entry.recorded_at))}
                  </time>
                </Button>
              </li>
            ))}
          </ol>
          {history.isError && (
            <ErrorNotice
              message="無法讀取版本歷史，請稍後重試。"
              onRetry={() => {
                void (history.isFetchNextPageError
                  ? history.fetchNextPage()
                  : history.refetch());
              }}
            />
          )}
          {!history.isPending && !history.isError && entries.length === 0 && (
            <p className="history-empty">目前沒有歷史紀錄。</p>
          )}
          {history.hasNextPage && (
            <Button
              className="secondary-button history-load-more"
              disabled={history.isFetching}
              onClick={() => {
                void history.fetchNextPage();
              }}
            >
              {history.isFetchingNextPage ? '正在載入…' : '載入較早版本'}
            </Button>
          )}
        </aside>
        <section className="history-content" aria-label="版本內容">
          {selectedVersion !== undefined && (
            <>
              <div className="history-content-heading">
                <h2 ref={contentHeading} tabIndex={-1}>
                  版本 {selectedVersion}
                </h2>
                <Button
                  type="button"
                  className="text-button history-back-to-versions"
                  onClick={() => {
                    versionsHeading.current?.scrollIntoView({ block: 'start' });
                    versionsHeading.current?.focus({ preventScroll: true });
                  }}
                >
                  返回版本清單
                </Button>
                <div className="history-view-actions">
                  <Button
                    className="secondary-button"
                    aria-pressed={mode === 'preview'}
                    onClick={() => {
                      setMode('preview');
                    }}
                  >
                    預覽內容
                  </Button>
                  <Button
                    className="secondary-button"
                    aria-pressed={mode === 'compare'}
                    onClick={() => {
                      setMode('compare');
                    }}
                  >
                    比較版本
                  </Button>
                  {!draftsBlocked && !verificationRequired && (
                    <Button
                      className="primary-button"
                      disabled={readOnly || !snapshot.data || snapshot.isFetching}
                      onClick={() => {
                        if (hasStoredDrafts(workspaceId, jdId)) {
                          setDraftsBlocked(true);
                          return;
                        }
                        setRestoreTarget(selectedVersion);
                      }}
                    >
                      恢復此版本
                    </Button>
                  )}
                </div>
              </div>
              {mode === 'preview' ? (
                snapshot.isPending ? (
                  <LoadingState />
                ) : snapshot.isError ? (
                  <ErrorNotice
                    message="無法讀取這個版本，請重新讀取。"
                    onRetry={() => {
                      void snapshot.refetch();
                    }}
                  />
                ) : (
                  <div className="history-preview">
                    <p className="history-readonly-note">
                      唯讀預覽 · 版本 {snapshot.data.entry.version}
                    </p>
                    <JobDescriptionSourcesProvider
                      jobDescription={snapshot.data.content}
                      version={snapshot.data.entry.version}
                    >
                      <JobDescriptionSources />
                      <JobDescriptionDocument
                        key={snapshot.data.entry.version}
                        idPrefix={`history-jd-${String(snapshot.data.entry.version)}`}
                        jobDescription={{
                          ...snapshot.data.content,
                          version: snapshot.data.entry.version,
                        }}
                      />
                    </JobDescriptionSourcesProvider>
                  </div>
                )
              ) : (
                <>
                  <div className="history-compare-controls">
                    <label>
                      比較起始版本
                      <select
                        value={selectedVersion}
                        onChange={(event) => {
                          setSelection(Number(event.target.value));
                        }}
                      >
                        {versions.map((version) => (
                          <option key={version} value={version}>
                            版本 {version}
                            {version === current.version ? '（目前）' : ''}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      比較目標版本
                      <select
                        value={targetVersion}
                        onChange={(event) => {
                          setComparisonTarget(Number(event.target.value));
                        }}
                      >
                        {versions.map((version) => (
                          <option key={version} value={version}>
                            版本 {version}
                            {version === current.version ? '（目前）' : ''}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  {snapshot.isError || targetSnapshot.isError || difference.isError ? (
                    <ErrorNotice
                      message="無法讀取版本比較，請重新讀取。"
                      onRetry={retryComparison}
                    />
                  ) : snapshot.isPending ||
                    targetSnapshot.isPending ||
                    difference.isPending ? (
                    <LoadingState>正在比較版本…</LoadingState>
                  ) : (
                    <JobDescriptionDifference
                      difference={difference.data}
                      before={snapshot.data.content}
                      after={targetSnapshot.data.content}
                    />
                  )}
                </>
              )}
            </>
          )}
        </section>
      </div>
      {restoreTarget !== null && (
        <RestoreVersionDialog
          current={current}
          readOnly={readOnly}
          targetVersion={restoreTarget}
          onClose={() => {
            setRestoreTarget(null);
          }}
          onDraftsFound={() => {
            setDraftsBlocked(true);
            setRestoreTarget(null);
          }}
          onVerificationRequired={() => {
            setVerificationRequired(true);
          }}
        />
      )}
    </>
  );
}
