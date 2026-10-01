# C 即時修補核心：新 App 接合前窄審

2026-09-13；新 App 基準 `7d3f474a`，舊核對基準 `033540cef870d1f92baa5c69133a799231c46d48`。本次只讀程式、舊實測與已核官方資料，另執行原方法的有界合成反例；沒有改產品、呼叫 provider、開 DB 或重跑舊模型。這是採用前檢查，不將正在移植的核心或尚未接線的 C 宣稱完成。

## 最少可採範圍

保留已驗的六步原生子圖 `seed → edit → validate → save → prepare → publish`、Deep Agents `StateBackend` 暫存、公開 `agents.apply_diff`、原 Store artifact 及 PublicationStore 的 CAS／receipt。先將三個核心檔形成可安裝 package 能力，不能由新 App import 舊 worktree；App 再接具名 `repair_memory(edits=[{path,diff}])`。不用新 parser、回退引擎、Memory 表或另一個 owner。

**讀取政策已核清，沒有重開：**本輪 initial guide／`jd_memory_view` 保留；只有本輪確切 C 回覆可更新目前讀取版。C 的 `applied_head` 指原操作 receipt，`head`／guide 可指明確回覆當時較新的 current，避免晚期 B 已發布後反而退回舊版。這是明示 C feedback 的刷新，不是每次讀取偷偷追 B。舊 [late-head 真 PG fixture](../../../../.worktrees/analysis-only-agent/experiments/analysis-agent/tests/test_postgres_live_memory.py) 明驗 applied revision 2／read revision 3；[live tests](../../../../.worktrees/analysis-only-agent/experiments/analysis-agent/tests/test_live_memory.py) 明驗下一輪 initial guide 勝過前輪 C 回覆。本文先前讀碼時考慮「只能讀 receipt.result」的方向已依此排除，不作 finding。

## 三個採用前必修反例

以下位置均指舊 [repair.py](../../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/repair.py)，不是新 App 已在執行這些錯誤。2026-09-13 探針以 AST 取原方法本體，注入純 fake publication／staged_texts；使用新 package 的真 `PublishRequest`／`Receipt` 型別。没有 import 舊模組或進 DB。四個觀察均重現，exit 0；不冒稱 native Saver 或交易驗證。

| ID／嚴重度 | 可重現反例與影響 | 最小修正 |
|---|---|---|
| CR-R01／P2：對帳未核原意圖 | `reconcile:105–120` 只核 operation、kind、source。給同一 receipt／source，但將 caller 的 edits 改成 `+UNPUBLISHED_CHANGED_INTENT`，仍回 `applied` 且 `changes` 為未發布內容。舊 [live_memory.py:145–171](../../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/live_memory.py) 的 binding 只有 message／call／operation，不能補足意圖核對。 | 以原生 C 子圖已保存的 **原 PublishRequest** 對帳 `receipt.request_digest`，並將同 run 原 AIMessage／call／validated edits digest 對上原 binding 與子圖材料。缺 request、錯 scope／source／args 或找不到同一原生任務，一律 unknown／停止；不可因同 key 就宣稱新 edits 成功。 |
| CR-R02／P2：未知來源／儲存錯誤被當可修參數 | `_validate:89–95` catch 全部 ValueError；令 `staged_texts` 拋 `ValueError('PRIVATE_SOURCE_IO')`，結果是 `invalid_edit`，detail 含原 marker。這抵銷了 [staged_texts](../../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/consolidation_tools.py) 刻意將未知錯誤向上拋出的邊界。 | 只 catch 已知的 `StagedMemoryValidationError`。新 source port 使用 typed `InvalidSourceReference` 區分已知無效引用；source unavailable／未知 ValueError／Store I/O 繼續停止，不耗模型修補次數、不暗示重寫 patch 可修好基礎服務。App 最外層回固定安全錯誤。 |
| CR-R03／P2：正常發布出口沒有核 current 至少涵蓋原結果 | `_publish:122–141` 在 `publish` 確認 applied revision 2 後，fake current 回 `None` 或 revision 1，兩者仍回 `status=applied` 並交不可能的讀取 head。`reconcile` 已有 `current >= receipt.result` 檢查，正常出口卻沒有。 | 共用一次已確認 applied／current 的同文件、有效版本與 revision 下限核對；缺失或落後時保留「原發布可能／已成功，但讀取 feedback 未確認」的 unknown 出口，不能讓空或落後 head 成為新的讀取版。current 3 的合法晚期刷新繼續允許。 |

