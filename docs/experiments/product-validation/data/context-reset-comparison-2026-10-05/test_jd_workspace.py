"""Research adapter checks against real PostgreSQL, without model dispatch."""

import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest
from baseline_store import read_baseline, read_reference_baselines, seed_baseline
from caliburn.adapters.database import Database
from caliburn.features.executions import history
from caliburn.features.executions.history_models import (
    AgentRole,
    ContextPosition,
    HistoryWindowKind,
    context_thread_id,
)
from caliburn.features.executions.models import ExecutionStatus
from caliburn.features.interviews import persistence as interviews
from caliburn.features.job_description import queries, source_persistence, work_queries
from caliburn.features.job_description.source_targets import source_target_contents
from caliburn.features.job_description.sources import MemorySource
from caliburn.features.job_files.models import CreateJobFile
from caliburn.transport.model_tools.memory_reads import MemoryReadTools
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from caliburn.workflows.jd_evidence import JdEvidenceWorkflow
from caliburn.workflows.job_files import JobFileWorkflow
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from caliburn.workflows.memory_reads import MemoryReadWorkflow
from jd_workspace import begin_turn
from memory_fixture import read_memory_fixture, seed_memory

pytest_plugins = ("tests.integration.conftest",)
pytestmark = pytest.mark.postgres
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def test_all_existing_citations_can_open_their_review_diff(database_settings):
    async def exercise():
        database = Database(database_settings)
        try:
            file_id = await seed_baseline(database)
            baseline = read_baseline()
            captured = read_reference_baselines(baseline)
            evidence = JdEvidenceWorkflow(database.sessions)
            anchors = {a.profile.revision_id: a for a in captured.anchors}
            current = source_target_contents(baseline.profile.profile, baseline.work)
            for reference in captured.references:
                difference = await evidence.read_changes(
                    file_id, baseline.profile.revision_id, reference.citation_id
                )
                assert difference.reference == reference
                anchor = anchors[reference.reviewed_revision_id]
                expected = source_target_contents(anchor.profile.profile, anchor.work)
                assert difference.before == expected[reference.target]
                assert difference.after == current[reference.target]
                assert difference.source_changes is None
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(exercise())


@pytest.mark.parametrize("arm", ["raw", "summary", "memory"])
def test_fixed_baseline_keeps_full_jd_interviews_and_references(database_settings, arm):
    async def exercise():
        database = Database(database_settings)
        try:
            file_id = await seed_baseline(database)
            async with database.sessions() as session:
                profile = await queries.read_profile(session, file_id)
                work = await work_queries.read_work(session, file_id)
                messages = await interviews.list_formal_interviews(session, file_id)
                references = await source_persistence.read_source_references(
                    session, file_id, profile.revision_id
                )
            assert len(work.tasks) == 13
            assert len(messages) == 105
            assert len(references) == 207
            assert sum(reference.needs_review for reference in references) == 39
            assert references == read_reference_baselines(read_baseline()).references
            assert arm in {"raw", "summary", "memory"}
            assert [m.interview_sequence for m in messages] == list(range(1, 106))
            baseline = json.loads((HERE / "baseline.json").read_text(encoding="utf-8"))
            original = json.loads(
                (ROOT / baseline["source_files"][0]["path"]).read_text(encoding="utf-8")
            )
            from pydantic import TypeAdapter

            assert (
                TypeAdapter(type(profile)).dump_python(profile, mode="json") == original["profile"]
            )
            assert TypeAdapter(type(work)).dump_python(work, mode="json") == original["work"]
            assert [TypeAdapter(type(m)).dump_python(m, mode="json") for m in messages] == [
                entry["message"] for entry in original["interviews"]
            ]
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(exercise())


