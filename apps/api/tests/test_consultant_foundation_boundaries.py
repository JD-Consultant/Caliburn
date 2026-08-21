"""The migration foundation uses framework primitives without old-system glue."""

from __future__ import annotations

import ast
from pathlib import Path

from app.consultant.state import ConsultantThreadState


API_ROOT = Path(__file__).parents[1]
FOUNDATION_ROOTS = (
    API_ROOT / "app" / "consultant",
    API_ROOT / "app" / "adapters" / "langgraph",
)


def _production_files() -> list[Path]:
    return sorted(
        path
        for root in FOUNDATION_ROOTS
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_consultant_foundation_uses_purpose_first_state_names() -> None:
    names = {name.lower() for name in ConsultantThreadState.__annotations__}
    retired_names = {
        "work_model",
        "focus",
        "focus_plan",
        "progress",
        "agenda",
        "proposal",
        "pending_proposals",
        "current_jd",
        "operation",
    }

    assert names.isdisjoint(retired_names)


def test_consultant_foundation_does_not_bridge_old_writers_models_or_rag() -> None:
    forbidden_prefixes = (
        "app.core",
        "app.documents",
        "app.task_analysis",
        "app.opks",
        "app.consultation",
        "app.adapters.openrouter",
        "ocs_contract",
        "indexer_contract",
        "jd_ocs_indexer",
        "jd_pdf_to_json",
        "embedder",
    )
    violations = {
        str(path.relative_to(API_ROOT)): sorted(
            module
            for module in _imports(path)
            if module.startswith(forbidden_prefixes)
        )
        for path in _production_files()
    }

    assert not {path: imports for path, imports in violations.items() if imports}


def test_consultant_foundation_directly_imports_langgraph_persistence() -> None:
    imports = set().union(*(_imports(path) for path in _production_files()))

    assert "langgraph.graph" in imports
    assert "langgraph.checkpoint.postgres.aio" in imports
    assert "langgraph.store.postgres.aio" in imports


def test_task6_hard_cut_removes_retired_workspace_modules_and_imports() -> None:
    retired_files = tuple(
        API_ROOT / "app" / "consultant" / f"candidate_{suffix}.py"
        for suffix in ("tool", "wire", "workspace")
    )
    assert all(not path.exists() for path in retired_files)

    retired_terms = tuple(
        "candidate_" + suffix
        for suffix in ("tool", "wire", "workspace")
    )
    for path in _production_files():
        source = path.read_text(encoding="utf-8")
        assert not any(term in source for term in retired_terms)
