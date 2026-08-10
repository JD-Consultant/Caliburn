"""Static guards for the current-only API and engine boundaries."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


API_DIR = Path(__file__).parents[1]
CORE_ROOT = API_DIR / "app" / "core"
DOCUMENTS_ROOT = API_DIR / "app" / "documents"
TASK_ANALYSIS_ROOT = API_DIR / "app" / "task_analysis"
OPKS_ROOT = API_DIR / "app" / "opks"
CONSULTATION_ROOT = API_DIR / "app" / "consultation"
EXPORT_ROOT = API_DIR / "app" / "export"
XLSX_ADAPTER_ROOT = API_DIR / "app" / "adapters" / "xlsx"
# 兩者才是真正的 composition root(ADR 0058):`app/api` 組裝 HTTP 與 transport
# mapping,`app/adapters` 實作各 feature module 擁有的 port——兩者都可以 import
# FastAPI／SQLAlchemy／HTTPX／OpenPyXL 與任何 feature module 的 public API。
COMPOSITION_SURFACES = (
    API_DIR / "app" / "api",
    API_DIR / "app" / "adapters",
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


def _imported_names(path: Path, module_name: str) -> list[tuple[int, str]]:
    """Names bound by `from <module_name> import X, Y` (level-0 only) in `path`.

    `_imports()` collapses an `ast.ImportFrom` down to its `node.module` string,
    which is exactly what makes `from app.task_analysis import operation` and
    `from app.task_analysis import TaskAnalysisModelPort` indistinguishable at
    that level — both report `module == "app.task_analysis"`. This helper stays
    static-AST-only like `_imports()`, but also surfaces `node.names` so a
    caller can check each imported name against a curated surface (e.g.
    `__all__`), not just the module string.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module == module_name
        ):
            found.extend((node.lineno, alias.name) for alias in node.names)
    return found


def _surface_files(roots: tuple[Path, ...]) -> tuple[Path, ...]:
    files: list[Path] = []
    for root in roots:
        assert root.exists(), f"missing current composition root: {root}"
        files.extend(root.rglob("*.py") if root.is_dir() else [root])
    return tuple(sorted(files, key=lambda path: path.as_posix()))


def test_only_current_route_modules_exist():
    route_names = {path.name for path in (API_DIR / "app" / "api" / "routes").glob("*.py")}
    assert route_names == {
        "__init__.py",
        "documents.py",
        "consultation.py",
        "opks.py",
        "export.py",
    }


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