def test_memory_body_and_jd_source_use_the_same_pinned_snapshot(database_settings):
    async def exercise():
        database = Database(database_settings)
        try:
            file_id = await seed_baseline(database)
            snapshot_id = await seed_memory(database, file_id)
            turn = await begin_turn(database, file_id, "請核對既有工作。", snapshot_id=snapshot_id)
            memory = MemoryReadTools(MemoryReadWorkflow(database.sessions), turn.binding)
            mapping = json.loads(await memory.invoke("read_work_understanding_map", "{}"))
            assert len(mapping["items"]) == 1
            title = mapping["items"][0]["target_title"]
            body = json.loads(
                await memory.invoke("read_work_understanding", json.dumps({"target_title": title}))
            )
            assert len(body["work_situation_references"]) == 12
            frozen = read_memory_fixture()
            objects = {item.content.title: item for item in frozen.objects}
            assert body["body"] == objects[title].content.body
            sequences = {
                entry.message.source_id: entry.message.interview_sequence
                for entry in read_baseline().interviews
            }
            for reference in body["work_situation_references"]:
                situation = json.loads(
                    await memory.invoke(
                        "read_work_situation",
                        json.dumps({"target_title": reference["target_title"]}),
                    )
                )
                original = objects[reference["target_title"]]
                assert situation["body"] == original.content.body
                assert set(situation["interview_references"]) == {
                    sequences[source_id] for source_id in original.interview_references
                }
            prepared = await turn.writes.prepare(
                "revise_jd_profile",
                json.dumps(
                    {
                        "changes": [
                            {
                                "action": "add_source",
                                "field": "purpose",
                                "source": {"kind": "work_understanding", "target_title": title},
                            }
                        ]
                    }
                ),
                uuid4(),
            )
            assert not isinstance(prepared, str), prepared
            assert await turn.writes.execute(prepared) == "updated"
            preview = await JdCandidateWorkflow(database.sessions).read(turn.writer.scope)
            async with database.sessions() as session:
                references = await source_persistence.read_source_references(
                    session, file_id, preview.position.revision_id
                )
            added = [r for r in references if isinstance(r.source, MemorySource)]
            assert len(added) == 1 and added[0].source.snapshot_id == snapshot_id
            fixed = await MemoryCandidateWorkflow(database.sessions).read_snapshot_object(
                file_id, snapshot_id, added[0].source.object_id
            )
            assert fixed.content.body == body["body"]
            assert fixed.revision_id == added[0].source.revision_id
            with pytest.raises(ValueError, match="already installed"):
                await seed_memory(database, file_id)
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(exercise())


@pytest.mark.parametrize("status", [ExecutionStatus.CANCELLED, ExecutionStatus.FAILED])
def test_stopping_discards_edits_and_foreign_locators_cannot_cross_files(database_settings, status):
    async def exercise():
        database = Database(database_settings)
        try:
            file_id = await seed_baseline(database)
            baseline = read_baseline()
            turn = await begin_turn(database, file_id, "這是應撤回的合成測試。")
            mapping = json.loads(
                await turn.reads.invoke("read_jd", '{"view":"map","read_ref":null}')
            )
            ref = mapping["responsibility_areas"][0]["work_tasks"][0]["read_ref"]
            other = await JobFileWorkflow(database.sessions).create(
                CreateJobFile(uuid4(), "另一隔離檔案", "合成員工")
            )
            control = await begin_turn(database, other.job_file.job_file_id, "另一份輸入。")
            args = json.dumps(
                {
                    "read_ref": ref,
                    "changes": [
                        {
                            "action": "set_field",
                            "field": "description",
                            "value": "不得寫入另一份檔案",
                        }
                    ],
                }
            )
            rejected = await control.writes.prepare("revise_jd_item", args, uuid4())
            assert isinstance(rejected, str) and json.loads(rejected)["code"] == "target_not_found"
            prepared = await turn.writes.prepare("revise_jd_item", args, uuid4())
            assert not isinstance(prepared, str), prepared
            assert await turn.writes.execute(prepared) == "updated"
            await ConsultantCompletionWorkflow(database.sessions).stop(turn.writer, status)
            async with database.sessions() as session:
                assert await work_queries.read_work(session, file_id) == baseline.work
                assert len(await interviews.list_formal_interviews(session, file_id)) == 105
                assert not (await work_queries.read_work(session, other.job_file.job_file_id)).tasks
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(exercise())


