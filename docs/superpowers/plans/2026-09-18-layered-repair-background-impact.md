# Layered Repair Background Impact Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure the next admitted B1→B2 background job cannot lose the dependency impact of successful layered C repairs, even when B1 returns `no_op`.

**Architecture:** Reuse the existing publication receipts as the durable change log and immutable bundle manifests as old/new dependency graphs. `BackgroundMemoryWorkflow` derives repair impact at its fixed base, unions it with B1-derived minimum requirements, and passes the union through the existing B2 required-ID completion gate; a successful consolidation receipt becomes the next implicit reconciliation boundary.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0.52, LangGraph 1.2.11, pytest, existing `caliburn_memory` bundle/publication/B1/B2 workflows.

**Spec:** `docs/specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md` §6.1 and `docs/specs/2026-09-17-layered-memory-background-workflow-design.md` §2.4.

## Global Constraints

- Do not add an Agent, model call, table, migration, queue, scheduler, registry, `held`/coverage manifest, persisted reconciliation watermark, or user-facing feature.
- Do not change C admission, notification/dispatcher behavior, `processed_source`, compaction, Prompt/Skills, provider, credential, JD behavior, or production authority.
- A repair publication remains independently complete and consistent; this seam cannot justify partial C publication.
- Runtime owns revisions, receipt selection, manifest diff, IDs, digests and attempt identity; the model only receives the existing required-ID projections.
- Old and new bindings both participate in impact derivation; B1 `no_op` cannot erase repair impact.
- Tests use real `MemoryArtifacts`, `PublicationStore`, B1/B2 sessions and workflows with fixed offline models; zero provider requests.

---

### Task 1: Publication reconciliation boundary

**Files:**
- Modify: `packages/consultant-memory/src/caliburn_memory/publication.py`
- Test: `packages/consultant-memory/tests/test_publication.py`

**Interfaces:**
- Produces: `PublicationStore.latest_consolidation_revision(*, through_revision: int) -> int`
- Preserves: existing `repair_receipts(after_revision, through_revision, limit)` ordering and bounds.

- [x] **Step 1: Write the failing boundary test**

```python
def test_latest_consolidation_revision_is_the_implicit_repair_checkpoint(publications):
    pub, artifacts = publications
    source = artifacts.source.reference
    first = pub.publish(pub.prepare(
        request(pub, artifacts).memory,
        expected_revision=0,
        kind="consolidation",
        processed_source=source,
    ))
    repair = pub.publish(request(
        pub, artifacts, revision=first.revision,
        text="更正", repair_sources=(source,),
    ))
    assert pub.latest_consolidation_revision(through_revision=repair.revision) == first.revision
```

- [x] **Step 2: Run the test and verify RED**

Run from `experiments/jd-relational-app`:

```powershell
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'
uv run --offline --frozen --no-sync pytest -c pyproject.toml ../../packages/consultant-memory/tests/test_publication.py::test_latest_consolidation_revision_is_the_implicit_repair_checkpoint -q -p no:cacheprovider
```

Expected: FAIL because `latest_consolidation_revision` does not exist.

- [x] **Step 3: Implement the bounded receipt query**

```python
def latest_consolidation_revision(self, *, through_revision: int) -> int:
    if type(through_revision) is not int or through_revision < 0:
        raise ValueError("Invalid consolidation receipt bound")
    with self.sessions() as session:
        value = session.scalar(select(func.max(ReceiptRow.result_revision)).where(
            ReceiptRow.document_id == self.document_id,
            ReceiptRow.kind == "consolidation",
            ReceiptRow.result_revision <= through_revision,
        ))
        return int(value or 0)
```

- [x] **Step 4: Verify GREEN and validation**

Add literal assertions for no consolidation, later consolidation and invalid negative/type bounds; rerun all of `test_publication.py`.

### Task 2: Allow Runtime-supplied repair impact through the existing B2 gate

**Files:**
- Modify: `packages/consultant-memory/src/caliburn_memory/understanding_maintenance.py`
- Modify: `packages/consultant-memory/src/caliburn_memory/understanding_workflow.py`
- Test: `packages/consultant-memory/tests/test_understanding_maintenance.py`
- Test: `packages/consultant-memory/tests/test_understanding_workflow.py`

**Interfaces:**
- Produces: `UnderstandingMaintenanceSession.open(case_stage, *, additional_required_case_ids=(), additional_required_understanding_ids=())`
- Produces: matching optional keyword arguments on `UnderstandingMaintenanceWorkflow.run_attempt(...)`.
- Preserves: serialized stage format and existing `required_case_ids` / `required_understanding_ids` model projection.

- [x] **Step 1: Write failing session tests**

Use a completed B1 no-op stage over an existing case and understanding. Assert that Runtime additions appear in the required tuples, invalid/non-current IDs fail closed, and the original B1-derived requirements can never be removed.

```python
stage = session.open(
    completed_no_op_case_stage,
    additional_required_case_ids=(case_id,),
    additional_required_understanding_ids=(understanding_id,),
)
assert stage.required_case_ids == (case_id,)
assert stage.required_understanding_ids == (understanding_id,)
```

- [x] **Step 2: Verify RED**

