import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import path from "node:path";
import { PassThrough } from "node:stream";
import test from "node:test";

import * as launcher from "./run-app.mjs";
import {
  backendInvocation,
  frontendDevInvocation,
  parseMode,
  runAppProcesses,
  webBuildDirectory,
} from "./run-app.mjs";

test("accepts only the two documented launcher modes", () => {
  assert.equal(parseMode("dev"), "dev");
  assert.equal(parseMode("start"), "start");
  assert.throws(() => parseMode("test"), /Unsupported App mode/u);
  assert.throws(() => parseMode(undefined), /<missing>/u);
});

function childProcess() {
  const child = new EventEmitter();
  child.exitCode = null;
  child.signalCode = null;
  child.kill = () => {
    child.signalCode = "SIGTERM";
    queueMicrotask(() => child.emit("close", null, "SIGTERM"));
  };
  return child;
}

test("stops an already started server when the next spawn throws", async () => {
  const first = childProcess();
  let calls = 0;
  await assert.rejects(runAppProcesses([{}, {}], {
    stop: (child) => child.kill(),
    start: () => {
      if (calls++ === 0) return first;
      throw new Error("spawn rejected");
    },
  }), /spawn rejected/u);
  assert.equal(first.signalCode, "SIGTERM");
});

test("stops the sibling server when spawn emits an asynchronous error", async () => {
  const first = childProcess();
  const second = childProcess();
  const children = [first, second];
  const running = runAppProcesses([{}, {}], {
    start: () => children.shift(), stop: (child) => child.kill(),
  });
  queueMicrotask(() => {
    second.emit("error", new Error("ENOENT"));
    second.emit("close", -1, null);
  });
  await assert.rejects(running, /ENOENT/u);
  assert.equal(first.signalCode, "SIGTERM");
});

test("waits for sibling closure and detaches its signal listeners", async () => {
  const first = childProcess();
  const second = childProcess();
  const children = [first, second];
  const signals = new EventEmitter();
  let siblingClosed = false;
  const running = runAppProcesses([{}, {}], {
    signals, start: () => children.shift(),
    stop: async (child) => {
      if (child === second) {
        await new Promise((resolve) => setImmediate(resolve));
        siblingClosed = true;
        child.kill();
      }
    },
  });
  first.exitCode = 7;
  first.emit("close", 7, null);
  assert.deepEqual(await running, { code: 7, signal: null });
  assert.equal(siblingClosed, true);
  assert.equal(signals.listenerCount("SIGINT"), 0);
  assert.equal(signals.listenerCount("SIGTERM"), 0);
});

test("terminating the launcher stops every owned child", async () => {
  const children = [childProcess(), childProcess()];
  let index = 0;
  const signals = new EventEmitter();
  const running = runAppProcesses([{}, {}], {
    signals, start: () => children[index++], stop: (child) => child.kill(),
  });
  signals.emit("SIGTERM");
  assert.deepEqual(await running, { code: null, signal: "SIGTERM" });
  assert.ok(children.every((child) => child.signalCode === "SIGTERM"));
});

test("forces an unresponsive child after the graceful deadline", async () => {
  const child = childProcess();
  const signals = new EventEmitter();
  const attempts = [];
  const running = runAppProcesses([{}], {
    signals, shutdownTimeoutMs: 5, start: () => child,
    stop: (owned, force = false) => {
      attempts.push(force);
      if (force) owned.kill();
    },
  });
  signals.emit("SIGTERM");
  await running;
  assert.deepEqual(attempts, [false, true]);
});

test("cleanup failure does not skip other children or hide the spawn error", async () => {
  const first = childProcess();
  const second = childProcess();
  const children = [first, second];
  const running = runAppProcesses([{}, {}, {}], {
    shutdownTimeoutMs: 5,
    start: () => {
      if (children.length) return children.shift();
      throw new Error("third spawn failed");
    },
    stop: (child) => {
      child.kill();
      if (child === first) throw new Error("stop failed");
    },
  });
  await assert.rejects(running, (error) => {
    assert.ok(error instanceof AggregateError);
    assert.deepEqual(error.errors.map((item) => item.message), ["third spawn failed", "stop failed"]);
    return true;
  });
  assert.equal(second.signalCode, "SIGTERM");
});

