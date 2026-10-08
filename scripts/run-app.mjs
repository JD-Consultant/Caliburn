import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { runAppProcesses } from "./app-processes.mjs";

export { runAppProcesses } from "./app-processes.mjs";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const allowedModes = new Set(["dev", "start"]);

export function parseMode(value) {
  if (!allowedModes.has(value)) {
    throw new Error(`Unsupported App mode: ${value ?? "<missing>"}`);
  }
  return value;
}

/**
 * 後端只有此啟動入口；額外參數原樣轉交，設定由明示環境提供。
 */
export function backendInvocation(root, { pythonExecutable, keyFileExists, extraArgs = [] }) {
  const keyFile = path.join(root, "apps", "api", ".env");
  return {
    command: pythonExecutable,
    args: [
      "apps/api/scripts/run_backend.py",
      ...(keyFileExists ? ["--key-file", keyFile] : []),
      ...extraArgs,
    ],
  };
}

/** 保留 uv run 的鎖定同步與自訂環境；服務啟動後不再依賴 uv wrapper 存活。 */
export async function prepareBackendPython(root, { env, run = runAppProcesses } = {}) {
  const result = await run([{
    command: "uv",
    args: ["run", "--project", "apps/api", "--locked", "python", "-c",
      "import json, sys; print(json.dumps(sys.executable))"],
  }], { cwd: root, env, captureStdout: true });
  if (result.code !== 0 || result.signal) {
    throw new Error("Backend environment preparation failed; no App services were started.");
  }
  let executable;
  try {
    executable = JSON.parse(result.stdout);
  } catch {
    // 不從 .venv 或 PATH 猜路徑，避免繞過 uv 選定的專案環境。
  }
  if (typeof executable !== "string" || !path.isAbsolute(executable)) {
    throw new Error("uv did not report an absolute Python executable.");
  }
  return executable;
}

/** start 由 API 提供已建置介面；不在啟動時隱含建置。 */
export function webBuildDirectory(root, exists = existsSync) {
  const directory = path.join(root, "apps", "web", "dist");
  if (!exists(path.join(directory, "index.html"))) {
    throw new Error("The web UI is not built. Run `pnpm build` first.");
  }
  return directory;
}

export function frontendDevInvocation(pnpmExecutable) {
  const args = ["--filter", "@caliburn/frontend", "--fail-if-no-match", "run", "dev"];
  const extension = path.extname(pnpmExecutable).toLowerCase();
  if ([".js", ".cjs", ".mjs"].includes(extension)) {
    return { command: process.execPath, args: [pnpmExecutable, ...args] };
  }
  return { command: pnpmExecutable, args };
}

async function main() {
  const mode = parseMode(process.argv[2]);
  const env = { ...process.env };
  let frontend;

  if (mode === "start") {
    env.CALIBURN_WEB_BUILD_DIRECTORY = webBuildDirectory(repoRoot);
  } else {
    const pnpmExecutable = process.env.npm_execpath;
    if (!pnpmExecutable) {
      throw new Error("Run this launcher through the repository pnpm script.");
    }
    frontend = frontendDevInvocation(pnpmExecutable);
  }

  const pythonExecutable = await prepareBackendPython(repoRoot, { env });
  const backend = backendInvocation(repoRoot, {
    pythonExecutable,
    keyFileExists: existsSync(path.join(repoRoot, "apps", "api", ".env")),
    extraArgs: process.argv.slice(3),
  });
  const invocations = frontend ? [backend, frontend] : [backend];
  const result = await runAppProcesses(invocations, { cwd: repoRoot, env });
  process.exitCode = result.signal ? 1 : (result.code ?? 1);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  });
}
