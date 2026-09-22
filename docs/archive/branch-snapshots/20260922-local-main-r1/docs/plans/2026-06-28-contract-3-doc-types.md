# Contract #3 (Part A) — Web OCS-Document TS from `ocs-contract` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use
> checkbox (`- [ ]`) syntax. Follows `docs/contract-strategy.md` (rubric row 2: JSON-Schema +
> codegen for a domain artifact with a TS consumer). Scope = **Part A only** (Part B REST
> envelopes deferred — see research record).

**Goal:** The web stops hand-writing the OCS document type and instead imports **generated**
TypeScript from `@caliburn/ocs-contract` (same `ocs-document.schema.json` that already generates
the Python models), so the document shape can't drift across the api⇄web boundary.

**Architecture:** Add a `json-schema-to-typescript` target to `@caliburn/ocs-contract` emitting a
pure-type `.ts`; the web imports it **type-only** (erased at build, no transpile needed) and
layers UI-only fields via `Ui*` extension types. Research record:
`docs/specs/2026-06-28-contract-3-api-web-document-research.md`.

**Tech Stack:** json-schema-to-typescript, TypeScript, Next 16 (npm workspaces + Turborepo).

## Global Constraints

- **SSOT = `packages/ocs-contract/schema/ocs-document.schema.json`** (unchanged). Both Python
  models and the new TS types are generated from it; never hand-edit generated output.
- **Web has no test framework.** Safety net = `npx tsc --noEmit` + `npm run lint` (eslint) +
  a **manual browser smoke** of the document workbench. The browser smoke is **hands-on with the
  user** and gates the tag (like the 4b cutover).
- **Contract types stay pure** (no `_`-prefixed UI fields); UI augmentation lives only in the web
  as `Ui*` extension types.
- Commit per task. Web app dir `/s/caliburn/apps/web`; contract pkg `/s/caliburn/packages/ocs-contract`; commit from `/s/caliburn`.

---

## Task 1: TS codegen target in `@caliburn/ocs-contract`

**Files:**
- Modify: `packages/ocs-contract/package.json` (devDep + scripts + `exports`/`types`)
- Create: `packages/ocs-contract/dist/ocs-document.ts` (generated; committed)
- Modify: `packages/ocs-contract/scripts/check-codegen.sh` (also guard the TS)

**Interfaces:**
- Produces: package export of generated interfaces — `OCSDocument` (and nested `OcsProfile`,
  `OcuUnit`, `TaskGroup`/task, `CompetencyBlock`, `CodeName`, `CodeText`, `Category`, `OcsName`,
  `VersionInfo`, …) importable as `import type { OCSDocument } from "@caliburn/ocs-contract"`.

- [ ] **Step 1: add the tool + scripts** to `packages/ocs-contract/package.json`:

```json
{
  "name": "@caliburn/ocs-contract",
  "private": true,
  "types": "./dist/ocs-document.ts",
  "exports": { ".": { "types": "./dist/ocs-document.ts" } },
  "scripts": {
    "codegen": "npm run codegen:py && npm run codegen:ts",
    "codegen:py": "uv run datamodel-codegen --input schema/ocs-document.schema.json --input-file-type jsonschema --output src/ocs_contract/models.py --output-model-type pydantic_v2.BaseModel --use-standard-collections --use-union-operator --use-schema-description --target-python-version 3.11 --disable-timestamp",
    "codegen:ts": "json2ts --input schema/ocs-document.schema.json --output dist/ocs-document.ts --additionalProperties false --no-style.semi false",
    "check-codegen": "bash scripts/check-codegen.sh",
    "build": "echo \"no build\""
  },
  "devDependencies": { "json-schema-to-typescript": "^15.0.0" }
}
```
  (Keep the existing `codegen` Python command available as `codegen:py`; `codegen` now does both.)

