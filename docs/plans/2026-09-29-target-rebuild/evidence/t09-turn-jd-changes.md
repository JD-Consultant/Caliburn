# T09：完成回答的 JD 變更檢視

日期：2026-09-30。**局部實作／驗證，不是 T09 或全產品驗收完成。**承接 [UI 交接缺口 2](t09-ui-redesign.md#5-api-缺口交回後端處理)。正式呈現與資料責任分別見[介面 §3.2](../../../implementation/interface-and-delivery.md#32-完成後查看這輪-jd-變更t09)、[JD 保存 §3.8](../../../implementation/jd-storage.md#38-完成-turn-的-jd-變更檢視t09)。

## 1. 問題、研究與取捨

原畫面可撤回一輪 JD，但缺少查看該輪實際變更的入口。JD candidate 已長期保留輪前／採用修訂，正文、關係、來源也都有固定歷史。因此直接從既有 owner 讀取並投影，**不新增 diff store、修訂平台或 LLM 摘要**。

本次核對第一手文件：

- [Python difflib](https://docs.python.org/3/library/difflib.html)：標準 unified diff 提供兩端文字差異與周邊行；借此避免自製差異演算法，沒有宣稱是最短 diff。產品成品投影保留標題、分組、順序與關聯名稱。
- [TanStack Query 按需查詢](https://tanstack.com/query/latest/docs/framework/react/guides/disabling-queries)：Dialog 開啟才啟用既有 Query，按 file／execution 隔離；結果是固定歷史，可於記憶體 cache 重用，不另存另一份 server state。
- [React state 結構](https://react.dev/learn/choosing-the-state-structure)：只留對話框開關，資料和讀取狀態用既有 Query cache；不以 Effect 複製到頁面。

本案工程取捨：第一版展示**正文淨效果＋來源新增／移除／調整筆數**，不做逐工具時間軸、候選即時 diff、歷史來源逐筆下鑽。這是可讀的結果比較，並非原操作流水帳或目前稿。淨文字為零不代表沒操作；來源版本／核對位置變更仍計入摘要。用既有 react-markdown 安全呈現，不新增套件。

## 2. 接線與責任

- `workflows/turn_jd_changes.py` 核對同檔案、顧問角色、completed；JD `change_queries.read_adopted_turn_changes` 讀原 adopted candidate 的固定兩端。不存在或未採用不能回空成功；無寫入、writer、模型或發布。
- HTTP `GET .../consultant-turns/{execution_id}/jd-changes` 不接受版本參數；唯一 schema 生成 Python／TS，回 execution 身分及 Markdown，no-store。使用既有 JD 保存，不新增 DB migration。
- 共用成品投影從 `transport/model_tools/jd_full_text.py` 移到 `transport/jd_full_text.py`，原模型全文讀取沿同一函式。新 `turn_jd_markdown.py` 只呈現，來源摘要以固定 reference 值比較，不拿最新 Memory 狀態混入。
- 前端 `TurnJdChanges` 在既有完成回答的 JD 操作處按需開啟，驗 schema／execution，錯誤可明確重讀，不自動撤回或解除待核對。原撤回 owner 和既有資格檢查不變。
- 原 `SafeSourceMarkdown` 提取為 `shared/ui/SafeMarkdown` 供兩個實際使用方共用；保留禁 raw HTML／連結導覽／遠端圖片的原規則。原始訪談不改走 Markdown。

## 3. Red／Green 與審查

1. 新 PG 測試第一跑有 6 個入口缺失反例與 1 個測試 fixture 拼錯方法，後者不算 Red。修正為既有 `candidates.edit` 後，**7 failed** 均因缺少 `/jd-changes` 回 404（4.85 秒）。覆蓋固定兩端、撤回後人工改稿、未完成／取消／失敗隔離、跨檔案、客戶端自選版本、來源-only 與無淨差異。
2. 前端先對既有 `UndoTurnJd` 寫檢視行為：**2 failed**，缺少「查看這輪 JD 變更」按鈕。實作後按需 GET、不誤送 undo、錯配身分拒絕與明確重讀通過。
3. 初次 green：PG 7＋既有全文投影 6 共 **13 passed**；前端新 2＋撤回 3＋安全 Markdown 1 共 **6 passed**。
4. 補 no-store 與既有公開端點一致：代表 HTTP 測例因缺 Cache-Control **1 failed**，加入 header 後再回歸。兩個 render 邊界測試（來源換版／移除、內嵌反引號）為**事後補測**，不冒稱 TDD。
5. 獨立唯讀 reviewer 檢查 HEAD `28e7d214` 至本切片差異與未追蹤檔，未發現 P1／P2；確認全文搬移 AST 相同（模組說明除外）、固定端點、無副作用、按需 Query 及來源摘要。未把明確排除的細節列成新增需求；review 不替代測試。

最終命令／結果沿下節；未把環境失敗算產品失敗或 Red。Windows sandbox 曾阻擋生成器臨時目錄與 Vite 子程序，正常 escalation 後用原工具執行，未改工具規則規避。

## 4. 驗證與限制

後端 cwd `apps/api`、`.venv-target/Scripts/python.exe`；PG 僅 `postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test`，conftest 隨機隔離 schema，未使用 Demo DB。回歸命令：

```text
python -B -m pytest tests/integration/test_turn_jd_changes.py tests/integration/test_jd_undo.py tests/integration/test_jd_reads.py tests/integration/test_jd_manual_changes.py tests/integration/test_jd_changes.py tests/unit/test_jd_full_text.py tests/unit/test_turn_jd_markdown.py tests/unit/test_import_boundaries.py tests/contracts/test_jd_changes_wire.py -q -p no:cacheprovider --tb=short
python scripts/generate_contracts.py --check
```

前端 cwd `apps/web`、bundled Node 24；`vitest run` 全 **28 檔／162 passed**，`tsc --noEmit`、本次 7 檔 ESLint 及 Prettier、`vite build` 通過。Build 有 >500KB chunk 警告（主包約 953KB／gzip 285KB），未為本切片新增拆包或放寬警告；後續依實際效能再判斷。

Python 本次 10 檔 Ruff／format、6 個來源檔 mypy 通過。上述最終 PG／單元／契約回歸 **56 passed（26.06 秒）**，生成器 `--check` exit 0、無漂移。6 份修改文件的 248 個本機連結／錨點檢查無錯，`git diff --check` 通過。

**未驗／非本輪：**新入口的真瀏覽器視覺與鍵盤旅程、真模型品質／長訪談、來源詳細歷史比較、候選即時 diff。Demo 後端未重啟，仍可能未載入此 API；不能只刷新前端便宣稱 Demo 新檢視可用。沒有付費模型請求、push、merge 或部署；T16／T17／T18 gate 仍未完成。
