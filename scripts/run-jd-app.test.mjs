import assert from "node:assert/strict";
import test from "node:test";

import { buildPnpmArgs, buildPnpmInvocation, parseApiOrigin, parseMode } from "./run-jd-app.mjs";

test("accepts only the two documented launcher modes", () => {
  assert.equal(parseMode("dev"), "dev");
  assert.equal(parseMode("start"), "start");
  assert.throws(() => parseMode("test"), /Unsupported App mode/u);
});

test("accepts one explicit IPv4 loopback API origin", () => {
  assert.equal(parseApiOrigin("http://127.0.0.1:8772\r\n"), "http://127.0.0.1:8772");
});

test("rejects ambiguous or non-loopback API locations", () => {
  assert.throws(
    () => parseApiOrigin("http://127.0.0.1:8772\nhttp://127.0.0.1:8773\n"),
    /did not return one API origin/u,
  );
  assert.throws(() => parseApiOrigin("http://localhost:8772\n"), /invalid API origin/u);
  assert.throws(() => parseApiOrigin("https://127.0.0.1:8772\n"), /invalid API origin/u);
  assert.throws(() => parseApiOrigin("http://127.0.0.1:8772/path\n"), /invalid API origin/u);
});

test("builds one fail-closed parallel pnpm workspace command", () => {
  assert.deepEqual(buildPnpmArgs("start"), [
    "--filter",
    "@caliburn/jd-relational-app",
    "--filter",
    "@caliburn/jd-relational-web",
    "--fail-if-no-match",
    "--parallel",
    "--stream",
    "run",
    "start",
  ]);
});

test("runs pnpm executables directly and JavaScript entrypoints through Node", () => {
  const expectedArgs = buildPnpmArgs("start");
  assert.deepEqual(buildPnpmInvocation("C:\\tools\\pnpm.exe", "start"), {
    command: "C:\\tools\\pnpm.exe",
    args: expectedArgs,
  });
  assert.deepEqual(buildPnpmInvocation("C:\\tools\\pnpm.cjs", "start"), {
    command: process.execPath,
    args: ["C:\\tools\\pnpm.cjs", ...expectedArgs],
  });
});
