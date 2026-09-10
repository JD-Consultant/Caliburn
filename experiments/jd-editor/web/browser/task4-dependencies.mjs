import { readFile, writeFile, readdir } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const require = createRequire(resolve(root, "package.json"));
const lock = JSON.parse(
  await readFile(resolve(root, "package-lock.json"), "utf8"),
);
const prior = spawnSync(
  "git",
  ["show", "HEAD:experiments/jd-editor/package-lock.json"],
  { cwd: root, encoding: "utf8" },
);
if (prior.status !== 0) throw Error(prior.stderr);
const old = JSON.parse(prior.stdout),
  packages = [];
for (const [path, item] of Object.entries(lock.packages)) {
  if (
    !path.includes("node_modules") ||
    old.packages[path]?.version === item.version
  )
    continue;
  let metadata = null,
    licenses = [];
  try {
    metadata = JSON.parse(
      await readFile(resolve(root, path, "package.json"), "utf8"),
    );
    for (const file of await readdir(resolve(root, path)))
      if (/^(license|licence|copying|notice)(\.|$)/i.test(file)) {
        const data = await readFile(resolve(root, path, file));
        licenses.push({
          file: path + "/" + file,
          sha256: createHash("sha256").update(data).digest("hex"),
        });
      }
  } catch {
    /* Omitted platform/optional packages retain lock metadata below. */
  }
  packages.push({
    path,
    name: metadata?.name ?? path.split("node_modules/").at(-1),
    version: item.version,
    license: metadata?.license ?? item.license ?? null,
    resolved: item.resolved,
    integrity: item.integrity,
    installed: !!metadata,
    licenses,
  });
}
const compiled = {};
for (const name of [
  "react",
  "react-dom",
  "react-server-dom-turbopack",
  "react-server-dom-webpack",
]) {
  const p = JSON.parse(
    await readFile(
      resolve(root, "node_modules/next/dist/compiled", name, "package.json"),
      "utf8",
    ),
  );
  compiled[name] = {
    name: p.name,
    version:
      name === "react" || name === "react-dom"
        ? require("next/dist/compiled/" + name).version
        : null,
    peerDependencies: p.peerDependencies ?? null,
  };
}
await writeFile(
  resolve(root, "web/license-inventory.json"),
  JSON.stringify(
    {
      checkedOn: "2026-09-10",
      scope:
        "New or changed Task4 isolated lock entries; unchanged Task1 licenses remain in parent inventory",
      node: { execPath: process.execPath, version: process.version },
      compiled,
      packages,
    },
    null,
    2,
  ) + "\n",
);
console.log(
  JSON.stringify(
    {
      count: packages.length,
      missingLicense: packages.filter((p) => !p.license).map((p) => p.path),
      licenses: [
        ...new Set(
          packages.map((p) =>
            typeof p.license === "string"
              ? p.license
              : JSON.stringify(p.license),
          ),
        ),
      ],
      compiled,
    },
    null,
    2,
  ),
);
