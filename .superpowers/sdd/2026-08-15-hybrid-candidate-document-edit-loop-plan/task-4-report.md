# Task 4 Report — publish verified consultant candidates

## Outcome

The final Structured Output now carries only `candidate_publication`: the neutral
triplet or a reference to one persisted candidate revision. It cannot carry a
Duty, Task, or OPKS draft. The product graph atomically validates the reference
and places the exact persisted `DocumentChangeSet` in the review queue; the
approved JD remains unchanged until an employee accept/edit-accept command.

## TDD evidence

- Baseline: the existing Task 3 candidate narrow suite was `6 passed, 28 deselected`.
- Initial hard-cut RED: `pytest -p no:cacheprovider tests/test_consultant_model_output.py tests/test_consultant_interview_flow.py tests/test_consultant_run_service.py tests/test_consultant_durable_authority_postgres.py -q` collected with `2 errors in 1.36s`: missing `OutputCandidatePublication` and `CandidatePublication`.
- Schema/run-service GREEN: `26 passed in 1.17s`; current model-output GREEN: `23 passed in 1.13s`.
- New authority RED correctly found that stale baseline hit the adapter revision guard before graph publication policy; the test now targets the graph policy directly. The source-current RED showed that a candidate-only source B could be superseded before final publication without a source gate at the adapter seam. The adapter now revalidates the persisted active candidate source IDs while holding the existing document lock.
- Current publication/neutral/Skill/source-current narrow GREEN: `4 passed, 33 deselected in 11.57s` with real `TEST_DATABASE_URL`.

## Coverage and authority

- Mapping rejects mixed neutral sentinel, bad digest, missing handles, and duplicate action IDs.
- Publication rejects unknown/old revision, digest mismatch, action subset/reorder/duplicate, another run, stale baseline, missing final Skill, and superseded candidate evidence. Every rejected publication leaves state and snapshot unchanged.
- Neutral final result clears an unreferenced candidate only after semantic commit and leaves the review queue/approved document unchanged. Existing lifecycle coverage retains candidate after whole model-run failure for same-run retry.
- Candidate publication validates exact ordered action IDs and publishes only the stored changeset; it never rematerializes a final document payload.

## Grammar and tool surface

The five Tool IDs are exactly `read_file`, `employee_source_get`,
`employee_source_lineage`, `employee_source_search`, and
`job_document_candidate_edit`; no model review-decision Tool exists. The
candidate input and final response each have zero optional parameters, unions,
and open objects after LangChain conversion. Combined observed grammar: 6
schemas, 0 defs, 129 properties, 2 optional, 0 union, 4 open objects, max depth
4, and 13,377 UTF-8 minified bytes. Total bytes are recorded evidence only,
not a provider limit.

## Review notes

`context.py` was an intentional unplanned minimal change: the prompt must direct
the model to use the candidate Tool then reference its latest receipt (or
neutral) in final output. `adapters/langgraph/postgres.py` was also required:
it rechecks persisted candidate sources at the publication authority seam under
the existing per-document lock, covering a Tool-to-final correction race.

An accidental temporary rewrite of `test_consultant_model_output.py` removed a
calibration test's `now` local. The file was restored from HEAD and only obsolete
final full-document assertions were removed; publication contract tests replaced
them. Regression proof: `1 passed, 33 deselected in 2.77s`.

## Focused gate and residue

The controller subsequently reran the requested six-file PostgreSQL gate from
committed HEAD, sequentially, with
`TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/caliburn`.
It exited 0 with **88 passed in 103.64s (0:01:43), zero skips**. This supersedes
the earlier host stdout-detachment observation.

After that gate, a direct PostgreSQL query reported zero rows in all five tables:
`consultant_documents`, `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`,
and `store`.

## Constraints audit

No Proposal legacy service, second graph/store/checkpointer, RAG, hidden router,
fallback, model accept/reject/defer Tool, or auto-accept was introduced. ADR 0060
was not edited, staged, normalized, restored, or committed.
