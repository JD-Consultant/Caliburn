import { spawn, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const appRoot = path.join(repoRoot, "experiments", "jd-relational-app");
const allowedModes = new Set(["dev", "start"]);

export function parseMode(value) {
  if (!allowedModes.has(value)) {
    throw new Error(`Unsupported App mode: ${value ?? "<missing>"}`);
  }
  return value;
}

export function parseApiOrigin(output) {
  const lines = output
    .split(/\r?\n/u)
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length !== 1) {
    throw new Error("The protected App configuration did not return one API origin.");
  }

  let origin;
  try {
    const url = new URL(lines[0]);
    if (
      url.protocol !== "http:" ||
      url.hostname !== "127.0.0.1" ||
      url.port === "" ||
      url.pathname !== "/" ||
      url.search !== "" ||
      url.hash !== "" ||
      url.username !== "" ||
      url.password !== ""
    ) {
      throw new Error("not a loopback origin");
    }
    origin = url.origin;
  } catch {
    throw new Error("The protected App configuration returned an invalid API origin.");
  }

  return origin;
}

export function buildPnpmArgs(mode) {
  return [
    "--filter",
    "@caliburn/jd-relational-app",
    "--filter",
    "@caliburn/jd-relational-web",
    "--fail-if-no-match",
    "--parallel",
    "--stream",
    "run",
    parseMode(mode),
  ];
}

export function buildPnpmInvocation(pnpmExecutable, mode) {
  const pnpmArgs = buildPnpmArgs(mode);
  const extension = path.extname(pnpmExecutable).toLowerCase();
  if ([".js", ".cjs", ".mjs"].includes(extension)) {
    return { command: process.execPath, args: [pnpmExecutable, ...pnpmArgs] };
  }
  return { command: pnpmExecutable, args: pnpmArgs };
}

function readApiOrigin() {
  const result = spawnSync(
    "uv",
    ["run", "--quiet", "--frozen", "--offline", "python", "-X", "utf8", "-m", "jd_relational", "api-origin"],
    {
      cwd: appRoot,
      encoding: "utf8",
      windowsHide: true,
    },
  );

  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    if (result.stderr) process.stderr.write(result.stderr);
    throw new Error(`Unable to read the App API origin (exit ${result.status}).`);
  }
  return parseApiOrigin(result.stdout);
}

function environmentWith(values) {
  const environment = { ...process.env };
  for (const [name, value] of Object.entries(values)) {
    for (const existingName of Object.keys(environment)) {
      if (existingName.toLowerCase() === name.toLowerCase()) {
        delete environment[existingName];
      }
    }
    environment[name] = value;
  }
  return environment;
}

async function main() {
  const mode = parseMode(process.argv[2]);
  const apiOrigin = readApiOrigin();
  const pnpmExecutable = process.env.npm_execpath;

  if (!pnpmExecutable) {
    throw new Error("Run this launcher through the repository pnpm script.");
  }

  const invocation = buildPnpmInvocation(pnpmExecutable, mode);
  const child = spawn(invocation.command, invocation.args, {
    cwd: repoRoot,
    env: environmentWith({
      JD_API_ORIGIN: apiOrigin,
      NEXT_TELEMETRY_DISABLED: "1",
    }),
    stdio: "inherit",
    windowsHide: true,
  });

  const result = await new Promise((resolve, reject) => {
    child.once("error", reject);
    child.once("close", (code, signal) => resolve({ code, signal }));
  });

  if (result.signal) {
    process.exitCode = 1;
    return;
  }
  process.exitCode = result.code ?? 1;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  });
}
