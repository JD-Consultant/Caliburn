"use client";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { useJdSession } from "./useJdSession";
import { JdEditor, applySavedHead, type LiveEditor } from "./JdEditor";
import { JdChanges } from "./JdChanges";
import { ReadOnlyValue } from "./JdNode";
import { guardUnload, mayLeave } from "./navigationGuard";
import type {
  JdChangeReadSuccess,
  SlateRange,
  JdSourceReadResult,
} from "@caliburn/jd-editor-contract";
export function JdWorkspace({ document }: { document: string }) {
  const session = useJdSession(document);
  const editor = useRef<LiveEditor | null>(null);
  const [epoch, setEpoch] = useState(0);
  const [leaving, setLeaving] = useState(false);
  const [history, setHistory] = useState<JdChangeReadSuccess[]>([]);
  const [showChanges, setShowChanges] = useState(false);
  const [sourceValue, setSourceValue] = useState<JdSourceReadResult | null>(
    null,
  );
  const [selectionIntent, setSelectionIntent] = useState(false);
  const ready = useCallback((value: LiveEditor) => {
    editor.current = value;
  }, []);
  useEffect(() => {
    session.bindHead((head, change) => {
      if (
        editor.current &&
        session.head &&
        (head.revision_ref !== session.head.revision_ref || session.dirty)
      ) {
        if (!applySavedHead(editor.current, session.head, head, change)) {
          editor.current = null;
          setEpoch((n) => n + 1);
          session.setNotice("已載入保存內容，本次編輯復原紀錄已重設。");
        }
      }
    });
    return () => {
      session.bindHead(null);
    };
  }, [session]);
  useEffect(() => {
    if (!session.dirty && !session.text) return;
    window.addEventListener("beforeunload", guardUnload);
    return () => window.removeEventListener("beforeunload", guardUnload);
  }, [session.dirty, session.text]);
  const capture = () => {
    const range = editor.current?.selection;
    if (!range || JSON.stringify(range.anchor) === JSON.stringify(range.focus))
      return null;
    if (!range.anchor.path.length || !range.focus.path.length) return null;
    return structuredClone(range) as SlateRange;
  };
  async function leave(choice: "save" | "stay" | "discard") {
    if (
      await mayLeave(
        { dirty: session.dirty, chat: !!session.text },
        choice,
        () => session.save(),
      )
    ) {
      session.discardBuffer();
      window.removeEventListener("beforeunload", guardUnload);
      window.location.assign("/");
    } else if (choice === "stay") setLeaving(false);
  }
  async function source(reference: string, offset = 0) {
    try {
      const page = await session.port.source(document, reference, offset);
      setSourceValue((old) =>
        offset && old?.reference === reference
          ? { ...page, segments: [...old.segments, ...page.segments] }
          : page,
      );
    } catch (error) {
      session.setError("依據無法讀取：" + String(error));
    }
  }
  async function previous() {
    try {
      const ref =
        history.at(-1)?.before_revision_ref ?? session.head?.revision_ref;
      if (!ref) return;
      const read = await session.port.read(document, { revision_ref: ref });
      if (!read.change_refs.length) {
        session.setNotice("已到最初版本");
        return;
      }
      const change = await session.port.changes(document, {
        change_ref: read.change_refs[0],
      });
      setHistory((items) => [...items, change]);
    } catch (error) {
      session.setError(String(error));
    }
  }
  return (
    <main className="workspace">
      <header className="workspace-header">
        <div>
          <a
            href="/"
            onClick={(e) => {
              if (session.dirty || session.text) {
                e.preventDefault();
                setLeaving(true);
              }
            }}
          >
            ← 我的職務說明書
          </a>
          <h1>{session.metadata?.title ?? "職務說明書"}</h1>
        </div>
        <span role="status" className="status">
          {session.loading
            ? "讀取中"
            : session.restartRequired
              ? "需要重新啟動，暫停編輯"
            : session.busy
              ? "正在處理"
              : session.metadata?.archived
                ? "已封存，可查看"
                : session.run &&
                    [
                      "receiving",
                      "running",
                      "stopping",
                      "uncertain",
                      "interrupted",
                    ].includes(session.run.status)
                  ? "顧問處理中，暫停編輯"
                  : session.dirty
                    ? "未保存"
                    : "已保存"}
        </span>
      </header>
      {session.error && (
        <div role="alert" className="alert">
          {session.error}
          <button onClick={() => void session.refresh().catch(() => {})}>
            重新讀取
          </button>
        </div>
      )}
      {session.notice && <p className="notice">{session.notice}</p>}
      {session.restartRequired && (
        <aside role="alert" className="candidate">
          <h3>上一個文件處理尚未停止</h3>
          <p>先保留此頁；目前畫面中的未保存修改與問句仍在，請勿重新整理或關頁。</p>
          <p>請在啟動此 App 的視窗停止服務，等待停止完成，再用原啟動入口重新啟動。之後按下方按鈕確認狀態；只重新整理網頁無法停止殘留的工作。</p>
          <button disabled={session.busy} onClick={() => void session.revalidate()}>重新讀取狀態</button>
        </aside>
      )}
      {sourceValue && (
        <aside className="source-panel">
          <h3>依據・已保存的原問答</h3>
          {sourceValue.segments.map((segment, i) => (
            <article key={i}>
              <strong>
                {segment.role === "user" ? "員工原文" : "顧問原文"}
              </strong>
              <p>{segment.text}</p>
            </article>
          ))}
          {sourceValue.omitted_content_types.length > 0 && (
            <p>
              未顯示的內容類型：{sourceValue.omitted_content_types.join("、")}
            </p>
          )}
          {sourceValue.next_offset !== null && (
            <button
              onClick={() =>
                void source(sourceValue.reference, sourceValue.next_offset!)
              }
            >
              讀取後續原文
            </button>
          )}
          <button onClick={() => setSourceValue(null)}>收起依據</button>
        </aside>
      )}
      {leaving && (
        <div role="dialog" aria-label="未保存內容">
          <p>
            {session.dirty ? "正文有未保存修改。" : ""}
            {session.text ? "這段話還沒送出；保存正文不會送出聊天。" : ""}
          </p>
          <button onClick={() => void leave("save")}>保存後離開</button>
          <button onClick={() => void leave("stay")}>繼續編輯</button>
          <button onClick={() => void leave("discard")}>
            捨棄未保存修改與未送出聊天後離開
          </button>
        </div>
      )}
      <div className="workspace-columns">
        <section className="chat-panel" aria-label="顧問訪談">
          <h2>顧問訪談</h2>
          <p className="intro">
            先談你的實際工作，資料足夠時顧問會開始整理。你可以隨時補充或更正。
          </p>
          <div className="messages">
            {session.messages.map((m) => (
              <article key={m.id} className={"message " + m.role}>
                <small>{m.role === "user" ? "你" : "顧問"}</small>
                <p>{m.text}</p>
              </article>
            ))}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void session
                .send(capture, false, selectionIntent)
                .then((sent) => {
                  if (sent) setSelectionIntent(false);
                });
            }}
          >
            <label htmlFor="message">補充或更正你的工作</label>
            <textarea
              id="message"
              value={session.text}
              onChange={(e) => {
                session.setText(e.target.value);
              }}
              disabled={session.busy || !!session.pendingRun}
              placeholder="例如：這項工作只在客戶提出需求時執行…"
            />
            <p className="hint">
              選取正文後送出，可請顧問處理該段；未保存修改會先保存。
            </p>
            <button
              className="primary"
              disabled={session.locked || !session.text.trim()}
            >
              {selectionIntent ? "請AI改這段" : "送出"}
            </button>
            {selectionIntent && (
              <button type="button" onClick={() => setSelectionIntent(false)}>
                改為純聊天
              </button>
            )}
            {session.run &&
              ["running", "stopping", "uncertain", "interrupted"].includes(
                session.run.status,
              ) && (
                <button type="button" onClick={() => void session.stop()}>
                  停止顧問
                </button>
              )}
            {session.run?.can_resume && (
              <button type="button" onClick={() => void session.resume()}>
                明示繼續顧問
              </button>
            )}
          </form>
          {session.pendingRun && (
            <aside>
              <p>正在確認是否收到原問句。</p>
              <button onClick={() => void session.lookup()}>再次確認</button>
              <button onClick={() => void session.send(capture, true)}>
                再次送出同一則
              </button>
            </aside>
          )}
        </section>
        <section className="document-panel" aria-label="目前職務說明書">
          <div className="document-heading">
            <h2>職務說明書</h2>
            <button
              className="primary"
              disabled={session.locked || !session.dirty}
              onClick={() => void session.save()}
            >
              保存
            </button>
            {session.dirty && (
              <button disabled={session.locked} onClick={() => {
                if (window.confirm("載入最新已保存內容？畫面上尚未保存的修改將被捨棄；未送出聊天與下方已送出候選都會保留。"))
                  void session.loadSavedHead();
              }}>
                捨棄畫面修改並載入最新稿
              </button>
            )}
            <button onClick={() => setShowChanges((v) => !v)}>這次改動</button>
            <button onClick={() => void previous()}>讀取上一筆歷史</button>
          </div>
          {session.head ? (
            <JdEditor
              key={epoch}
              value={session.value}
              locked={session.locked}
              saving={session.saving}
              onEdit={(value) => session.edit(value)}
              onReady={ready}
              onSelection={() => setSelectionIntent(true)}
              source={(ref) => void source(ref)}
            />
          ) : (
            <p>
              {session.error ? "暫時無法讀取，請重試。" : "讀取職務說明書…"}
            </p>
          )}
          {showChanges && session.change && (
            <JdChanges
              change={session.change}
              source={(ref) => void source(ref)}
            />
          )}
          <div>
            {history.map((change, i) => (
              <details key={i} open>
                <summary>
                  歷史 {i + 1}・{change.origin === "ai" ? "顧問" : "人工"}修改
                </summary>
                <JdChanges change={change} source={(ref) => void source(ref)} />
              </details>
            ))}
          </div>
          {session.recovery?.request_key && (
            <aside className="candidate">
              <h3>{session.recovery.status === 'available' ? '上次人工保存結果' : '上次人工保存结果尚未確認'}</h3>
              {session.recovery.status === 'available' && <p>{['committed','no_change'].includes(session.recovery.result.status) ? '已確認保存。' : '這次修改未保存：' + session.recovery.result.status}</p>}
              {!session.candidate && session.recovery.status !== 'available' && <p>本機沒有原候選；仍可確認原保存結果，但無法還原未保存的內容。</p>}
              {session.recovery.can_recover && <button disabled={session.busy} onClick={() => void session.recoverManual()}>
                {session.recovery.status === 'available' ? '清理上次保存狀態' : '確認上次保存結果'}
              </button>}
              <button disabled={session.busy} onClick={() => void session.revalidate()}>重新讀取狀態</button>
            </aside>
          )}
          {session.candidate && (
            <aside className="candidate">
              <h3>尚待處理的送出候選</h3>
              <p>
                這份材料尚未確認保存；不會覆蓋目前工作稿。未處理前關頁再開仍會保留。
              </p>
              <button disabled={!session.canRetryCandidate} onClick={() => void session.save(true)}>
                再次送出同一份
              </button>
              <button
                disabled={session.manualUnknown}
                onClick={() => {
                  if (
                    window.confirm(
                      "捨棄這份尚待處理的候選？目前已保存文件會保留。",
                    )
                  )
                    session.discardCandidate();
                }}
              >
                捨棄這份候選
              </button>
              <ReadOnlyValue value={session.candidate.value} />
            </aside>
          )}
        </section>
      </div>
    </main>
  );
}
