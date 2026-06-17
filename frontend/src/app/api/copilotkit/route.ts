// CopilotKit runtime endpoint (App Router). Proxies to the Python backend's
// /copilotkit (CopilotKitRemoteEndpoint, served by app.copilotkit_live_app).
// No LLM in the Next runtime — the agent is remote — so EmptyAdapter is used.
import {
  CopilotRuntime,
  EmptyAdapter,
  copilotKitEndpoint,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { NextRequest } from "next/server";

// Backend CopilotKit endpoint. Live app default :8001 (uvicorn app.copilotkit_live_app:app --port 8001).
const REMOTE_URL =
  process.env.COPILOTKIT_REMOTE_URL ?? "http://localhost:8001/copilotkit";

const runtime = new CopilotRuntime({
  remoteEndpoints: [copilotKitEndpoint({ url: REMOTE_URL })],
});

export const POST = async (req: NextRequest): Promise<Response> => {
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter: new EmptyAdapter(),
    endpoint: "/api/copilotkit",
  });
  return handleRequest(req);
};
