"use client";

// D13 CellFiller：per-cell FieldCombobox。選項＝知識包大池（全部，可借用；ADR 0021），
// 預勾＝任務自己的官方配套（o/p/k/s_refs 聯集）：空格開面板自動套用、「自動勾選」鈕重套，
// 之後以使用者動過的為準（文件是真相）。每格點選即 onSave(nextDoc)，無存檔鈕。
import { useEffect, useRef } from "react";
import type { OcsDocument } from "@/types";
import { getBlock, setKS, setOp } from "@/lib/ocsDoc";
import { taskUrns } from "@/lib/urn";
import { ownTaskRefs, toItems, valuePoolOptions } from "@/lib/pack";
import { useKnowledge } from "@/hooks/useKnowledge";
import { FieldCombobox } from "./fields/FieldCombobox";
import type { CellTarget } from "./JobDocTable";
import { X } from "lucide-react";

function taskName(doc: OcsDocument, unitIdx: number, taskIdx: number): string {
  const tc = doc.ocs_content?.ocu_units?.[unitIdx]?.tasks?.[taskIdx]?.task_codes?.[0];
  return tc?.name || "任務";
}

const TITLES: Record<CellTarget["kind"], string> = {
  o: "工作產出 O",
  p: "行為指標 P",
  k: "知識 K",
  s: "技能 S",
};

export function CellFillerPanel({
  document,
  target,
  profileId,
  onSave,
  onClose,
}: {
  document: OcsDocument;
  target: CellTarget;
  profileId: string;
  onSave: (doc: OcsDocument) => void;
  onClose: () => void;
}) {
  const { unitIdx, taskIdx } = target;
  const task = document.ocs_content?.ocu_units?.[unitIdx]?.tasks?.[taskIdx];
  // 任務身分 URN（合併列 _refs 多筆；自訂任務空 → own 集為空，仍可借用大池）。
  const urns = taskUrns(task ?? {});
  const { data: pack, isLoading } = useKnowledge(profileId, true);
  const own = pack ? ownTaskRefs(pack, urns) : null;
  const block = getBlock(document, unitIdx, taskIdx);
  const tn = taskName(document, unitIdx, taskIdx);
  const title = `${tn}：${TITLES[target.kind]}`;
  // 任務範圍碼：T1.1 → O1.1.1 / P1.1.1（自訂時依任務遞增）。
  const taskCode = task?.task_codes?.[0]?.code ?? "";
  const taskNum = taskCode.replace(/^T/i, "");

  // 該格的池選項（own-first 重排：_ref 與引用行對到本任務）＋ 預設集（own refs 命中的列）。
  const forKind = (kind: CellTarget["kind"]) => {
    if (!pack || !own) return { options: [], defaults: [] };
    const pool = {
      o: pack.pools.outputs, p: pack.pools.indicators,
      k: pack.pools.knowledge, s: pack.pools.skills,
    }[kind];
    const ownKeys = new Set({ o: own.o, p: own.p, k: own.k, s: own.s }[kind]);
    const options = valuePoolOptions(pool, own.pairs);
    return { options, defaults: options.filter((op) => ownKeys.has(op.name)) };
  };
  const { options, defaults } = forKind(target.kind);

  // 初次預勾（spec 預勾統一規則：初次/按自動勾選時套用）——空格開面板自動帶入官方配套；
  // applied ref 防 StrictMode 雙跑；panel 由 key=targetKey 每次開格重掛，故「一開一次」。
  const applied = useRef(false);
  useEffect(() => {
    if (applied.current || !pack || !block || !own) return;
    const { defaults: d } = forKind(target.kind);
    if (d.length === 0) return;
    const empty = {
      o: (block.outputs?.length ?? 0) === 0,
      p: (block.indicators?.length ?? 0) === 0,
      k: (block.knowledge?.length ?? 0) === 0,
      s: (block.skills?.length ?? 0) === 0,
    }[target.kind];
    applied.current = true;
    if (!empty) return;
    const items = toItems(d);
    if (target.kind === "k") onSave(setKS(document, unitIdx, taskIdx, "knowledge", items));
    else if (target.kind === "s") onSave(setKS(document, unitIdx, taskIdx, "skills", items));
    else if (target.kind === "o") onSave(setOp(document, unitIdx, taskIdx, items, block.indicators ?? []));
    else onSave(setOp(document, unitIdx, taskIdx, block.outputs ?? [],
      items.map((i) => ({ code: i.code, text: i.name, _id: i._id, _src: i._src, _ref: i._ref }))));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pack]);

  let combobox: React.ReactNode = null;

  if (target.kind === "k") {
    combobox = (
      <FieldCombobox
        label="選知識 K"
        layout="list"
        value={block?.knowledge ?? []}
        options={options}
        defaults={defaults}
        autoApplyLabel="選同工作任務"
        autoCode="K"
        onCommit={(items) => onSave(setKS(document, unitIdx, taskIdx, "knowledge", items))}
      />
    );
  } else if (target.kind === "s") {
    combobox = (
      <FieldCombobox
        label="選技能 S"
        layout="list"
        value={block?.skills ?? []}
        options={options}
        defaults={defaults}
        autoApplyLabel="選同工作任務"
        autoCode="S"
        onCommit={(items) => onSave(setKS(document, unitIdx, taskIdx, "skills", items))}
      />
    );
  } else if (target.kind === "o") {
    combobox = (
      <FieldCombobox
        label="選產出 O"
        layout="list"
        value={block?.outputs ?? []}
        options={options}
        defaults={defaults}
        autoApplyLabel="選同工作任務"
        autoCode={`O${taskNum}.`}
        onCommit={(items) => onSave(setOp(document, unitIdx, taskIdx, items, block?.indicators ?? []))}
      />
    );
  } else {
    // target.kind === "p" — indicators are {code,text}, convert to/from {code,name}
    combobox = (
      <FieldCombobox
        label="選指標 P"
        layout="list"
        value={(block?.indicators ?? []).map((i) => ({ code: i.code, name: i.text, _id: i._id, _src: i._src, _ref: i._ref }))}
        options={options}
        defaults={defaults}
        autoApplyLabel="選同工作任務"
        autoCode={`P${taskNum}.`}
        onCommit={(items) =>
          onSave(
            setOp(
              document,
              unitIdx,
              taskIdx,
              block?.outputs ?? [],
              items.map((i) => ({ code: i.code, text: i.name, _id: i._id, _src: i._src, _ref: i._ref })),
            ),
          )
        }
      />
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <div className="h-full w-full max-w-md overflow-y-auto bg-background p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold">{title}</h3>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-5 w-5" />
          </button>
        </div>
        {isLoading ? (
          <p className="text-xs text-muted-foreground">載入候選中…</p>
        ) : (
          combobox
        )}
      </div>
    </div>
  );
}
