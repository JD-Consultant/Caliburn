"""Full offline batch: real PostgreSQL, real JD tools, scripted provider only."""

import asyncio
import json
import re
from collections import Counter
from decimal import Decimal

import httpx2
import psycopg
import pytest
from prepare_study import prepare
from psycopg import sql
from run_study import execute_batch
from study_batch import ARMS
from study_prompt import instructions_for
from tests.unit.test_response_loop import response_at

pytest_plugins = ("tests.integration.conftest",)
pytestmark = pytest.mark.postgres


def test_frozen_batch_runs_all_cases_and_persists_separate_arm_products(
    database_settings, tmp_path
):
    output = tmp_path / "batch"
    prepare(output)
    calls = Counter()
    observed = []

    def respond(request):
        payload = json.loads(request.content)
        if request.url.path.endswith("/input_tokens"):
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 900}
            )
        assert request.url.path.endswith("/responses")
        arm = next(arm for arm in ARMS if payload["instructions"] == instructions_for(arm))
        calls[arm] += 1
        ordinal = (calls[arm] + 1) // 2
        if calls[arm] % 2:
            observed.append((arm, ordinal))
            if ordinal == 1:
                assert "2026年11月1日" not in json.dumps(payload, ensure_ascii=False)
        raw = response_at(
            sum(calls.values()), final=calls[arm] % 2 == 0, tools=calls[arm] % 2
        ).model_dump(mode="json")
        raw["model"] = "gpt-6-luna"
        raw["service_tier"] = "default"
        raw["usage"] = {
            "input_tokens": 900,
            "output_tokens": 100,
            "total_tokens": 1000,
            "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 50},
        }
        if calls[arm] % 2:
            raw["output"][-1].update(
                name="revise_jd_profile",
                arguments=json.dumps(
                    {
                        "changes": [
                            {
                                "action": "set_field",
                                "field": "job_title",
                                "value": f"合成{arm}-{ordinal}",
                            },
                            {
                                "action": "add_source",
                                "field": "job_title",
                                "source": {"kind": "current_input"},
                            },
                        ]
                    }
                ),
            )
        return httpx2.Response(200, json=raw)

    async def run():
        await execute_batch(
            output,
            database_url=database_settings.url,
            api_key="synthetic-no-fee",
            batch_usd=Decimal("0.10"),
            seconds=300,
            authorization_note="offline test only",
            transport=httpx2.MockTransport(respond),
        )

    try:
        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as loop:
            loop.run(run())
        result = json.loads((output / "result.json").read_text(encoding="utf-8"))
        assert result["status"] == "completed", result
        assert Decimal(result["usage"]["cumulative_occupied_usd"]) == (
            Decimal("1.391700015")
            + Decimal(result["usage"]["actual_estimated_usd"])
            + Decimal(result["usage"]["count_estimated_usd"])
        )
        assert calls == {arm: 16 for arm in ARMS}
        assert observed[:6] == [
            ("raw", 1),
            ("summary", 1),
            ("memory", 1),
            ("summary", 2),
            ("memory", 2),
            ("raw", 2),
        ]
        for arm in ARMS:
            product = json.loads((output / f"product-{arm}-c08.json").read_text(encoding="utf-8"))
            assert product["profile"]["profile"]["job_title"] == f"合成{arm}-8"
            assert len(product["interviews"]) == 121
            assert len(result["completed"][arm]) == 8
        assert len(list(output.glob("exchange-*.json"))) == 24
        assert "synthetic-opaque-" not in (output / "trace.jsonl").read_text(encoding="utf-8")
        with pytest.raises(FileExistsError):
            with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as loop:
                loop.run(run())
    finally:
        # Only namespaces minted by this invocation, never preexisting research data.
        with psycopg.connect(database_settings.url, autocommit=True) as connection:
            for path in output.glob("namespace-*.json"):
                schema = json.loads(path.read_text(encoding="utf-8"))["schema"]
                assert re.fullmatch(r"eval_reset_[0-9a-f]{32}", schema)
                connection.execute(
                    sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema))
                )
