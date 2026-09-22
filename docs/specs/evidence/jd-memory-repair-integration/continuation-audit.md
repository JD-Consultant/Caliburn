# JD App 接續方向與未提交實作審核

> **2026-09-13 後續：CA-01／02 已修**，見[App 接合結果稿](../../2026-09-13-jd-memory-repair-app-integration-slice.md)。本稿維持當時的審核狀態；§3 的診斷探針斷言「恢復仍阻擋」，現在會如預期失敗，保留為當時紀錄，產品回歸改看結果稿列出的命名案例。§4 的 wheel 與 adoption 界線也已在該結果稿收尾。

2026-09-13；JD-R002／OI-02。Owner 要求核對額度交接前後有沒有理解錯誤，並補詳細施工規範。本次停止新增產品功能，讀取有效需求、完成文件、交接計畫與實際 diff，另做兩個零 provider 反例。**結論：產品方向未見倒退；C 接合仍有兩個可重現的恢復缺口，不能宣稱完成。**本稿是主代理審核，不是新一輪獨立審查通過。

## 1. 審核基準及能回答的範圍

- 交接依據：[原接續計畫](../../../plans/2026-09-13-jd-app-continuation-handoff.md)；已提交基準 `8403d7e2e7904d2cd9db55a44bdeea26e105fd45`／tag `jd-memory-repair-core-20260913`。核對該基準後目前 working tree，不以檔案是否 tracked 推定有沒有施工。
- 先讀 [C 核心完成文件](../../2026-09-13-jd-memory-repair-core-slice.md)、核心採用／宿主／讀取成果，再讀本目錄原生觀察、binding、factory、closure 前置。核心完成與 App 接合是兩個驗收範圍。
- Owner 指出此處發生模型交接；Git 與工作檔不能證明每段修改由哪個模型產生。本稿評判交付內容，不把缺口歸因於特定模型名稱。
- 沒有審查全部歷史程式、所有職位或正式部署；兩個反例只能證明所列缺口，不等於已找到所有錯誤。這輪不重跑無新變動的全部舊實驗。

審核時檔案 SHA-256：

| 檔案 | SHA-256 |
|---|---|
| `experiments/jd-relational-app/src/jd_relational/ai_runtime.py` | `158adc6ef0620d1c1ad94848eafd2b45a8ec1c4e4a1591a97be7bf9d5244718c` |
| `experiments/jd-relational-app/src/jd_relational/ai_checkpoints.py` | `3993277a1cd76347fec6e5b76322b7436e36957eb0d04311ebcba072e3190207` |
| `packages/consultant-memory/src/caliburn_memory/repair.py` | `2e96de84add61679d908f87de67dc105b487b1f1ea1c83c1774a3c91ac1ab879` |

## 2. 方向判斷：已有顧問，正在接新 App

| 問題 | 查核結果／判斷 |
|---|---|
| 是否又做回文章／Plate 編輯器？ | 本次 diff 位於 `experiments/jd-relational-app` 與正常 Memory package；沒有改回 Plate、新整份 JSON current authority 或新增另一條 JD writer。既有十三表關聯 current、六章 CRUD、人與 AI 共用業務規則方向保留。這是針對本次 diff 的結論，未重新驗收全部 UI。 |
| 是否重做原本完成的顧問？ | 舊隔離顧問已有真模型成果。此次 factory 仍由原 `RepairWorkflow.graph` 共用同一六節點，App 加原 call／source／owner 接點，未另造修補引擎。不能把新 App 尚未完成寫成舊顧問完全沒有完成。 |
| 是否添加使用者未要的功能？ | 未見新增逐筆接受、舊聊天選輪、Excel、權限／多人或新資料表。恢復用原 call 與原 checkpoint 是保存證據，不是歷史選輪產品功能。 |
| 是否可直接宣布顧問成品可用？ | 不可。日常 `enable_chat=False`；新 App 尚缺完整 B1/B2 採用、部分旅程及自然 JD 品質驗收。舊顧問成功不能代替新工具接合後的真模型驗收。 |

既有完成依據必須保留：

- [CT49 固定新版長訪談](../../../../.worktrees/analysis-only-agent/docs/specs/2026-09-09-ct49-fixed-long-interview-results.md)：11 輪真模型／FastAPI／PG，工作理解、案例詳記、晚期更正、來源回查，無新資訊的一輪不重做 Memory；有 Minor，並非所有職位或百輪成功率。
- [CT50 已測配置與續談](../../../../.worktrees/analysis-only-agent/docs/specs/2026-09-09-ct50-tested-profile-results.md)：已測配置接線、真正前景與空近期 context 回查；有獨立審查與固定保存證據。CT49＋50 共 135 次真請求、估算 US$0.16871788，帳本已關閉；本次沒有重跑。
- [2026-09-13 C 核心](../../2026-09-13-jd-memory-repair-core-slice.md)：正常套件、官方 patch、原 request 查回已完成。新接手不能重新寫 matcher、另建 Memory schema 或退回較早的 old_text/new_text 設計。

