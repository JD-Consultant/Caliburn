"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CopilotKit } from "@copilotkit/react-core";
import { useState } from "react";

const AGENT_NAME = "jd_authoring"; // matches backend serving.AGENT_NAME

export function Providers({ children }: { children: React.ReactNode }) {
  const [qc] = useState(() => new QueryClient());
  return (
    <QueryClientProvider client={qc}>
      <CopilotKit runtimeUrl="/api/copilotkit" agent={AGENT_NAME}>
        {children}
      </CopilotKit>
    </QueryClientProvider>
  );
}
