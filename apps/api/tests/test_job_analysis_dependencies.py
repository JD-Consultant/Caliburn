"""Static guards for the current-only API and engine boundaries."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


API_DIR = Path(__file__).parents[1]
ROOT = API_DIR / "app" / "job_analysis"
CORE_ROOT = API_DIR / "app" / "core"
DOCUMENTS_ROOT = API_DIR / "app" / "documents"
TASK_ANALYSIS_ROOT = API_DIR / "app" / "task_analysis"
OPKS_ROOT = API_DIR / "app" / "opks"
CONSULTATION_ROOT = API_DIR / "app" / "consultation"
COMPOSITION_SURFACES = (
    API_DIR / "app" / "api" / "job_analysis_deps.py",
    API_DIR / "app" / "api" / "routes" / "job_analysis.py",
    API_DIR / "app" / "adapters" / "job_analysis_postgres",
)


def _imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.lineno, node.module))
    return found


def _surface_files(roots: tuple[Path, ...]) -> tuple[Path, ...]:
    files: list[Path] = []
    for root in roots:
        assert root.exists(), f"missing current composition root: {root}"
        files.extend(root.rglob("*.py") if root.is_dir() else [root])
    return tuple(sorted(files, key=lambda path: path.as_posix()))


def test_only_current_api_route_modules_exist():
    route_names = {path.name for path in (API_DIR / "app" / "api" / "routes").glob("*.py")}
    assert route_names == {"__init__.py", "job_analysis.py"}


def test_current_composition_does_not_import_removed_paths():
    forbidden = (
        "app.interview",
        "app.interview_vnext",
        "app.job_authoring",
        "app.services",
        "app.schemas",
        "indexer_contract",
        "ocs_contract",
    )
    violations = []
    for path in _surface_files(COMPOSITION_SURFACES):
        for line, module in _imports(path):
            if any(module == root or module.startswith(f"{root}.") for root in forbidden):
                violations.append(f"{path.relative_to(API_DIR)}:{line} imports {module}")
    assert violations == []


def test_core_imports_only_stdlib_pydantic_or_itself():
    """`app.core`（含 `app.core.domain`）是 shared kernel:只能 import stdlib、pydantic
    或自己。這已隱含禁止 FastAPI、SQLAlchemy、HTTPX、OpenPyXL,以及任何
    `app.job_analysis.application`／feature／adapter 模組(ADR 0058 規則 1)。
    """
    assert CORE_ROOT.exists(), f"missing shared kernel: {CORE_ROOT}"
    violations = []
    for path in CORE_ROOT.rglob("*.py"):
        for line, module in _imports(path):
            root = module.split(".", 1)[0]
            allowed = (
                root in sys.stdlib_module_names
                or root == "pydantic"
                or module == "app.core"
                or module.startswith("app.core.")
            )
            if not allowed:
                violations.append(f"{path.relative_to(CORE_ROOT)}:{line} imports {module}")
    assert violations == []


def test_documents_imports_only_core_stdlib_pydantic_or_itself():
    """`app.documents` 是 feature module:只能 import stdlib、pydantic、`app.core`
    或自己。這已隱含禁止 FastAPI、SQLAlchemy、HTTPX、OpenPyXL,以及任何
    `app.job_analysis`／adapter 模組(ADR 0058 規則 2)。
    """
    assert DOCUMENTS_ROOT.exists(), f"missing feature module: {DOCUMENTS_ROOT}"
    violations = []
    for path in DOCUMENTS_ROOT.rglob("*.py"):
        for line, module in _imports(path):
            root = module.split(".", 1)[0]
            allowed = (
                root in sys.stdlib_module_names
                or root == "pydantic"
                or module == "app.core"
                or module.startswith("app.core.")
                or module == "app.documents"
                or module.startswith("app.documents.")
            )
            if not allowed:
                violations.append(f"{path.relative_to(DOCUMENTS_ROOT)}:{line} imports {module}")
    assert violations == []


def test_task_analysis_imports_only_core_stdlib_pydantic_or_itself():
    """`app.task_analysis` 是 feature module:只能 import stdlib、pydantic、`app.core`
    或自己。這已隱含禁止 FastAPI、SQLAlchemy、HTTPX、OpenPyXL、具體的
    `OpenRouterAdapter`,以及任何 `app.job_analysis`／`app.opks`／adapter 模組
    (ADR 0058 規則 2)。
    """
    assert TASK_ANALYSIS_ROOT.exists(), f"missing feature module: {TASK_ANALYSIS_ROOT}"
    violations = []
    for path in TASK_ANALYSIS_ROOT.rglob("*.py"):
        for line, module in _imports(path):
            root = module.split(".", 1)[0]
            allowed = (
                root in sys.stdlib_module_names
                or root == "pydantic"
                or module == "app.core"
                or module.startswith("app.core.")
                or module == "app.task_analysis"
                or module.startswith("app.task_analysis.")
            )
            if not allowed:
                violations.append(
                    f"{path.relative_to(TASK_ANALYSIS_ROOT)}:{line} imports {module}"
                )
    assert violations == []


def test_opks_imports_only_core_stdlib_pydantic_or_itself():
    """`app.opks` 是 feature module:只能 import stdlib、pydantic、`app.core`
    或自己。這已隱含禁止 FastAPI、SQLAlchemy、HTTPX、OpenPyXL、具體的
    `OpenRouterAdapter`,以及任何 `app.job_analysis`／`app.task_analysis`／
    `app.documents`／adapter 模組(ADR 0058 規則 2)——`opks` 與 `task_analysis`
    互不 import 對方,即使兩者都會被 `consultation`(Task 6)一起消費。
    """
    assert OPKS_ROOT.exists(), f"missing feature module: {OPKS_ROOT}"
    violations = []
    for path in OPKS_ROOT.rglob("*.py"):
        for line, module in _imports(path):
            root = module.split(".", 1)[0]
            allowed = (
                root in sys.stdlib_module_names
                or root == "pydantic"
                or module == "app.core"
                or module.startswith("app.core.")
                or module == "app.opks"
                or module.startswith("app.opks.")
            )
            if not allowed:
                violations.append(f"{path.relative_to(OPKS_ROOT)}:{line} imports {module}")
    assert violations == []


def test_consultation_imports_only_core_task_analysis_opks_stdlib_pydantic_or_itself():
    """`app.consultation` 是 ADR 0058 規則 2 唯一的具名例外:orchestrator 可以同時
    import `app.task_analysis`／`app.opks`,但只能拿它們的 root public API
    (`__init__.py` curated 的 surface),不得直接 reach into 對方的 implementation
    file(例如 `app.task_analysis.operation`／`app.opks.generation`)。

    這條規則在 `ast.ImportFrom` 層是可以精確檢查的:`from app.task_analysis import X`
    的 `node.module` 一律恰好是字串 `"app.task_analysis"`,不管 `X` 是什麼名字;
    `from app.task_analysis.operation import X` 的 `node.module` 則是
    `"app.task_analysis.operation"`。所以「只准 root、禁止 submodule」不是用
    `startswith` 判斷(那會兩者都放行),而是用「必須恰好等於 root 字串」判斷——這與
    `documents`／`task_analysis`／`opks` 三個既有 guard 對『自己』用
    `== root or startswith(f"{root}.")`(自己允許 submodule)刻意不同:consultation
    對外只信任兩個 feature module 的 curated `__init__`,對自己(`app.consultation`)
    才允許 submodule(`durable_turn.py`／`turn.py` 互相 import)。

    這個檢查不覆蓋 `import app.task_analysis`(不透過 `from`)之後改用屬性存取
    reach 進 submodule 的邊界案例——repo 現行慣例一律用 `from X import Y`,沒有這種
    寫法;若未來出現,需要另外補 `ast.Attribute` 層的檢查。
    """
    assert CONSULTATION_ROOT.exists(), f"missing feature module: {CONSULTATION_ROOT}"
    violations = []
    for path in CONSULTATION_ROOT.rglob("*.py"):
        for line, module in _imports(path):
            root = module.split(".", 1)[0]
            allowed = (
                root in sys.stdlib_module_names
                or root == "pydantic"
                or module == "app.core"
                or module.startswith("app.core.")
                or module == "app.consultation"
                or module.startswith("app.consultation.")
                or module == "app.task_analysis"
                or module == "app.opks"
            )
            if not allowed:
                violations.append(
                    f"{path.relative_to(CONSULTATION_ROOT)}:{line} imports {module}"
                )
    assert violations == []


def test_job_analysis_never_imports_persistence_or_web_frameworks():
    forbidden = {"alembic", "asyncpg", "fastapi", "psycopg", "sqlalchemy", "starlette"}
    violations = []
    for path in ROOT.rglob("*.py"):
        for line, module in _imports(path):
            if module.split(".", 1)[0] in forbidden:
                violations.append(f"{path.relative_to(ROOT)}:{line} imports {module}")
    assert violations == []
