"use client";

// HITL via CopilotKit v2 useInterrupt (D22). renderInChat:false → the hook
// returns a ReactElement we place in our own (no-chat) UI. Listens to the agent's
// on_interrupt custom events. Wired: select_profile, edit_tasks, ask_human,
// curate_ks (per-task K/S), curate_attitudes, preview.
import { useInterrupt } from "@copilotkit/react-core/v2";
import { useState } from "react";

const AGENT_NAME = "jd_authoring";

type ProfileCandidate = {
  ocs_code: string;
  ocs_name?: string | null;
};

// edit_tasks payload (backend build_task_pool → _pool_to_tasks). Resume contract:
// backend reads edited["tasks"] (a dict, NOT a string), so resolve({ tasks }).
type PoolTask = {
  task_name: string;
  source?: string;
  indexer_ref?: { ocs_code?: string; task_code?: string };
  unit_id?: string;
  unit_title?: string;
};

// KSA item shape shared by curate_ks + curate_attitudes.
// sources：展示用 provenance（哪些 task_code 帶入此候選），不寫入文件。
type KsaItem = { content: string; source?: string; icap_ref?: string | null; sources?: string[] };

// preview payload (build_doc _assemble). resume value ignored → resolve() to confirm.
type CodedKsa = { code?: string; name?: string; source?: string };
type DocPreview = {
  ocs_profile?: { ocs_code?: string; occupation_name?: string; job_description?: string };
  ocs_content?: {
    ocu_units?: Array<{
      ocu_code?: string;
      ocu_name?: string;
      tasks?: Array<{
        task_code?: string;
        task_name?: string;
        indicators?: { code?: string; text?: string }[];
        outputs?: { code?: string; name?: string }[];
        knowledge?: { code?: string; name?: string }[];
        skills?: { code?: string; name?: string }[];
      }>;
    }>;
  };
  ocs_ksa?: { attitudes?: CodedKsa[] };
};

type InterruptValue = {
  kind?: string;
  // select_profile
  candidates?: ProfileCandidate[];
  tasks?: PoolTask[];
  // ask_human
  stage?: string;
  slot?: string;
  field?: string;
  task_name?: string;
  label?: string;
  question?: string;
  // curate_ks
  task_index?: number;
  task_total?: number;
  // curate_ks candidates structure + selected
  // curate_attitudes: candidates/selected are flat KsaItem arrays (typed via `as never` at call site)
  selected?: { knowledge?: KsaItem[]; skills?: KsaItem[] } | KsaItem[];
  // preview
  document?: DocPreview;
};

