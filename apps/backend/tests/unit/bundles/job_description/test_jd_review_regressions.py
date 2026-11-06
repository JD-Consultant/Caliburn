"""獨立審查的工具契約反例；驗 native schema 與實際工具接受範圍。"""

from jsonschema import Draft202012Validator
from langchain_core.utils.function_calling import convert_to_openai_function

from caliburn.bundles.job_description.write_tools import create_write_tools
from tests.unit.bundles.job_description.test_write_sources import prepare_memory
from tests.unit.bundles.job_description.test_write_tools import Harness, payload


def test_mathematical_integer_level_matches_published_tool_schema() -> None:
    harness = Harness()
    arguments: dict[str, object] = {
        "changes": [{"action": "set_baseline_competency_level", "value": 1.0}]
    }
    tool = next(
        tool for tool in create_write_tools() if tool.name == "revise_jd_profile"
    )
    schema = convert_to_openai_function(tool, strict=True)["parameters"]
    Draft202012Validator(schema).validate(arguments)
    result = payload(harness.invoke("revise_jd_profile", arguments))
    assert result["status"] == "updated"
    assert harness.store.snapshot().baseline_competency_level == 1


def test_confirming_onto_existing_fixed_source_is_a_business_rejection() -> None:
    harness = Harness()
    current = prepare_memory(harness)
    old = current.model_copy(update={"published_version": 2})
    old_citation = harness.store.root.add_citation(
        target_kind="job_description", target_id=harness.store.root.id, source=old
    )
    harness.store.root.add_citation(
        target_kind="job_description", target_id=harness.store.root.id, source=current
    )
    before = harness.store.snapshot()
    result = payload(
        harness.invoke(
            "revise_jd_profile",
            {
                "changes": [
                    {
                        "action": "confirm_reference_alignment",
                        "citation_ref": harness.ref("citation", old_citation),
                    }
                ],
            },
        )
    )
    assert result["status"] == "rejected"
    assert result["code"] == "invalid_arguments"
    assert harness.store.snapshot() == before
    assert harness.store.commits == 0
