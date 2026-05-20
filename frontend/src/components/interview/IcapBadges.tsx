"use client";

import { Badge } from "@/components/ui/badge";
import type { IcapCandidate } from "@/types";
import { cn } from "@/lib/utils";

interface Props {
  candidates: IcapCandidate[];
}

const COLOR: Record<IcapCandidate["recommendation"], string> = {
  建議參考: "bg-emerald-100 text-emerald-800 border-emerald-200",
  部分參考: "bg-yellow-100 text-yellow-800 border-yellow-200",
  低信心: "bg-gray-100 text-gray-600 border-gray-200",
};

export function IcapBadges({ candidates }: Props) {
  if (!candidates.length) return null;

  return (
    <div className="px-4 py-2 border-b bg-muted/30">
      <p className="text-xs text-muted-foreground mb-2">iCAP 對應職能基準</p>
      <div className="flex flex-wrap gap-2">
        {candidates.map((c) => (
          <span
            key={c.icap_id}
            className={cn(
              "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium",
              COLOR[c.recommendation]
            )}
          >
            <span className="font-semibold">{Math.round(c.similarity * 100)}%</span>
            {c.icap_title}
            <span className="opacity-70">· {c.recommendation}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
