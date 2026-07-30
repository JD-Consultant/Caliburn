import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const packageRoot = fileURLToPath(new URL("..", import.meta.url));
const npmCli = process.env.npm_execpath;
if (!npmCli) throw new Error("npm_execpath is unavailable outside an npm lifecycle");
const generated = [
  "src/job_analysis_contract/models.py",
  "types/job-analysis-workspace.ts",
];

const codegen = spawnSync(process.execPath, [npmCli, "run", "--silent", "codegen"], {
  cwd: packageRoot,
  stdio: "inherit",
});
if (codegen.error) throw codegen.error;
if (codegen.status !== 0) process.exit(codegen.status ?? 1);

const diff = spawnSync("git", ["diff", "--exit-code", "--", ...generated], {
  cwd: packageRoot,
  stdio: "inherit",
});
if (diff.error) throw diff.error;
process.exit(diff.status ?? 1);
