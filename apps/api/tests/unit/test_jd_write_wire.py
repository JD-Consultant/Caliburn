"""Model selections remain minimal, explicit, and distinct from App-owned identity."""

import json

import pytest
from pydantic import ValidationError

from caliburn.features.job_description.models import (
    ClearProfileField,
    ProfileField,
    SetProfileField,
)
from caliburn.transport.model_tools.jd_write_wire import parse_profile_write, parse_task_write
from caliburn.workflows.jd_profile_writes import AddProfileSource, AlignProfileSource
from caliburn.workflows.jd_sources import CurrentInputSourceSelection, InterviewSourceSelection


def test_profile_wire_separates_text_clear_and_explicit_evidence_choices() -> None:
    changes, sources = parse_profile_write(
        json.dumps(
            {
                "changes": [
                    {"action": "set_field", "field": "job_title", "value": "前端工程師"},
                    {"action": "clear_field", "field": "reports_to"},
                    {
                        "action": "add_source",
                        "field": "job_title",
                        "source": {"kind": "current_input"},
                    },
                    {
                        "action": "confirm_reference_alignment",
                        "field": "purpose",
                        "citation_ref": "citation_app",
                    },
                ]
            }
        )
    )
    assert changes == (
        SetProfileField(ProfileField.JOB_TITLE, "前端工程師"),
        ClearProfileField(ProfileField.REPORTS_TO),
    )
    assert sources == (
        AddProfileSource(ProfileField.JOB_TITLE, CurrentInputSourceSelection()),
        AlignProfileSource(ProfileField.PURPOSE, "citation_app"),
    )


def test_task_wire_preserves_empty_unknown_fields_and_per_detail_evidence() -> None:
    intent = parse_task_write(
        json.dumps(
            {
                "parent_read_ref": None,
                "title": "前端交付",
                "description": None,
                "outcomes": [
                    {
                        "text": "交付可操作網站",
                        "supporting_sources": [{"kind": "interview", "interview_sequence": 8}],
                    }
                ],
                "requirements": [],
                "required_knowledge": [],
                "required_skills": [],
                "supporting_sources": [],
            }
        )
    )
    assert intent.description is None
    assert intent.sources == ()
    assert intent.outcomes[0].sources == (InterviewSourceSelection(8),)
    assert intent.requirements == ()


def test_model_cannot_smuggle_scope_or_a_version_into_profile_wire() -> None:
    with pytest.raises(ValidationError):
        parse_profile_write(
            json.dumps(
                {
                    "changes": [
                        {
                            "action": "add_source",
                            "field": "purpose",
                            "source": {
                                "kind": "work_situation",
                                "target_title": "盤點",
                                "revision_id": "fake",
                            },
                        }
                    ]
                }
            )
        )
