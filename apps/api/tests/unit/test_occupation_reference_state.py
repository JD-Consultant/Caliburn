"""Only explicitly excluded work is retained, with exact reversible list edits."""

from dataclasses import asdict

import pytest

from caliburn.features.occupation_references.models import (
    OccupationReferenceState,
    ReferenceStateError,
    select_references,
    update_excluded_work,
)
from caliburn.features.occupation_references.persistence import state_payload, state_value


def test_unselected_and_empty_choices_keep_excluded_work() -> None:
    initial = OccupationReferenceState(excluded_work=("正式環境部署",))
    selected = select_references(initial, ("frontend:v1", "backend:v2", "frontend:v1"))
    empty = select_references(selected, ())
    assert initial.selected_reference_ids is None
    assert selected.selected_reference_ids == ("frontend:v1", "backend:v2")
    assert empty.selected_reference_ids == ()
    assert empty.excluded_work == ("正式環境部署",)


def test_exclusions_append_exact_unique_text_without_semantic_merging() -> None:
    original = OccupationReferenceState(("frontend:v1",), excluded_work=("正式部署",))
    updated = update_excluded_work(original, ("帳務調整", "正式部署", "正式上線", "帳務調整"), ())
    assert updated.excluded_work == ("正式部署", "帳務調整", "正式上線")
    assert updated.selected_reference_ids == ("frontend:v1",)
    assert original.excluded_work == ("正式部署",)


def test_employee_correction_removes_exact_exclusion_without_erasing_other_work() -> None:
    original = OccupationReferenceState(excluded_work=("正式部署", "帳務調整", "正式上線"))
    updated = update_excluded_work(original, ("資料庫維護",), ("帳務調整",))
    assert updated.excluded_work == ("正式部署", "正式上線", "資料庫維護")
    assert update_excluded_work(updated, (), updated.excluded_work).excluded_work == ()


@pytest.mark.parametrize(
    ("add", "remove"),
    [((), ()), (("正式部署",), ("正式部署",)), (("帳務調整",), ("不存在",))],
)
def test_invalid_update_rejects_entire_batch(add: tuple[str, ...], remove: tuple[str, ...]) -> None:
    original = OccupationReferenceState(excluded_work=("正式部署",))
    with pytest.raises(ReferenceStateError):
        update_excluded_work(original, add, remove)
    assert original.excluded_work == ("正式部署",)


def test_removal_is_exact_and_does_not_guess_semantic_equivalence() -> None:
    original = OccupationReferenceState(excluded_work=("正式部署",))
    for text in ("部署", "正式上線", " 正式部署"):
        with pytest.raises(ReferenceStateError):
            update_excluded_work(original, (), (text,))


@pytest.mark.parametrize("work", ["", "  \t", "部署\x00範圍", 3, None])
def test_invalid_exclusion_is_rejected(work: str) -> None:
    with pytest.raises(ReferenceStateError):
        OccupationReferenceState(excluded_work=(work,))


def test_mutable_or_duplicate_exclusions_cannot_bypass_update_rules() -> None:
    with pytest.raises(ReferenceStateError):
        OccupationReferenceState(excluded_work=["正式部署"])  # type: ignore[arg-type]
    with pytest.raises(ReferenceStateError):
        OccupationReferenceState(excluded_work=("正式部署", "正式部署"))


@pytest.mark.parametrize("reference", ["", "   ", "reference\x00id"])
def test_invalid_reference_is_rejected(reference: str) -> None:
    with pytest.raises(ReferenceStateError):
        select_references(OccupationReferenceState(), (reference,))


def test_state_contains_only_reference_choices_and_excluded_work() -> None:
    state = OccupationReferenceState(excluded_work=("正式部署",))
    assert asdict(state) == {"selected_reference_ids": None, "excluded_work": ("正式部署",)}
    with pytest.raises(TypeError):
        OccupationReferenceState(confirmations=())  # type: ignore[call-arg]


def test_persistence_roundtrip_preserves_exclusions_without_source_metadata() -> None:
    state = OccupationReferenceState(("frontend",), ("正式部署", "帳務調整"))
    payload = state_payload(state)
    assert payload == {
        "selected_reference_ids": ["frontend"],
        "excluded_work": ["正式部署", "帳務調整"],
    }
    assert state_value(payload) == state


def test_old_confirmation_state_is_rejected_instead_of_converted_to_exclusions() -> None:
    with pytest.raises(ReferenceStateError):
        state_value({"selected_reference_ids": None, "confirmations": []})


@pytest.mark.parametrize(
    "payload",
    [
        {"selected_reference_ids": None, "excluded_work": [], "confirmations": []},
        {"selected_reference_ids": None},
        {"selected_reference_ids": None, "excluded_work": None},
        {"selected_reference_ids": None, "excluded_work": ["正式部署", "正式部署"]},
    ],
)
def test_saved_state_shape_is_strict(payload: dict[str, object]) -> None:
    with pytest.raises(ReferenceStateError):
        state_value(payload)
