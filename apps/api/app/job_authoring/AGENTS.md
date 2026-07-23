# job_authoring — agent rules

Canonical employee/AI co-authored job document core. Greenfield module from
**[ADR 0038](../../../../docs/adr/0038-interview-vnext-context-engine-and-professional-consultant-workflow.md)**;
exact build spec is
**[2026-07-23 minimal authoring core plan](../../../../docs/plans/2026-07-23-interview-vnext-minimal-authoring-core-plan.md)**.
This file is the short rule sheet — it does **not** restate the plan. Read the
plan before changing anything here.

Current product scope is a standalone/single-user deliverable. `tenant_id`
exists only because the vNext persistence parent and composite foreign keys
already require that storage scope. Unless the owner explicitly asks for SaaS,
do not add organization/member/ACL/quota/billing/admin behavior or tests. The
next engineering budget belongs to the LLM job-analysis loop and minimal user
workspace, not platform generalization.

## Non-negotiable invariants

- **Canonical truth lives here.** Do not re-derive document truth from the old
  editor `_pending`, `DocumentVersion.content`, or `InterviewState.candidates`.
- **AI only proposes.** A model output never mutates accepted truth. Every
  document change flows through an employee `add`/`replace` command or an
  employee `accept`/`edit`/`reject` decision on a pending proposal.
- **Application owns identity.** Models supply no UUIDs; ids are UUIDv5 over the
  locked literal names in `transitions.py` (plan §6.1).
- **Every persisted claim has provenance**, and every proposed task/output has a
  non-empty Evidence basis. Consultant questions, public references, and model
  common sense are not employee Evidence.
- **Three tables only** (`job_authoring_documents/revisions/proposals`). No
  generic event/patch/ACL/framework table, no fourth table, no K/S, indicator,
  publish/export, provider call, Web, or route in this slice.

## Layering / dependencies (plan §4, §6.2, §14.9)

- Pure core — `contracts.py`, `commands.py`, `canonical.py`, `transitions.py`,
  `digest.py`, `errors.py` (+ schema writers) — imports only the standard
  library, Pydantic, and this package. Never SQLAlchemy, FastAPI, provider SDKs,
  the interview vNext domain, the OCS contract, or a Web DTO.
- `canonical.py` is an independent copy of the vNext hash rules; a parity test
  proves byte/hash equality. Do not import the interview hash helper here.
- Only the persistence adapter (`postgres*.py`, A2) may import
  `app.interview_vnext` — to read `InterviewState.v3` for the Evidence bridge —
  and it converts to authoring DTOs. The interview vNext domain never imports
  back into `job_authoring`.

## Changing things

- Contracts are the exact shapes in plan §5. The ten committed schemas are
  generated: after touching a contract, run
  `uv run --locked python -m app.job_authoring.write_schemas` and commit the
  zero-diff result. Do not hand-edit `schemas/*.json`.
- Hit a plan §18 stop condition (needing R5 schema changes, a fourth table,
  non-atomic accept/edit, LLM-summarized digest, etc.)? Stop and report with
  evidence — do not paper over it with a shim, `dict[str, Any]`, swallowed
  exception, disabled validator, or `_pending` write.
