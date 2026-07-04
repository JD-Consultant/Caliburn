// 知識包 → 選單選項（ADR 0021；spec §5）。唯一的 pack 讀取邏輯集中點，全部純函式。
// 池序 = append 序（職位優先序），選單不排序不搜尋；選項無碼 → FieldCombobox 顯序號。
import type {
  CodeName, KnowledgePack, MatchGroup, MatchResult, NoteItem, OptionItem, PackSrc,
  PoolRow, SourceRef,
} from "@/types";

const newId = () => (globalThis.crypto?.randomUUID?.() ?? `id-${Math.random().toString(36).slice(2)}`);

export function packSrcToRef(s: PackSrc): SourceRef {
  return {
    ocs_code: s.ocs_code,
    occupation_name: s.ocs_name,
    code: s.code ?? "",
    ocu_code: s.ocu_code ?? undefined,
    task_code: s.task_code ?? undefined,
    task_name: s.task_name ?? undefined,
  };
}

// 值池（K/S/O/P/態度/notes）→ 選項。ownPairs 給了 → 該列若含「自己的來源」
// （ocs_code+task_code 命中），把它穩定重排到 srcs 首位：_ref 與引用行首行都對到本任務。
export function valuePoolOptions(
  pool: Record<string, PoolRow>,
  ownPairs?: { ocs_code: string; task_code: string }[],
): OptionItem[] {
  return Object.entries(pool).map(([name, row]) => {
    let srcs = row.srcs.map(packSrcToRef);
    if (ownPairs?.length) {
      const i = row.srcs.findIndex((s) =>
        ownPairs.some((p) => p.ocs_code === s.ocs_code && p.task_code === (s.task_code ?? "")));
      if (i > 0) srcs = [srcs[i], ...srcs.slice(0, i), ...srcs.slice(i + 1)];
    }
    return { code: "", name, srcs };
  });
}

// 三類池（職類別/職業別/行業別）：key = 國家分類碼（選單例外顯真實碼）。
// 主基準是否官方(spec 2026-07-04 §4:主基準空白/自訂 → 自動勾選不套)。
export function isOfficialBasis(pack: KnowledgePack, ocsCode: string): boolean {
  return !!ocsCode && pack.occupation_details.some((d) => d.ocs_code === ocsCode);
}

// 表頭層自動勾選 defaults:srcs 含主基準碼的選項(順序照池序,不重排)。
export function primaryDefaults(options: OptionItem[], primaryCode: string): OptionItem[] {
  return options.filter((o) => (o.srcs ?? []).some((s) => s.ocs_code === primaryCode));
}

// 舊 draft notes 遷移(spec 2026-07-04 §3):string[] → 影子列;文字對池命中=official
// (來源凍結為池列首來源),未命中=custom;顯示碼照序 n{i}(不補零)。
export function noteRowsFromStrings(texts: string[], pool: Record<string, PoolRow>): NoteItem[] {
  return texts.map((t, i) => {
    const src = pool[t]?.srcs?.[0];
    return src
      ? { code: `n${i + 1}`, text: t, _id: newId(), _src: "official" as const, _ref: packSrcToRef(src) }
      : { code: `n${i + 1}`, text: t, _id: newId(), _src: "custom" as const };
  });
}

export function codedPoolOptions(
  pool: Record<string, { name: string; srcs: PackSrc[] }>,
): OptionItem[] {
  return Object.entries(pool).map(([code, row]) => ({
    code,
    name: row.name,
    srcs: row.srcs.map((s) => ({ ...packSrcToRef(s), code })),
  }));
}

// 選項 → 官方文件項（勾選/預勾共用形狀；_ref = srcs[0]，即 own-first 重排後的本任務來源）。
export function toItems(options: OptionItem[]): CodeName[] {
  return options.map((o) => ({
    code: o.code, name: o.name, _id: newId(), _src: "official" as const,
    _ref: o.srcs?.[0] ?? { ocs_code: "", occupation_name: "", code: o.code },
  }));
}

// 任務自己的官方配套（聯集，照 urns 順序；level 衝突取第一個非空 = 順序 1 優先）。
export function ownTaskRefs(pack: KnowledgePack, urns: string[]): {
  k: string[]; s: string[]; o: string[]; p: string[];
  level: number | null; levelSrc: SourceRef | null;
  pairs: { ocs_code: string; task_code: string }[];
} {
  const acc = { k: [] as string[], s: [] as string[], o: [] as string[], p: [] as string[] };
  let level: number | null = null;
  let levelSrc: SourceRef | null = null;
  const pairs: { ocs_code: string; task_code: string }[] = [];
  for (const urn of urns) {
    const st = pack.source_tasks[urn];
    if (!st) continue;
    pairs.push({ ocs_code: st.ocs_code, task_code: st.task_code });
    for (const [field, refs] of [["k", st.k_refs], ["s", st.s_refs], ["o", st.o_refs], ["p", st.p_refs]] as const) {
      for (const key of refs) if (!acc[field].includes(key)) acc[field].push(key);
    }
    if (level === null && st.competency_level !== null) {
      level = st.competency_level;
      levelSrc = {
        ocs_code: st.ocs_code, occupation_name: st.ocs_name, code: "",
        task_code: st.task_code, task_name: st.task_name,
      };
    }
  }
  return { ...acc, level, levelSrc, pairs };
}

