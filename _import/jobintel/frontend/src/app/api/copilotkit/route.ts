// CopilotKit runtime endpoint (App Router). Connects to the Python backend's
// AG-UI endpoint (served by ag-ui-langgraph add_langgraph_fastapi_endpoint at
// /copilotkit on app.copilotkit_live_app) via an AG-UI HttpAgent registered on
// the runtime. This replaces the legacy copilotKitEndpoint/remoteEndpoints path,
// which is incompatible with new CopilotKit JS useAgent (decision-log D22).
import {
  CopilotRuntime,
  EmptyAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { HttpAgent } from "@ag-ui/client";
import { NextRequest } from "next/server";

// Backend AG-UI run endpoint. Live app default :8001
// (.venv\Scripts\python run_live.py). Override via COPILOTKIT_REMOTE_URL.
// Use 127.0.0.1 (not localhost): Node/undici on Windows resolves localhost to
// IPv6 ::1, but uvicorn binds IPv4 127.0.0.1 → "fetch failed" before reaching it.
const REMOTE_URL =
  process.env.COPILOTKIT_REMOTE_URL ?? "http://127.0.0.1:8001/copilotkit";

const runtime = new CopilotRuntime({
  agents: {
    jd_authoring: new HttpAgent({ url: REMOTE_URL }),
  },
});

export const POST = async (req: NextRequest): Promise<Response> => {
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter: new EmptyAdapter(),
    endpoint: "/api/copilotkit",
  });
  return handleRequest(req);
};
