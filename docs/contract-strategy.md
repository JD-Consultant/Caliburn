# Caliburn Contract Strategy（契約作法規範）

> Standing standard for **how we choose and deliver a contract** at any seam between Caliburn
> components. Authored 2026-06-28. Generalizes the decisions in ADR 0004 (contract #1) and
> ADR 0010 (contract #2), and pre-answers contract #3. This is the "作法規範" — read it before
> opening a new contract.

## 1. Why

A "seam" is any boundary where one component's output is another's input (HTTP API, a shared
document format, an event). The failure mode is **drift**: one side changes the shape, the other
keeps assuming the old one — silently (especially with `extra="ignore"`). A contract makes the
shape a **single source of truth (SSOT)** so drift is caught structurally or in CI, not in prod.

Drift happens in **both directions** — code changes without the spec, or spec changes without the
code (TotalShiftLeft 2026). Pick the lightest mechanism that closes the directions that can
actually bite *this* seam.

## 2. The decision rubric

Answer top-to-bottom; take the first row that matches.

| If the seam is… | Use | Why | Precedent |
|---|---|---|---|
| **External / partner-facing**, or has hidden/many independent consumers | **Consumer-Driven Contracts (Pact)** + schema baseline | makes hidden consumer deps visible; spec-compliance alone too weak | (none yet) |
| Internal, but has a **non-Python consumer** (web/TS, mobile, another lang) **or** the data is a **language-neutral domain artifact / real-world standard** | **JSON-Schema SSOT + codegen** (pydantic + TS), schema-diff in CI | one neutral schema → typed models in every language; survives language boundaries | **#1 `ocs-contract`** (OCS document; web/TS renders it) |
| Internal, **all-Python**, one or few in-repo consumers | **Shared typed package** (pydantic, editable path dep) | both ends import the *same classes* → drift impossible; zero codegen | **#2 `indexer-contract`** (indexer⇄api query API) |
| Internal, all-Python, but provider wants **decoupled/independent evolution** or a non-Python consumer is **imminent** | **OpenAPI-first codegen** (provider spec → generated client), regen + diff CI | provider stays authoritative; consumer regenerated; easy later language fan-out | (escalation path for #2) |

**Escalation, not rework:** these are ordered by power/cost. Start at the lowest matching row;
promote only when a new force appears (e.g. a shared-package seam gains a TS consumer → promote
its shapes to JSON-Schema). Record the promotion as a new ADR.

### The two axes that decide it
1. **Consumer language set** — any non-Python consumer ⇒ you need a language-neutral artifact
   (JSON-Schema/OpenAPI), not a Python package.
2. **External vs internal** — external/partner ⇒ consumer-driven (Pact); internal ⇒
   provider-driven schema/package is enough (Pactflow/Speakeasy/TotalShiftLeft all converge on
   this split).
Secondary: is the payload a **domain artifact** (a real standard, e.g. the OCS document) or an
**internal RPC wire format**? Domain artifacts justify a standalone schema even when current
consumers are all-Python (future-proofing + documentation value).

## 3. The mechanisms (use-when, in one line each)
- **Shared typed package** (`packages/*-contract`, pydantic, `[tool.uv.sources]` editable path
  dep): all-Python seams. Guard = both ends import the same class (assert `A is B`). No CI codegen.
- **JSON-Schema + codegen** (`schema/*.json` SSOT → datamodel-code-generator pydantic +
  json-schema-to-typescript): cross-language / domain-artifact seams. Guard =
  `scripts/check-codegen.sh` (regen + `git diff`, `--disable-timestamp`).
- **OpenAPI-first codegen** (commit provider `openapi.json` → `openapi-python-client` /
  datamodel-codegen): provider-authoritative with future language fan-out. Guard = regen + diff.
- **Pact / CDC**: external/partner APIs. Guard = consumer tests publish, provider verifies.

## 4. Delivery lifecycle (every contract follows this)
Same discipline used for Phases 1–3 and contracts #1/#2:
1. **Research record** → `docs/specs/<date>-contract-N-<name>-research.md`: diagnosis of the
   drift surface, authoritative sources, the rubric row chosen + why, design options.
2. **Decision** → an **ADR** (`docs/adr/00NN-*.md`, Chinese, Nygard-style) recording the chosen
   mechanism, the rejected ones, and the escalation trigger. Index it in `docs/adr/README.md`.
3. **Plan** → `docs/plans/<date>-contract-N-<name>.md`: bite-size, move-only where possible.
4. **Execute against a safety net** — existing test suites (and golden tests) are the
   characterization net; consolidation must be **green-before == green-after**. One commit per
   task; back-compat re-export shims are fine (definitions live only in the SSOT).
5. **Guard + tag** — wire the mechanism's CI guard (§3); tag `contractN-<name>`.

## 5. Worked precedents & the pre-answer for #3
- **#1 `ocs-contract`** (ADR 0004): the OCS document. Non-Python consumer (web/TS renders it) +
  real-world standard ⇒ **JSON-Schema + codegen**. ✔ rubric row 2.
- **#2 `indexer-contract`** (ADR 0010): indexer query API. All-Python, single consumer ⇒
  **shared pydantic package**. ✔ rubric row 3.
- **#3 api⇄web authored document (pre-answer):** the authored document **is an OCS document**,
  and the **web/TS consumer renders it** ⇒ rubric row 2 ⇒ **JSON-Schema + codegen, and reuse
  `ocs-contract`'s schema**: add the TS generation target (`json-schema-to-typescript`) for the
  web, and define the thin api⇄web REST *envelope* (request/response wrapper around the OCS
  document) as its own small schema or shared types. Do **not** hand-write TS document types in
  the web app. This pre-answer remains the legacy OCS editor/export seam. **ADR 0039 changes the
  vNext live-workspace seam:** canonical Authoring is no longer an OCS document, so the new
  Python⇄TypeScript seam uses its own small `job-workspace-contract` JSON Schema + generated
  Pydantic/TS package; `ocs-contract` remains the deterministic public/export shape. Do not make
  either contract import or redefine the other.

## 6. References
- Alistair Cockburn — Hexagonal (ports define the contract). Chris Richardson — *Microservices
  Patterns* (API-first). Percival & Gregory — *Architecture Patterns with Python*.
- FastAPI — *Generating Clients/SDKs* (OpenAPI-native). Pactflow / Pact docs — consumer-driven
  contracts. Speakeasy — *Pact vs OpenAPI*. TotalShiftLeft (2026) — *API Contract Testing* &
  *Schema-First Strategy* (internal⇒schema-first, external⇒Pact; drift is bidirectional;
  colocate spec with impl in a monorepo).
- Local: ADR 0004, ADR 0010, and the two contract research records in `docs/specs/`.
