# Task 5 Report — semantic candidate context overlays

- Status: implemented on `refactor/langgraph-consultant-runtime`; ADR0060 remained pre-existing and unstaged.
- RED: `uv run pytest -p no:cacheprovider tests/test_consultant_context.py tests/test_consultant_interview_flow.py tests/test_consultant_document_review.py -q` → `4 failed, 27 passed, 6 skipped`; failures were the absent pending/history/active sections.
- GREEN: focused context test → `4 passed, 6 skipped`; brief four-file gate → `36 passed, 6 skipped in 0.64s`.
- Changed production files: `apps/api/app/consultant/context.py`, `apps/api/app/consultant/views.py`.
- Changed test file: `apps/api/tests/test_consultant_context.py`; existing interview-flow, document-review and sufficiency suites were included in the focused regression gate.
- Pending/deferred payload has changeset/revision/action IDs, operation, path, before/after, source IDs, dependency/supersession IDs, atomic subgroup and status.
- Decision history retains rejected target/reason, stale target/reason, and edit-accepted model-after plus employee-after; approved slice remains the stored employee-approved document only.
- Example: nine approved Task statements remain in `<approved_document_slice>` while a rejected Output is only in decision history and cannot enter pending or approved content.
- Relevance/budgets: direct current-work/approved-focus matches first, same-changeset dependency closure second, then stable fill; pending/deferred max 12, history newest 8 by `(created_revision, changeset_id, action order)`, and status-specific omitted counts.
- Same-run retry exposes active candidate revision/digest and semantic actions only when request run ID matches; new runs omit it; active candidate action limit is 32.
- Token evidence: context receipt still counted the fully rendered prompt and final gate preserved its configured token budget assertions; no employee source body is copied into the receipt.
- Progress evidence: candidate staging changes no deterministic coverage/depth/decision/gap projection; publication makes review decisions pending, and accept/edit-accept remains the only approved-content edge.
- Deviation/concern: `uv run ruff check` could not run because this environment has no `ruff` executable; `git diff --check` passed before staging.
