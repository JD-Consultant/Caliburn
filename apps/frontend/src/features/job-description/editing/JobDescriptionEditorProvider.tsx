import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import type { JobDescriptionResponse } from '../../../shared/api/generated/types.gen';
import { validateJobDescriptionErrorResponse } from '../../../shared/api/generated/validators';
import { HttpError, InvalidRequestError } from '../../../shared/api/http';
import { lookupJobDescription } from '../api';
import { JobDescriptionEditorContext, type JobDescriptionWrite } from './editor-context';
import { loadDrafts, storeDrafts, type TextDraft, type TextDrafts } from './drafts';
import './editing.css';

function failureMessage(error: unknown): string {
  if (error instanceof InvalidRequestError)
    return '輸入不符合欄位規則，本次尚未送出。請修正後繼續。';
  if (error instanceof HttpError && validateJobDescriptionErrorResponse(error.body)) {
    const detail = error.body.detail;
    if (detail.commit_status === 'committed')
      return '修改已保存，但無法取得完整回覆。請重新讀取後核對。';
    if (detail.commit_status === 'not_committed') {
      if (detail.code === 'jd_concurrency_conflict')
        return '這份 JD 已有其他變更或暫時忙碌，本次未保存。請重新讀取並核對保留的輸入。';
      return '本次未保存，可能有重複名稱、無效欄位或內容已被刪除。請核對後修正。';
    }
  }
  return '無法確認這次修改是否已保存。請重新讀取核對；系統不會自動重送。';
}

