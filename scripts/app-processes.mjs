import { execFile, spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";
import { promisify } from "node:util";

const executeFile = promisify(execFile);

function isRunning(child) {
  return child.exitCode === null && child.signalCode === null;
}

function processGroupIsAlive(child) {
  if (!child.pid) return false;
  try {
    process.kill(-child.pid, 0);
    return true;
  } catch (error) {
    if (error.code === "ESRCH") return false;
    if (error.code === "EPERM") return true;
    throw error;
  }
}

async function waitForGroupsGone(children, isProcessGroupAlive, signal) {
  while (children.some(isProcessGroupAlive)) {
    try {
      await delay(25, undefined, { signal });
    } catch (error) {
      if (signal.aborted) return;
      throw error;
    }
  }
}

async function waitForOwnedClosure(closed, children, milliseconds, platform, isProcessGroupAlive) {
  if (platform === "win32") return waitWithin(closed, milliseconds);
  const controller = new AbortController();
  try {
    return await waitWithin(Promise.all([
      closed, waitForGroupsGone(children, isProcessGroupAlive, controller.signal),
    ]), milliseconds);
  } finally {
    controller.abort();
  }
}

async function stopProcessTree(child, force = false) {
  if (!child.pid) return;
  if (process.platform === "win32") {
    if (!isRunning(child)) return;
    try {
      // Windows 的 kill 只處理包裝程序；以本次取得的 PID 收回其子程序。
      await executeFile("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
        windowsHide: true,
        timeout: 5_000,
        maxBuffer: 8_192,
      });
    } catch (error) {
      if (isRunning(child)) throw error;
    }
  } else {
    try {
      // 啟動時建立獨立程序群組，只送往本次持有的群組。
      process.kill(-child.pid, force ? "SIGKILL" : "SIGTERM");
    } catch (error) {
      if (error.code !== "ESRCH") throw error;
    }
  }
}

async function waitWithin(promise, milliseconds) {
  let timer;
  try {
    return await Promise.race([
      promise.then(() => true),
      new Promise((resolve) => { timer = setTimeout(() => resolve(false), milliseconds); }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

/** 啟動失敗、子程序退出及訊號共用同一條有界收尾路徑。 */
export async function runAppProcesses(invocations, {
  cwd,
  env,
  captureStdout = false,
  start = (invocation) => spawn(invocation.command, invocation.args, {
    cwd, env, stdio: captureStdout ? ["inherit", "pipe", "inherit"] : "inherit",
    windowsHide: true,
    detached: process.platform !== "win32",
  }),
  stop = stopProcessTree,
  signals = process,
  platform = process.platform,
  isProcessGroupAlive = processGroupIsAlive,
  shutdownTimeoutMs = 90_000,
  forcedShutdownTimeoutMs = 5_000,
  warn = (message) => process.stderr.write(`${message}\n`),
} = {}) {
  if (invocations.length === 0) throw new Error("No App processes to start.");
  const children = [];
  const listeners = [];
  const closures = [];
  const output = [];
  let outputBytes = 0;
  let finish;
  const finished = new Promise((resolve) => { finish = resolve; });
  const onInterrupt = () => finish({ code: null, signal: "SIGINT" });
  const onTerminate = () => finish({ code: null, signal: "SIGTERM" });
  signals.on("SIGINT", onInterrupt);
  signals.on("SIGTERM", onTerminate);
  let result;
  let failure;
  try {
    for (const invocation of invocations) {
      const child = start(invocation, env);
      // 每次啟動立刻登記，避免下一次同步失敗遺失先前程序。
      children.push(child);
      const onError = (error) => finish({ error });
      child.on("error", onError);
      let onClose;
      closures.push(new Promise((resolve) => {
        onClose = (code, signal) => {
          finish({ code, signal });
          resolve();
        };
        child.once("close", onClose);
      }));
      listeners.push(() => {
        child.off("error", onError);
        child.off("close", onClose);
      });
      if (captureStdout) {
        // 只供短命的環境定位命令使用；同步訊息留在 stderr，stdout 有界保存。
        const onData = (chunk) => {
          outputBytes += chunk.length;
          if (outputBytes > 1024 * 1024) {
            finish({ error: new Error("Preparation output exceeded the capture limit.") });
          } else {
            output.push(chunk);
          }
        };
        child.stdout.on("data", onData);
        child.stdout.on("error", onError);
        listeners.push(() => {
          child.stdout.off("data", onData);
          child.stdout.off("error", onError);
        });
      }
    }
    result = await finished;
    if (result.error) throw result.error;
  } catch (error) {
    failure = error;
  } finally {
    try {
      const closed = Promise.all(closures);
      const errors = [];
      // A POSIX group can outlive its pnpm/Python leader; only Windows uses PID liveness.
      let graceful = children.length === 0 ||
        (platform === "win32" && children.every((child) => !isRunning(child)));
      if (!graceful && platform === "win32") {
        // 真實 Ctrl+C 已廣播至同一 console；Windows kill 並非正常關閉訊號。
        if (!failure && result?.signal === "SIGINT") {
          graceful = await waitWithin(closed, shutdownTimeoutMs);
        }
      } else if (!graceful) {
        const stopped = await Promise.allSettled(
          children.map(async (child) => stop(child, false)),
        );
        errors.push(...stopped.filter((item) => item.status === "rejected").map((item) => item.reason));
        graceful = await waitForOwnedClosure(
          closed, children, shutdownTimeoutMs, platform, isProcessGroupAlive,
        );
      }
      if (!graceful) {
        const reason = platform === "win32" && (failure || result?.signal !== "SIGINT")
          ? "A normal shutdown signal could not be delivered."
          : `The ${shutdownTimeoutMs / 1_000}-second normal shutdown deadline expired.`;
        warn(`${reason} Forcing owned App processes to stop. Saved results may remain unconfirmed; query the original execution ID before retrying.`);
        const forced = await Promise.allSettled(
          (platform === "win32" ? children.filter(isRunning) : children)
            .map(async (child) => stop(child, true)),
        );
        errors.push(...forced.filter((item) => item.status === "rejected").map((item) => item.reason));
        if (!await waitForOwnedClosure(
          closed, children, forcedShutdownTimeoutMs, platform, isProcessGroupAlive,
        )) {
          errors.push(new Error("App processes did not close before the shutdown deadline."));
        }
      }
      if (errors.length) {
        failure = new AggregateError(failure ? [failure, ...errors] : errors,
          "App process cleanup failed.");
      }
    } finally {
      signals.off("SIGINT", onInterrupt);
      signals.off("SIGTERM", onTerminate);
      for (const detach of listeners) detach();
    }
  }
  if (failure) throw failure;
  return captureStdout ? { ...result, stdout: Buffer.concat(output).toString("utf8") } : result;
}
