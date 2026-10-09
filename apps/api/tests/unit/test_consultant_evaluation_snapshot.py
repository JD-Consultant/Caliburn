"""比較開始後，呼叫者修改 DTO 不得改變已聲明的候選或案例。"""

import hashlib
import json
import sys
from pathlib import Path

import pytest

from caliburn.adapters.database_settings import DatabaseSettings
from caliburn.settings import ModelSettings
from evaluations import authorized_consultant_comparison as authorized
from evaluations import consultant_comparison as scripted
from evaluations.consultant_cases import ConsultantComparison


def comparison_and_mutation():
    inputs = ["固定公開輸入"]
    criteria = ["固定評閱判準"]
    comparison = ConsultantComparison.model_validate(
        {
            "case": {"name": "synthetic", "inputs": inputs, "criteria": criteria},
            "candidates": [
                {
                    "name": name,
                    "prompts": {"focus": name + "-focus"},
                    "tool_descriptions": {"read_jd": name + "-read"},
                }
                for name in ("baseline", "candidate")
            ],
        }
    )

    def mutate():
        for candidate in comparison.candidates:
            candidate.prompts["focus"] = "changed-after-entry"
            candidate.tool_descriptions["read_jd"] = "changed-after-entry"
        inputs.append("不可追加的輸入")
        criteria.append("不可追加的判準")

    return comparison, mutate


def assert_recorded_and_executed_originals(output, observed):
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["case"]["inputs"] == ["固定公開輸入"]
    assert manifest["case"]["criteria"] == ["固定評閱判準"]
    assert len(observed) == 2
    for recorded, (configuration, case) in zip(manifest["candidates"], observed, strict=True):
        name = recorded["name"]
        assert recorded["configuration"]["prompts"]["focus"] == name + "-focus"
        assert configuration.prompts.focus == name + "-focus"
        assert recorded["configuration"]["tool_descriptions"] == [
            {"name": "read_jd", "description": name + "-read"}
        ]
        assert configuration.tool_descriptions[0].description == name + "-read"
        assert case.inputs == ("固定公開輸入",)
        assert case.criteria == ("固定評閱判準",)


@pytest.mark.parametrize("mutation_at", ["first_await", "after_manifest"])
async def test_authorized_comparison_freezes_entire_batch_before_first_await(
    monkeypatch, tmp_path, mutation_at
):
    comparison, mutate = comparison_and_mutation()
    output = tmp_path / "authorized"
    observed = []
    cost_limits = {"max_batch_cost_usd": "1"}
    original_mkdir = Path.mkdir

    def mkdir(path, *args, **kwargs):
        if path == output and mutation_at == "first_await":
            mutate()
            cost_limits["max_batch_cost_usd"] = "99"
        return original_mkdir(path, *args, **kwargs)

    def prepare_database(url):
        if mutation_at == "after_manifest":
            mutate()
        return DatabaseSettings(url=url, schema="eval_synthetic")

    async def run_candidate(settings, composition, case, **kwargs):
        observed.append((composition.consultant_configuration, case))
        return scripted.CandidateRun({"all_inputs_completed": True}, True)

    def reject_provider(settings):
        raise AssertionError("This test must not construct a provider client")

    monkeypatch.setattr(Path, "mkdir", mkdir)
    monkeypatch.setattr(authorized, "save_source_snapshot", lambda _: {})
    monkeypatch.setattr(authorized, "prepare_isolated_database", prepare_database)
    monkeypatch.setattr(authorized, "run_candidate", run_candidate)
    await authorized.run_authorized_comparison(
        comparison,
        database_url="postgresql://localhost/synthetic_test",
        model=ModelSettings(api_key="synthetic-never-used"),
        create_guarded_client=reject_provider,
        authorization_reference="synthetic authorization",
        guard_version="synthetic guard",
        declared_cost_limits=cost_limits,
        output_directory=output,
    )
    assert_recorded_and_executed_originals(output, observed)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["declared_cost_limits"] == {"max_batch_cost_usd": "1"}


def test_scripted_comparison_keeps_all_candidates_fixed_after_manifest(monkeypatch, tmp_path):
    comparison, mutate = comparison_and_mutation()
    specification = tmp_path / "case.json"
    specification.write_text(comparison.model_dump_json(), encoding="utf-8")
    output = tmp_path / "scripted"
    observed = []

    def prepare_database(url):
        mutate()
        return DatabaseSettings(url=url, schema="eval_synthetic")

    async def run_candidate(settings, composition, case, **kwargs):
        observed.append((composition.consultant_configuration, case))
        return scripted.CandidateRun({"all_inputs_completed": True}, True)

    monkeypatch.setattr(
        ConsultantComparison, "model_validate_json", classmethod(lambda cls, raw: comparison)
    )
    monkeypatch.setattr(scripted, "save_source_snapshot", lambda _: {})
    monkeypatch.setattr(scripted, "prepare_isolated_database", prepare_database)
    monkeypatch.setattr(scripted, "run_candidate", run_candidate)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "consultant_comparison",
            str(specification),
            "--scripted",
            "--database-url",
            "postgresql://localhost/synthetic_test",
            "--output",
            str(output),
        ],
    )
    assert scripted.main() == 0
    assert_recorded_and_executed_originals(output, observed)


def test_cli_manifest_hash_identifies_the_bytes_actually_parsed(monkeypatch, tmp_path):
    comparison, _ = comparison_and_mutation()
    original = comparison.model_dump_json().encode()
    specification = tmp_path / "case.json"
    specification.write_bytes(original)
    output = tmp_path / "manifest.json"
    original_validate = ConsultantComparison.model_validate_json

    def validate(cls, raw):
        result = original_validate(raw)
        specification.write_bytes(b"changed-after-reading")
        return result

    monkeypatch.setattr(ConsultantComparison, "model_validate_json", classmethod(validate))
    monkeypatch.setattr(
        sys, "argv", ["comparison", str(specification), "--dry-run", "--output", str(output)]
    )
    assert scripted.main() == 0
    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["specification_sha256"] == hashlib.sha256(original).hexdigest()