test("starts the backend through the resolved interpreter and preserves the optional key file", () => {
  const root = path.join("C:", "repo");
  const pythonExecutable = path.join(root, "custom-venv", "python.exe");
  const without = backendInvocation(root, { pythonExecutable, keyFileExists: false });
  assert.equal(without.command, pythonExecutable);
  assert.deepEqual(without.args, [
    "apps/api/scripts/run_backend.py",
  ]);
  const withKey = backendInvocation(root, { pythonExecutable, keyFileExists: true });
  assert.deepEqual(withKey.args.slice(-2), ["--key-file", path.join(root, "apps", "api", ".env")]);
});

test("prepares the interpreter through the existing locked uv run environment", async () => {
  const root = path.resolve("repo");
  const pythonExecutable = path.join(root, "custom environment", "python.exe");
  const env = { UV_PROJECT_ENVIRONMENT: path.dirname(pythonExecutable) };
  const resolved = await launcher.prepareBackendPython(root, {
    env,
    run: async (invocations, options) => {
      assert.deepEqual(invocations, [{
        command: "uv",
        args: ["run", "--project", "apps/api", "--locked", "python", "-c",
          "import json, sys; print(json.dumps(sys.executable))"],
      }]);
      assert.equal(options.cwd, root);
      assert.equal(options.env, env);
      assert.equal(options.captureStdout, true);
      return { code: 0, signal: null, stdout: JSON.stringify(pythonExecutable) + "\r\n" };
    },
  });
  assert.equal(resolved, pythonExecutable);
});

test("does not prepare a backend after failed or interrupted dependency synchronization", async () => {
  for (const result of [{ code: 2, signal: null }, { code: null, signal: "SIGTERM" }]) {
    await assert.rejects(launcher.prepareBackendPython(path.resolve("repo"), {
      run: async () => ({ ...result, stdout: JSON.stringify(process.execPath) }),
    }), /Backend environment preparation failed/u);
  }
});

test("rejects missing or non-absolute interpreter output without guessing a path", async () => {
  for (const stdout of ["", "not-json", '"python"', '""', "null"]) {
    await assert.rejects(launcher.prepareBackendPython(path.resolve("repo"), {
      run: async () => ({ code: 0, signal: null, stdout }),
    }), /did not report an absolute Python executable/u);
  }
});

test("captures finite command output and keeps the normal closure cleanup", async () => {
  const child = childProcess();
  child.stdout = new PassThrough();
  const signals = new EventEmitter();
  const running = runAppProcesses([{}], {
    signals, captureStdout: true, start: () => child, stop: () => {},
  });
  child.stdout.write(Buffer.from('"C:/合成/python.exe"\n'));
  child.exitCode = 0;
  child.emit("close", 0, null);
  assert.deepEqual(await running, { code: 0, signal: null, stdout: '"C:/合成/python.exe"\n' });
  assert.equal(signals.listenerCount("SIGTERM"), 0);
  assert.equal(child.stdout.listenerCount("data"), 0);
});

test("rejects excessive preparation output and still stops its owned process", async () => {
  const child = childProcess();
  child.stdout = new PassThrough();
  const running = runAppProcesses([{}], {
    captureStdout: true, start: () => child, stop: (owned) => owned.kill(),
  });
  child.stdout.write(Buffer.alloc(1024 * 1024 + 1));
  queueMicrotask(() => {
    child.exitCode = 0;
    child.emit("close", 0, null);
  });
  await assert.rejects(running, /Preparation output exceeded/u);
  assert.equal(child.signalCode, "SIGTERM");
  assert.equal(child.stdout.listenerCount("data"), 0);
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
