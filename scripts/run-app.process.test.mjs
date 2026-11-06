import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";
import { runInvocation } from "./run-app.mjs";

test("a backend failure reaches the root command exit status", async () => {
  assert.equal(
    await runInvocation({
      command: process.execPath,
      args: ["-e", "process.exit(7)"],
    }),
    7,
  );
});

test(
  "termination waits for backend cleanup before the root command exits",
  {
    skip:
      process.platform === "win32"
        ? "Windows console Ctrl+C is covered by the recorded real PTY probe."
        : false,
    timeout: 10000,
  },
  async (t) => {
    const directory = await mkdtemp(
      path.join(os.tmpdir(), "caliburn-shutdown-"),
    );
    const childFile = path.join(directory, "child.mjs");
    const parentFile = path.join(directory, "parent.mjs");
    const marker = path.join(directory, "finished.txt");
    const pidFile = path.join(directory, "child.pid");
    await writeFile(
      childFile,
      `import { writeFileSync } from 'node:fs';
process.on('SIGTERM',()=>setTimeout(()=>{writeFileSync(process.argv[2],'released');process.exit(0)},100));
writeFileSync(process.argv[3],String(process.pid));console.log('READY');setInterval(()=>{},1000);`,
    );
    const module = pathToFileURL(path.resolve("scripts/run-app.mjs")).href;
    await writeFile(
      parentFile,
      `import {runInvocation} from ${JSON.stringify(module)};
process.exitCode = await runInvocation({command:process.execPath,args:process.argv.slice(2)});`,
    );
    const parent = spawn(
      process.execPath,
      [parentFile, childFile, marker, pidFile],
      { stdio: ["ignore", "pipe", "pipe"] },
    );
    const closed = once(parent, "close");
    t.after(async () => {
      try {
        parent.kill("SIGKILL");
        try {
          await readFile(marker);
        } catch (error) {
          if (error.code !== "ENOENT") throw error;
          // A failed signal-forwarding assertion must not leave the detached
          // synthetic backend alive. Its own ready record identifies this PID.
          try {
            const childPid = Number(await readFile(pidFile, "utf8"));
            if (Number.isInteger(childPid) && childPid > 0)
              process.kill(childPid, "SIGKILL");
          } catch (cleanupError) {
            if (!["ENOENT", "ESRCH"].includes(cleanupError.code))
              throw cleanupError;
          }
        }
      } finally {
        await rm(directory, { recursive: true, force: true });
      }
    });
    await new Promise((resolve, reject) => {
      parent.stdout.on("data", (data) => {
        if (data.toString().includes("READY")) resolve();
      });
      parent.once("error", reject);
    });
    parent.kill("SIGTERM");
    assert.equal((await closed)[0], 0);
    assert.equal(await readFile(marker, "utf8"), "released");
  },
);
