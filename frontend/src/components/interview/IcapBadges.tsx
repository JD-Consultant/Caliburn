"use client";

import type { IcapCandidate } from "@/types";
import { cn } from "@/lib/utils";
import { icapCandidateTone, icapConfidenceLabel, icapRecommendationLabel } from "@/lib/icap";

interface Props {
  candidates: IcapCandidate[];
}

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
              icapCandidateTone(c)
            )}
          >
            <span className="font-semibold">{icapConfidenceLabel(c)}</span>
            {c.icap_title}
            <span className="opacity-70">· {icapRecommendationLabel(c)}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
