import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";

import {
  backendInvocation,
  frontendDevInvocation,
  parseMode,
  webBuildDirectory,
} from "./run-app.mjs";

test("accepts only the two documented launcher modes", () => {
  assert.equal(parseMode("dev"), "dev");
  assert.equal(parseMode("start"), "start");
  assert.throws(() => parseMode("test"), /Unsupported App mode/u);
  assert.throws(() => parseMode(undefined), /<missing>/u);
});

test("starts the locked backend through uv and passes the key file only when it exists", () => {
  const root = path.join("C:", "repo");
  const without = backendInvocation(root, { keyFileExists: false });
  assert.equal(without.command, "uv");
  assert.deepEqual(without.args, [
    "run",
    "--project",
    "apps/api",
    "--locked",
    "python",
    "apps/api/scripts/run_backend.py",
  ]);
  const withKey = backendInvocation(root, { keyFileExists: true });
  assert.deepEqual(withKey.args.slice(-2), ["--key-file", path.join(root, "apps", "api", ".env")]);
});

test("forwards extra arguments, such as a port, to the backend after the key file", () => {
  const root = path.join("C:", "repo");
  const invocation = backendInvocation(root, { keyFileExists: true, extraArgs: ["--port", "8104"] });
  assert.deepEqual(invocation.args.slice(-4), [
    "--key-file",
    path.join(root, "apps", "api", ".env"),
    "--port",
    "8104",
  ]);
});

test("serving the built UI fails closed when nothing has been built", () => {
  const root = path.join("C:", "repo");
  assert.throws(() => webBuildDirectory(root, () => false), /Run `pnpm build` first/u);
  assert.equal(
    webBuildDirectory(root, (file) => file.endsWith("index.html")),
    path.join(root, "apps", "web", "dist"),
  );
});

test("runs the frontend dev server by pnpm executable or through Node for scripts", () => {
  const args = ["--filter", "@caliburn/frontend", "--fail-if-no-match", "run", "dev"];
  assert.deepEqual(frontendDevInvocation("C:\\tools\\pnpm.exe"), {
    command: "C:\\tools\\pnpm.exe",
    args,
  });
  assert.deepEqual(frontendDevInvocation("C:\\tools\\pnpm.mjs"), {
    command: process.execPath,
    args: ["C:\\tools\\pnpm.mjs", ...args],
  });
});