def test_real_tool_edit_is_atomic_readable_and_formalized_with_its_source(database_settings):
    async def exercise():
        database = Database(database_settings)
        try:
            file_id = await seed_baseline(database)
            original = read_baseline()
            turn = await begin_turn(database, file_id, "合成測試：原工作不變，新增週二核對。")
            candidates = JdCandidateWorkflow(database.sessions)
            before = await candidates.read(turn.writer.scope)
            mapping = json.loads(
                await turn.reads.invoke("read_jd", '{"view":"map","read_ref":null}')
            )
            task = mapping["responsibility_areas"][0]["work_tasks"][0]
            ref = task["read_ref"]
            assert len(ref) < 24
            initial = json.loads(
                await turn.reads.invoke("read_jd", json.dumps({"view": "item", "read_ref": ref}))
            )
            replacement = initial["description"] + "另於週二核對。"
            changes = [
                {"action": "set_field", "field": "description", "value": replacement},
                {
                    "action": "add_source",
                    "target": {"kind": "item"},
                    "source": {"kind": "interview", "interview_sequence": 106},
                },
            ]
            assert turn.writes is not None, (
                "Research tools must execute actual JD edits, not just proposals"
            )
            rejected = await turn.writes.prepare(
                "revise_jd_item", json.dumps({"read_ref": ref, "changes": changes}), uuid4()
            )
            assert isinstance(rejected, str)
            assert json.loads(rejected)["code"] == "scope_not_allowed"
            assert (await candidates.read(turn.writer.scope)).position == before.position
            changes[1]["source"] = {"kind": "current_input"}
            prepared = await turn.writes.prepare(
                "revise_jd_item", json.dumps({"read_ref": ref, "changes": changes}), uuid4()
            )
            assert not isinstance(prepared, str), prepared
            assert await turn.writes.execute(prepared) == "updated"
            after = await candidates.read(turn.writer.scope)
            assert await turn.writes.execute(prepared) == "updated"
            assert (await candidates.read(turn.writer.scope)).position == after.position
            readback = json.loads(
                await turn.reads.invoke("read_jd", json.dumps({"view": "item", "read_ref": ref}))
            )
            assert readback["description"] == replacement
            assert any(s["kind"] == "current_input" for s in readback["supporting_sources"])
            async with database.sessions() as session:
                assert await work_queries.read_work(session, file_id) == original.work

            # Transactional test positions, as in production's completion suite.
            # No native saver/provider claim: the live runner must save real positions.
            role = AgentRole.JOB_CONSULTANT
            prepared_position = ContextPosition(
                context_thread_id(turn.writer.scope, role, HistoryWindowKind.PREPARED_HISTORY),
                "offline-prepared",
                HistoryWindowKind.PREPARED_HISTORY,
            )
            completed_position = ContextPosition(
                context_thread_id(turn.writer.scope, role, HistoryWindowKind.COMPLETED_WORK),
                "offline-completed",
                HistoryWindowKind.COMPLETED_WORK,
            )
            async with database.sessions.begin() as session:
                await history.adopt_prepared_context(session, turn.writer, role, prepared_position)
            exchange = await ConsultantCompletionWorkflow(database.sessions).complete(
                turn.writer, after.position, "合成測試：已更新。", completed_position
            )
            assert exchange.employee_input.interview_sequence == 106
            async with database.sessions() as session:
                formal = await work_queries.read_work(session, file_id)
                references = await source_persistence.read_source_references(
                    session, file_id, formal.revision_id
                )
            assert formal.tasks[0].description == replacement
            assert any(r.source.source_id == exchange.employee_input.source_id for r in references)
            assert len(references) == 208
            with pytest.raises(ValueError, match="empty namespace"):
                await seed_baseline(database)
            await database.close()
            database = Database(database_settings)
            async with database.sessions() as session:
                assert await work_queries.read_work(session, file_id) == formal
                old = await work_queries.read_work_at(
                    session, file_id, original.profile.revision_id
                )
                assert old == original.work
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(exercise())