因此，正確工作名稱是：**把已驗訪談顧問與 Memory 採用到新的關聯式 JD App，補新接點的保存／停止／恢復，再驗自然產出 JD。**

## 3. 已重現問題：優先修這兩個位置

### CA-01／P2：原模型 call 已存，source 失敗而尚無 repair binding

- 位置：`memory_repair_session.py::prepare` 先呼叫 `source_notice`；`ai_runtime.py::_recover_pending_repair`（審核時約 329–333 行）要求已有 session、binding 及 progress。
- 觸發：真正原生 Agent 保存 `repair_memory` call，`after_model` 取得本輪來源時拋出 I/O，尚未完成 binding，也沒有進 C。讓本次 invoke 結束後，用原 native checkpoint 觀察並進同一恢復 helper。
- 實際：model 1 次，C seed 0 次，Memory 仍初始 revision 1；binding 空且沒有 C checkpoint。恢復仍回 `run_recovery_required`，缺失 binding 不會因服務恢復自行出現。
- 影響：這個未執行更正不能正常收尾，可能持續阻擋該文件後續操作；未觀察到重複發布、原話或 JD 遺失。
- 要求：取得原生停止位置與原 call 的確切證據後，能閉合「尚未執行」的同 call 結果。不能重跑 prepare、配新 operation/source、假造完整 binding，或將 C 加進只讀工具白名單逃過驗證。結果必須在 `get/lookup/recover` 與下輪准入一致成立。

### CA-02／P2：固定 C 子圖停在原生 START

- 位置：`ai_checkpoints.py::_repair_position` 接受 `START`；`ai_runtime.py::_recover_pending_repair`（約 357–369 行）只接受 `seed/edit/validate/save/prepare` 作未發布位置。
- 觸發：真正 C input checkpoint 已存，第一個 loop checkpoint 保存失敗。公開 fixed child snapshot 的 `next` 為 `["__start__"]`；C seed 尚未執行。
- 實際：model 1 次、seed 0、Memory revision 1、已有一筆 binding；恢復仍回 `run_recovery_required`。
- 影響：已知尚未進入 C 的停止位置無法收尾；是恢復可用性缺口，未觀察到發布或資料破壞。
- 要求：從原生固定 START 材料核原 input／binding／call 一致後，產生正確未執行或未發布結果。**不能只把 START 字串加到白名單**；其他節點、未知 shape、錯誤 scope 及已到 publish 的狀態仍須保持原嚴格判斷。

### 可重現證據

[診斷探針](continuation-audit-probe.py)使用真 native Agent、InMemorySaver／Store 與 SQLite fixture；不連外部 PG 或模型，不偽造 owner 死亡證據。它直接驗恢復 helper，**不是已完成整個 App 解鎖的端到端證據**。兩案採「預期目前會阻擋」斷言，PASS 代表缺口重現；後續須轉成期待正常收尾的產品回歸測試。

```powershell
Set-Location S:/caliburn/experiments/jd-relational-app
$env:PYTHONUTF8='1'
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -c pyproject.toml -q -s -p no:cacheprovider ../../docs/specs/evidence/jd-memory-repair-integration/continuation-audit-probe.py --tb=short
```

原 `.research-tmp/jd-c-continuation-audit/test_direction_audit.py` 首次結果：**2 passed／5.06s**；保存下列輸出。移入本目錄只把 repo 導入路徑改成可由祖先定位，正式重跑結果另在本稿文末記錄。

```text
AUDIT source_before_binding: seed=0 model=1 publication=0; recovery blocks
AUDIT child_start_checkpoint: seed=0 model=1 publication=0; recovery blocks
```

## 4. 已通過範圍與不能冒稱的證據

接續施工的既有工具結果（本次審核未重新跑整組；範圍重疊不累加）：

| 範圍 | 既有最後結果 | 正確解讀 |
|---|---|---|
| 受影響 App 選定 15 個檔案 | 435 PASS／11.35s | 原生／離線接合回歸，不是整個 App 所有測試 |
| Memory package 全測 | 130 PASS／6.90s | 經 App 環境執行，包含 factory；不等於獨立安裝全部依賴成功 |
| `test_consultant_memory_postgres.py` 全檔 | 8 PASS／9.16s | 真 PG＋固定 SDK；正常 C 後讀取、提交確認遺失、門閘、来源／Store注入故障、close確認遺失、取消排空；不是自然模型 |
| 本次審核兩案 | 2 個缺口重現 | 不是 2 個缺口已修復 |

需修正的紀錄與驗收缺口：

