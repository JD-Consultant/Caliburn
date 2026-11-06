/** Root commands select one backend project; uv owns env loading and execution. */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const operations = {
  dev: ["caliburn.server"],
  start: ["caliburn.server"],
  status: ["caliburn.status"],
  migrate: ["caliburn.migrate", "upgrade", "head"],
};

export function webBuildDirectory(directory) {
  const dist = path.join(directory, "apps/frontend/dist");
  if (!existsSync(path.join(dist, "index.html"))) {
    throw new Error("The web UI is not built. Run `pnpm build` first.");
  }
  return dist;
}

export function backendInvocation(directory, { mode, args = [] }) {
  if (!Object.hasOwn(operations, mode))
    throw new Error(`Unsupported operation: ${mode}`);
  const cwd = path.join(directory, "apps/backend");
  return {
    command: "uv",
    args: [
      "run",
      "--locked",
      ...(["dev", "start"].includes(mode) ? ["--extra", "local-models"] : []),
      ...(existsSync(path.join(cwd, ".env")) ? ["--env-file", ".env"] : []),
      "python",
      "-m",
      ...operations[mode],
      ...args,
    ],
    cwd,
    env:
      mode === "start"
        ? { CALIBURN_REBUILD_WEB_DIST: webBuildDirectory(directory) }
        : {},
  };
}

/** Keep this parent alive until the server has released its resources. */
export async function runInvocation(invocation) {
  const child = spawn(invocation.command, invocation.args, {
    cwd: invocation.cwd,
    env: { ...process.env, ...invocation.env },
    stdio: "inherit",
    windowsHide: true,
    // POSIX gets one forwarded signal; Windows keeps shared console delivery.
    detached: process.platform !== "win32",
  });
  // Windows delivers console Ctrl+C to the child too. Sending it again would
  // turn the server's graceful shutdown into a second, forced interruption.
  const interrupt = () => {
    if (process.platform !== "win32") child.kill("SIGINT");
  };
  const terminate = () => child.kill("SIGTERM");
  process.on("SIGINT", interrupt);
  process.on("SIGTERM", terminate);
  try {
    return await new Promise((resolve, reject) => {
      child.once("error", reject);
      child.once("close", (code, signal) =>
        resolve(code ?? (signal === "SIGINT" ? 130 : 1)),
      );
    });
  } finally {
    process.off("SIGINT", interrupt);
    process.off("SIGTERM", terminate);
  }
}

if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  try {
    const invocation = backendInvocation(root, {
      mode: process.argv[2],
      args: process.argv.slice(3),
    });
    process.exitCode = await runInvocation(invocation);
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
