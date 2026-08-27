"""Final cutover guard: no second product runtime or authority may remain."""

from __future__ import annotations

import ast
import json
from pathlib import Path


API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = API_ROOT / "app"


def _production_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_old_runtime_modules_routes_and_web_surfaces_are_absent() -> None:
    removed = (
        APP_ROOT / "task_analysis",
        APP_ROOT / "opks",
        APP_ROOT / "consultation",
        APP_ROOT / "core",
        APP_ROOT / "documents",
        APP_ROOT / "models",
        APP_ROOT / "adapters" / "postgres",
        APP_ROOT / "api" / "routes" / "documents.py",
        APP_ROOT / "api" / "routes" / "consultation.py",
        APP_ROOT / "api" / "routes" / "opks.py",
        APP_ROOT / "api" / "routes" / "export.py",
        APP_ROOT / "api" / "documents_mapper.py",
        APP_ROOT / "api" / "consultation_mapper.py",
        APP_ROOT / "api" / "opks_mapper.py",
        APP_ROOT / "adapters" / "openrouter" / "openrouter.py",
        APP_ROOT / "adapters" / "openrouter" / "openrouter_evidence.py",
        REPO_ROOT / "apps" / "web" / "src" / "features" / "documents",
        REPO_ROOT / "apps" / "web" / "src" / "features" / "consultation",
        REPO_ROOT / "apps" / "web" / "src" / "features" / "opks",
        REPO_ROOT / "apps" / "web" / "src" / "features" / "export",
        REPO_ROOT
        / "apps"
        / "web"
        / "src"
        / "app"
        / "workspace"
        / "[document_id]"
        / "_components",
    )
    assert [str(path.relative_to(REPO_ROOT)) for path in removed if path.exists()] == []


def test_production_import_graph_has_no_old_or_rag_runtime() -> None:
    banned = (
        "app.core",
        "app.task_analysis",
        "app.opks",
        "app.consultation",
        "app.documents",
        "app.adapters.postgres",
        "app.adapters.openrouter.openrouter",
        "app.adapters.openrouter.openrouter_evidence",
        "ocs_contract",
        "indexer_contract",
    )
    violations: list[str] = []
    for path in APP_ROOT.rglob("*.py"):
        for module in _production_imports(path):
            if module.startswith(banned):
                violations.append(f"{path.relative_to(API_ROOT)} -> {module}")
    assert violations == []


def test_only_fresh_consultant_root_migration_and_no_old_tables_remain() -> None:
    versions = API_ROOT / "alembic" / "versions"
    migrations = sorted(path.name for path in versions.glob("*.py"))
    assert migrations == ["0018_consultant_runtime_root.py"]
    migration = (versions / migrations[0]).read_text(encoding="utf-8")
    assert 'down_revision = None' in migration
    legacy_tables = (
        "job_analysis_documents",
        "job_analysis_jd_tasks",
        "job_analysis_jd_duties",
        "job_analysis_proposals",
        "job_analysis_opks_items",
        "job_analysis_opks_proposals",
        "job_analysis_journal",
    )
    production = "\n".join(
        path.read_text(encoding="utf-8")
        for path in APP_ROOT.rglob("*.py")
    )
    assert [name for name in legacy_tables if name in production or name in migration] == []


def test_generated_contract_has_only_consultant_and_problem_surfaces() -> None:
    schema_path = (
        REPO_ROOT
        / "packages"
        / "job-analysis-contract"
        / "schema"
        / "job-analysis-workspace.schema.json"
    )
    definitions = json.loads(schema_path.read_text(encoding="utf-8"))["$defs"]
    banned_exact = {
        "DirectDocumentEditWrite",
        "DocumentMetadataWrite",
        "DocumentMetadataView",
        "DocumentSummary",
        "JdHeaderView",
        "JobAnalysisWorkspaceView",
        "EmployeeTurnWrite",
        "ProposalDecisionWrite",
        "OpksProposalDecisionWrite",
        "TaskOrderWrite",
        "OpksOrderWrite",
        "DutyOrderWrite",
    }
    banned_prefixes = (
        "ActiveQuestion",
        "CurrentJd",
        "ProposalJd",
        "ProposalView",
        "OpksProposal",
        "WorkModel",
    )
    assert sorted(
        name
        for name in definitions
        if name in banned_exact or name.startswith(banned_prefixes)
    ) == []


def test_only_current_document_has_a_public_direct_edit_route() -> None:
    consultant_routes = (
        APP_ROOT / "api" / "routes" / "consultant.py"
    ).read_text(encoding="utf-8")

    assert '"/{document_id}/current-document"' in consultant_routes
    assert '"/{document_id}/approved-document"' not in consultant_routes
