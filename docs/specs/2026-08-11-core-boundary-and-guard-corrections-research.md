# `core` 邊界與 AST guard 修正 — 研究與診斷

## 來源

外部審核者對 `refactor/current-application-modules` 分支（ADR 0058 落地施工的
[current application modularization plan](../plans/2026-08-10-current-application-modularization-plan.md)）
的審查回饋，判定「暫不通過」，提出 2 個 P1（阻塞）與 1 個 P2 發現。三個發現逐一
用實際檔案驗證如下，全部屬實。

## 發現 1（P1）：事後改寫 Accepted ADR 加註「接受例外」

`docs/adr/0058-current-api-functional-modules-and-dependency-rules.md` 狀態是
`Accepted`（`2026-08-10，owner 核准交付實作者執行`）。全分支 review 修正回合中，
`ef090a5` 在其 `## Consequences` 段落尾端直接加了一句「`core/opks_integrity.py`
是規則 7『型別／port』判準下一個已知且被接受、但需持續留意的例外」。

`AGENTS.md:10`：「架構決策寫 Nygard 式 ADR，預設 `Proposed`，並更新
`docs/adr/README.md`；翻案開新號。」—— 在既有 Accepted ADR 裡加註一個新的例外
判準，屬於對原決策範圍的「翻案」，應該開新號 ADR，不是直接編輯已核准的文件。

檢視 `apps/api/app/core/opks_integrity.py`（180 行）內容，確認它裝的不是型別／
port：`stale_invalid_opks_proposals()`（行 119-172）內嵌完整的 OPKS staleness
判斷邏輯，並直接寫死使用者可見的繁中文案（例如
`"同一項職務內容已經建立，舊提案不再適用。"`）。這是貨真價實的 domain policy，
規則 7 原文「型別／port 進 core 必須同時符合：… 零 IO／framework／transport」
並未明說禁止 policy，但整條規則的框架語言（「型別／port」）明顯预設 core 裝的是
穩定型別與介面，不是帶決策邏輯與文案的函式。這是一個真實的邊界問題，不是文字遊戲。

## 發現 2（P1）：`core` 的「只能從 module root import」規則沒有真正落地

ADR 0058 規則 4：「跨模組只能 import 模組 root 明確 re-export 的 public
API；不得 import 另一模組的 `internal` 或底層實作檔。不得建立聚合所有功能的
全域 facade。」

驗證：

- `apps/api/app/core/__init__.py` 只有一段 docstring，零 re-export。
- `grep -rn "from app\.core\." --include="*.py" app | grep -v "^app/core/"` 在
  `apps/api/` 下數出 112 處直接 import `app.core.<submodule>` 的用法
  （`app.core.domain`、`app.core.persistence`、`app.core.journal`、
  `app.core.state`、`app.core.authority`、`app.core.errors`、
  `app.core.model_outcome`、`app.core.opks_integrity`）。
- `apps/api/tests/test_job_analysis_dependencies.py` 的
  `test_api_only_imports_feature_module_roots` docstring 寫著：「`app.core`
  的 submodule … 不在這條規則內──`core` 是共享 kernel，沒有單一 curated root
  收斂全部型別，直接 import submodule 是既有、被接受的慣例。」—— 這個判斷寫在
  test 的 docstring 裡，但 ADR 0058 從未做過這個決策；是實作者在寫 guard 時
  單方面認定的慣例。

這個判斷本身站得住腳，但走錯了流程：一個真的架構決策（要不要幫 `core` 建
root facade、或正式承認具名 submodule 就是 public interface）不該只活在
test docstring 裡，應該是 ADR 記錄下來的決定。

## 發現 3（P2）：AST guard 有可繞過路徑

`_imports()`（`test_job_analysis_dependencies.py:33`）：

```python
elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
    found.append((node.lineno, node.module))
```

只處理 `node.level == 0`（絕對 import），任何 relative import
（`from ..opks import X`，`node.level > 0`）完全被略過——而且這個 helper 被
**所有** guard 共用，不只是 API guard，所以 `core`／`documents`／`task_analysis`／
`opks`／`consultation`／`export`／API 七個 guard 全部有同一個漏洞。

驗證是否已被利用：

```bash
grep -rn "^from \.\." --include="*.py" apps/api/app/core apps/api/app/documents \
  apps/api/app/task_analysis apps/api/app/opks apps/api/app/consultation \
  apps/api/app/export
grep -rn "^from \.\." --include="*.py" apps/api/app \
  | grep -v "^apps/api/app/\(core\|documents\|task_analysis\|opks\|consultation\|export\)/"
```

兩個 grep 都是空結果——目前沒有任何一處真的用這個漏洞繞過邊界。是潛在漏洞，
不是現存違規；但既然這條分支的紀律是「保留測試作安全網」，安全網本身有洞就該補。

