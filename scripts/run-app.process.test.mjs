/** 需既有 uv／Python 依賴；只開合成 loopback 服務，不讀 App key 或資料庫。 */
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { EventEmitter } from "node:events";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";

import { backendInvocation, prepareBackendPython, runAppProcesses } from "./run-app.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

async function readReady(file) {
  const deadline = Date.now() + 10_000;
  while (Date.now() < deadline) {
    try {
      return JSON.parse(await readFile(file, "utf8"));
    } catch (error) {
      if (error.code !== "ENOENT" && !(error instanceof SyntaxError)) throw error;
    }
    await delay(20);
  }
  throw new Error("The owned synthetic service did not report readiness.");
}

function isAlive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    if (error.code !== "ESRCH") throw error;
    return false;
  }
}

async function assertStopped(pid) {
  const deadline = Date.now() + 2_000;
  while (isAlive(pid) && Date.now() < deadline) await delay(20);
  assert.equal(isAlive(pid), false, `Owned process ${pid} was left running`);
}

for (const termination of ["backend_exits", "launcher_terminates", "launcher_interrupts"]) {
  test(`the real Python and sibling processes close when ${termination}`, async () => {
    // uv 自己決定專案環境；離線執行不下載依賴，也不改成 exact sync。
    const env = { ...process.env, UV_OFFLINE: "1" };
    const pythonExecutable = await prepareBackendPython(root, { env });
    await mkdir(path.join(root, ".tmp"), { recursive: true });
    const directory = await mkdtemp(path.join(root, ".tmp", "launcher-owned-"));
    const pythonReady = path.join(directory, "python.json");
    const nodeReady = path.join(directory, "node.json");
    const probe = path.join(directory, "owned_service.py");
    await writeFile(probe, `import json, os, pathlib, socket, sys, time
with socket.socket() as server:
    server.bind(('127.0.0.1', 0))
    server.listen()
    pathlib.Path(sys.argv[1]).write_text(json.dumps({'pid': os.getpid()}))
    time.sleep(30)
`);
    const backend = backendInvocation(root, { pythonExecutable, keyFileExists: false });
    // 僅替換服務本體；保留 production 選出的 executable 與相同程序管理路徑。
    backend.args = [probe, pythonReady];
    const sibling = {
      command: process.execPath,
      args: ["-e", [
        "require('node:fs').writeFileSync(process.argv[1], JSON.stringify({pid:process.pid}));",
        "setInterval(() => {}, 1000)",
      ].join(" "), nodeReady],
    };
    const children = [];
    const signals = new EventEmitter();
    let python, node;
    const running = runAppProcesses([backend, sibling], {
      cwd: root, env, signals, shutdownTimeoutMs: 1_000,
      start: (invocation) => {
        const child = spawn(invocation.command, invocation.args, {
          cwd: root, env, stdio: "inherit", windowsHide: true,
          detached: process.platform !== "win32",
        });
        children.push(child);
        return child;
      },
    });
    // 先接住非同步 spawn 失敗；待 readiness／收尾完成後仍把錯誤交給測試。
    const settled = running.then((result) => ({ result }), (error) => ({ error }));
    try {
      await Promise.all([
        readReady(pythonReady).then((ready) => { python = ready; }),
        readReady(nodeReady).then((ready) => { node = ready; }),
      ]);
      if (termination === "backend_exits") children[0].kill("SIGKILL");
      else signals.emit(termination === "launcher_interrupts" ? "SIGINT" : "SIGTERM");
      const { error } = await settled;
      if (error) throw error;
      await Promise.all([assertStopped(python.pid), assertStopped(node.pid)]);
      assert.equal(signals.listenerCount("SIGTERM"), 0);
    } finally {
      signals.emit("SIGTERM");
      await settled;
      // 反例失敗也只清理這次握有的 PID；失敗時保留合成探針資料供查核。
      for (const owned of [python, node]) {
        if (owned && isAlive(owned.pid)) process.kill(owned.pid, "SIGKILL");
      }
    }
    await rm(directory, { recursive: true, force: true });
  });
}
