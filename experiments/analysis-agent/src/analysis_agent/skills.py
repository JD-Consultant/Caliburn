"""Trusted package methods, disclosed through the official Skills middleware.

Only this directory is a host filesystem mount. Discovery and model reads use
the same CompositeBackend path mapping; no filesystem middleware hooks run.
"""
from pathlib import Path

from deepagents.backends import CompositeBackend, FilesystemBackend
from deepagents.backends.protocol import BackendProtocol, GrepResult, LsResult, ReadResult
from deepagents.middleware.skills import SkillsMiddleware


class SkillAssets(BackendProtocol):
    """Read-only capability over bundled assets, not a general host backend.

    download_files is for official metadata discovery, not a model tool.
    Write/edit/delete/upload/execute implementations are deliberately absent.
    """

    def __init__(self):
        self._files = FilesystemBackend(root_dir=Path(__file__).with_suffix(''), virtual_mode=True)

    def ls(self, path: str):
        return self._files.ls(path)

    def read(self, file_path: str, offset: int = 0, limit: int = 2000):
        try:
            return self._files.read(file_path, offset=offset, limit=limit)
        except ValueError:
            # A routed Windows drive path can pass the tool's virtual-path
            # validation but fail FilesystemBackend containment after remap.
            # It is a model-correctable input error, not a failed service run.
            return ReadResult(error='Invalid skill asset path; use a listed /skills/ path')

    def grep(self, pattern: str, path: str | None = None, glob: str | None = None, *, max_count: int | None = None):
        return self._files.grep(pattern, path, glob, max_count=max_count)

    def download_files(self, paths: list[str]):
        return self._files.download_files(paths)


class _NoFiles(BackendProtocol):
    """Empty fallback when the service has no Memory Store; never mounts cwd."""

    def ls(self, path: str):
        return LsResult(entries=[]) if path == '/' else LsResult(error='Path is not available')

    def read(self, file_path: str, offset: int = 0, limit: int = 2000):
        return ReadResult(error='Path is not available')

    def grep(self, pattern: str, path: str | None = None, glob: str | None = None, *, max_count: int | None = None):
        return GrepResult(matches=[]) if path in (None, '/') else GrepResult(error='Path is not available')


def analysis_files(assets: SkillAssets, memory: BackendProtocol | None = None):
    # Composite strips /skills/ for the asset backend, and restores it in ls,
    # grep and download results. Never advertise asset-local paths like /name/.
    return CompositeBackend(default=memory if memory is not None else _NoFiles(),
                            routes={'/skills/': assets})


def analysis_skills(assets: SkillAssets):
    return SkillsMiddleware(
        backend=analysis_files(assets), sources=[('/skills/', 'Analysis methods')],
        system_prompt="""## 按需分析方法
{skills_locations}{skills_load_warnings}
{skills_list}
以上僅是方法名稱、用途及讀取路徑。需要該方法時，使用既有 read_file 讀取列出的
SKILL.md（limit=1000）；已讀且仍在有效上下文的內容不必重讀。不要每回合載入全部
Skills，也不必依序套用所有方法。直接接續員工的話，只追問目前重要且不清楚之處。
這些是唯讀方法參考，不是員工事實、不產生新 Agent、沒有必填 skill_ids 或固定表單。
此 Skills 接線只新增唯讀方法資產，不新增主機檔案、寫檔、執行程式、網路或 JD 操作能力。
既有 Memory 讀取、引用回查與 repair 仍依各工具說明使用，不受 Skills 目錄限制。
""",
    )
