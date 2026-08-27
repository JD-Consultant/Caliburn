"use client";

import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";

export function CurrentDocumentSection({
  id,
  ariaLabel,
  eyebrow,
  title,
  summary,
  actions,
  children,
  defaultOpen = true,
}: {
  id?: string;
  ariaLabel: string;
  eyebrow: string;
  title: string;
  summary?: string;
  actions?: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section
      id={id}
      aria-label={ariaLabel}
      className="rounded-2xl border border-stone-200 bg-white shadow-sm"
    >
      <details
        open={open}
        onToggle={(event) => setOpen(event.currentTarget.open)}
      >
        <summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-3 marker:content-none">
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-semibold tracking-[0.14em] text-stone-400 uppercase">
              {eyebrow}
            </p>
            <h3 className="truncate text-sm font-semibold text-stone-950">
              {title}
            </h3>
            {summary ? (
              <p className="mt-0.5 truncate text-xs text-stone-500">
                {summary}
              </p>
            ) : null}
          </div>
          {actions ? (
            <div onClick={(event) => event.preventDefault()}>{actions}</div>
          ) : null}
          <ChevronDown className="size-4 shrink-0 text-stone-400" />
        </summary>
        <div className="border-t border-stone-100 px-4 py-4">{children}</div>
      </details>
    </section>
  );
}