- [ ] **Step 2: install + generate.** `cd /s/caliburn/packages/ocs-contract && npm install && npm run codegen:ts`. Inspect `dist/ocs-document.ts` — it must contain the top-level document interface and the nested types. Note the exact exported name json2ts produces (driven by the schema `title`/`$id`); if it is not `OCSDocument`, record the real name for Task 2.

- [ ] **Step 3: type-check the generated file in isolation.** `npx tsc --noEmit --strict dist/ocs-document.ts` → no errors.

- [ ] **Step 4: extend the guard.** In `scripts/check-codegen.sh`, after the Python diff block,
  regen TS and diff it too:

```bash
npm run codegen:ts
if ! git diff --quiet -- dist/ocs-document.ts; then
  echo "ERROR: dist/ocs-document.ts is out of sync with the schema. Run 'npm run codegen:ts' and commit."
  git --no-pager diff --stat -- dist/ocs-document.ts
  git checkout -- dist/ocs-document.ts
  exit 1
fi
echo "OK: generated TS in sync with schema."
```

- [ ] **Step 5: run the guard** to confirm in-sync: `npm run check-codegen` → OK for both.

- [ ] **Step 6: Commit.**

```bash
cd /s/caliburn && git add packages/ocs-contract && git commit -m "feat(ocs-contract): generate TypeScript types from the schema (Contract #3 Part A T1)

Add json-schema-to-typescript target → dist/ocs-document.ts; package exports it
for the web. check-codegen now guards both Python and TS generation."
```

---

## Task 2: web imports the generated types + UI extensions

**Files:**
- Modify: `apps/web/package.json` (add `"@caliburn/ocs-contract": "*"` workspace dep)
- Modify: `apps/web/src/types/index.ts` (delete hand OCS mirror; re-export generated + add `Ui*`)
- Modify: consumers as `tsc` flags them: `src/lib/ocsDoc.ts`, `src/lib/headerMeta.ts`,
  `src/components/interview/v3/*` (JobDocTable, CellFillerPanel, DocHeader, AiTaskPanel,
  TaskCuratePanel, …), `src/hooks/useDocument.ts`

**Interfaces:**
- Consumes: `@caliburn/ocs-contract` generated types. Web-local `Ui*` types = generated base `&`
  the front-end fields (`_id?`, `_src?`, `_ref?`, `_uid?`, `_tid?`, `_notes?`, `_levelSrc?`).

- [ ] **Step 1: add the workspace dep** to `apps/web/package.json` dependencies:
  `"@caliburn/ocs-contract": "*"`, then `cd /s/caliburn && npm install` (root, hoists workspace).

- [ ] **Step 2: replace the hand OCS types** in `apps/web/src/types/index.ts`. Remove the
  block from `ItemSource`/`SourceRef`/`CodeName`/`Indicator`/`CompetencyBlock`/`OcsTask`/
  `OcuUnit`/`OcsName`/`OcsCategory`/`OcsProfile`/`OcsDocument` and replace with imports + UI
  extensions (use the real generated names from Task 1 Step 2; shown assuming `OCSDocument` etc.):

```ts
import type {
  OCSDocument, OcsProfile, OcuUnit, CompetencyBlock, CodeName, CodeText,
} from "@caliburn/ocs-contract";

export type { OCSDocument, OcsProfile, OcuUnit, CompetencyBlock, CodeName, CodeText };

// Front-end-only augmentation (NOT part of the contract; stripped on finalize/export).
export type ItemSource = "official" | "custom";
export interface SourceRef { ocs_code: string; occupation_name: string; code: string; task_code?: string; task_name?: string; }
export type UiCodeName  = CodeName  & { _id?: string; _src?: ItemSource; _ref?: SourceRef };
export type UiIndicator = CodeText  & { _id?: string; _src?: ItemSource; _ref?: SourceRef };
export type UiBlock = Omit<CompetencyBlock, "indicators" | "outputs" | "knowledge" | "skills"> & {
  indicators: UiIndicator[]; outputs: UiCodeName[]; knowledge: UiCodeName[]; skills: UiCodeName[];
};
export type UiTask = { task_codes: UiCodeName[]; competency_blocks: UiBlock[];
  provenance?: { ocs_code: string; task_code: string; urn?: string };
  _tid?: string; _notes?: string; _levelSrc?: SourceRef & { level: number }; };
export type UiUnit = Omit<OcuUnit, "tasks"> & { tasks: UiTask[]; _uid?: string };
export type UiDocument = Omit<OCSDocument, "ocs_content"> & { ocs_content: { ocu_units: UiUnit[] } };
```
  Keep `DocumentEnvelope` but retype `content: UiDocument` (the editable in-memory doc). Keep the
  REST-envelope + AI-result interfaces unchanged (Part B).

