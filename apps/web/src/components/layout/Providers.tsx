"use client";

import { QueryClient, defaultShouldDehydrateQuery } from "@tanstack/react-query";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import { CopilotKitProvider } from "@copilotkit/react-core/v2";
import { useState } from "react";

// v2 provider (D22): v2 supports custom-UI/headless interrupt rendering without a
// chat component (v1 useCoAgent/useLangGraphInterrupt is chat-centric). Agent is
// referenced per-hook by agentId ("jd_authoring"); the runtime route registers it.

// 持久化版本印記:schema/契約破壞性變更時 bump → 自動失效舊快取（spec D-1d）。
const PERSIST_BUSTER = "ocs-v4-1";
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
        // 只持久化標了 meta.persist 的 query（task-catalogs/header-meta）；document 不存。
        dehydrateOptions: {
          shouldDehydrateQuery: (q) =>
            defaultShouldDehydrateQuery(q) && q.meta?.persist === true,
        },
      }}
    >
      <CopilotKitProvider runtimeUrl="/api/copilotkit">{children}</CopilotKitProvider>
    </PersistQueryClientProvider>
  );
}