def test_api_only_imports_feature_module_roots():
    """composition-root／infrastructure 檔案(`app/api`、`app/adapters`、
    `app_factory.py`、`main.py`、`database.py`、`config.py`、`observability.py`、
    `logging_config.py`、`models/**`)只能 import feature module 的 root public
    API,不得直接 reach 進 `app.documents.xxx`／`app.opks.xxx`／
    `app.task_analysis.xxx`／`app.consultation.xxx`／`app.export.xxx` 的
    implementation file(ADR 0058 規則 4)。`app.core` 的 submodule(例如
    `app.core.persistence`)不在這條規則內——`core` 是共享 kernel,沒有單一
    curated root 收斂全部型別,直接 import submodule 是既有、被接受的慣例。

    掃描範圍是 `app/` 整棵樹扣掉 `core`／`documents`／`task_analysis`／`opks`／
    `consultation`／`export` 六個 feature/core package,而不是只掃 `app/api`——
    之前 `app_factory.py`／`main.py`／`database.py`／`config.py`／
    `observability.py`／`models/**` 這些檔案完全沒有任何 guard 覆蓋,一次意外的
    rename 或搬移也不會被任何測試擋下。`app/adapters` 現在也落在這條規則內;
    既有 adapter 只 import `app.core.*`(允許,不受這條規則約束)與
    `app.export` 的 curated root(`ExportDocument`／`ExportOpksEntry`／
    `ExportTaskEntry` 都在 `app.export.__all__` 內),不會被誤判。

    跟 consultation guard(`da83d9c`)同一個理由:只檢查 `node.module` 的
    prefix 不夠——`from app.documents import authoring` 的 `node.module` 恰好是
    `"app.documents"`,不 `startswith("app.documents.")`,但 `authoring` 其實是
    `documents/__init__.py` 自己 `from .authoring import ...` side effect 綁上去
    的真實 submodule,不是 curated export。所以這裡額外用 `_imported_names()`
    檢查每個被 import 的名字是否真的在對應 feature root 的 `__all__` 裡。
    """
    import app.consultation as consultation_module
    import app.documents as documents_module
    import app.export as export_module
    import app.opks as opks_module
    import app.task_analysis as task_analysis_module

    feature_roots = ("documents", "opks", "task_analysis", "consultation", "export")
    curated_surfaces: dict[str, frozenset[str]] = {
        "app.documents": frozenset(documents_module.__all__),
        "app.opks": frozenset(opks_module.__all__),
        "app.task_analysis": frozenset(task_analysis_module.__all__),
        "app.consultation": frozenset(consultation_module.__all__),
        "app.export": frozenset(export_module.__all__),
    }

    # Canary — proves the loophole this guard closes actually exists. `authoring`
    # is a real submodule that `documents/__init__.py` binds onto `app.documents`
    # (via its own `from .authoring import ...`), so `from app.documents import
    # authoring` reports the exact same `node.module` ("app.documents") as any
    # legitimate curated import — the old prefix-only check could not tell them
    # apart. It must not be part of the curated `__all__` surface, and the
    # name-level check below (not the prefix check above it) is what flags it.
    synthetic = ast.parse("from app.documents import authoring\n").body[0]
    assert isinstance(synthetic, ast.ImportFrom)
    assert synthetic.module == "app.documents"  # same as a legitimate import
    canary_name = synthetic.names[0].name
    assert canary_name == "authoring"
    assert canary_name not in curated_surfaces["app.documents"]

    app_root = API_DIR / "app"
    assert app_root.exists(), f"missing app package: {app_root}"
    excluded_roots = {"core", "documents", "task_analysis", "opks", "consultation", "export"}
    scan_files: list[Path] = []
    for entry in sorted(app_root.iterdir()):
        if entry.is_dir():
            if entry.name in excluded_roots or entry.name == "__pycache__":
                continue
            scan_files.extend(entry.rglob("*.py"))
        elif entry.suffix == ".py":
            scan_files.append(entry)

    violations = []
    for path in scan_files:
        for line, module in _imports(path):
            for root in feature_roots:
                prefix = f"app.{root}."
                if module.startswith(prefix):
                    violations.append(
                        f"{path.relative_to(API_DIR)}:{line} imports {module}"
                    )
        for module_name, curated in curated_surfaces.items():
            for line, name in _imported_names(path, module_name):
                if name not in curated:
                    violations.append(
                        f"{path.relative_to(API_DIR)}:{line} imports "
                        f"non-curated name {name!r} from {module_name}"
                    )
    assert violations == []