Run the new session tests and confirm failure is the missing keyword contract, not fixture setup.

- [x] **Step 3: Implement additive validation**

Change `open()` to union its Runtime additions with `_impact(case_stage)`. Change `_validate()` so the stored required sets must contain all B1-derived IDs and every extra case/understanding must be a current ID in the fixed candidate/base. Do not add repair fields to the stage schema.

- [x] **Step 4: Lock attempt identity**

Pass additions through `run_attempt()`. When a checkpoint already exists, compare its fixed required tuples with the newly opened expected tuples in addition to the existing case-stage identity check; reject mismatches rather than resume a different repair impact.

- [x] **Step 5: Verify GREEN**

Run both B2 test files and retain the existing tampered-B1-impact rejection test.

### Task 3: Derive old/new repair impact and feed B2

**Files:**
- Modify: `packages/consultant-memory/src/caliburn_memory/background_workflow.py`
- Test: `packages/consultant-memory/tests/test_background_workflow.py`

**Interfaces:**
- Consumes: `latest_consolidation_revision`, ordered `repair_receipts`, receipt result bundle lineage, and Task 2 optional B2 requirements.
- Produces: a private deterministic `(case_ids, understanding_ids)` impact for the workflow's fixed base.

- [x] **Step 1: Write the failing A/B/C regression**

Build a real layered base with CASE-A/B/C supporting UNDERSTANDING-U. Publish a repair that revises C and revalidates U with only A/B. Run the next source job with B1 fixed-model `no_op`; assert B2's first task requires C and U, reads them, revalidates U against A/B, and publishes one complete bundle.

Mutation caught: deriving impact only from current bindings or only from B1 changes makes the test fail because C/U disappear from the required projection.

- [x] **Step 2: Verify RED**

Run only the new workflow test. Expected: B2 receives empty required sets and cannot complete the scripted C/U revalidation path.

- [x] **Step 3: Implement deterministic receipt/manifest diff**

At the workflow's fixed `base_publication_revision`, page all repair receipts after the latest consolidation result revision. For each receipt:

```python
changed_cases = {
    case_id for case_id in old_case_ids | new_case_ids
    if old_case_digest.get(case_id) != new_case_digest.get(case_id)
}
affected_understandings = {
    binding.understanding_id
    for binding in (*old_manifest.understanding_case_bindings,
                    *new_manifest.understanding_case_bindings)
    if binding.case_id in changed_cases
}
affected_understandings |= {
    understanding_id
    for understanding_id in old_understanding_ids | new_understanding_ids
    if old_understanding_digest.get(understanding_id)
       != new_understanding_digest.get(understanding_id)
       or old_bindings.get(understanding_id) != new_bindings.get(understanding_id)
}
```

Verify every receipt result manifest names the receipt's exact base revision/version. Fail closed on non-layered or inconsistent lineage; do not reinterpret legacy two-file Memory.

- [x] **Step 4: Pass the union into B2**

Call `understanding_workflow.run_attempt()` with the repair-derived additions. Keep B1 stage unchanged; do not synthesize fake B1 changes or alter its outcome.

- [x] **Step 5: Verify GREEN and recovery behavior**

Run `test_background_workflow.py`; add assertions that a successful consolidation advances the implicit boundary, while a stale retry recomputes against the new fixed head instead of reusing old impact.

### Task 4: Responsibility docs, full verification and one precise commit

**Files:**
- Modify: `packages/consultant-memory/README.md`
- Modify: `docs/current-decisions.md`
- Modify: `docs/specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md`
- Modify: `docs/specs/2026-09-17-layered-memory-background-workflow-design.md`

**Interfaces:**
- Documents the implemented package behavior and remaining layered C/App boundary without changing production authority.

- [x] **Step 1: Update status without duplicating architecture**

Record actual commits/tests only after they run. Keep the design detail in the two specs; README and current decisions carry status and routing only.

- [x] **Step 2: Run package verification**

```powershell
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'
uv run --offline --frozen --no-sync pytest -c pyproject.toml ../../packages/consultant-memory/tests -q -p no:cacheprovider
python -m compileall -q ../../packages/consultant-memory/src ../../packages/consultant-memory/tests
```

- [x] **Step 3: Run adjacent App verification**

```powershell
uv run --offline --frozen --no-sync pytest -c pyproject.toml tests/test_background_memory_app.py tests/test_layered_background_dispatch.py tests/test_background_agent_compaction.py -q -p no:cacheprovider
```

- [x] **Step 4: Review scope and diff**

Run `git diff --check`, verify no schema/migration/provider/Prompt/dispatcher changes, and inspect every changed file against the two specs.

- [x] **Step 5: Commit the verified slice**

```powershell
git add packages/consultant-memory/src packages/consultant-memory/tests packages/consultant-memory/README.md docs/current-decisions.md docs/specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md docs/specs/2026-09-17-layered-memory-background-workflow-design.md docs/superpowers/plans/2026-09-18-layered-repair-background-impact.md
git commit -m "feat(memory): preserve repair impact for background analysis"
```

Do not push, merge, tag, invoke a provider, or claim layered C/App completion in this slice.
