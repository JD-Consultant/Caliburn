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


def test_candidate_workspace_depends_only_on_current_document_authority() -> None:
    path = API_ROOT / "app" / "consultant" / "candidate_workspace.py"
    imports = _imports(path)
    application_imports = {
        module for module in imports if module.startswith(("app.", "packages."))
    }

    assert application_imports <= {
        "app.consultant.candidate_wire",
        "app.consultant.document_authority",
        "app.consultant.document_review",
        "app.consultant.results",
        "app.consultant.state",
    }
    assert not any(
        module.startswith(
            (
                "app.api",
                "app.core",
                "app.documents",
                "app.task_analysis",
                "app.opks",
                "app.consultation",
                "app.adapters",
                "ocs_contract",
                "indexer_contract",
            )
        )
        for module in imports
    )
