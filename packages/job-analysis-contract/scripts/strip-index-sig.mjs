import { readFileSync, writeFileSync } from "node:fs";

const file = "types/job-analysis-workspace.ts";
const before = readFileSync(file, "utf8");
const after = before.replace(/^\s*\[k: string\]: unknown;\r?\n/gm, "");
writeFileSync(file, after);
