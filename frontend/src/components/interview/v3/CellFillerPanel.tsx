"use client";

// D13 CellFiller：per-cell FieldCombobox (official O/P/K/S from useTaskCatalog + custom).
// Each cell commits immediately via onSave(nextDoc); no Save button.
import type { OcsDocument } from "@/types";
import { getBlock, setKS, setOp } from "@/lib/ocsDoc";
import { useTaskCatalog } from "@/hooks/useTaskCatalog";
import { FieldCombobox } from "./fields/FieldCombobox";
import type { CellTarget } from "./JobDocTable";
import { X } from "lucide-react";

function taskName(doc: OcsDocument, unitIdx: number, taskIdx: number): string {
  const tc = doc.ocs_content?.ocu_units?.[unitIdx]?.tasks?.[taskIdx]?.task_codes?.[0];
  return tc?.name || "任務";
}

function taskKey(doc: OcsDocument, unitIdx: number, taskIdx: number): string {
  return doc.ocs_content?.ocu_units?.[unitIdx]?.tasks?.[taskIdx]?.task_codes?.[0]?.code ?? "";
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
  const tk = taskKey(document, unitIdx, taskIdx);
  const cat = useTaskCatalog(profileId, tk, true);
  const block = getBlock(document, unitIdx, taskIdx);
  const tn = taskName(document, unitIdx, taskIdx);
  const title = `${tn}：${TITLES[target.kind]}`;

  let combobox: React.ReactNode = null;

  if (target.kind === "k") {
    combobox = (
      <FieldCombobox
        label="選知識 K"
        value={block?.knowledge ?? []}
        options={cat.knowledge}
        customMode="footer"
        autoCode="K"
        onCommit={(items) => onSave(setKS(document, unitIdx, taskIdx, "knowledge", items))}
      />
    );
  } else if (target.kind === "s") {
    combobox = (
      <FieldCombobox
        label="選技能 S"
        value={block?.skills ?? []}
        options={cat.skills}
        customMode="footer"
        autoCode="S"
        onCommit={(items) => onSave(setKS(document, unitIdx, taskIdx, "skills", items))}
      />
    );
  } else if (target.kind === "o") {
    combobox = (
      <FieldCombobox
        label="選產出 O"
        value={block?.outputs ?? []}
        options={cat.outputs}
        customMode="footer"
        autoCode="O"
        onCommit={(items) => onSave(setOp(document, unitIdx, taskIdx, items, block?.indicators ?? []))}
      />
    );
  } else {
    // target.kind === "p" — indicators are {code,text}, convert to/from {code,name}
    combobox = (
      <FieldCombobox
        label="選指標 P"
        value={(block?.indicators ?? []).map((i) => ({ code: i.code, name: i.text }))}
        options={cat.indicators.map((i) => ({ code: i.code, name: i.text }))}
        customMode="footer"
        autoCode="P"
        onCommit={(items) =>
          onSave(
            setOp(
              document,
              unitIdx,
              taskIdx,
              block?.outputs ?? [],
              items.map((i) => ({ code: i.code, text: i.name })),
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
        {cat.isLoading ? (
          <p className="text-xs text-muted-foreground">載入候選中…</p>
        ) : (
          combobox
        )}
      </div>
    </div>
  );
}
