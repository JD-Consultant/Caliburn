"use client";

import { QueryClient, defaultShouldDehydrateQuery } from "@tanstack/react-query";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import { useState } from "react";

// T12(ADR 0030):CopilotKitProvider 退場——AI 共編走訪談引擎 REST+`_pending`;
// react-query persist(knowledge)保留原結構,勿連根拔。

// 持久化版本印記:schema/契約破壞性變更時 bump → 自動失效舊快取（spec D-1d）。
// v4-3:task-catalogs/header-meta 退役（P3,ADR 0021）,舊持久化條目作廢;
// 現在唯一持久化的是 knowledge。
const PERSIST_BUSTER = "ocs-v4-3";
const MAX_AGE = 1000 * 60 * 60 * 24; // 24h；被持久化 query 的 gcTime 需 ≥ 此值。

export function Providers({ children }: { children: React.ReactNode }) {
  const [qc] = useState(() => new QueryClient());
  // storage 在 SSR（無 window）給 undefined → createSyncStoragePersister 自動 noop。
  const [persister] = useState(() =>
    createSyncStoragePersister({
      storage: typeof window !== "undefined" ? window.localStorage : undefined,
      key: "caliburn-rq-cache",
    }),
  );
  return (
    <PersistQueryClientProvider
      client={qc}
      persistOptions={{
        persister,
        maxAge: MAX_AGE,
        buster: PERSIST_BUSTER,
        // 只持久化標了 meta.persist 的 query（knowledge）；document 不存。
        dehydrateOptions: {
          shouldDehydrateQuery: (q) =>
            defaultShouldDehydrateQuery(q) && q.meta?.persist === true,
        },
      }}
    >
      {children}
    </PersistQueryClientProvider>
  );
}
