from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest


API_DIR = Path(__file__).parents[1]
ROOT = API_DIR / "app" / "interview_vnext"
DOMAIN_ROOT = ROOT / "domain"


def _imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.lineno, node.module))
    return found


def _module_imports(path: Path) -> list[tuple[int, str]]:
    """Every import target, keeping relative ones.

    ``_imports`` drops ``from .x import y`` because inside ``domain/`` any relative
    import is domain-internal and the stdlib/pydantic whitelist does not care which
    sibling it hit. The R5-A corrective guard does care about the sibling, so it
    needs the relative form resolved to its module name.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.append((node.lineno, node.module))
            else:
                # `from . import evidence` carries the sibling in names, not module.
                found.extend((node.lineno, alias.name) for alias in node.names)
    return found


def test_support_module_never_imports_evidence_or_aggregates():
    """R5-A corrective §3.2:`domain/support.py` 是 QuoteSpan/QuoteMatch 的唯一
    owner,依賴方向只准 evidence -> support。反向再多一條 import,R5-B 的
    ``Evidence.v3.support`` 就會形成 import cycle;late import/forward-ref 掩蓋
    不算修好,所以這裡鎖結構而不是鎖 runtime。"""
    path = DOMAIN_ROOT / "support.py"
    forbidden = {"evidence", "question_frame", "state"}
    violations: list[str] = []
    for line, module in _module_imports(path):
        if module.rsplit(".", 1)[-1] in forbidden:
            violations.append(f"{path.relative_to(DOMAIN_ROOT)}:{line} imports {module}")
    assert violations == []


def _fresh_process(script: str) -> subprocess.CompletedProcess[str]:
    """在全新 interpreter 跑 `script`(cwd=apps/api,無 network/DB)。

    warm pytest process 早已載入每個 domain module,看不到 partial-module
    initialization 或未解析 forward ref;只有冷啟動 process 看得到。
    """
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=API_DIR,
        env={**os.environ, "PYTHONUTF8": "1"},
        capture_output=True,
        text=True,
        timeout=180,
        encoding="utf-8",  # Windows console 預設 cp950,顯式 UTF-8
        errors="replace",
    )


_ONE_CLASS_AUTHORITY = """
from app.interview_vnext import domain
from app.interview_vnext.application import turn_interpret as application_turn_interpret
from app.interview_vnext.llm import turn_interpret as llm_turn_interpret

# Evidence.v3 carries no top-level quote at all: the support union owns the
# primitive, so evidence.py must not re-declare or re-export one (plan §7.1).
assert not hasattr(evidence, "QuoteSpan"), "evidence re-declares QuoteSpan"
assert not hasattr(evidence, "QuoteMatch"), "evidence re-declares QuoteMatch"
assert "span" not in evidence.Evidence.model_fields, "Evidence.v3 has no top-level span"
assert "quote" not in evidence.Evidence.model_fields, "Evidence.v3 has no top-level quote"

assert domain.QuoteSpan is support.QuoteSpan, "domain export is a second QuoteSpan"
assert application_turn_interpret.QuoteSpan is support.QuoteSpan
assert application_turn_interpret.QuoteMatch is support.QuoteMatch
assert llm_turn_interpret.QuoteSpan is support.QuoteSpan
"""

_COLD_PROCESS_SCRIPTS = {
    "support_first": (
        "import app.interview_vnext.domain.support as support\n"
        "import app.interview_vnext.domain.evidence as evidence\n" + _ONE_CLASS_AUTHORITY
    ),
    "evidence_first": (
        "import app.interview_vnext.domain.evidence as evidence\n"
        "import app.interview_vnext.domain.support as support\n" + _ONE_CLASS_AUTHORITY
    ),
    "evidence_schema": (
        "from app.interview_vnext.domain.evidence import Evidence\n"
        "defs = Evidence.model_json_schema()['$defs']\n"
        "assert 'QuoteSpan' in defs and 'QuoteMatch' in defs, sorted(defs)\n"
    ),
    "support_schema": (
        "from pydantic import TypeAdapter\n"
        "from app.interview_vnext.domain.support import EvidenceSupport\n"
        "schema = TypeAdapter(EvidenceSupport).json_schema()\n"
        "assert schema['discriminator']['propertyName'] == 'support_kind', schema\n"
        "assert 'QuoteSpan' in schema['$defs'], sorted(schema['$defs'])\n"
    ),
}


@pytest.mark.parametrize("case", sorted(_COLD_PROCESS_SCRIPTS))
def test_quote_primitive_ownership_holds_in_a_cold_process(case):
    """R5-A corrective §8.1:兩種 import 進入點、兩種 schema generation 都要在
    全新 process 成功,且 QuoteSpan/QuoteMatch 全域只有一份 class authority。"""
    proc = _fresh_process(_COLD_PROCESS_SCRIPTS[case])
    assert proc.returncode == 0, proc.stderr


def test_vnext_never_imports_v3_interview_internals():
    violations: list[str] = []
    for path in ROOT.rglob("*.py"):
        for line, module in _imports(path):
            if module == "app.interview" or module.startswith("app.interview."):
                violations.append(f"{path.relative_to(ROOT)}:{line} imports {module}")
    assert violations == []

def test_domain_imports_only_stdlib_pydantic_or_itself():
    violations: list[str] = []
    for path in DOMAIN_ROOT.rglob("*.py"):
        for line, module in _imports(path):
            root = module.split(".", 1)[0]
            allowed = (
                root in sys.stdlib_module_names
                or root == "pydantic"
                or module == "app.interview_vnext.domain"
                or module.startswith("app.interview_vnext.domain.")
            )
            if not allowed:
                violations.append(f"{path.relative_to(DOMAIN_ROOT)}:{line} imports {module}")
    assert violations == []


def test_application_and_domain_never_import_persistence_frameworks():
    """V2-B §6:application ports 是純 Protocol/DTO;SQLAlchemy/driver 只准住
    persistence adapter。domain 一併鎖(比 stdlib+pydantic 白名單再多一道明示)。"""
    forbidden_roots = {"sqlalchemy", "alembic", "asyncpg", "psycopg"}
    violations: list[str] = []
    for relative_root in ("application", "domain"):
        for path in (ROOT / relative_root).rglob("*.py"):
            for line, module in _imports(path):
                if module.split(".", 1)[0] in forbidden_roots:
                    violations.append(f"{path.relative_to(ROOT)}:{line} imports {module}")
    assert violations == []


def test_production_app_does_not_import_eval_adapter():
    """V3-4 §4:provider eval adapter 只住 `apps/api/evals/`;production `app/`
    (含 composition root、route、interview_vnext)不得 import `evals` 任何子模組。"""
    app_root = Path(__file__).parents[1] / "app"
    violations: list[str] = []
    for path in app_root.rglob("*.py"):
        for line, module in _imports(path):
            if module == "evals" or module.startswith("evals."):
                violations.append(f"{path.relative_to(app_root)}:{line} imports {module}")
    assert violations == []


def test_neutral_llm_and_capture_contracts_do_not_import_provider_or_agent_sdks():
    forbidden_roots = {
        "anthropic",
        "openai",
        "langchain",
        "langgraph",
        "pydantic_ai",
    }
    violations: list[str] = []
    for relative_root in ("llm", "observability"):
        for path in (ROOT / relative_root).rglob("*.py"):
            for line, module in _imports(path):
                if module.split(".", 1)[0] in forbidden_roots:
                    violations.append(f"{path.relative_to(ROOT)}:{line} imports {module}")
    assert violations == []
