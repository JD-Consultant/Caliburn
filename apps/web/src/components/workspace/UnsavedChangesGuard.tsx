"use client";

import Link from "next/link";
import { useEffect } from "react";

const MESSAGE = "尚有未儲存的變更，確定要離開嗎？";

export function UnsavedChangesGuard({ dirty }: { dirty: boolean }) {
  useEffect(() => {
    if (!dirty) return;
    const beforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [dirty]);
  return null;
}

export function GuardedLink({
  dirty,
  ...props
}: React.ComponentProps<typeof Link> & { dirty: boolean }) {
  return (
    <Link
      {...props}
      onNavigate={(event) => {
        props.onNavigate?.(event);
        if (dirty && !window.confirm(MESSAGE)) event.preventDefault();
      }}
    />
  );
}