function ProfilePicker({
  candidates,
  onConfirm,
}: {
  candidates: ProfileCandidate[];
  // ordered by selection = priority; backend reads resume["ocs_codes"].
  onConfirm: (ocsCodes: string[]) => void;
}) {
  const [order, setOrder] = useState<string[]>([]); // 點選順序 = 優先度
  const [done, setDone] = useState(false);
  if (!candidates.length) {
    return <div className="text-sm text-muted-foreground">indexer 沒有回傳候選 OCS。</div>;
  }

  const toggle = (code: string) =>
    setOrder((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
    );

  return (
    <div className="space-y-2 rounded-xl border p-3">
      <p className="text-sm font-medium">選擇職類（OCS）— 可複選，點選順序＝優先度</p>
      {candidates.map((c) => {
        const rank = order.indexOf(c.ocs_code); // -1 = 未選
        const picked = rank >= 0;
        return (
          <button
            key={c.ocs_code}
            type="button"
            className={`flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm hover:bg-muted ${
              picked ? "border-blue-500 bg-blue-50" : ""
            }`}
            disabled={done}
            onClick={() => toggle(c.ocs_code)}
          >
            <span
              className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs ${
                picked ? "bg-blue-600 text-white" : "border text-muted-foreground"
              }`}
            >
              {picked ? rank + 1 : ""}
            </span>
            <span className="flex-1">
              <span className="font-mono text-xs text-muted-foreground">{c.ocs_code}</span>
              {c.ocs_name ? `　${c.ocs_name}` : ""}
            </span>
          </button>
        );
      })}
      <button
        type="button"
        className="w-full rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        disabled={done || order.length === 0}
        onClick={() => {
          setDone(true);
          onConfirm(order);
        }}
      >
        確認（已選 {order.length} 個）
      </button>
    </div>
  );
}

// Single editable review surface for the task pool (D24-b: 勾/改/增/刪 + provenance).
// Each row carries a stable client _id so inline inputs keep focus across edits,
// plus an `included` flag (keep/drop). Confirm resolves the full task objects
// (provenance preserved: catalog rows keep indexer_ref/unit;
// custom rows are source="company").
type TaskRow = PoolTask & { _id: number; included: boolean };

function TaskCurator({
  tasks,
  onConfirm,
}: {
  tasks: PoolTask[];
  onConfirm: (tasks: PoolTask[]) => void;
}) {
  const [rows, setRows] = useState<TaskRow[]>(
    () => tasks.map((t, i) => ({ ...t, _id: i, included: true })),
  );
  const [nextId, setNextId] = useState(tasks.length);
  const [done, setDone] = useState(false);

  const patch = (id: number, p: Partial<TaskRow>) =>
    setRows((rs) => rs.map((r) => (r._id === id ? { ...r, ...p } : r)));
  const removeRow = (id: number) => setRows((rs) => rs.filter((r) => r._id !== id));
  const addCustom = () => {
    setRows((rs) => [...rs, { _id: nextId, included: true, task_name: "", source: "company" }]);
    setNextId((n) => n + 1);
  };

  // Group by unit for readability; custom rows (no unit) fall under 公司自訂任務.
  const groups: { title: string; rows: TaskRow[] }[] = [];
  rows.forEach((r) => {
    const title = r.unit_title ?? "公司自訂任務";
    let g = groups.find((x) => x.title === title);
    if (!g) {
      g = { title, rows: [] };
      groups.push(g);
    }
    g.rows.push(r);
  });

  const keptCount = rows.filter((r) => r.included && r.task_name.trim()).length;

  return (
    <div className="space-y-3 rounded-xl border p-3">
      <p className="text-sm font-medium">確認任務清單（可勾選/改名/刪除/新增）— 保留 {keptCount}</p>
      <div className="space-y-3">
        {groups.map((g) => (
          <div key={g.title} className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">{g.title}</p>
            {g.rows.map((r) => (
              <div
                key={r._id}
                className="flex items-start gap-2 rounded-lg border px-3 py-2 text-sm"
              >
                <input
                  type="checkbox"
                  className="mt-1.5"
                  checked={r.included}
                  disabled={done}
                  onChange={() => patch(r._id, { included: !r.included })}
                />
                <span className="flex-1">
                  <span className="flex items-center gap-1.5">
                    <input
                      className={`flex-1 rounded border px-2 py-1 text-sm ${
                        r.included ? "" : "text-muted-foreground line-through"
                      }`}
                      value={r.task_name}
                      disabled={done}
                      placeholder={r.source === "company" ? "輸入自訂任務名稱…" : ""}
                      onChange={(e) => patch(r._id, { task_name: e.target.value })}
                    />
                    <span
                      className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] ${
                        r.source === "company"
                          ? "bg-amber-100 text-amber-700"
                          : "bg-blue-50 text-blue-600"
                      }`}
                    >
                      {r.source === "company" ? "公司" : "catalog"}
                    </span>
                  </span>
                </span>
                <button
                  type="button"
                  className="mt-0.5 rounded px-1 text-red-500 hover:bg-red-50 disabled:opacity-50"
                  disabled={done}
                  onClick={() => removeRow(r._id)}
                  aria-label="刪除任務"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        ))}
      </div>
      <button
        type="button"
        className="text-xs text-blue-600 hover:underline disabled:opacity-50"
        disabled={done}
        onClick={addCustom}
      >
        ＋ 新增自訂任務
      </button>
      <button
        type="button"
        className="w-full rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        disabled={done || keptCount === 0}
        onClick={() => {
          setDone(true);
          // keep included rows with a non-blank name; emit clean PoolTask
          // objects (drop client-only _id/included), provenance preserved.
          onConfirm(
            rows
              .filter((r) => r.included && r.task_name.trim())
              .map((r) => ({
                task_name: r.task_name.trim(),
                source: r.source,
                indexer_ref: r.indexer_ref,
                unit_id: r.unit_id,
                unit_title: r.unit_title,
              })),
          );
        }}
      >
        確認，開始深度訪談
      </button>
    </div>
  );
}

function AskHuman({
  value,
  onAnswer,
}: {
  value: InterruptValue;
  onAnswer: (answer: string) => void;
}) {
  const [text, setText] = useState("");
  const [done, setDone] = useState(false);
  const stageLabel =
    value.stage === "star" ? "STAR" : value.stage === "five_w2h" ? "5W2H" : "深問";
  return (
    <div className="space-y-2 rounded-xl border p-3">
      <div className="flex items-center gap-2">
        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">
          {stageLabel}
        </span>
        {value.task_name ? (
          <span className="text-xs text-muted-foreground">{value.task_name}</span>
        ) : null}
        {value.label ? <span className="text-xs font-medium">{value.label}</span> : null}
      </div>
      <p className="text-sm">{value.question ?? "請補充說明"}</p>
      <textarea
        className="w-full rounded-lg border px-3 py-2 text-sm"
        rows={3}
        value={text}
        disabled={done}
        onChange={(e) => setText(e.target.value)}
        placeholder="輸入回答…"
      />
      <button
        type="button"
        className="w-full rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        disabled={done || !text.trim()}
        onClick={() => {
          setDone(true);
          onAnswer(text.trim());
        }}
      >
        送出
      </button>
    </div>
  );
}

function CurateList({
  title, candidates, value, onChange, done,
}: {
  title: string;
  candidates: KsaItem[];
  value: KsaItem[];
  onChange: (items: KsaItem[]) => void;
  done: boolean;
}) {
  // candidates default unchecked: check by content match
  const has = (c: string) => value.some((v) => v.content === c);
  const toggle = (it: KsaItem) =>
    onChange(has(it.content) ? value.filter((v) => v.content !== it.content) : [...value, it]);
  const edit = (i: number, content: string) =>
    onChange(value.map((v, j) => (j === i ? { ...v, content } : v)));
  const remove = (i: number) => onChange(value.filter((_, j) => j !== i));
  const add = () => onChange([...value, { content: "", source: "company", icap_ref: null }]);
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium text-muted-foreground">{title}（已選 {value.length}）</p>
      {candidates.map((c) => (
        <label key={c.content} className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={has(c.content)} disabled={done} onChange={() => toggle(c)} />
          <span className={has(c.content) ? "" : "text-muted-foreground"}>{c.content}</span>
          {c.icap_ref ? <span className="font-mono text-[10px] text-muted-foreground">{c.icap_ref}</span> : null}
          {c.sources?.length ? (
            <span className="shrink-0 rounded bg-sky-100 px-1 py-0.5 text-[10px] text-sky-700"
                  title={"來自：" + c.sources.join("、")}>
              共 {c.sources.length}
            </span>
          ) : null}
        </label>
      ))}
      {value.filter((v) => !candidates.some((c) => c.content === v.content)).map((v, i) => (
        <div key={`extra-${i}`} className="flex items-center gap-2">
          <input className="flex-1 rounded border px-2 py-1 text-sm" value={v.content} disabled={done}
                 onChange={(e) => edit(value.indexOf(v), e.target.value)} />
          <button type="button" className="text-red-500" disabled={done} onClick={() => remove(value.indexOf(v))}>✕</button>
        </div>
      ))}
      <button type="button" className="text-xs text-blue-600 hover:underline" disabled={done} onClick={add}>＋ 新增自訂</button>
    </div>
  );
}