CR-R02 不表示所有 ValueError 都不能分類。[memory_patch.py](../../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/memory_patch.py) 只包住純 `apply_diff(original,diff)` 的已知解析／context ValueError，讀寫 StateBackend 在這個 catch 外；這個位置有明確函式契約，可以保持。不能把同樣 catch 擴到會讀 source／Store 的 `staged_texts` 或整個 workflow。

## 新 App 必要接線，沒有另造資料權威

| 接點 | 已有能力與最小補件 |
|---|---|
| 原操作／來源身份 | [AiToolSession](../../../../experiments/jd-relational-app/src/jd_relational/consultant_tools.py) 已在 native `after_model` 保存原 call 的 JD binding，再進 tools。C 沿相同時序另保存必要的 C call identity／input digest／App operation identity／本輪 source 與 base，模型仍只填 edits；不要將 Memory publication 偽裝成 JD operation。原始 Human／AI 及 source 仍由同一 Saver／ConversationSourceService 管。 |
| 原生 C task 材料 | `RepairWorkflow` 以原生同步子圖繼承同 Saver，保存 staging／prepared request。取消對帳從已知 C 任務的公開 `StateSnapshot.tasks`／固定 checkpoint 讀原 request，與原 message／call／scope 配對；不透過猜 namespace 或重新跑 seed/save/prepare 重造 request。先做真 nested graph 的保存前／prepare 後／publish 後中斷反例，確認實際公開 snapshot 形狀，再接最小專用 decoder。 |
| 取消與未知發布 | [ManualRuntime](../../../../experiments/jd-relational-app/src/jd_relational/manual_runtime.py) 已掌握真正 foreground Future／外來宿主 proof。C 同步子圖仍在這個工作生命週期內；timeout 或 stop Event 不是已停止。對帳只讀原 receipt，沒有 receipt 仍 unknown；不執行 `_publish`、不換 operation、不借 JD stopped-reconcile 寫出 Memory 失敗回執。只有公開原生 task 確切證明未進工具才可說未執行，不能用「沒有 task.error」代替。 |
| 成功 C 與收尾 | [AiRuntime._verify_saved_results:165](../../../../experiments/jd-relational-app/src/jd_relational/ai_runtime.py) 現只分 JD write／六個已知 read；直接塞 C 成功會被當非法 JD result。`_settle:611` 的未绑定未知工具也不能用 `_not_executed` 覆蓋可能已發布的 C。須明列 C 的原 publication receipt 驗證與 pending 分類，收尾未知時保留 gate；不能把 C 加入 read 名稱豁免。 |
| 同輪讀取版 | [memory_context.memory_session:121](../../../../experiments/jd-relational-app/src/jd_relational/memory_context.py) 現將 runtime state 與 immutable 初始 session.view 相等後直接用初始 backend。保留這個 initial check，另承接已核本輪 C feedback 的 current head／guide binding；從該固定版本建立 native reader，用現有 tool override。不要改寫 initial view、每次查 publication.current，或把前輪 ToolMessage 當本輪刷新。根／child／close 都保留新 current binding；它與 initial 的責任不同。 |
| 錯誤與停限 | 保持兩個可編輯路徑、1–8 edits、12000 diff 字元及原兩次可修失敗限制。Native schema error 必須是固定 ToolMessage（沿已修的 BaseTool error policy）並持久計數；後續由原 Agent 修改參數，不加 ToolRetry 重送未知發布。不增加已停放的 final 強制重試 hook。B 尚未接時不能把「已通知背景整理」當已完成回執。 |

