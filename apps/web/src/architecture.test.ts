import * as fs from "node:fs";
import * as path from "node:path";

import { describe, expect, it } from "vitest";
import * as ts from "typescript";

// Enforces the feature-first boundaries from ADR 0058 / the current-only
// modularization plan:
//   1. `shared/**` may never import from `features/*`.
//   2. `features/<A>/**` may never import from `features/<B>/**` (sibling
//      features may only be composed at the app layer).
//   3. `app/**` may reach a feature only through that feature's `index.ts`
//      barrel (`@/features/<name>`), never a deep path that reaches past it.
//
// This is a static import-graph check using the TypeScript compiler API, not
// a type-checker: it only classifies which top-level zone (`shared`,
// `features/<name>`, `app`, or "other") each file and each of its import
// targets belongs to.

const SRC_ROOT = __dirname;
const SELF = __filename;

type Zone =
  | { kind: "shared" }
  | { kind: "features"; name: string; segments: string[] }
  | { kind: "app" }
  | { kind: "other" };

function listSourceFiles(dir: string): string[] {
  const files: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...listSourceFiles(full));
      continue;
    }
    if (/\.(ts|tsx)$/.test(entry.name) && full !== SELF) {
      files.push(full);
    }
  }
  return files;
}

function toSrcRelative(absolutePath: string): string {
  return path.relative(SRC_ROOT, absolutePath).split(path.sep).join("/");
}

function classify(srcRelativePath: string): Zone {
  const segments = srcRelativePath.split("/").filter(Boolean);
  if (segments[0] === "shared") return { kind: "shared" };
  if (segments[0] === "features") {
    return { kind: "features", name: segments[1], segments };
  }
  if (segments[0] === "app") return { kind: "app" };
  return { kind: "other" };
}

/** Resolves an import specifier to a `src`-relative path, or null if the
 * specifier points outside `src` (an npm package — bare specifiers, and
 * scoped packages like `@tanstack/...` which don't match our `@/` alias). */
function resolveSpecifier(fromFile: string, specifier: string): string | null {
  let targetAbsolute: string;
  if (specifier.startsWith("@/")) {
    targetAbsolute = path.join(SRC_ROOT, specifier.slice(2));
  } else if (specifier.startsWith(".")) {
    targetAbsolute = path.resolve(path.dirname(fromFile), specifier);
  } else {
    return null;
  }
  const rel = toSrcRelative(targetAbsolute).replace(/\.(tsx|ts)$/, "");
  return rel;
}

type ImportEdge = { fromFile: string; specifier: string };

function collectImportEdges(file: string): ImportEdge[] {
  const text = fs.readFileSync(file, "utf8");
  const sourceFile = ts.createSourceFile(
    file,
    text,
    ts.ScriptTarget.Latest,
    true,
    file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  const edges: ImportEdge[] = [];

  const visit = (node: ts.Node) => {
    if (
      (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) &&
      node.moduleSpecifier &&
      ts.isStringLiteral(node.moduleSpecifier)
    ) {
      edges.push({ fromFile: file, specifier: node.moduleSpecifier.text });
    }
    if (
      ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword &&
      node.arguments.length > 0 &&
      ts.isStringLiteral(node.arguments[0])
    ) {
      edges.push({ fromFile: file, specifier: node.arguments[0].text });
    }
    ts.forEachChild(node, visit);
  };
  visit(sourceFile);
  return edges;
}

const allFiles = listSourceFiles(SRC_ROOT);
const allEdges = allFiles.flatMap(collectImportEdges);

const sharedImportsFeature: string[] = [];
const featureImportsSiblingFeature: string[] = [];
const appDeepImportsFeature: string[] = [];

for (const edge of allEdges) {
  const fromRel = toSrcRelative(edge.fromFile);
  const fromZone = classify(fromRel);
  const targetRel = resolveSpecifier(edge.fromFile, edge.specifier);
  if (targetRel === null) continue;
  const targetZone = classify(targetRel);
  if (targetZone.kind !== "features") continue;

  if (fromZone.kind === "shared") {
    sharedImportsFeature.push(
      `${fromRel} imports "${edge.specifier}" (feature "${targetZone.name}")`,
    );
  } else if (fromZone.kind === "features") {
    if (fromZone.name !== targetZone.name) {
      featureImportsSiblingFeature.push(
        `${fromRel} (feature "${fromZone.name}") imports "${edge.specifier}" (feature "${targetZone.name}")`,
      );
    }
  } else if (fromZone.kind === "app") {
    // Only `features/<name>` (exactly two segments) is the barrel; anything
    // deeper reaches past `index.ts` into feature internals.
    if (targetZone.segments.length !== 2) {
      appDeepImportsFeature.push(
        `${fromRel} imports "${edge.specifier}" — must import "@/features/${targetZone.name}" (its index.ts), not a deep path`,
      );
    }
  }
}

describe("architecture boundaries (feature-first)", () => {
  it("found source files to scan", () => {
    // Guards against the scan silently matching zero files (e.g. if this
    // test is moved and __dirname no longer points at src/).
    expect(allFiles.length).toBeGreaterThan(20);
  });

  it("shared/** must not import from features/*", () => {
    expect(sharedImportsFeature, sharedImportsFeature.join("\n")).toEqual([]);
  });

  it("a feature must not import from a sibling feature", () => {
    expect(
      featureImportsSiblingFeature,
      featureImportsSiblingFeature.join("\n"),
    ).toEqual([]);
  });

  it("app/** may only reach a feature through its index.ts barrel", () => {
    expect(appDeepImportsFeature, appDeepImportsFeature.join("\n")).toEqual([]);
  });
});