def test_core_imports_only_stdlib_pydantic_or_itself():
    """`app.core`（含 `app.core.domain`）是 shared kernel:只能 import stdlib、pydantic
    或自己。這已隱含禁止 FastAPI、SQLAlchemy、HTTPX、OpenPyXL,以及任何
    feature／adapter 模組(ADR 0058 規則 1)。
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
    adapter 模組(ADR 0058 規則 2)。
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
    `OpenRouterAdapter`,以及任何 `app.opks`／adapter 模組(ADR 0058 規則 2)。
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
    `OpenRouterAdapter`,以及任何 `app.task_analysis`／`app.documents`／
    adapter 模組(ADR 0058 規則 2)——`opks` 與 `task_analysis` 互不 import
    對方,即使兩者都會被 `consultation` 一起消費。
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


def test_export_imports_only_core_stdlib_pydantic_or_itself():
    """`app.export` 是 feature module:純 deterministic Current State 投影,只能
    import stdlib、pydantic、`app.core` 或自己。這已隱含禁止 FastAPI、
    SQLAlchemy、HTTPX、以及最重要的——OpenPyXL(render-time adapter 屬於
    `app.adapters.xlsx`,不屬於這個 feature module,ADR 0058 規則 2、3)。
    """
    assert EXPORT_ROOT.exists(), f"missing feature module: {EXPORT_ROOT}"
    violations = []
    for path in EXPORT_ROOT.rglob("*.py"):
        for line, module in _imports(path):
            root = module.split(".", 1)[0]
            allowed = (
                root in sys.stdlib_module_names
                or root == "pydantic"
                or module == "app.core"
                or module.startswith("app.core.")
                or module == "app.export"
                or module.startswith("app.export.")
            )
            if not allowed:
                violations.append(f"{path.relative_to(EXPORT_ROOT)}:{line} imports {module}")
    assert violations == []


def test_consultation_imports_only_core_task_analysis_opks_stdlib_pydantic_or_itself():
    """`app.consultation` 是 ADR 0058 規則 2 唯一的具名例外:orchestrator 可以同時
    import `app.task_analysis`／`app.opks`,但只能拿它們的 root public API
    (`__init__.py` curated 的 surface),不得直接 reach into 對方的 implementation
    file(例如 `app.task_analysis.operation`／`app.opks.generation`)。

    這條規則在 `ast.ImportFrom` 層可以精確檢查「module」:`from app.task_analysis
    import X` 的 `node.module` 一律恰好是字串 `"app.task_analysis"`,不管 `X` 是什麼
    名字;`from app.task_analysis.operation import X` 的 `node.module` 則是
    `"app.task_analysis.operation"`。所以「只准 root、禁止 submodule」不是用
    `startswith` 判斷(那會兩者都放行),而是用「必須恰好等於 root 字串」判斷——這與
    `documents`／`task_analysis`／`opks` 三個既有 guard 對『自己』用
    `== root or startswith(f"{root}.")`(自己允許 submodule)刻意不同:consultation
    對外只信任兩個 feature module 的 curated `__init__`,對自己(`app.consultation`)
    才允許 submodule(`durable_turn.py`／`turn.py` 互相 import)。

    只看 `node.module` 還不夠:`app.task_analysis.__init__` 內部自己
    `from .operation import ...`,這個 side effect 會把 `operation` 這個
    submodule 物件綁到 `app.task_analysis` 這個 package 物件上,讓
    `from app.task_analysis import operation` 這種寫法的 `node.module` 也恰好等於
    `"app.task_analysis"`——跟合法的 `from app.task_analysis import
    TaskAnalysisModelPort` 在 module 字串層完全無法分辨,但拿到的其實是完整的
    submodule,等於直接 reach into implementation file,正是這條規則要擋的洞。
    所以這裡額外用 `_imported_names()` 檢查每個被 import 的「名字」本身是否真的在
    `app.task_analysis.__all__`／`app.opks.__all__` 這個 curated surface 裡——這步
    需要真的 `import app.task_analysis`／`import app.opks` 來讀 `__all__`,而不是
    純 AST(這是測試碼本身要做的事,不是被檢查的 production import 邊界,見下方
    canary)。

    這個檢查不覆蓋 `import app.task_analysis`(不透過 `from`)之後改用屬性存取
    reach 進 submodule 的邊界案例——repo 現行慣例一律用 `from X import Y`,沒有這種
    寫法;若未來出現,需要另外補 `ast.Attribute` 層的檢查。
    """
    import app.opks as opks_module
    import app.task_analysis as task_analysis_module

    curated_surfaces = {
        "app.task_analysis": frozenset(task_analysis_module.__all__),
        "app.opks": frozenset(opks_module.__all__),
    }

    # Canary — proves the loophole this guard closes actually exists and that
    # the fix below is what closes it. `operation` is a real submodule that
    # Python's import machinery binds onto `app.task_analysis` (because
    # `task_analysis/__init__.py` does `from .operation import ...`), so
    # `from app.task_analysis import operation` reports the exact same
    # `node.module` as any legitimate import from that package — the old
    # module-only check could not tell them apart. It must not be part of the
    # curated `__all__` surface, and the name-level check further below (not
    # the module-level check) is what would flag it.
    synthetic = ast.parse("from app.task_analysis import operation\n").body[0]
    assert isinstance(synthetic, ast.ImportFrom)
    assert synthetic.module == "app.task_analysis"  # same as a legitimate import
    canary_name = synthetic.names[0].name
    assert canary_name == "operation"
    assert canary_name not in curated_surfaces["app.task_analysis"]

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
        for module_name, curated in curated_surfaces.items():
            for line, name in _imported_names(path, module_name):
                if name not in curated:
                    violations.append(
                        f"{path.relative_to(CONSULTATION_ROOT)}:{line} imports "
                        f"non-curated name {name!r} from {module_name}"
                    )
    assert violations == []


def test_openpyxl_is_confined_to_the_xlsx_adapter():
    """ADR 0058:OpenPyXL 是 render-time 細節,只能住在 `app.adapters.xlsx`——
    不得洩漏進 `app.export`(純投影)、其他 feature module,或 `app/api`。
    """
    assert XLSX_ADAPTER_ROOT.exists(), f"missing xlsx adapter: {XLSX_ADAPTER_ROOT}"
    violations = []
    for path in (API_DIR / "app").rglob("*.py"):
        if XLSX_ADAPTER_ROOT in path.parents:
            continue
        for line, module in _imports(path):
            if module == "openpyxl" or module.startswith("openpyxl."):
                violations.append(f"{path.relative_to(API_DIR)}:{line} imports {module}")
    assert violations == []
