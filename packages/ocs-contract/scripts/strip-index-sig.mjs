// Post-process json2ts output: drop the `[k: string]: unknown;` index signatures
// that the schema's `additionalProperties: true` produces. The JSON schema stays
// tolerant (additive) for the wire/Python side; the generated TS contract is
// CLOSED so TS consumers get precise types (and `Omit`/`keyof` work — an open
// index signature collapses explicit keys to `unknown`).
import { readFileSync, writeFileSync } from "node:fs";

const f = "types/ocs-document.ts";
const before = readFileSync(f, "utf8");
const after = before.replace(/^\s*\[k: string\]: unknown;\r?\n/gm, "");
writeFileSync(f, after);
console.log("stripped index signatures from", f);
