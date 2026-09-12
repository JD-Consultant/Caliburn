"""Offline immutable intent checks; no admission, ref issuer or database evidence."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import traceback
from uuid import UUID, uuid4

import pytest

from jd_relational.domain import CommandContext, Ref, Source
from jd_relational.intents import BoundEdit, IntentValidationError, bind_edit
from jd_relational.selection import Selection


BASE = UUID("10000000-0000-4000-8000-000000000001")
OPERATION = UUID("20000000-0000-4000-8000-000000000001")


@pytest.fixture
def context():
    refs = {
        "field": Ref("doc", str(BASE), "task", "task-a", field="description"),
        "task": Ref("doc", str(BASE), "task", "task-a"),
        "other": Ref("doc", str(BASE), "task", "task-b"),
        "tasks": Ref("doc", str(BASE), "container", child_kind="task"),
        "duties": Ref("doc", str(BASE), "container", child_kind="duty"),
        "duty": Ref("doc", str(BASE), "duty", "duty-a"),
        "detail": Ref("doc", str(BASE), "detail", "detail-a"),
        "capability": Ref("doc", str(BASE), "capability", "capability-a"),
        "condition": Ref("doc", str(BASE), "condition", "condition-a"),
        "conditions": Ref("doc", str(BASE), "container", child_kind="qualification"),
    }
    return CommandContext("doc", str(BASE), refs,
        {"qa-original": Source("doc"), "qa-other": Source("doc")},
        lambda: "generated-only-by-domain",
        {"selection": Selection("field", "甲😀甲", 3, 4, "甲")})


def command(tool="jd_set_text", **arguments):
    if not arguments:
        arguments = {"target_field_ref": "field", "text": "保留完整工作內容", "basis_refs": ["qa-original"]}
    return {"tool": tool, "arguments": arguments}


def bind(context, value=None, **overrides):
    kwargs = dict(operation_id=OPERATION, origin="manual", ai_run_id=None,
                  command=value or command(), context=context)
    kwargs.update(overrides)
    return bind_edit(**kwargs)


def test_bound_edit_has_stable_public_api_and_independent_command_and_context(context):
    value = command()
    bound = bind(context, value)
    assert isinstance(bound, BoundEdit)
    assert (bound.document_id, bound.operation_id, bound.base_revision_id, bound.origin, bound.ai_run_id) == (
        "doc", OPERATION, BASE, "manual", None)
    assert len(bound.request_digest) == 64
    before = bound.command
    value["arguments"]["text"] = "caller changed"
    value["arguments"]["basis_refs"].clear()
    context.refs.clear()
    context.sources.clear()
    context.selections.clear()
    bound.command["arguments"]["text"] = "consumer changed"
    assert bound.command == before
    assert bound.context.refs["field"].entity_id == "task-a"
    assert bound.context.sources["qa-original"].readable is True
    with pytest.raises(TypeError):
        bound.context.refs["field"] = Ref("wrong", "wrong", "task")
    with pytest.raises(FrozenInstanceError):
        bound.origin = "ai"
    assert "保留完整工作內容" not in repr(bound)


def test_reissued_tokens_and_extra_context_do_not_change_digest(context):
    original = bind(context)
    reissued = replace(context, refs={"fresh": context.refs["field"], "unused": context.refs["other"]})
    value = command()
    value["arguments"]["target_field_ref"] = "fresh"
    assert bind(reissued, value, operation_id=uuid4()).request_digest == original.request_digest
    context.refs["unrelated"] = Ref("another-document", str(uuid4()), "task", "unrelated")
    context.sources["unrelated"] = Source("another-document", False)
    assert bind(context).request_digest == original.request_digest


@pytest.mark.parametrize("change", ["base", "run", "origin", "text", "target", "source", "document"])
def test_changed_intent_has_different_digest(context, change):
    original = bind(context, origin="ai", ai_run_id="run-a")
    value = command()
    options = dict(origin="ai", ai_run_id="run-a")
    if change == "base":
        base = str(uuid4())
        context = replace(context, base_revision=base,
                          refs={key: replace(ref, revision=base) for key, ref in context.refs.items()})
    elif change == "run":
        options["ai_run_id"] = "run-b"
    elif change == "origin":
        options.update(origin="manual", ai_run_id=None)
    elif change == "text":
        value["arguments"]["text"] += "更正"
    elif change == "target":
        context.refs["field"] = replace(context.refs["field"], entity_id="task-b")
    elif change == "source":
        value["arguments"]["basis_refs"] = ["qa-other"]
    elif change == "document":
        context = replace(context, document_id="another",
            refs={key: replace(ref, document_id="another") for key, ref in context.refs.items()},
            sources={key: Source("another") for key in context.sources})
    assert bind(context, value, **options).request_digest != original.request_digest


@pytest.mark.parametrize("operation", [str(OPERATION), 42, None, True])
def test_operation_identity_must_be_an_app_uuid(context, operation):
    with pytest.raises(IntentValidationError, match="invalid_input"):
        bind(context, operation_id=operation)


@pytest.mark.parametrize("origin,run", [("ai", None), ("manual", "run"), ("unknown", None), ("ai", 42), ("ai", "")])
def test_origin_and_trusted_run_must_match(context, origin, run):
    with pytest.raises(IntentValidationError):
        bind(context, origin=origin, ai_run_id=run)


@pytest.mark.parametrize("base", ["not-a-uuid", BASE, None])
def test_context_base_must_be_a_uuid_string(context, base):
    with pytest.raises(IntentValidationError):
        bind(replace(context, base_revision=base))


@pytest.mark.parametrize("problem", ["unknown", "foreign_document", "stale", "wrong_type", "item_as_field", "bad_source", "foreign_source", "missing_source"])
def test_invalid_used_refs_or_sources_are_rejected_before_binding(context, problem):
    value = command()
    if problem == "unknown":
        value["arguments"]["target_field_ref"] = "missing"
    elif problem == "foreign_document":
        context.refs["field"] = replace(context.refs["field"], document_id="other")
    elif problem == "stale":
        context.refs["field"] = replace(context.refs["field"], revision=str(uuid4()))
    elif problem == "wrong_type":
        context.refs["field"] = {"private": "SensitiveX"}
    elif problem == "item_as_field":
        value["arguments"]["target_field_ref"] = "task"
    elif problem == "bad_source":
        context.sources["qa-original"] = Source("doc", False)
    elif problem == "foreign_source":
        context.sources["qa-original"] = Source("other")
    elif problem == "missing_source":
        context.sources.clear()
    with pytest.raises(IntentValidationError) as error:
        bind(context, value)
    assert error.value.code == "invalid_input"
    assert "SensitiveX" not in "".join(traceback.format_exception(error.value))


def selection_command():
    return command("jd_replace_selection", selection_ref="selection", replacement_text="乙", basis_refs=[])


def test_selection_digest_uses_stable_field_and_capture_not_issued_tokens(context):
    original = bind(context, selection_command())
    reissued = replace(context, refs={"fresh-field": context.refs["field"]},
        selections={"fresh-selection": replace(context.selections["selection"], field_ref="fresh-field")})
    value = selection_command()
    value["arguments"]["selection_ref"] = "fresh-selection"
    assert bind(reissued, value).request_digest == original.request_digest
    for selection in [Selection("field", "甲😀甲", 0, 1, "甲"), Selection("field", "乙😀甲", 3, 4, "甲")]:
        changed = replace(context, selections={"selection": selection})
        assert bind(changed, selection_command()).request_digest != original.request_digest
    context.selections.clear()
    assert original.context.selections["selection"].field_text == "甲😀甲"


@pytest.mark.parametrize("selection", [None, Selection("missing", "甲😀甲", 3, 4, "甲"),
    Selection("task", "甲😀甲", 3, 4, "甲"), Selection("field", "甲😀甲", 2, 3, "😀"),
    Selection("field", "甲😀甲", 3, 4, "錯"), Selection("field", "甲\r\n甲", 3, 4, "甲")])
def test_invalid_selection_capture_is_safely_rejected(context, selection):
    if selection is None:
        context.selections.clear()
    else:
        context.selections["selection"] = selection
    with pytest.raises(IntentValidationError):
        bind(context, selection_command())


def test_generated_shape_validation_occurs_once_without_context_or_id_generation(context, monkeypatch):
    import jd_relational.intents as intents
    count = 0
    original = intents.manual_command
    def validate_once(value):
        nonlocal count
        count += 1
        return original(value)
    def forbidden_id():
        pytest.fail("Binding cannot allocate domain IDs.")
    monkeypatch.setattr(intents, "manual_command", validate_once)
    bind(replace(context, new_id=forbidden_id))
    assert count == 1
    value = command()
    value["arguments"]["document_id"] = "model-scope"
    with pytest.raises(IntentValidationError):
        bind(context, value)


def test_invalid_shape_does_not_expose_original_input_or_chained_validation(context):
    value = command()
    value["arguments"]["text"] = {"private": "SensitiveX"}
    with pytest.raises(IntentValidationError) as error:
        bind(context, value)
    assert str(error.value) == "invalid_input"
    assert "SensitiveX" not in "".join(traceback.format_exception(error.value))


def all_tool_commands():
    field_change = {"kind": "set_field", "target_field_ref": "field", "text": "更正範圍", "basis_refs": ["qa-original"]}
    detail_change = {"kind": "add_task_detail", "task_ref": "task", "detail_kind": "requirement",
                     "after_ref": "detail", "text": "完整條件", "basis_refs": []}
    return [
        command("jd_create_task", container_ref="tasks", after_ref="other", name="任務", description=None,
                basis_refs=[], outcomes=[{"text": "成果", "basis_refs": ["qa-original"]}],
                requirements=[{"text": "要求", "basis_refs": []}],
                capabilities=[{"capability_ref": "capability", "basis_refs": ["qa-other"]}]),
        command("jd_revise_work", changes=[field_change, detail_change,
            {"kind": "remove_task_detail", "detail_ref": "detail"},
            {"kind": "set_task_capability", "task_ref": "task", "capability_ref": "capability", "mode": "link", "basis_refs": []},
            {"kind": "add_condition", "container_ref": "conditions", "after_ref": "condition", "text": "資格", "basis_refs": []},
            {"kind": "remove_condition", "condition_ref": "condition"}]),
        command(),
        command("jd_insert_item", item={"kind": "duty", "container_ref": "duties", "after_ref": "duty",
                "name": "職責", "scope_text": None, "basis_refs": []}),
        command("jd_delete_item", target_ref="duty", content_changes=[field_change, detail_change]),
        command("jd_move_item", target_ref="task", destination_container_ref="tasks", after_ref="other",
                content_changes=[field_change, detail_change]),
        command("jd_set_task_capability", task_ref="task", capability_ref="capability", mode="link", basis_refs=[]),
        selection_command(),
    ]


@pytest.mark.parametrize("value", all_tool_commands(), ids=lambda value: value["tool"])
def test_all_eight_generated_tools_resolve_nested_issued_aliases(context, value):
    original = bind(context, value)
    aliases = {token: "reissued-" + token for token in context.refs}
    aliases["selection"] = "reissued-selection"
    def reissue(item):
        if isinstance(item, dict):
            return {key: aliases.get(child, child) if key.endswith("_ref") and isinstance(child, str)
                    else reissue(child) for key, child in item.items()}
        if isinstance(item, list):
            return [reissue(child) for child in item]
        return item
    reissued_context = replace(context,
        refs={aliases[key]: ref for key, ref in context.refs.items()},
        selections={aliases[key]: replace(selection, field_ref=aliases[selection.field_ref])
                    for key, selection in context.selections.items()})
    assert bind(reissued_context, reissue(value)).request_digest == original.request_digest


def test_line_endings_are_canonical_but_text_is_not_treated_as_an_alias(context):
    value = command()
    value["arguments"]["text"] = "  field\r\n第二行  "
    original = bind(context, value)
    lf = deepcopy(value)
    lf["arguments"]["text"] = "  field\n第二行  "
    assert bind(context, lf).request_digest == original.request_digest
    reissued = replace(context, refs={"fresh": context.refs["field"]})
    lf["arguments"]["target_field_ref"] = "fresh"
    assert bind(reissued, lf).request_digest == original.request_digest
    lf["arguments"]["text"] = "  fresh\n第二行  "
    assert bind(reissued, lf).request_digest != original.request_digest


def test_source_order_is_part_of_complete_command_and_opaque_values_are_not_rewritten(context):
    value = command()
    value["arguments"]["basis_refs"] = ["qa-original", "qa-other"]
    original = bind(context, value)
    value["arguments"]["basis_refs"].reverse()
    assert bind(context, value).request_digest != original.request_digest
    assert original.command["arguments"]["basis_refs"] == ["qa-original", "qa-other"]


def test_copied_context_values_are_not_original_objects(context):
    original_ref = context.refs["field"]
    original_source = context.sources["qa-original"]
    original_selection = context.selections["selection"]
    bound = bind(context)
    assert bound.context.refs["field"] == original_ref and bound.context.refs["field"] is not original_ref
    assert bound.context.sources["qa-original"] == original_source and bound.context.sources["qa-original"] is not original_source
    assert bound.context.selections["selection"] == original_selection and bound.context.selections["selection"] is not original_selection
