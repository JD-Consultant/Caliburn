"""補足官方 serializer 遺失的 SDK 省略欄位語意；內容仍由 JsonPlus 保存。"""

from typing import Any, cast

from langgraph.checkpoint.serde.jsonplus import EXT_PYDANTIC_V2, JsonPlusSerializer
from openai import BaseModel
from ormsgpack import Ext

type FieldSets = dict[tuple[object, ...], set[str]]

_TYPE_PREFIX = "openai-fields-v1+"


class OpenAIFieldSetSerializer(JsonPlusSerializer):
    """只補 SDK model_fields_set，不替換 SDK 值、型別或官方內容編碼。"""

    def dumps_typed(self, obj: Any) -> tuple[str, bytes]:
        field_sets: FieldSets = {}
        _collect_field_sets(obj, (), field_sets)
        if not field_sets:
            return super().dumps_typed(obj)
        metadata = [(list(path), sorted(fields)) for path, fields in field_sets.items()]
        kind, payload = super().dumps_typed((self._encode_sdk_models(obj), metadata))
        return _TYPE_PREFIX + kind, payload

    def _encode_sdk_models(self, value: object) -> object:
        if isinstance(value, BaseModel):
            # SDK 的 compact output 含 user/input_text，但欄位型別仍窄於實值。
            # 沿 JsonPlus 的官方 Pydantic envelope，只在 SDK dump 關閉會帶出
            # 原話的型別警告；內容、extra 與官方 allowlist／還原機制不變。
            _, payload = super().dumps_typed(
                (
                    type(value).__module__,
                    type(value).__name__,
                    value.model_dump(warnings=False),
                    "model_validate_json",
                )
            )
            return Ext(EXT_PYDANTIC_V2, payload)
        if isinstance(value, dict):
            return {
                name: self._encode_sdk_models(child) for name, child in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [self._encode_sdk_models(child) for child in value]
        return value

    def loads_typed(self, data: tuple[str, bytes]) -> Any:
        kind, payload = data
        if not kind.startswith(_TYPE_PREFIX):
            return super().loads_typed(data)
        value, metadata = super().loads_typed(
            (kind.removeprefix(_TYPE_PREFIX), payload)
        )
        field_sets = {tuple(path): set(fields) for path, fields in metadata}
        return _restore_field_sets(value, (), field_sets)


def _collect_field_sets(
    value: object, path: tuple[object, ...], result: FieldSets
) -> None:
    if isinstance(value, BaseModel):
        result[path] = value.model_fields_set
        for name, child in value:
            _collect_field_sets(child, (*path, name), result)
    elif isinstance(value, dict):
        for name, child in value.items():
            _collect_field_sets(child, (*path, name), result)
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _collect_field_sets(child, (*path, index), result)


def _restore_field_sets(
    value: object, path: tuple[object, ...], field_sets: FieldSets
) -> object:
    if isinstance(value, BaseModel):
        restored = {
            name: _restore_field_sets(child, (*path, name), field_sets)
            for name, child in value
        }
        # SDK 的 override 會把所有 kwargs 重加 fields_set；沿公開 Pydantic
        # 父方法保留原值及 explicit-null／unset，不改 SDK 私有屬性。
        return super(BaseModel, type(value)).model_construct(
            _fields_set=field_sets[path], **cast(dict[str, Any], restored)
        )
    if isinstance(value, dict):
        return {
            name: _restore_field_sets(child, (*path, name), field_sets)
            for name, child in value.items()
        }
    if isinstance(value, list):
        return [
            _restore_field_sets(child, (*path, index), field_sets)
            for index, child in enumerate(value)
        ]
    return value