`apps/api/scripts/job_analysis_opks_elicitation_live_smoke.py` 的匯入
（行 64、78）確認：

```python
from app.documents.authoring import create_document  # 不經 app.documents root
from app.opks.llm import (...)                        # 不經 app.opks root
```

`apps/api/scripts/` 不在任何 guard 的掃描範圍內（掃描根固定在 `app/`），
`apps/api/tests/` 同樣從未被納入掃描——兩者是對稱的、一直存在的現狀，但這個
「scripts／tests 在功能模組依賴圖之外」的決策同樣沒有在 ADR 或任何文件裡寫清楚。

## 選項

### 針對 `core/opks_integrity.py`（規則 7 例外）

1. **承認為記錄在案的例外**（目前 ADR 0058 被以錯誤流程加註的內容）——維持現有
   檔案位置，但把決策正式寫進新 ADR 而非事後改寫 0058。
2. **搬進獨立 `core/opks_policy.py` 之類的子模組**——不解決「型別 vs
   policy」的分類問題，只是換個檔名，價值有限。
3. **重新調整功能邊界，讓這段邏輯回到 `opks` 底下**，`documents` 改用某種
   間接機制（例如事件、hook）觸發清理，避免新增 `documents → opks` 邊。這是
   ADR 0058 Context 段落本來就評估過、認為代價更高的路線（會把單一 authority
   transaction 拆成多步協調），不建議在一個「source-level only、不改行為」的
   modularization 分支裡順手做架構級行為變更。

**建議：選項 1**，但走正確流程——新開 Proposed ADR 記錄這個例外，而不是編輯
Accepted ADR。理由與 ADR 0058 原文已經寫的一致（替代方案 `documents → opks`
邊更差），只是需要合法的文件出處。

### 針對 `core` 的 public API 規則

1. **正式承認具名 submodule 就是 public interface，`core` 不需要（也不應該）
   有單一聚合 facade。** 這是 Python 生態系「shared kernel」package 常見模式
   （例如 stdlib 的 `os.path`、`collections.abc`、`xml.etree.ElementTree`、
   `urllib.parse` 都是直接 import submodule，沒有一個把全部型別攤平到頂層
   `__init__.py` 的 facade）；ADR 0058 自己在規則 3 也有「檔案超過 500
   行、單一 facade 超過 25 個 public names … 必須觸發拆分審查」的門檛，
   `core` 目前橫跨 domain／state／authority／persistence／journal／errors／
   model_outcome／opks_integrity 八個子模組、上百個名字，硬塞進一個 facade
   只會製造一個超大 facade，跟規則 3 的精神衝突。
2. **建立 `core/__init__.py` root facade**，把八個子模組的 public 型別全部
   re-export。會製造一個遠超過 25 個 public names 的巨型 facade，且每次
   `core` 新增型別都要同步兩處，維護成本高，跟規則 3 的門檛直接衝突。

**建議：選項 1**，但一樣要用新 ADR 正式記錄——這是「refine 規則 4，讓 `core`
比照 shared kernel 慣例免除 root-only 限制」的決策，不是可以只寫在 test
docstring 裡的隱性共識。

### 針對 `apps/api/scripts/` 與 `apps/api/tests/` 是否納入 guard

1. **維持現狀（不納入）**，但在新 ADR 裡明講：scripts／tests 是診斷／驗證
   工具，不是 ADR 0058 定義的功能模組依賴圖的一部分，允許因為診斷或測試需求
   直接 reach 進 internal 實作。
2. **把 scripts 納入跟 `app/api`／`app/adapters` 一樣的 guard 範圍。** 會立刻
   fail（`job_analysis_opks_elicitation_live_smoke.py` 現有的
   `app.documents.authoring`／`app.opks.llm` imports），需要同時決定要不要
   在對應 feature root 補公開這些名字，牽動比這次修正範圍更大的面。

**建議：選項 1**，維持現狀但正式記錄決策，避免下次審核者再問同一個問題。

### 針對 relative-import 漏洞

不是政策選擇，是 guard 本身的正確性 bug——直接修，不需要 ADR：`_imports()`／
`_imported_names()` 要把 `node.level > 0` 的 relative import 解析回完整
module path（用被掃描檔案自己的 package 位置換算），跟現有 absolute-import
分支用同一套 `__all__` cross-check 邏輯處理，不能因為是 relative import 就
整條略過。

## 結論

三個發現都成立。前兩個是「決策沒有走 ADR 流程」的問題，用一份新的 Proposed
ADR（0059）補齊；第三個是 guard 程式碼本身的正確性 bug，直接修。