function CurateKsPanel({ value, onConfirm }: {
  value: { task_index: number; task_total: number; task_name: string;
           candidates: { knowledge: KsaItem[]; skills: KsaItem[] };
           selected: { knowledge: KsaItem[]; skills: KsaItem[] } };
  onConfirm: (ks: { knowledge: KsaItem[]; skills: KsaItem[] }) => void;
}) {
  const [k, setK] = useState<KsaItem[]>(value.selected?.knowledge ?? []);
  const [s, setS] = useState<KsaItem[]>(value.selected?.skills ?? []);
  const [done, setDone] = useState(false);
  return (
    <div className="space-y-3 rounded-xl border p-3">
      <p className="text-sm font-medium">
        任務 {value.task_index + 1}/{value.task_total}：{value.task_name} — 選知識(K) / 技能(S)
      </p>
      <CurateList title="知識 K" candidates={value.candidates.knowledge} value={k} onChange={setK} done={done} />
      <CurateList title="技能 S" candidates={value.candidates.skills} value={s} onChange={setS} done={done} />
      <button type="button" className="w-full rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              disabled={done}
              onClick={() => { setDone(true);
                onConfirm({ knowledge: k.filter((x) => x.content.trim()), skills: s.filter((x) => x.content.trim()) }); }}>
        確認此任務，下一個
      </button>
    </div>
  );
}

function CurateAttitudesPanel({ value, onConfirm }: {
  value: { candidates: KsaItem[]; selected: KsaItem[] };
  onConfirm: (attitudes: KsaItem[]) => void;
}) {
  const [a, setA] = useState<KsaItem[]>(value.selected ?? []);
  const [done, setDone] = useState(false);
  return (
    <div className="space-y-3 rounded-xl border p-3">
      <p className="text-sm font-medium">選態度（A，全職類共用）</p>
      <CurateList title="態度 A" candidates={value.candidates} value={a} onChange={setA} done={done} />
      <button type="button" className="w-full rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              disabled={done}
              onClick={() => { setDone(true); onConfirm(a.filter((x) => x.content.trim())); }}>
        確認態度，產生文件
      </button>
    </div>
  );
}

