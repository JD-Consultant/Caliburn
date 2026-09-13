"""Public SDK apply_diff over real native staging; no model, Store or SQL."""
import pytest
from deepagents.backends import StateBackend
from deepagents.middleware.filesystem import FilesystemState
from langgraph.graph import END, START, StateGraph

from caliburn_memory.patch import PATHS, MemoryPatchError, apply_staged_patch


class PatchState(FilesystemState):
    outcomes: list
    errors: list


def staged(files, patches):
    def seed(_state):
        for path, text in files.items():
            assert StateBackend().write(path, text).error is None
        return {}

    def apply(_state):
        outcomes, errors = [], []
        for path, diff in patches:
            try:
                outcomes.append(apply_staged_patch(path, diff))
            except MemoryPatchError as error:
                errors.append(str(error))
        return {"outcomes": outcomes, "errors": errors}

    graph = StateGraph(PatchState)
    graph.add_node("seed", seed)
    graph.add_node("apply", apply)
    graph.add_edge(START, "seed")
    graph.add_edge("seed", "apply")
    graph.add_edge("apply", END)
    return graph.compile().invoke({"messages": [], "outcomes": [], "errors": []})


def content(result, path=PATHS["knowledge"]):
    return result["files"][path]["content"]


@pytest.mark.parametrize("path", list(PATHS.values()))
def test_sdk_patch_changes_only_the_selected_staged_file(path):
    original = "# 工作\n例外由主管核准。\n其他責任不變。"
    other = next(candidate for candidate in PATHS.values() if candidate != path)
    result = staged({path: original, other: "其他檔案保留"}, [
        (path, "@@\n # 工作\n-例外由主管核准。\n+例外由處長核准。\n 其他責任不變。")])
    assert result["outcomes"] == [True] and result["errors"] == []
    assert content(result, path) == original.replace("主管", "處長")
    assert content(result, other) == "其他檔案保留"


@pytest.mark.parametrize("diff,reason", [
    ("", "nonempty"),
    ("@@\n unchanged", "added or removed"),
    ("*** Begin Patch\n*** Update File: /memory/knowledge.md\n@@\n-原文\n+新版\n*** End Patch", "diff body"),
    ("@@\n-原文\n+新版\n*** End Patch\nignored content", "diff body"),
    ("@@\n-原文\n+新版\n*** End of File\nignored content", "diff body"),
    ("@@\n-原文\n+新版\n***\nignored content", "diff body"),
    ("@@\n-原文\n+新版\n*** Update File: /memory/guide.md\n@@\n-x\n+y", "diff body"),
    ("@@\n-原文\n+" + "x" * 12001, "12000"),
])
def test_rejected_body_cannot_queue_a_partial_write(diff, reason):
    result = staged({PATHS["knowledge"]: "原文"}, [(PATHS["knowledge"], diff)])
    assert result["outcomes"] == [] and reason in result["errors"][0]
    assert content(result) == "原文"


@pytest.mark.parametrize("ending", ["*** End Patch", "*** End of File", "*** End of File\n*** End Patch"])
def test_official_terminal_markers_are_allowed_without_following_operations(ending):
    result = staged({PATHS["knowledge"]: "# 月報\n每月彙整\n細節不變"}, [
        (PATHS["knowledge"], "@@\n # 月報\n-每月彙整\n+每月首日彙整\n 細節不變\n" + ending)])
    assert result["outcomes"] == [True] and result["errors"] == []
    assert content(result) == "# 月報\n每月首日彙整\n細節不變"


def test_real_context_selects_repeated_chinese_case_and_preserves_other_scope():
    original = "# 案例 A\n- 每月回報\n# 案例 B\n- 每月回報\n  - 例外由主管判斷"
    result = staged({PATHS["knowledge"]: original}, [(PATHS["knowledge"],
        "@@\n # 案例 B\n-  - 每月回報\n+- 每週回報\n   - 例外由主管判斷")])
    assert result["errors"] == []
    assert content(result) == original.replace("# 案例 B\n- 每月回報", "# 案例 B\n- 每週回報")


@pytest.mark.parametrize("header", ["@@", "@@ 不存在的標題"])
def test_documented_sdk_first_match_limit_is_not_misrepresented_as_unique_matching(header):
    original = "# A\n每月回報\n# B\n每月回報"
    result = staged({PATHS["knowledge"]: original}, [
        (PATHS["knowledge"], header + "\n-每月回報\n+每週回報")])
    assert result["outcomes"] == [True]
    assert content(result) == "# A\n每週回報\n# B\n每月回報"


def test_missing_actual_context_is_an_error_and_does_not_write():
    original = "# A\n每月回報"
    result = staged({PATHS["knowledge"]: original}, [(PATHS["knowledge"],
        "@@\n # 不存在\n-每月回報\n+每週回報")])
    assert "Invalid Context" in result["errors"][0]
    assert "nothing from this patch was written" in result["errors"][0]
    assert content(result) == original


def test_late_hunk_failure_does_not_queue_the_successful_first_hunk():
    original = "# A\n每月回報\n# B\n原有責任"
    result = staged({PATHS["knowledge"]: original}, [(PATHS["knowledge"],
        "@@\n # A\n-每月回報\n+每週回報\n@@\n # B\n-不存在的責任\n+新責任")])
    assert "Invalid Context" in result["errors"][0]
    assert result["outcomes"] == [] and content(result) == original


def test_subsequent_patch_reads_the_latest_staged_text_and_no_change_is_false():
    path = PATHS["knowledge"]
    result = staged({path: "主管核准"}, [(path, "@@\n-主管核准\n+處長核准"),
        (path, "@@\n-處長核准\n+處長核准"), (path, "@@\n-處長核准\n+總監核准")])
    assert result["outcomes"] == [True, False, True] and result["errors"] == []
    assert content(result) == "總監核准"


def test_backward_hunks_fail_instead_of_reordering_the_sdk_search():
    original = "# A\n原A\n# B\n原B"
    result = staged({PATHS["knowledge"]: original}, [(PATHS["knowledge"],
        "@@\n # B\n-原B\n+新B\n@@\n # A\n-原A\n+新A")])
    assert result["errors"] and content(result) == original


def test_missing_file_and_non_memory_path_cannot_create_files():
    result = staged({}, [(PATHS["knowledge"], "@@\n-old\n+new"),
        ("/interviews/immutable/summary.md", "@@\n-old\n+new")])
    assert "File not found" in result["errors"][0]
    assert "Patch denied" in result["errors"][1]
    assert result.get("files", {}) == {}


def test_staging_context_is_required_and_is_not_replaced_with_host_files():
    with pytest.raises(RuntimeError, match="graph"):
        apply_staged_patch(PATHS["knowledge"], "@@\n-old\n+new")