- [ ] **Step 3: fix `tsc` errors iteratively.** `cd /s/caliburn/apps/web && npx tsc --noEmit`;
  resolve each error by switching component/local types from the old names to the `Ui*` variants
  (the editing surface uses `Ui*`; anything that finalizes/exports already strips `_` fields).
  Repeat until clean. Do **not** weaken types with `any` — if the generated contract reveals a
  real mismatch (e.g. nullable not handled), fix the call site.

- [ ] **Step 4: lint.** `npm run lint` → clean (fix unused imports left by the type swap).

- [ ] **Step 5: Commit** (code green; browser not yet verified).

```bash
cd /s/caliburn && git add -A && git commit -m "refactor(web): consume generated OCS types from @caliburn/ocs-contract (Contract #3 Part A T2)

Delete the hand-written OCS document mirror; import generated contract types and
layer UI-only fields via Ui* extensions. tsc + eslint green; browser smoke pending."
```

---

## Task 3: browser smoke (JOINT) + ADR + tag

**Files:** Create `docs/adr/0011-web-ocs-types-generated.md`; modify `docs/adr/README.md`.

- [ ] **Step 1: browser smoke (with the user).** Start the stack (`turbo dev` or web on :3000 +
  api on :8001) and verify the document workbench still renders/edits/saves: open a profile's
  document, edit O/P/K/S cells, header pickers, finalize/export — no console type/runtime errors,
  output JSON still contract-valid. Fix any runtime fallout, re-run `tsc`/`lint`.

- [ ] **Step 2: Write ADR 0011** (Chinese, Nygard-style): context (web hand-mirrored the OCS
  document → drift vs `ocs-contract`); decision (rubric row 2 — generate TS from the schema, web
  imports it type-only, UI fields via `Ui*` extensions; Part B envelopes deferred to OpenAPI-first
  after api response_models); consequences (document shape single-sourced across languages;
  `check-codegen` guards TS too; web augmentation isolated); status Accepted 2026-06-28; link the
  research record + `contract-strategy.md`. Add the index row to `docs/adr/README.md`.

- [ ] **Step 3: Commit + tag.**

```bash
cd /s/caliburn
git add docs/adr/0011-web-ocs-types-generated.md docs/adr/README.md
git commit -m "docs(adr): 0011 web OCS types generated from ocs-contract (Contract #3 Part A)"
git tag -a contract3-doc-types -m "Contract #3 Part A: web consumes generated OCS TS from ocs-contract (schema SSOT). tsc+eslint green + browser smoke."
```

---

## Self-Review notes
- **Spec coverage:** research §4 Part A ↔ Tasks 1–3; Part B explicitly out of scope.
- **Naming risk:** the generated top-level interface name depends on the schema `title`/`$id`
  (Task 1 Step 2 records the real name; Task 2 must use it — the example assumes `OCSDocument`).
- **Type erasure:** the web import is `import type` → no runtime dep / no `transpilePackages`
  needed; build stays unchanged.
- **Net:** `tsc --noEmit` + `eslint` are the automated gate (web has no test framework); the
  browser smoke (Task 3 Step 1) is mandatory before the tag and is done with the user.
