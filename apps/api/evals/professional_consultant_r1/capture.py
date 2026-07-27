"""Trial capture 與 Manifest（設計 §10）。

不建 event sourcing、DB、hash chain 或通用 eval framework。
一次 trial 一個不可變目錄；寫完就不再改。

**禁止保存**（設計 §10）：API key／Authorization、provider 隱藏 reasoning、
模型 chain-of-thought、未遮罩 secret、由 request 猜出的 resolved endpoint。
redaction 由 `redact()` 強制執行，不靠呼叫端自律。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import Result, canonical_hash, canonical_json

# 任何 key 命中就整個值換成 stub。大小寫不敏感。
SECRET_KEYS = frozenset(
    {"authorization", "api_key", "apikey", "x-api-key", "bearer", "token", "secret", "password"}
)
REASONING_KEYS = frozenset({"reasoning", "reasoning_details", "reasoning_content", "thinking"})

REDACTED_SECRET = "[redacted:secret]"
REDACTED_REASONING = "[redacted:reasoning]"

MANIFEST_FILENAME = "manifest.json"

# 設計 §10 要求 manifest 至少保存的欄位。
REQUIRED_MANIFEST_KEYS = (
    "case_id",
    "case_revision",
    "case_family_id",
    "source_type",
    "suite_hash",
    "arm",
    "round",
    "attempt",
    "prompt_version",
    "schema_hash",
    "context_assembler_version",
    "requested_model",
    "resolved_model",
    "resolved_provider",
    "provider_config_hash",
    "files",
    "outcomes",
    "usage",
    "latency_ms",
    "limitations",
)


def redact(node: Any) -> Any:
    """遞迴遮罩 secret 與 reasoning。回傳新結構，不改原物件。"""
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for key, value in node.items():
            lowered = key.lower() if isinstance(key, str) else key
            if isinstance(lowered, str) and lowered in SECRET_KEYS:
                out[key] = REDACTED_SECRET
            elif isinstance(lowered, str) and lowered in REASONING_KEYS:
                out[key] = REDACTED_REASONING
            else:
                out[key] = redact(value)
        return out
    if isinstance(node, list):
        return [redact(item) for item in node]
    return node


def contains_secret_or_reasoning(node: Any) -> bool:
    """給測試與寫檔前的守門用：只要還有未遮罩的敏感 key 就回 True。"""
    if isinstance(node, dict):
        for key, value in node.items():
            lowered = key.lower() if isinstance(key, str) else key
            if isinstance(lowered, str) and lowered in (SECRET_KEYS | REASONING_KEYS):
                if value not in (REDACTED_SECRET, REDACTED_REASONING):
                    return True
            if contains_secret_or_reasoning(value):
                return True
        return False
    if isinstance(node, list):
        return any(contains_secret_or_reasoning(item) for item in node)
    return False


@dataclass
class TrialCapture:
    """一個 trial 目錄的寫入器。同一個檔名只准寫一次。"""

    directory: Path

    def __post_init__(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        self._written: dict[str, str] = {}

    def write(self, filename: str, payload: Any) -> str:
        """遮罩後寫入，回傳該檔的 canonical hash。重複寫同一檔名是錯誤。"""
        if filename in self._written:
            raise ValueError(f"trial capture 是不可變的，{filename} 已寫過")
        safe = redact(payload)
        if contains_secret_or_reasoning(safe):  # pragma: no cover - 防禦性
            raise ValueError(f"{filename} 仍含未遮罩的敏感內容，拒絕寫入")
        text = canonical_json(safe)
        (self.directory / filename).write_text(text, encoding="utf-8")
        digest = canonical_hash(safe)
        self._written[filename] = digest
        return digest

    @property
    def files(self) -> dict[str, str]:
        """檔名 → canonical hash。放進 manifest 當 reference。"""
        return dict(self._written)

    def write_manifest(self, manifest: dict[str, Any]) -> Path:
        safe = redact(manifest)
        path = self.directory / MANIFEST_FILENAME
        path.write_text(canonical_json(safe), encoding="utf-8")
        return path


def verify_manifest(manifest: Any, capture: TrialCapture | None = None) -> Result:
    """manifest 的最低完整性檢查（設計 §10、§12.1 第 11 項）。"""
    result = Result()
    if not isinstance(manifest, dict):
        result.error("manifest_shape", "manifest 必須是物件", MANIFEST_FILENAME)
        return result

    for key in REQUIRED_MANIFEST_KEYS:
        if key not in manifest:
            result.error("manifest_shape", f"manifest 缺少必要欄位 {key}", MANIFEST_FILENAME)

    if contains_secret_or_reasoning(manifest):
        result.error("manifest_redaction", "manifest 含未遮罩的 secret 或 reasoning", MANIFEST_FILENAME)

    # ADR 0040 決定 22：resolved 事實只能來自回應。
    resolved = manifest.get("resolved_model")
    requested = manifest.get("requested_model")
    if resolved is None and manifest.get("outcomes", {}).get("transport") == "ok":
        result.error(
            "resolved_route",
            "transport 成功卻沒有 resolved_model —— 不得由 request 回填",
            MANIFEST_FILENAME,
        )
    if resolved is not None and requested is not None and not isinstance(resolved, str):
        result.error("resolved_route", "resolved_model 必須是字串或 null", MANIFEST_FILENAME)

    files = manifest.get("files")
    if not isinstance(files, dict):
        result.error("manifest_shape", "files 必須是 {檔名: hash} 物件", MANIFEST_FILENAME)
    elif capture is not None:
        for name, digest in capture.files.items():
            if files.get(name) != digest:
                result.error(
                    "manifest_refs",
                    f"files[{name}] 的 hash 與實際寫入的內容不符",
                    MANIFEST_FILENAME,
                )
        for name in files:
            if name not in capture.files:
                result.error("manifest_refs", f"files 指向不存在的檔案：{name}", MANIFEST_FILENAME)

    return result


def load_manifest(directory: Path) -> dict[str, Any]:
    return json.loads((directory / MANIFEST_FILENAME).read_text(encoding="utf-8"))
