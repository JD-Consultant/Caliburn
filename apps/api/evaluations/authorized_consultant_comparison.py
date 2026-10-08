"""已授權真 provider 研究的程式化範例；明示注入現有整批護欄，不改全域值。

呼叫方式（active research harness 自行提供已核實的 guard／transport）：

    def create_guarded_client(model):
        return create_responses_client(
            api_key=model.api_key,
            timeout_seconds=model.request_timeout_seconds,
            http_client=httpx2.AsyncClient(transport=approved_transport_factory()),
        )

    await run_authorized_comparison(
        comparison, database_url=isolated_test_url, model=model_settings,
        create_guarded_client=create_guarded_client,
        authorization_reference="本次核准紀錄", guard_version="已核實的護欄版本",
        declared_cost_limits={"max_batch_cost_usd": "本次核准額度"},
        output_directory=new_output_directory,
    )

所有 candidate／A／B1／B2 應共用呼叫者的同一批 guard 狀態；每個 client／transport
有自己的關閉責任。declared_cost_limits 只保存呼叫者聲明，真正准入由該 guard 執行。
歷史 BatchGuard 帶有固定模型／arm 契約，沒有被此模組 import 或假定適用所有新候選。
"""

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import asdict
from pathlib import Path

from openai import AsyncOpenAI

from caliburn.app_composition import AppComposition
from caliburn.settings import ModelSettings, Settings
from evaluations.consultant_cases import ConsultantComparison
from evaluations.consultant_comparison import (
    BASE_URL,
    prepare_isolated_database,
    run_candidate,
    save_new,
    save_source_snapshot,
)


async def run_authorized_comparison(
    comparison: ConsultantComparison,
    *,
    database_url: str,
    model: ModelSettings,
    create_guarded_client: Callable[[ModelSettings], AsyncOpenAI],
    authorization_reference: str,
    guard_version: str,
    declared_cost_limits: Mapping[str, str | int],
    output_directory: Path,
) -> tuple[dict[str, object], ...]:
    """執行固定案例的有限候選；非完成即停止，不重跑／追加輸入或重設 guard。"""
    if not authorization_reference.strip() or not guard_version.strip() or not declared_cost_limits:
        raise ValueError("Record the effective authorization, guard version and batch limits")
    # 首次等待前固定整批候選；案例已由 frozen DTO 的字串／tuple 組成。
    case = comparison.case
    candidates = tuple(candidate.prepare() for candidate in comparison.candidates)
    manifest = {
        "mode": "authorized_provider",
        "authorization_reference": authorization_reference,
        "guard_version": guard_version,
        "declared_cost_limits": dict(declared_cost_limits),
        "case": case.model_dump(mode="json"),
        "candidates": [candidate.manifest() for candidate in candidates],
        "model": {
            key: str(value) if key == "max_cost_usd" and value is not None else value
            for key, value in asdict(model).items()
            if key != "api_key"
        },
    }
    await asyncio.to_thread(output_directory.mkdir, parents=True, exist_ok=False)
    manifest.update(await asyncio.to_thread(save_source_snapshot, output_directory))
    await asyncio.to_thread(
        save_new,
        output_directory / "manifest.json",
        manifest,
    )
    results = []
    for candidate in candidates:
        destination = output_directory / candidate.name
        await asyncio.to_thread(destination.mkdir)
        try:
            database = await asyncio.to_thread(prepare_isolated_database, database_url)
            await asyncio.to_thread(
                save_new, destination / "runtime.json", {"schema": database.schema}
            )
            result = await run_candidate(
                Settings(database=database, model=model, dev_origin=BASE_URL),
                AppComposition(
                    consultant_configuration=candidate.configuration,
                    interview_plans_enabled=candidate.interview_plans_enabled,
                    create_responses_client=create_guarded_client,
                ),
                case,
                timeout_seconds=model.turn_timeout_seconds + model.request_timeout_seconds,
            )
            await asyncio.to_thread(save_new, destination / "result.json", result)
            results.append(result)
            if not result["all_inputs_completed"]:
                break
        except Exception as error:
            await asyncio.to_thread(
                save_new, destination / "failure.json", {"error_type": type(error).__name__}
            )
            raise
    return tuple(results)