export function JobDescriptionEditorProvider({
  jobDescription,
  onSaved,
  readOnly = false,
  children,
}: {
  jobDescription: JobDescriptionResponse;
  onSaved: (jd: JobDescriptionResponse) => void | Promise<void>;
  readOnly?: boolean;
  children: ReactNode;
}) {
  const { workspace_id: workspaceId, job_description_id: jdId } = jobDescription;
  const [drafts, setDraftState] = useState(() => loadDrafts(workspaceId, jdId));
  const draftsRef = useRef(drafts);
  const [reviewing, setReviewing] = useState(() => Object.keys(drafts).length > 0);
  const [blocked, setBlocked] = useState(reviewing);
  const blockedRef = useRef(blocked);
  const [busy, setBusy] = useState(false);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const editingKeyRef = useRef<string | null>(null);
  const readOnlyRef = useRef(readOnly);
  useEffect(() => {
    readOnlyRef.current = readOnly;
  }, [readOnly]);
  const [message, setMessage] = useState<string | null>(
    reviewing ? '已取回此分頁保留的輸入，尚未重新送出。請先核對目前內容。' : null,
  );
  const [storageAvailable, setStorageAvailable] = useState(true);
  const [reloaded, setReloaded] = useState(false);
  const [reloading, setReloading] = useState(false);
  const head = useRef(jobDescription);
  const queue = useRef(Promise.resolve());
  const count = useRef(0);
  const active = useRef(true);
  const saved = useRef(onSaved);

  useEffect(() => {
    saved.current = onSaved;
  }, [onSaved]);
  useEffect(() => {
    if (
      !count.current &&
      !blockedRef.current &&
      Object.keys(draftsRef.current).length === 0
    )
      head.current = jobDescription;
  }, [jobDescription, busy, drafts]);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);

  const persist = useCallback(
    (next: TextDrafts) => {
      if (!active.current) return;
      draftsRef.current = next;
      setDraftState(next);
      setStorageAvailable(storeDrafts(workspaceId, jdId, next));
      if (Object.keys(next).length === 0 && !blockedRef.current) {
        setReviewing(false);
        setMessage(null);
      }
    },
    [workspaceId, jdId],
  );

  const setDraft = useCallback(
    (key: string, draft: TextDraft) => {
      persist({ ...draftsRef.current, [key]: draft });
    },
    [persist],
  );

  const discardDraft = useCallback(
    (key: string, confirmedValue?: string) => {
      if (
        confirmedValue !== undefined &&
        draftsRef.current[key]?.value !== confirmedValue
      )
        return;
      const next = { ...draftsRef.current };
      delete next[key];
      persist(next);
    },
    [persist],
  );

  const claimEdit = useCallback((key: string) => {
    if (
      readOnlyRef.current ||
      (editingKeyRef.current !== null && editingKeyRef.current !== key)
    )
      return false;
    editingKeyRef.current = key;
    setEditingKey(key);
    return true;
  }, []);

  const releaseEdit = useCallback((key: string) => {
    if (editingKeyRef.current !== key) return;
    editingKeyRef.current = null;
    setEditingKey(null);
    if (active.current && draftsRef.current[key]) {
      blockedRef.current = true;
      setBlocked(true);
      setReviewing(true);
      setReloaded(false);
      setMessage(
        '編輯項目已離開畫面，未確認的輸入仍保留。請重新讀取後核對，或放棄這筆輸入。',
      );
    }
  }, []);

  const execute = useCallback((write: JobDescriptionWrite): Promise<boolean> => {
    if (blockedRef.current || readOnlyRef.current || !active.current)
      return Promise.resolve(false);
    count.current += 1;
    setBusy(true);
    const result = queue.current
      .then(async () => {
        if (blockedRef.current || readOnlyRef.current || !active.current) return false;
        let committed: JobDescriptionResponse;
        try {
          committed = await write(head.current);
        } catch (error) {
          blockedRef.current = true;
          if (active.current) {
            setBlocked(true);
            setReviewing(true);
            setReloaded(false);
            setMessage(failureMessage(error));
          }
          return false;
        }
        head.current = committed;
        try {
          await saved.current(committed);
        } catch {
          blockedRef.current = true;
          if (active.current) {
            setBlocked(true);
            setReviewing(true);
            setReloaded(false);
            setMessage('修改已保存，但畫面尚未同步。請重新讀取，不需要再次送出。');
          }
        }
        return true;
      })
      .finally(() => {
        count.current -= 1;
        if (active.current) setBusy(count.current > 0);
      });
    queue.current = result.then(() => undefined);
    return result;
  }, []);

  const waitForWrites = useCallback(async () => {
    await queue.current;
    return !blockedRef.current && Object.keys(draftsRef.current).length === 0;
  }, []);

  async function reload() {
    setReloading(true);
    try {
      const current = await lookupJobDescription(workspaceId);
      if (!current) throw new Error('JD 不存在');
      head.current = current;
      await saved.current(current);
      setReloaded(true);
      setMessage('已讀取目前內容。保留的輸入尚未送出，請逐欄比較後套用或放棄。');
    } catch {
      setMessage('無法重新讀取 JD，請檢查連線。保留的輸入不會自動送出。');
    } finally {
      setReloading(false);
    }
  }

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (count.current || Object.keys(draftsRef.current).length) event.preventDefault();
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, []);

  return (
    <JobDescriptionEditorContext.Provider
      value={{
        jobDescription,
        busy,
        blocked: blocked || readOnly,
        readOnly,
        editingKey,
        claimEdit,
        releaseEdit,
        reviewing,
        drafts,
        execute,
        waitForWrites,
        setDraft,
        discardDraft,
      }}
    >
      {!storageAvailable && (
        <p role="alert" className="error-notice">
          瀏覽器無法暫存輸入，重新整理可能遺失尚未確認的文字。請先完成保存。
        </p>
      )}
      {message && (
        <div role="alert" className="jd-edit-notice">
          <p>{message}</p>
          {Object.keys(drafts).length > 0 && (
            <details>
              <summary>保留的輸入（{Object.keys(drafts).length}）</summary>
              <ul>
                {Object.entries(drafts).map(([key, draft]) => (
                  <li key={key}>
                    <strong>{draft.label}</strong>
                    <p>
                      {key.startsWith('new:')
                        ? '尚未完成的新增表單，內容保留在原位置。'
                        : draft.value}
                    </p>
                    <button
                      type="button"
                      className="text-button"
                      disabled={busy}
                      onClick={() => discardDraft(key)}
                    >
                      放棄這筆輸入
                    </button>
                  </li>
                ))}
              </ul>
            </details>
          )}
          <div className="jd-notice-actions">
            <button
              type="button"
              className="secondary-button"
              disabled={busy || reloading}
              onClick={() => {
                void reload();
              }}
            >
              重新讀取
            </button>
            {reloaded && (
              <button
                type="button"
                className="secondary-button"
                disabled={busy || reloading}
                onClick={() => {
                  blockedRef.current = false;
                  setBlocked(false);
                  setReviewing(Object.keys(draftsRef.current).length > 0);
                  setMessage(
                    Object.keys(draftsRef.current).length
                      ? '請逐欄選擇「套用輸入」或「使用目前內容」。未選擇的輸入會繼續保留。'
                      : null,
                  );
                }}
              >
                已核對，繼續編輯
              </button>
            )}
          </div>
        </div>
      )}
      {children}
    </JobDescriptionEditorContext.Provider>
  );
}
