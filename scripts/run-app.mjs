import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const allowedModes = new Set(["dev", "start"]);

export function parseMode(value) {
  if (!allowedModes.has(value)) {
    throw new Error(`Unsupported App mode: ${value ?? "<missing>"}`);
  }
  return value;
}

/**
 * The single backend entry: the loopback server, configured only through explicit environment.
 * Extra arguments (for example `--port 8104`) go to the backend unchanged.
 */
export function backendInvocation(root, { keyFileExists, extraArgs = [] }) {
  const keyFile = path.join(root, "apps", "api", ".env");
  return {
    command: "uv",
    args: [
      "run",
      "--project",
      "apps/api",
      "--locked",
      "python",
      "apps/api/scripts/run_backend.py",
      ...(keyFileExists ? ["--key-file", keyFile] : []),
      ...extraArgs,
    ],
  };
}

/** `start` serves the built UI from the API process; it never builds or guesses a directory. */
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

function run(invocation, env) {
  return spawn(invocation.command, invocation.args, {
    cwd: repoRoot,
    env,
    stdio: "inherit",
    windowsHide: true,
  });
}

async function main() {
  const mode = parseMode(process.argv[2]);
  const backend = backendInvocation(repoRoot, {
    keyFileExists: existsSync(path.join(repoRoot, "apps", "api", ".env")),
    extraArgs: process.argv.slice(3),
  });
  const env = { ...process.env };
  const children = [];

  if (mode === "start") {
    env.CALIBURN_WEB_BUILD_DIRECTORY = webBuildDirectory(repoRoot);
    children.push(run(backend, env));
  } else {
    const pnpmExecutable = process.env.npm_execpath;
    if (!pnpmExecutable) {
      throw new Error("Run this launcher through the repository pnpm script.");
    }
    children.push(run(backend, env), run(frontendDevInvocation(pnpmExecutable), env));
  }

  // Ctrl+C reaches every process attached to the terminal, so each child shuts itself down
  // normally. The launcher only waits, and stops the others once any child has ended.
  const result = await new Promise((resolve, reject) => {
    for (const child of children) {
      child.once("error", reject);
      child.once("close", (code, signal) => resolve({ code, signal }));
    }
  });
  for (const child of children) {
    if (child.exitCode === null && child.signalCode === null) child.kill();
  }
  process.exitCode = result.signal ? 1 : (result.code ?? 1);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  });
}