1. **舊狀態未回寫。**交接與入口還寫 session 3 FAIL／1 PASS、工具 14 個、未掛 C；目前已有 15 個工具與正常 C 接合。這些舊數字保留為交接前首敗，不作目前待辦。
2. **新連線不是新程序。**PG 測試的 `opened(engine, None, dataset)` 在同一 pytest 程序重新開資源。既有 `tests/ai_host_recovery_worker.py` 的 AiRuntime 未注入 Memory engine/source，不能替本次 C 跨程序恢復背書。前次口頭「新程序」應更正；H2 仍須加 C 專用的真 Windows 新宿主案例。
3. **結果稍後出現的測法要說清楚。**unknown 測試先令 publish 在提交前失敗，之後由測試本身執行 `original_publish(*attempted[0])`（審核時第333行）。它證明 App 沒自行重送且能核同一回執，不證明真延遲交易／斷程序後原工作仍提交。另有真正提交後再拋錯的案例，兩者不混稱。
4. **注入故障的範圍。**source／Store 案例是在對應方法拋錯，不等於整個 SQL 服務實際斷線或 Store 部分寫入都已驗。只為實際未解風險補必要案例，不無限擴故障排列。
5. **H3 尚未完成。**本次 H2 獨立代理僅交初步 findings，因使用額度未產生完整結論；不能記獨審 PASS。`adoption.json` 尚為舊 repair hash；新 wheel 雖有產物，完整乾淨依賴安装因離線 cache 缺件未成功。
6. **wheel 驗證界線。**新 wheel SHA `8177326ee4ac9efc900978778ce031a3afcbdf2e2b4832199394745406e99ac1` 位於 `.research-tmp/jd-memory-c-app-dist-20260913/`。已驗 wheel 模組載入且不含 analysis_agent，但借用 App 依賴目錄；不是乾淨環境完整安裝。H3 補受鎖約束的安裝及核對，不趁機升級。

## 5. 官方依據與本案判斷

2026-09-13 本次重新查阅 [LangGraph 子圖](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)、[持久狀態](https://docs.langchain.com/oss/python/langgraph/persistence)、[AWS 安全重試](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)。App 鎖 LangChain 1.4.0／LangGraph 1.2.11，已發布套件、MIT；文件網站會更新，適用行為由本地 lock／原碼與反例一起核對。AWS 是現行工程文章，沒有套件版本或指定本案 schema。

官方支持原生子圖／checkpoint 與保留原請求身分，**不保證任意組合就能恢復，也沒有規定本案十五工具、binding 欄位或判定表**。固定 wrapper 是已完成前置實驗後的本案接法，CA-01／02 是該接法必須補的邊界，不能用「大廠共識」代替測試。

LLM patch／結果契約沿 [C 核心的 OpenAI／Anthropic 官方證據](../../2026-09-13-jd-memory-repair-core-slice.md)及 [原 call／artifact 驗證](records-results.md)；本次不改模型輸入，沒有以新廣搜推翻已驗方法。只對新恢復反例做有限研究。

## 6. 為什麼仍花時間、如何收斂

實際主線是：關聯式業務與保存 → 手動 App → 聊天／共同工具 → 原話来源 → Memory 套件／宿主／讀取 → C 接合。前面已有驗收成果；當前卡點集中在 C 保存到哪裡、取消何時真停止、回覆遺失如何核原結果，並非持續研究 JD 欄位或從零教顧問訪談。

其中一部分時間用於必要的跨 Saver／Store／SQL 接點驗證；但測試 fixture 錯誤、環境路徑／cache 問題、狀態沒有及時回寫、將新連線說成新程序，也增加了返工。不能把全部耗時都說成規範所必需，更無證據把它歸因於模型交接。

下一工作單位只處理 CA-01／02、補 C 真新宿主驗證並完成 H3。之後直接採用已驗 B1/B2 與顧問方法，接完整 JD 旅程。逐檔步驟、反例到驗收與停止條件回寫[同一接續計畫 §5](../../../plans/2026-09-13-jd-app-continuation-handoff.md)，不另造競爭計畫、不新增產品範圍。本次未修產品程式，兩個問題維持 OPEN。

## 7. 本次審核收尾

- 移入本目錄後按 §3 命令重新執行：**2 passed／4.68s**，兩行診斷输出與首跑一致；代表CA-01／02仍可重現，尚未修復。
- 審核稿、接續計畫、總計畫、問題清單、決策入口與兩份README共7份文件的本地引用皆存在；受影響已追蹤文件`git diff --check`通過。原生換行提示不當成內容錯誤。
- 三個受審程式hash與 §1 相同，本次沒有修改產品程式或真資料。工作區其餘未提交內容保留；沒有把尚未完成的C接合提交／tag為完成版本。
- 接续實作的完整獨審未完成；本次只有主代理的方向／程式窄審與兩個原生反例。CA-01／02、C跨程序與H3仍交接續計畫，沒有以文件完成代替施工完成。