// ── 職責/任務兩選單（TaskCuratePanel）─────────────────────────────────────────
export interface UnitRowVM {
  name: string;                 // units 池 key
  srcs: SourceRef[];            // 來源職責（每來源含 ocu_code）
  ownTaskKeys: string[];        // 該職責官方帶的任務（合併列=聯集；值 = tasks 池 key）
}
export interface TaskRowVM {
  name: string;                 // tasks 池 key
  urns: string[];               // 池列 srcs（source_tasks 的 URN）
  srcs: SourceRef[];            // 顯示用（URN → source_tasks 解出）
  similarTo?: { name: string; score: number }[];  // 相似比對灰區對(ADR 0022,純顯示)
}

export function unitRows(pack: KnowledgePack): UnitRowVM[] {
  return Object.entries(pack.pools.units).map(([name, row]) => {
    const pairSet = new Set(row.srcs.map((s) => `${s.ocs_code}__${s.ocu_code ?? ""}`));
    const ownTaskKeys: string[] = [];
    for (const st of Object.values(pack.source_tasks)) {
      if (!pairSet.has(`${st.ocs_code}__${st.ocu_code ?? ""}`)) continue;
      if (st.task_name && !ownTaskKeys.includes(st.task_name)) ownTaskKeys.push(st.task_name);
    }
    return { name, srcs: row.srcs.map(packSrcToRef), ownTaskKeys };
  });
}

export function taskRows(pack: KnowledgePack): TaskRowVM[] {
  return Object.entries(pack.pools.tasks).map(([name, row]) => ({
    name,
    urns: row.srcs,
    srcs: row.srcs.flatMap((urn) => {
      const st = pack.source_tasks[urn];
      return st ? [{
        ocs_code: st.ocs_code, occupation_name: st.ocs_name, code: st.task_code,
        task_code: st.task_code, task_name: st.task_name,
      }] : [];
    }),
  }));
}

// ── 表頭（DocHeader）──────────────────────────────────────────────────────────
export interface BasisOption {
  ocs_code: string;
  occupation_name: string;
  job_category_name: string;
  job_description: string;
  ocs_level: number | null;
}

export function primaryBasisOptions(pack: KnowledgePack): BasisOption[] {
  return pack.occupation_details.map((d) => ({
    ocs_code: d.ocs_code,
    occupation_name: d.ocs_name.occupation_name ?? "",
    job_category_name: d.ocs_name.job_category_name ?? "",
    job_description: d.job_description,
    ocs_level: d.ocs_level,
  }));
}

// ── 相似比對(ADR 0022)。鐵律:選擇邏輯(primaryDefaults/自動套/勾選/寫入身分)跑在
// 平選項上一行不改;以下只是 render 前最後一步的顯示變換(把分群搬進選擇邏輯 = 違規)。──

// survivorship(顯示代表):主基準成員優先(不變量 B)→ 文字最長 → 名稱升序(決定論)。
function survivor(members: OptionItem[], primaryCode: string): OptionItem {
  const primary = members.find((o) => (o.srcs ?? []).some((s) => s.ocs_code === primaryCode));
  if (primary) return primary;
  return [...members].sort((a, b) => b.name.length - a.name.length || a.name.localeCompare(b.name))[0];
}

// 值池選項 → 顯示列:群成員收成一列(代表 = survivor,其餘進 variants)。代表列**就是
// 成員本人**(群無可選身分,文件永遠只出現成員真身)。match 缺席 → 原樣返回(降級)。
// 池序保持:群放在首個成員的位置;成員對不上池 → 不收合。
export function groupedValueOptions(
  options: OptionItem[], match: MatchResult | undefined, primaryCode: string,
): OptionItem[] {
  if (!match?.groups?.length) return options;
  const byName = new Map(options.map((o) => [o.name, o]));
  const groupOf = new Map<string, MatchGroup>();
  for (const g of match.groups) for (const m of g.members) groupOf.set(m.id, g);
  const emitted = new Set<MatchGroup>();
  const out: OptionItem[] = [];
  for (const o of options) {
    const g = groupOf.get(o.name);
    if (!g) { out.push(o); continue; }
    if (emitted.has(g)) continue;
    emitted.add(g);
    const members = g.members.map((m) => byName.get(m.id)).filter((x): x is OptionItem => !!x);
    if (members.length < 2) { out.push(o); continue; }   // 成員對不上池 → 不收合
    const rep = survivor(members, primaryCode);
    out.push({ ...rep, variants: members.filter((m) => m !== rep) });
  }
  return out;
}

// 任務列 + 灰區對(雙向)。similarity 缺席 → 原樣(降級)。純顯示:不勾、不併、不擋。
export function taskRowsWithSimilar(pack: KnowledgePack): TaskRowVM[] {
  const rows = taskRows(pack);
  const pairs = pack.similarity?.task?.possible_matches ?? [];
  if (!pairs.length) return rows;
  const map = new Map<string, { name: string; score: number }[]>();
  const push = (k: string, v: { name: string; score: number }) => {
    const arr = map.get(k) ?? [];
    arr.push(v);
    map.set(k, arr);
  };
  for (const p of pairs) {
    push(p.left_id, { name: p.right_id, score: p.score });
    push(p.right_id, { name: p.left_id, score: p.score });
  }
  return rows.map((r) => (map.has(r.name) ? { ...r, similarTo: map.get(r.name)! } : r));
}
