"""共用工具函式。"""
import json
import logging
import re

logger = logging.getLogger("jobintel")


def safe_parse_json(text: str, default=None):
    """
    從 LLM 輸出解析 JSON，容錯 markdown code block。
    若兩種方法都失敗，記錄 warning 並回傳 default（預設為 []）。
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    logger.warning("JSON parse failed. Raw output (first 300 chars): %s", text[:300])
    return [] if default is None else default
