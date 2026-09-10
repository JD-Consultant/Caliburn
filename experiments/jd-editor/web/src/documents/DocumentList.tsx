"use client";
import React, { useCallback, useEffect, useState } from "react";
import { api } from "../jd/api";
import type { DocumentInput, DocumentOutput } from "../generated/analysis-api";
import {
  pendingCreates,
  requestRecoveryCache,
} from "../jd/requestRecoveryCache";
import { DocumentActions } from "./DocumentActions";
export function DocumentList() {
  const [rows, setRows] = useState<DocumentOutput[] | null>(null);
  const [archived, setArchived] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<DocumentInput[]>([]);
  const [cacheReady, setCacheReady] = useState(false);
  const [cacheError, setCacheError] = useState("");
  const checkRecovery = useCallback(() => {
    try {
      const found = pendingCreates(localStorage);
      setPending(found);
      setCacheReady(true);
      setCacheError("");
      return found;
    } catch (error) {
      setCacheReady(false);
      setCacheError("無法讀取上次建立記錄，尚不能建立新文件。" + String(error));
      return null;
    }
  }, []);
  const load = useCallback(async () => {
    checkRecovery();
    try {
      setRows(await api.documents(archived));
      setError("");
    } catch (error) {
      setError("暫時無法讀取，請重試。" + String(error));
    }
  }, [archived, checkRecovery]);
  useEffect(() => {
    void Promise.resolve().then(load);
  }, [load]);
  async function create(title: string, recovery?: DocumentInput) {
    if (busy || !cacheReady) return;
    const found = checkRecovery();
    if (!found || (!recovery && found.length) ||
      (recovery && !found.some((item) => item.request_key === recovery.request_key && item.title === recovery.title))) return;
    setBusy(true);
    try {
      const payload = recovery ?? { title, request_key: crypto.randomUUID() };
      requestRecoveryCache(localStorage).writeCreate(payload);
      setPending(pendingCreates(localStorage));
      const document = await api.create(payload);
      requestRecoveryCache(localStorage).clearCreate(payload.request_key);
      window.location.assign("/workspace/" + encodeURIComponent(document.id));
    } catch (error) {
      setError("尚未確認建立結果，請依原記錄再次確認。" + String(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="catalog">
      <header>
        <p className="eyebrow">CALIBURN · 職務分析</p>
        <h1>我的職務說明書</h1>
        <p>從實際工作出發，與顧問一起整理你的職務內容。</p>
      </header>
      <DocumentActions
        disabled={busy || !cacheReady || pending.length > 0}
        onCreate={(title) => create(title)}
      />
      {cacheError && <p role="alert">{cacheError}<button onClick={checkRecovery}>重新讀取建立記錄</button></p>}
      {pending.map((item) => (
        <aside key={item.request_key}>
          <p>確認上次建立結果：{item.title}</p>
          <button disabled={busy} onClick={() => void create(item.title, item)}>
            依原記錄再次確認
          </button>
        </aside>
      ))}
      <div className="list-heading">
        <h2>{archived ? "已封存文件" : "工作中的文件"}</h2>
        <button
          onClick={() => {
            setRows(null);
            setArchived((v) => !v);
          }}
        >
          {archived ? "查看工作中文件" : "查看已封存"}
        </button>
      </div>
      {error ? (
        <p role="alert">
          {error}
          <button onClick={() => void load()}>重試</button>
        </p>
      ) : rows === null ? (
        <p>讀取中…</p>
      ) : rows.length === 0 ? (
        <div className="empty">
          <h3>{archived ? "沒有已封存文件" : "尚未建立文件"}</h3>
          <p>以暫定名稱建立，之後就能開始訪談。</p>
        </div>
      ) : (
        <ul className="document-list">
          {rows.map((row) => (
            <li key={row.id}>
              <div>
                <h3>{row.title}</h3>
                <p>
                  建立於 {new Date(row.created_at).toLocaleDateString("zh-TW")}
                </p>
              </div>
              <a href={"/workspace/" + encodeURIComponent(row.id)}>開啟 →</a>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
