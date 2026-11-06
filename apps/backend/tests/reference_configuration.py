"""合成 Host 測試共用的公版設定；建立資源不連線或載入模型。"""

from pathlib import Path

from caliburn.modules.occupation_reference.configuration import ReferenceConfiguration

HOST_REFERENCE_CONFIGURATION = ReferenceConfiguration(
    collection="host_test", qdrant_url="http://127.0.0.1:1"
)


def write_reference_configuration(directory: Path) -> Path:
    path = directory / "reference.json"
    path.write_text(HOST_REFERENCE_CONFIGURATION.model_dump_json(), encoding="utf-8")
    return path
