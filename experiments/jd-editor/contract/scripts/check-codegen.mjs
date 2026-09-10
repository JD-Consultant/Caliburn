import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { root, generate, generated } from "./codegen.mjs";
const temp = await mkdtemp(join(tmpdir(), "jd-codegen-"));
try {
  await generate(temp);
  for (const file of generated) {
    if (
      !(await readFile(join(root, file))).equals(
        await readFile(join(temp, file)),
      )
    )
      throw new Error(`Generated file differs: ${file}`);
  }
  console.log("Generated schema and DTOs match SSOT.");
} finally {
  await rm(temp, { recursive: true, force: true });
}
