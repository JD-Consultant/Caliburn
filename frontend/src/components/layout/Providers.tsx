"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CopilotKitProvider } from "@copilotkit/react-core/v2";
import { useState } from "react";

// v2 provider (D22): v2 supports custom-UI/headless interrupt rendering without a
// chat component (v1 useCoAgent/useLangGraphInterrupt is chat-centric). Agent is
// referenced per-hook by agentId ("jd_authoring"); the runtime route registers it.
export function Providers({ children }: { children: React.ReactNode }) {
  const [qc] = useState(() => new QueryClient());
  return (
    <QueryClientProvider client={qc}>
      <CopilotKitProvider runtimeUrl="/api/copilotkit">{children}</CopilotKitProvider>
    </QueryClientProvider>
  );
}
