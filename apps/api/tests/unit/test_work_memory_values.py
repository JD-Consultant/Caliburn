"""Update contract sections 3/5/10/11 and read contract section 4, without I/O."""

from dataclasses import FrozenInstanceError, replace
from uuid import UUID

import pytest

from caliburn.features.work_memory.changes import (
    apply_content_changes,
    apply_reference_changes,
    require_unique_title,
    resolve_title,
)
from caliburn.features.work_memory.models import (
    InvalidMemoryChangeError,
    MemoryContent,
    MemoryContentChanges,
    MemoryMapEntry,
    MemoryMapInconsistencyError,
    MemoryTargetNotFoundError,
    ReferenceChanges,
)


@pytest.mark.parametrize("field", ["title", "description", "body"])
@pytest.mark.parametrize("text", ["", " \t\r\n", "\u3000", "text\x00"])
def test_content_rejects_blank_or_nul_in_every_required_field(field: str, text: str) -> None:
    content = MemoryContent("盤點", "庫存盤點範圍", "每月盤點庫存。")
    with pytest.raises(InvalidMemoryChangeError):
        replace(content, **{field: text})


def test_content_changes_reject_no_supplied_field() -> None:
    with pytest.raises(InvalidMemoryChangeError):
        MemoryContentChanges()


@pytest.mark.parametrize("field", ["title", "description", "body"])
@pytest.mark.parametrize("text", ["", " \t\r\n", "\u3000", "text\x00"])
def test_supplied_content_changes_reject_blank_or_nul(field: str, text: str) -> None:
    changes = MemoryContentChanges(title="盤點")
    with pytest.raises(InvalidMemoryChangeError):
        replace(changes, **{field: text})


def test_content_preserves_whitespace_case_and_unicode_codepoints() -> None:
    title = " \tCafe\u0301\u3000"
    description = "  Café 的庫存盤點\r\n"
    body = "## Café\r\n\r\n每月盤點庫存。  \r\n"
    content = MemoryContent(title, description, body)
    changes = MemoryContentChanges(title, description, body)
    entry = MemoryMapEntry(UUID(int=1), title, description)

    assert (content.title, content.description, content.body) == (title, description, body)
    assert (changes.title, changes.description, changes.body) == (title, description, body)
    assert (entry.title, entry.description) == (title, description)


@pytest.mark.parametrize("field", ["title", "description", "body"])
def test_partial_content_change_preserves_omitted_fields_and_original(field: str) -> None:
    current = MemoryContent(" 原標題 ", " 原描述\r\n", "## 原正文\r\n")
    changes = MemoryContentChanges(**{field: " \tNew Cafe\u0301\r\n"})

    result = apply_content_changes(current, changes)

    assert result == replace(current, **{field: " \tNew Cafe\u0301\r\n"})
    assert current == MemoryContent(" 原標題 ", " 原描述\r\n", "## 原正文\r\n")


def test_combined_content_change_uses_precomputed_patch_result() -> None:
    current = MemoryContent("盤點", "每月盤點", "## 頻率\n每月一次。")
    changes = MemoryContentChanges("每週盤點", "每週檢查庫存", "## 頻率\n每週一次。")

    assert apply_content_changes(current, changes) == MemoryContent(
        "每週盤點", "每週檢查庫存", "## 頻率\n每週一次。"
    )
    assert current == MemoryContent("盤點", "每月盤點", "## 頻率\n每月一次。")


def test_identical_content_is_a_value_noop() -> None:
    current = MemoryContent("盤點", "每月盤點", "每月一次。")
    assert apply_content_changes(current, MemoryContentChanges(title="盤點")) == current


@pytest.mark.parametrize(
    ("value", "field", "replacement"),
    [
        (MemoryContent("盤點", "範圍", "正文"), "title", "新標題"),
        (MemoryContentChanges(body="新正文"), "body", "另一正文"),
        (ReferenceChanges(add=frozenset({UUID(int=1)})), "add", frozenset()),
        (MemoryMapEntry(UUID(int=1), "盤點", "範圍"), "title", "新標題"),
    ],
)
def test_internal_values_are_frozen(value: object, field: str, replacement: object) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(value, field, replacement)


def test_reference_changes_reject_empty_intent() -> None:
    with pytest.raises(InvalidMemoryChangeError):
        ReferenceChanges()


def test_reference_changes_reject_adding_and_removing_the_same_identity() -> None:
    reference_id = UUID(int=1)
    with pytest.raises(InvalidMemoryChangeError):
        ReferenceChanges(add=frozenset({reference_id}), remove=frozenset({reference_id}))


def test_reference_changes_preserve_unmentioned_members_and_inputs() -> None:
    retained, removed, added = UUID(int=1), UUID(int=2), UUID(int=3)
    current = frozenset({retained, removed})
    allowed = frozenset({added})
    changes = ReferenceChanges(add=frozenset({added}), remove=frozenset({removed}))

    result = apply_reference_changes(current, changes, allowed)

    assert result == frozenset({retained, added})
    assert isinstance(result, frozenset)
    assert current == frozenset({retained, removed})
    assert allowed == frozenset({added})
    assert changes == ReferenceChanges(add=frozenset({added}), remove=frozenset({removed}))