function DocPreviewPanel({
  document: doc,
  onConfirm,
}: {
  document: DocPreview;
  onConfirm: () => void;
}) {
  const [done, setDone] = useState(false);
  const units = doc.ocs_content?.ocu_units ?? [];
  const ksa = doc.ocs_ksa ?? {};
  const ksaRow = (label: string, items?: CodedKsa[]) =>
    items?.length ? (
      <p className="text-sm">
        <span className="font-medium">{label}：</span>
        {items.map((it) => `${it.code ?? ""} ${it.name ?? ""}`).join("； ")}
      </p>
    ) : null;

  return (
    <div className="space-y-3 rounded-xl border p-3">
      <p className="text-sm font-medium">文件預覽</p>
      <div className="rounded-lg bg-muted/40 p-2 text-sm">
        <p className="font-semibold">{doc.ocs_profile?.occupation_name ?? "（未命名職類）"}</p>
        <p className="font-mono text-xs text-muted-foreground">{doc.ocs_profile?.ocs_code}</p>
        {doc.ocs_profile?.job_description ? (
          <p className="mt-1 text-xs text-muted-foreground">{doc.ocs_profile.job_description}</p>
        ) : null}
      </div>

      <div className="space-y-2">
        {units.map((u) => (
          <div key={u.ocu_code} className="rounded-lg border p-2">
            <p className="text-sm font-medium">
              <span className="font-mono text-xs text-muted-foreground">{u.ocu_code}</span>{" "}
              {u.ocu_name}
            </p>
            <ul className="mt-1 space-y-1">
              {(u.tasks ?? []).map((t) => (
                <li key={t.task_code} className="text-sm">
                  <span className="font-mono text-xs text-muted-foreground">{t.task_code}</span>{" "}
                  {t.task_name}
                  {t.outputs?.length ? (
                    <span className="block pl-4 text-xs text-muted-foreground">
                      產出：{t.outputs.map((o) => o.name).join("、")}
                    </span>
                  ) : null}
                  {t.indicators?.length ? (
                    <span className="block pl-4 text-xs text-muted-foreground">
                      指標：{t.indicators.length} 項
                    </span>
                  ) : null}
                  {t.knowledge?.length ? (
                    <span className="block pl-4 text-xs text-muted-foreground">
                      K：{t.knowledge.map((x) => x.name).join("、")}
                    </span>
                  ) : null}
                  {t.skills?.length ? (
                    <span className="block pl-4 text-xs text-muted-foreground">
                      S：{t.skills.map((x) => x.name).join("、")}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="space-y-1">
        {ksaRow("態度 A", ksa.attitudes)}
      </div>

      <button
        type="button"
        className="w-full rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
        disabled={done}
        onClick={() => {
          setDone(true);
          onConfirm();
        }}
      >
        確認，儲存文件
      </button>
    </div>
  );
}

export function InterruptHandlers() {
  return useInterrupt({
    agentId: AGENT_NAME,
    renderInChat: false,
    render: ({ event, resolve }) => {
      // event.value is normally the parsed payload; tolerate a JSON string too.
      let raw: unknown = event.value;
      if (typeof raw === "string") {
        try {
          raw = JSON.parse(raw);
        } catch {
          /* leave as-is */
        }
      }
      const value = (raw ?? {}) as InterruptValue;
      if (value.kind === "select_profile") {
        // backend reads resume["ocs_codes"] (ordered = priority) → resolve a dict.
        return (
          <ProfilePicker
            candidates={value.candidates ?? []}
            onConfirm={(ocsCodes) => resolve({ ocs_codes: ocsCodes })}
          />
        );
      }
      if (value.kind === "edit_tasks") {
        // backend reads edited["tasks"] → resolve a dict, not a string.
        return (
          <TaskCurator
            tasks={value.tasks ?? []}
            onConfirm={(tasks) => resolve({ tasks })}
          />
        );
      }
      if (value.kind === "ask_human") {
        // backend: answer if isinstance(answer, str) → resolve a STRING (not a dict).
        return <AskHuman value={value} onAnswer={(answer) => resolve(answer)} />;
      }
      if (value.kind === "curate_ks") {
        return <CurateKsPanel value={value as never} onConfirm={(ks) => resolve({ ks })} />;
      }
      if (value.kind === "curate_attitudes") {
        return <CurateAttitudesPanel value={value as never} onConfirm={(attitudes) => resolve({ attitudes })} />;
      }
      if (value.kind === "preview") {
        // backend ignores the resume value → resolve() just confirms/saves.
        return (
          <DocPreviewPanel document={value.document ?? {}} onConfirm={() => resolve(true)} />
        );
      }
      return <></>;
    },
  });
}