本次已看到移植中的新 `InvalidSourceReference` bridge；這是 core／App 之間的語意區分，不是第二套 validator。現有 `read_conversation`／summary owner caller 也須同步保留「無效引用可修、來源不可用停止」，不能讓新的 typed exception 被原 broad `except Exception` 轉錯。這是 caller 適配項，待作者停寫後以原 source 工具反例複核，不審未定稿為新增已確認 bug。

## 有限驗證的退出條件

1. **核心正反：**整批兩檔成功／後一 patch 失敗不出版；同 key 原 request 查回不讀 source 或改 head；同 key 不同 edits／request 被拒；format／引用可修錯誤與 source／Store 故障分開。保留 SDK 重複 context、合法尾標與尾隨多檔拒絕原反例，不自行新增 matcher。
2. **真 native 中斷：**同 parent／C child Saver，分別在 seed 前、save 前、prepare 已保存後、COMMIT 已成功但 feedback 前停止；新 observer 精確拿原 task/request，恢復只對帳，不重播模型／Store save／publish。缺原 request 不推定失敗；確認原 receipt 後才補原 call 結果。
3. **讀版政策：**初始 H1 → C applied H2／feedback read H2；若 feedback 前已有 B H3，允許 applied H2／read H3；feedback 之後的 B H4 不再自動刷新。原 initial guide 仍 H1，新一輪才讀目前版。current 缺失或小於 applied 必停；前輪 C 回覆不污染新一輪。
4. **共用生命週期：**C I/O 未完時 cancel／close 不釋放 Store／pool；原 publication 不確定時不開下一輪／不假 completed。完成與失敗均沿同 owner、same-call ToolMessage 及原 native state 收尾。真 PG／新程序證据依實作後另驗，本文沒有代證。

## 官方依據與適用限制

本輪沿 [CT10 固定官方比較](../../../../.worktrees/analysis-only-agent/docs/specs/2026-09-07-memory-editor-framework-comparison.md)、[CT11 實際採用](../../../../.worktrees/analysis-only-agent/docs/specs/2026-09-07-official-memory-patch-trial-results.md)、[CT35 共用錯誤回饋決策](../../../../.worktrees/analysis-only-agent/docs/specs/2026-09-08-ct35-attempted-repair-recovery-review.md)及[新版 owner 官方接點](../jd-relational-ai-runtime/ownership-preflight.md)，沒有重啟品牌或 matcher 比較。2026-09-13 本地核對：Deep Agents 0.7.13、LangChain 1.4.0、LangGraph 1.2.11；package 正採已驗 `openai-agents==0.22.0` 的公開純函式。沒有聲稱這是新查的 PyPI 最新版本。

- OpenAI 的 [patch harness](https://developers.openai.com/api/docs/guides/tools-apply-patch#implementing-the-patch-harness) 與 [固定 SDK 原碼](https://github.com/openai/openai-agents-python/blob/18de65134083ee8cbdb84ae30a34c1f30ef4cb86/src/agents/apply_diff.py) 支持本機套用及 App 回報；first-match／whitespace fallback 不是唯一匹配或語意正確保證。這裡不用 Runner／provider client，也不等同 Responses 原生 hosted tool。
- Anthropic [工具錯誤](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls#handling-errors-with-is_error) 及 OpenAI [原 call 結果](https://developers.openai.com/api/docs/guides/function-calling#formatting-results) 支持實際 error/result 交回原模型；沒有共同規定本案 patch schema、兩次失敗數字或 Memory 表。
- LangGraph [checkpoint](https://docs.langchain.com/oss/python/langgraph/checkpointers) 的同步保存、公開 task 狀態與 replay 區別，及 Python [Future](https://docs.python.org/3.12/library/concurrent.futures.html) 的取消／timeout 限制，支持原生材料及同 owner 排空。不能從工具例外或等待逾時推導「SQL 從未提交」。

官方能力與原流程足以支持以上有界採用；剩餘是實際接點反例，不需要新 UI、產品語意討論或另一套 patch／恢復框架。核心完成後仍須由非作者獨審新 staging／repair／patch；本前置不是完整 C runtime 或自然修補品質的 PASS。
