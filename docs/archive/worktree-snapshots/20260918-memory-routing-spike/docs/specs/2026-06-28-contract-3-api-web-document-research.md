# Contract #3 Research Record — api ⇄ web Authored Document

> Research record (per `docs/contract-strategy.md`). Authored 2026-06-28. Third of the three
> planned contracts. The contract-strategy standard **pre-answered the mechanism**; this record
> confirms it against the real code and scopes the work.

## 1. Goal

Kill the drift between the **web's hand-written TypeScript OCS-document type** and the
authoritative `ocs-contract` schema, by making the web consume **generated** TS from that schema.
Decide whether to also formalize the **api⇄web REST envelopes**.

## 2. Current state (the drift surface)

- `packages/ocs-contract` is the OCS-document SSOT: `schema/ocs-document.schema.json` →
  `datamodel-codegen` → `src/ocs_contract/models.py` (Python), guarded by
  `scripts/check-codegen.sh`. It is **also an npm package** (`@caliburn/ocs-contract`) — but its
  only codegen target is Python. **No TypeScript is generated, and the web imports nothing from
  it.**
- `apps/web/src/types/index.ts` **hand-writes the entire OCS document**: `OcsDocument`,
  `OcsProfile`, `OcsName`, `OcsCategory`, `OcuUnit`, `OcsTask`, `CompetencyBlock`, `CodeName`,
  `Indicator` — a hand mirror of the schema, **plus** front-end-only fields layered onto the
  leaves/nodes (`_id`, `_src`, `_ref`, `_uid`, `_tid`, `_notes`, `_levelSrc`). `lib/ocsDoc.ts`,
  `JobDocTable.tsx`, `CellFillerPanel.tsx`, etc. consume these.
- The same file also hand-writes the **api⇄web REST envelopes**: `DocumentEnvelope`,
  `JobProfile`, `HeaderMeta`(+candidates), `TaskCandidates`, `PickedTask`, `OcsSearchHit`, and
  the AI-proposal results (`RecommendKsResult`, `DraftOpResult`, `ExtractTasksResult`,
  `StructureTaskResult`, `ClarifyResult`). `lib/api.ts` is the fetch client.

**Drift risk:** the OCS document is the **of-record** the consultant authors; its shape is
defined by `ocs-document.schema.json` and produced by `pdf-to-json` + assembled by the api. The
web re-declares that shape by hand → any schema change (a new section, a renamed field) silently
diverges in the UI. This is exactly the cross-language drift the contract-strategy rubric's row 2
targets. The current hand type already drifts loosely (e.g. web `version_info: { versions:
unknown[] }` vs the schema's `VersionInfo`/`VersionEntry`).

## 3. Rubric application (per `docs/contract-strategy.md`)

- **The OCS document** = a domain artifact / real-world standard **with a non-Python (TS)
  consumer** ⇒ **rubric row 2: JSON-Schema SSOT + codegen**. The schema already exists; add the
  **TS generation target** (`json-schema-to-typescript`) to `@caliburn/ocs-contract` and have the
  web import the generated types. UI-only fields (`_id`, `_uid`, …) are **not** part of the
  contract; the web layers them via **extension types** over the generated base (contract stays
  pure; UI augmentation stays web-local). ✔ This is the high-value core of contract #3.
- **The api⇄web REST envelopes** = api-authored shapes with a TS consumer ⇒ rubric row 4
  (**OpenAPI-first codegen**, `openapi-typescript` from the api's `openapi.json`). **But** many
  api routes (`documents.py`, `ai/*`) currently return **raw dicts**, not pydantic
  `response_model`s, so the api's OpenAPI is **incomplete** — codegen would emit `unknown`/`any`
  for those. Closing this requires first adding response models across the api (a separate,
  larger refactor). The envelopes are also thin, simple, api-owned, and low-churn. → **Defer**
  Part B to a follow-up; do it via OpenAPI-first **after** the api has complete response models.

## 4. Decision (recommended scope)

**Part A now — generate web OCS-document TS from `ocs-contract`:**
1. Add a `json-schema-to-typescript` codegen target to `@caliburn/ocs-contract` →
   emit `src/ocs_contract.ts` (or `dist/`) of pure contract types; extend `check-codegen` to
   guard it (regen + `git diff`).
2. Web imports the generated `OcsDocument` (+ nested) from `@caliburn/ocs-contract` (workspace
   dep) and **deletes the hand-written mirror** in `src/types/index.ts`, replacing it with
   **UI-extension types** (`Ui*` = generated base `& { _id?, _uid?, ... }`) used by the editing
   components.
3. Keep the REST-envelope + AI-result types hand-written **for now** (Part B), but re-point their
   document-shaped fields (e.g. `DocumentEnvelope.content`) at the generated `OcsDocument`.

**Part B later (separate contract/ADR) — REST envelopes via OpenAPI-first:** add pydantic
`response_model`s across `api` routes, export `openapi.json`, generate the web's API client/types
with `openapi-typescript`, retire the hand envelopes. Out of scope here.

## 5. Safety net & method
- **Net (web has no test framework):** `tsc --noEmit` (type-check) + `eslint` are the gate;
  final confirmation is a **manual browser smoke** of the document workbench. Swapping the
  hand type for the generated base **will surface type mismatches** in components — fixing those
  is the bulk of the work and the proof the contract is now honored.
- **Method:** (1) add TS codegen to ocs-contract + commit generated output + guard; (2) wire web
  workspace dep + replace the document types with generated base + `Ui*` extensions, fixing
  `tsc` errors component-by-component; (3) `tsc` + `eslint` green; (4) **browser smoke (hands-on
  with the user)**; (5) ADR 0011 + tag `contract3-doc-types`.
- **Execution caveat:** unlike the Python phases, the web has no automated behaviour net →
  execution should pause for a joint browser check before tagging (like the 4b cutover).

## 6. Out of scope
Part B (REST-envelope OpenAPI codegen + api response_models); behaviour/UX changes; the AI/
header-meta endpoints' own shapes (hand-typed until Part B).