@pytest.mark.parametrize("already_present", [False, True])
def test_disallowed_add_is_rejected_even_when_already_present(already_present: bool) -> None:
    retained, disallowed = UUID(int=1), UUID(int=2)
    current = frozenset({retained, disallowed}) if already_present else frozenset({retained})
    changes = ReferenceChanges(add=frozenset({disallowed}), remove=frozenset({retained}))

    with pytest.raises(InvalidMemoryChangeError):
        apply_reference_changes(current, changes, allowed=frozenset())

    assert retained in current


@pytest.mark.parametrize("allowed", [frozenset(), frozenset({UUID(int=2), UUID(int=3)})])
def test_removing_a_missing_relationship_rejects_the_combined_change(
    allowed: frozenset[UUID],
) -> None:
    retained, missing, added = UUID(int=1), UUID(int=2), UUID(int=3)
    current = frozenset({retained})
    changes = ReferenceChanges(add=frozenset({added}), remove=frozenset({missing}))

    with pytest.raises(InvalidMemoryChangeError):
        apply_reference_changes(current, changes, allowed=allowed | {added})

    assert current == frozenset({retained})


def test_removing_the_last_reference_is_valid_without_add_eligibility() -> None:
    reference_id = UUID(int=1)
    current = frozenset({reference_id})

    assert (
        apply_reference_changes(current, ReferenceChanges(remove=current), allowed=frozenset())
        == frozenset()
    )
    assert current == frozenset({reference_id})


def test_adding_an_existing_relationship_is_a_value_noop() -> None:
    current = frozenset({UUID(int=1)})
    assert (
        apply_reference_changes(current, ReferenceChanges(add=current), allowed=current) == current
    )


def test_first_reference_can_be_added_to_an_empty_collection() -> None:
    reference_id = UUID(int=1)
    assert apply_reference_changes(
        frozenset(), ReferenceChanges(add=frozenset({reference_id})), frozenset({reference_id})
    ) == frozenset({reference_id})


@pytest.mark.parametrize("target_title", ["Missing", "ALPHA", " Alpha", "Alpha ", "Alph"])
def test_title_lookup_does_not_guess_or_normalize_a_missing_target(target_title: str) -> None:
    entries = (MemoryMapEntry(UUID(int=1), "Alpha", "First object"),)
    with pytest.raises(MemoryTargetNotFoundError):
        resolve_title(entries, target_title)


@pytest.mark.parametrize("target_title", ["", "\u3000", "Alpha\x00"])
def test_title_lookup_rejects_invalid_selector(target_title: str) -> None:
    with pytest.raises(InvalidMemoryChangeError):
        resolve_title((), target_title)


def test_empty_map_reports_a_typed_missing_target() -> None:
    with pytest.raises(MemoryTargetNotFoundError):
        resolve_title((), "盤點")


@pytest.mark.parametrize("other_title", ["ALPHA", " Alpha", "Alpha ", "Cafe\u0301"])
def test_lookup_and_uniqueness_share_exact_string_equality(other_title: str) -> None:
    original_title = "Café" if other_title == "Cafe\u0301" else "Alpha"
    original_id, other_id = UUID(int=1), UUID(int=2)
    original_entry = MemoryMapEntry(original_id, original_title, "Original")
    other_content = MemoryContent(other_title, "Other", "Body")
    entries = (original_entry, MemoryMapEntry(other_id, other_title, "Other"))

    assert resolve_title(entries, original_title) == original_id
    assert resolve_title(entries, other_title) == other_id
    require_unique_title(other_id, other_content, (original_entry,))
    with pytest.raises(MemoryTargetNotFoundError):
        resolve_title((original_entry,), other_title)


def test_duplicate_titles_in_a_supplied_map_are_an_inconsistency() -> None:
    entries = (
        MemoryMapEntry(UUID(int=1), "盤點", "甲"),
        MemoryMapEntry(UUID(int=2), "盤點", "乙"),
    )
    with pytest.raises(MemoryMapInconsistencyError):
        resolve_title(entries, "盤點")


def test_title_uniqueness_ignores_self_and_checks_only_the_supplied_layer() -> None:
    target_id, other_id = UUID(int=1), UUID(int=2)
    content = MemoryContent("盤點", "範圍", "正文")
    this_layer = (MemoryMapEntry(target_id, "盤點", "原描述"),)
    other_layer = (MemoryMapEntry(other_id, "盤點", "另一層"),)

    require_unique_title(target_id, content, this_layer)
    require_unique_title(other_id, content, other_layer)
    require_unique_title(target_id, content, ())
    with pytest.raises(InvalidMemoryChangeError):
        require_unique_title(other_id, content, this_layer)


def test_reused_title_selects_new_identity_without_retargeting_existing_references() -> None:
    original_id, replacement_id = UUID(int=1), UUID(int=2)
    current_references = frozenset({original_id})
    entries = (
        MemoryMapEntry(original_id, "Y", "Renamed object"),
        MemoryMapEntry(replacement_id, "X", "Reused title"),
    )

    assert resolve_title(entries, "X") == replacement_id
    assert resolve_title(entries, "Y") == original_id
    with pytest.raises(InvalidMemoryChangeError):
        apply_reference_changes(
            current_references,
            ReferenceChanges(remove=frozenset({resolve_title(entries, "X")})),
            allowed=frozenset({original_id, replacement_id}),
        )
    assert current_references == frozenset({original_id})
    assert (
        apply_reference_changes(
            current_references,
            ReferenceChanges(remove=frozenset({resolve_title(entries, "Y")})),
            allowed=frozenset(),
        )
        == frozenset()
    )
