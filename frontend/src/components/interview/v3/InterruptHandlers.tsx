"use client";

// v3 HITL via CopilotKit v2 useInterrupt (D22). renderInChat:false → the hook
// returns a ReactElement we place in our own (no-chat) UI. Listens to the agent's
// on_interrupt custom events. Wired: select_profile, edit_tasks. Deep-interview
// (ask_human) + edit_ksa/preview are deferred until the LLM API is testable.
import { useInterrupt } from "@copilotkit/react-core/v2";
import { useState } from "react";

const AGENT_NAME = "jd_authoring";

type ProfileCandidate = {
  id?: string;
  ocs_code: string;
  job_title?: string | null;
  task_title?: string | null;
};

// edit_tasks payload (backend build_task_pool → _pool_to_tasks). Resume contract:
// backend reads edited["tasks"] (a dict, NOT a string), so resolve({ tasks }).
type PoolTask = {
  task_name: string;
  source?: string;
  indexer_ref?: { ocs_code?: string; task_id?: string };
  unit_id?: string;
  unit_title?: string;
  activity_examples?: string[];
};

// edit_ksa payload (assemble_ksa). Item = {content, source, icap_ref}.
// Resume: backend reads edited["ksa"] → resolve({ ksa }).
type KsaItem = { content: string; source?: string; icap_ref?: string | null };
type Ksa = { knowledge: KsaItem[]; skills: KsaItem[]; attitudes: KsaItem[] };

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
      }>;
    }>;
  };
  ocs_ksa?: { knowledge?: CodedKsa[]; skills?: CodedKsa[]; attitudes?: CodedKsa[] };
};

type InterruptValue = {
  kind?: string;
  candidates?: ProfileCandidate[];
  tasks?: PoolTask[];
  // ask_human
  stage?: string;
  slot?: string;
  field?: string;
  task_name?: string;
  label?: string;
  question?: string;
  // edit_ksa / preview
  ksa?: Ksa;
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
              {c.job_title ? `　${c.job_title}` : ""}
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

function TaskCurator({
  tasks,
  onConfirm,
}: {
  tasks: PoolTask[];
  onConfirm: (tasks: PoolTask[]) => void;
}) {
  // Default: keep all proposed tasks; user un-checks the ones to drop.
  const [kept, setKept] = useState<Set<number>>(
    () => new Set(tasks.map((_, i) => i)),
  );
  const [done, setDone] = useState(false);

  if (!tasks.length) {
    return <div className="text-sm text-muted-foreground">indexer 沒有回傳任務。</div>;
  }

  // Preserve catalog order while grouping by unit for readability.
  const units: { unit_title: string; items: { task: PoolTask; idx: number }[] }[] = [];
  tasks.forEach((task, idx) => {
    const title = task.unit_title ?? "（未分類）";
    let group = units.find((u) => u.unit_title === title);
    if (!group) {
      group = { unit_title: title, items: [] };
      units.push(group);
    }
    group.items.push({ task, idx });
  });

  const toggle = (idx: number) =>
    setKept((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });

  return (
    <div className="space-y-3 rounded-xl border p-3">
      <p className="text-sm font-medium">
        確認任務清單（保留 {kept.size} / {tasks.length}）
      </p>
      <div className="space-y-3">
        {units.map((u) => (
          <div key={u.unit_title} className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">{u.unit_title}</p>
            {u.items.map(({ task, idx }) => (
              <label
                key={idx}
                className="flex cursor-pointer items-start gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-muted"
              >
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={kept.has(idx)}
                  disabled={done}
                  onChange={() => toggle(idx)}
                />
                <span className="flex-1">
                  <span className={kept.has(idx) ? "" : "text-muted-foreground line-through"}>
                    {task.task_name}
                  </span>
                  {task.activity_examples?.length ? (
                    <span className="mt-0.5 block text-xs text-muted-foreground">
                      {task.activity_examples.slice(0, 3).join("、")}
                    </span>
                  ) : null}
                </span>
              </label>
            ))}
          </div>
        ))}
      </div>
      <button
        type="button"
        className="w-full rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        disabled={done || kept.size === 0}
        onClick={() => {
          setDone(true);
          onConfirm(tasks.filter((_, i) => kept.has(i)));
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

function KsaEditor({
  ksa,
  onConfirm,
}: {
  ksa: Ksa;
  onConfirm: (ksa: Ksa) => void;
}) {
  const [draft, setDraft] = useState<Ksa>(() => ({
    knowledge: [...(ksa.knowledge ?? [])],
    skills: [...(ksa.skills ?? [])],
    attitudes: [...(ksa.attitudes ?? [])],
  }));
  const [done, setDone] = useState(false);

  const cats: { key: keyof Ksa; label: string }[] = [
    { key: "knowledge", label: "知識 K" },
    { key: "skills", label: "技能 S" },
    { key: "attitudes", label: "態度 A" },
  ];

  const edit = (key: keyof Ksa, i: number, content: string) =>
    setDraft((d) => {
      const items = [...d[key]];
      items[i] = { ...items[i], content };
      return { ...d, [key]: items };
    });
  const remove = (key: keyof Ksa, i: number) =>
    setDraft((d) => ({ ...d, [key]: d[key].filter((_, j) => j !== i) }));
  const add = (key: keyof Ksa) =>
    setDraft((d) => ({ ...d, [key]: [...d[key], { content: "", source: "company", icap_ref: null }] }));

  return (
    <div className="space-y-3 rounded-xl border p-3">
      <p className="text-sm font-medium">編輯 KSA（catalog 帶入，可增刪改）</p>
      {cats.map(({ key, label }) => (
        <div key={key} className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground">
            {label}（{draft[key].length}）
          </p>
          {draft[key].map((it, i) => (
            <div key={i} className="flex items-center gap-2">
              <input
                className="flex-1 rounded-lg border px-2 py-1 text-sm"
                value={it.content}
                disabled={done}
                onChange={(e) => edit(key, i, e.target.value)}
              />
              {it.icap_ref ? (
                <span className="font-mono text-[10px] text-muted-foreground">{it.icap_ref}</span>
              ) : null}
              <button
                type="button"
                className="rounded px-2 text-sm text-red-500 hover:bg-red-50 disabled:opacity-50"
                disabled={done}
                onClick={() => remove(key, i)}
              >
                ✕
              </button>
            </div>
          ))}
          <button
            type="button"
            className="text-xs text-blue-600 hover:underline disabled:opacity-50"
            disabled={done}
            onClick={() => add(key)}
          >
            ＋ 新增
          </button>
        </div>
      ))}
      <button
        type="button"
        className="w-full rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        disabled={done}
        onClick={() => {
          setDone(true);
          // drop blank rows; keep item shape {content, source, icap_ref}
          const clean = (items: KsaItem[]) =>
            items.filter((it) => it.content.trim()).map((it) => ({ ...it, content: it.content.trim() }));
          onConfirm({
            knowledge: clean(draft.knowledge),
            skills: clean(draft.skills),
            attitudes: clean(draft.attitudes),
          });
        }}
      >
        確認 KSA，產生文件
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
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="space-y-1">
        {ksaRow("知識 K", ksa.knowledge)}
        {ksaRow("技能 S", ksa.skills)}
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
      if (value.kind === "edit_ksa") {
        // backend reads edited["ksa"] → resolve a dict.
        return (
          <KsaEditor
            ksa={value.ksa ?? { knowledge: [], skills: [], attitudes: [] }}
            onConfirm={(ksa) => resolve({ ksa })}
          />
        );
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
