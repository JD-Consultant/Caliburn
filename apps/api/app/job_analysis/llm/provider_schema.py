"""`TaskAnalysisResult.v1` 的 provider-facing JSON Schema(§12.4)。

只有這一份契約需要提交 provider schema;Task、Proposal、Context 是套件內部契約,
用 Pydantic ＋ unit test 就夠,不為內部 DTO 產生大量 JSON Schema 與 golden。

`schemas/task_analysis_result.v1.json` 是 committed golden:送給模型的形狀改變時,
diff 必須在 review 裡看得見,而不是悄悄跟著 Python 型別漂走。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .portable_schema import portable_strict_output_schema
from .result import TASK_ANALYSIS_RESULT_SCHEMA_NAME, TaskAnalysisResult


PROVIDER_SCHEMA_PATH = (
    Path(__file__).parent / "schemas" / f"{TASK_ANALYSIS_RESULT_SCHEMA_NAME}.json"
)


def task_analysis_result_provider_schema() -> dict[str, Any]:
    return portable_strict_output_schema(TaskAnalysisResult.model_json_schema())


def committed_provider_schema() -> dict[str, Any]:
    return json.loads(PROVIDER_SCHEMA_PATH.read_text(encoding="utf-8"))


def render_provider_schema_file() -> str:
    """Golden 的唯一渲染方式(換行固定 `\\n`,尾端一個換行)。"""

    return (
        json.dumps(
            task_analysis_result_provider_schema(),
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
        )
        + "\n"
    )
