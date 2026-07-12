"""strict-subset schema 建構器(給 LlmPort.select_schema 用)。

原住 commands.py(v1);ADR 0030 T3 抽出成中性模組——scribe_schema/curation/
backstop/attitudes 都用,v1 的 commands.py 退場(T12)後這裡是唯一家。
"""


def _s(t: str | list[str]) -> dict:
    return {"type": t}


def _obj(props: dict) -> dict:
    """strict 規則:required = 全部欄位、additionalProperties=false。"""
    return {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }


def _variant(tag: str, **props) -> dict:
    return _obj({"type": {"enum": [tag]}, **props})
