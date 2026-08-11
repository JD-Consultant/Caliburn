# 0059. `core` shared-kernel 邊界澄清：root-only 例外、`opks_integrity.py` 例外、guard 掃描範圍

- **狀態**：Accepted
- **日期**：2026-08-11
- **核准**：2026-08-11，owner 核准；guard 已同步落地（`_is_public_core_import()`
  於六個 consumer guard 強制底線私有 submodule 例外，非僅文件宣告）
- **研究**：[`2026-08-11-core-boundary-and-guard-corrections-research.md`](../specs/2026-08-11-core-boundary-and-guard-corrections-research.md)

## Context

[ADR 0058](0058-current-api-functional-modules-and-dependency-rules.md) 的規則 4
與規則 7 在 `core` 落地施工過程中出現兩個沒有被 0058 明確決定的邊界問題，第三
個是 AST guard 的掃描範圍問題：

1. 規則 4：「跨模組只能 import 模組 root 明確 re-export 的 public
   API；…不得建立聚合所有功能的全域 facade。」`core/__init__.py`
   實際上只有 docstring、零 re-export；production code 有 100 餘處直接
   `from app.core.<submodule> import …`（`domain`／`state`／`authority`／
   `persistence`／`journal`／`errors`／`model_outcome`／`opks_integrity`／
   `portable_schema`，以及 `domain` 自己底下的 `domain.task`／
   `domain.work_model` 等更深的具名 submodule）。這個現況在施工當下被寫進
   `apps/api/tests/test_job_analysis_dependencies.py` 的 test docstring，
   斷言「`core` 是共享 kernel，直接 import submodule 是既有、被接受的慣例」
   ——但 0058 從未做過這個決定，是實作者單方面認定。
2. 規則 7：「型別／port 進 `core` 必須同時符合：至少兩個功能真的消費、
   語意穩定且共同、零 IO／framework／transport。」
   `apps/api/app/core/opks_integrity.py` 的 `stale_invalid_opks_proposals()`
   內嵌完整 OPKS staleness 判斷邏輯，並直接寫死使用者可見繁中文案——這是
   domain policy，不是型別或 port。這個落差先前被以編輯 Accepted ADR 0058
   `## Consequences` 段落的方式「補記」，違反 `AGENTS.md` 工作紀律第 2 條
   「翻案開新號」；本 ADR 撤回那次不當編輯，把決策改放這裡。
3. `apps/api/scripts/**`（診斷／live-smoke 工具）與 `apps/api/tests/**`
   （測試）從未被納入任何 AST guard 的掃描範圍（掃描根固定在 `app/`）；
   `apps/api/scripts/job_analysis_opks_elicitation_live_smoke.py` 目前確實
   直接 import `app.documents.authoring`／`app.opks.llm` 等非 curated
   路徑。這個「scripts／tests 在功能模組依賴圖之外」的現況同樣沒有被任何
   文件正式記錄過。

三者共同的根因：真實的架構決策在施工當下用 test docstring 或事後編輯 Accepted
ADR 的方式定案，沒有走 0058 自己要求的 ADR 流程。本 ADR 補齊這三個決策。

## Decision

1. **`core` 免除規則 4 的「root-only import」限制，且不設具名 submodule 清單
   作為限制條件。** `core` 是 shared kernel，不是功能模組：它天生要被所有
   功能模組消費，若把 `core` 底下所有子模組（目前含 `core.domain`／
   `core.state`／`core.authority`／`core.persistence`／`core.journal`／
   `core.errors`／`core.model_outcome`／`core.opks_integrity`／
   `core.portable_schema`，以及 `core.domain` 自己再往下的
   `core.domain.task`／`core.domain.work_model` 等九個子模組）的所有 public
   型別都攤平進單一 `core/__init__.py`，會製造一個遠超過 0058 規則 11 後方
   review-trigger 段落所定的 25-public-names 拆分審查門檛的巨型 facade，
   且每次 `core` 新增型別都要同步兩處。改為承認 `core` 任意深度的具名
   submodule 本身就是 public interface——這是 Python 生態系
   shared-kernel package 的常見模式（stdlib 的 `os.path`、
   `collections.abc`、`xml.etree.ElementTree`、`urllib.parse` 都是直接
   import submodule，沒有把全部型別攤平到頂層的 facade）。上面列出的九個
   子模組是目前實際存在、被消費的例子，**不是窮舉清單**；`core` 之下任何
   非底線開頭的具名 submodule，不論巢狀幾層，都自動屬於 public interface，
   新增子模組不需要回頭修這份 ADR。`core/__init__.py` 維持目前的
   docstring-only 狀態，不建 root facade；guard test 對 `app.core` 的檢查
   本來就是前綴比對（`module == "app.core" or module.startswith("app.core.")`），
   已經涵蓋任意深度，這條決策只是把既有的 guard 行為正式記錄下來，不需要
   另外限制允許的 core submodule 集合。規則 4 對五個功能模組
   （`documents`／`task_analysis`／`opks`／`consultation`／`export`）與
   `api`／`adapters` composition surfaces 仍然全部有效——只有 `core` 本身
   例外，且只有這一種例外。
2. **`core/opks_integrity.py` 是規則 7 的一個記錄在案、需持續留意的例外。**
   它裝的是 OPKS 專屬 staleness／pruning policy（含使用者可見繁中文案），
   不是純型別或 port；接受這個例外的理由是替代方案（讓
   `documents → opks` 多一條規則 2 未授權的跨功能邊）代價更高——會把單一
   authority transaction 拆成多步跨模組協調，且違反規則 2 明定的唯一允許
   跨功能方向（`consultation → task_analysis/opks`）。這不是全面放寬規則
   7；只有這一個檔案被記錄為例外，未來任何新的「兩個功能都要用」但帶
   policy 的東西，都要重新走一次評估，不能直接援引這個先例。
3. **`apps/api/scripts/**` 與 `apps/api/tests/**` 在 0058 定義的功能模組
   依賴圖之外。** 兩者是診斷／驗證工具，不是 production 執行路徑，允許因為
   診斷或測試需求直接 reach 進 feature 的 internal 實作（例如
   `job_analysis_opks_elicitation_live_smoke.py` 需要組出特定場景直接操作
   `app.opks.llm` 的 wire 層）。AST guard 的掃描根維持固定在 `app/`，不擴及
   `scripts/`／`tests/`。

## Consequences

`apps/api/tests/test_job_analysis_dependencies.py` 的相關 test docstring
（`test_api_only_imports_feature_module_roots`）改為引用本 ADR，取代原本
「既有、被接受的慣例」這種無出處的斷言。ADR 0058 `## Consequences`
段落尾端那句由 `ef090a5` 事後加註的例外句子撤回；`core/opks_integrity.py`
的例外地位改由本 ADR 承載。

`core` 免除 root-only 限制不代表 `core` 可以無限膨脹——規則 7 的四項判準
（至少兩個功能真的消費、語意穩定且共同、零 IO／framework／transport，加上
本 ADR 記錄的單一 policy 例外）仍然是進入 `core` 的門檻；只是「怎麼從
`core` 匯出」這件事不再要求單一 root facade。
