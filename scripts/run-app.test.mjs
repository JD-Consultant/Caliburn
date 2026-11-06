import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { backendInvocation, webBuildDirectory } from "./run-app.mjs";

function checkout(t) {
  const root = mkdtempSync(path.join(os.tmpdir(), "caliburn-delivery-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  mkdirSync(path.join(root, "apps", "backend"), { recursive: true });
  return root;
}

test("backend launch selects the locked app project and its explicit env file", (t) => {
  const root = checkout(t);
  writeFileSync(path.join(root, "apps/backend/.env"), "SYNTHETIC=example\n");
  const invocation = backendInvocation(root, { mode: "dev" });
  assert.equal(invocation.command, "uv");
  assert.equal(invocation.cwd, path.join(root, "apps/backend"));
  assert.deepEqual(invocation.args, [
    "run",
    "--locked",
    "--extra",
    "local-models",
    "--env-file",
    ".env",
    "python",
    "-m",
    "caliburn.server",
  ]);
});

test("status works without a dotenv file and never selects a server or migration", (t) => {
  const invocation = backendInvocation(checkout(t), { mode: "status" });
  assert.deepEqual(invocation.args, [
    "run",
    "--locked",
    "python",
    "-m",
    "caliburn.status",
  ]);
});

test("migration is explicit and invalid operations fail before starting a process", (t) => {
  const root = checkout(t);
  assert.deepEqual(backendInvocation(root, { mode: "migrate" }).args, [
    "run",
    "--locked",
    "python",
    "-m",
    "caliburn.migrate",
    "upgrade",
    "head",
  ]);
  assert.throws(
    () => backendInvocation(root, { mode: "erase" }),
    /Unsupported/u,
  );
});

test("production refuses a missing build and selects the app frontend build", (t) => {
  const root = checkout(t);
  assert.throws(() => webBuildDirectory(root), /pnpm build/u);
  const dist = path.join(root, "apps/frontend/dist");
  mkdirSync(dist, { recursive: true });
  writeFileSync(path.join(dist, "index.html"), "<!doctype html>");
  assert.equal(webBuildDirectory(root), dist);
  assert.equal(
    backendInvocation(root, { mode: "start" }).env.CALIBURN_REBUILD_WEB_DIST,
    dist,
  );
});
test("explicit checkpoint setup reaches the migration CLI", (t) => {
  assert.deepEqual(
    backendInvocation(checkout(t), {
      mode: "migrate",
      args: ["--with-checkpoints"],
    }).args,
    [
      "run",
      "--locked",
      "python",
      "-m",
      "caliburn.migrate",
      "upgrade",
      "head",
      "--with-checkpoints",
    ],
  );
});
