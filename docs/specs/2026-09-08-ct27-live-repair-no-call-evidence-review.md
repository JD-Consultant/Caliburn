# CT27：自然即時修補零工具——官方機制與續談證據核對

2026-09-08 · Q019-MEM-CADENCE-01／CT15-R07 · **G2研究完成，下一局部診斷待審；G8仍OPEN。不是修復完成。**

## 1. Preflight與有效邊界

- 唯一問題：CT26中，回覆已採用更正，為何未呼叫工具更新持久Memory？
- Owner本輪授權研究；**不改src／tests／prompt／模型、不跑付費生成、不接觸資料庫**。
- 必讀依據：[流程](../decision-process.md)、[CT26實測](2026-09-08-ct26-natural-live-repair-validation.md)、[CT25核准提示與防錯保留](2026-09-08-ct25-gpt-prompt-stack-and-live-repair-candidate.md)、[CT23最新裁決（§0）](2026-09-08-ct23-memory-maintenance-responsibility-review.md)。CT17～CT20、CT24與CT11按本題回查，不重新研究整個Memory架構。
- B維持**LLM段落通知＋既有文字量後備，低資訊量先累積**；不重提Owner已拒絕的逐輪／短尾批／強制維護，不把之後B追上算成C成功。
- 保留reasoning／thinking、既有案例細節／引用／patch／原子發布保護。官方差異不自動授權換工具或重設context；排除JD及production。

## 2. 實際證據：失敗停在選動作，不在執行

**Observed fact：**CT26的實際system及六工具完整符合CT25，HTTP200／completed；模型直接給final answer，沒有任何tool call。當前導覽已含10日期限及正文地址；更正訊息是5日。正文／導覽仍10日、revision3。[完整證據](evidence/2026-09-08-ct26-natural-correction.json)

因此本次不是schema拒絕、patch找不到、CAS衝突、DB失敗或重試／步數不足。LangChain的`_make_model_to_tools_edge`在AI沒有tool call時結束，是官方agent loop的正常規則，不是漏執行收到的工具。[LangChain agents](https://docs.langchain.com/oss/python/langchain/agents)

### 2.1 這輪新核對：四次測試的延續條件相同

逐一比較下列JSON的`fixture_sha256`、`requests[0].opaque_input`與非system的`input`，不是從報告摘要猜測：

| 既有實測 | 同一CT16資料副本 | 同一opaque compaction | 同一可見續談三則 | 首次回覆有工具 |
|---|---|---|---|---|
| [CT17](evidence/2026-09-08-ct17-correction-persistence.json) | 是 | 是 | 是 | 無 |
| [CT19](evidence/2026-09-08-ct19-routing-regression.json) | 是 | 是 | 是 | 無 |
| [CT22](evidence/2026-09-08-ct22-natural-correction.json) | 是 | 是 | 是 | 無 |
| [CT26](evidence/2026-09-08-ct26-natural-correction.json) | 是 | 是 | 是 | 無 |

共同fixture SHA256：`7a0914d09e90ad64a7f6ff5b70e35f060ffc6983022d4198227e1512a92d685f`；共同opaque摘要指紋：`a7c6371079a083784b93acbbdc574d899272e13096f6050f21362c1d28e5233c`。只比對已封存指紋，未解讀／重建隱藏推理。

三則可見續談依序是：員工已重述5日且沒有其他更正；顧問已回答以5日為準；員工再次明確說5日不是10日。四輪都是medium／all_turns、同六工具名稱；**提示版本不同，不能說完整請求相同，也不是四個獨立職位的失敗率**。CT22／CT26有完整工具定義及tool_choice稽核，較早trace不能用缺欄位推定同等可見性。

這不推翻舊FAIL：聊天已正確但Memory仍舊，正是產品必須處理的情境。新資訊是**多次換提示都沒有隔離「第一次更正」與「續接先前只回答未保存的歷史」**。CT18／CT25已知道舊歷史存在，本輪補的是四份實際輸入及hash的一致性，不冒充首次發現。

## 3. 官方到底做什麼：避免同名就當等價

### 3.1 即時修補仍需要模型選動作

**Official fact：**OpenAI Sandbox Memory的live update需要Filesystem能力；讀取需要Shell，先注入小導覽、再按需讀Memory與詳記。本機官方SDK的live-update提示要求核實過時內容後當輪修補、完成前保存；未找到「模型零工具時由Memory capability自行判斷並補寫」的機制。[Sandbox Memory](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)

Anthropic專用`memory_20250818`工具有API注入的Memory指引，但仍是Claude產生讀寫要求、客戶端實作執行與回傳；這不是把任意函式改名memory便獲得相同行為，也不是每次必要修補都成功的保證。[Anthropic Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)

OpenAI `auto`容許零工具；`required`只要求呼叫工具，不能獨自判斷應修哪段、是否該修或是否保存正確。Anthropic對未呼叫工具建議檢查用途／名稱／schema與使用時機；我們已修过描述落差且CT26仍失敗，不能再把同一建議當新的已證實修法。[Tool choice](https://developers.openai.com/api/docs/guides/function-calling#tool-choice)、[Anthropic troubleshooting](https://platform.claude.com/docs/en/agents-and-tools/tool-use/troubleshooting-tool-use)

### 3.2 三種patch介面不可混為一談

| 實際介面 | 模型交付內容 | 執行者／限制 |
|---|---|---|
| 本案`repair_memory` | JSON函式參數`edits`，逐筆`path`／`diff` | 已核准的Memory scope／版本／整批發布；本機使用官方SDK patch applier |
| OpenAI Agents SDK 0.22.0 Sandbox Filesystem | `SandboxApplyPatchTool(CustomTool)`，`apply_patch`＋Lark grammar，直接patch文字 | SDK解析多個操作、先驗全部路徑，再交workspace editor逐筆執行；不能由此宣稱具本案整批Memory原子發布 |
| OpenAI Responses原生`type: apply_patch` | 原生`apply_patch_call` operation，回傳`apply_patch_call_output` | 應用程式提供執行／錯誤回饋，與上一列custom tool不是同一wire contract |

官方[custom tools](https://developers.openai.com/api/docs/guides/function-calling#custom-tools)支持文字／grammar免JSON包裝；[原生apply patch](https://developers.openai.com/api/docs/guides/tools-apply-patch)另有原生契約。**共用官方套用程式，不代表模型面前的工具相同；官方範例也不能證明目前Luna／provider／LangChain接線已支持另一種wire。**

這個整合選擇已在[CT11](2026-09-07-official-memory-patch-trial-results.md)說明；本輪補查SDK Sandbox實際是CustomTool而非原生apply_patch，沒有翻案。CT11明確要求修補的測試曾成功，證明執行路徑可用，不代表自然訪談會主動選它。**CT26尚未輸出patch，沒有證據把零工具直接歸因於JSON或匹配格式。**

### 3.3 Context／reasoning是待隔離因素，不是已定罪

OpenAI GPT-5.6指南指出持續推理有助長任務，但前提改變時可能沿用過時思路；應維持清楚成果、必要限制、逐項比較，不無限堆疊提示。這提供診斷方向，**不證明本次opaque內容、medium或模型能力造成漏存**。[GPT-5.6 prompting](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)

`all_turns`利用相容的先前推理；`current_turn`不是刪除對話歷史的開關。inline compaction本身也攜帶先前狀態與推理；不能假設改一個reasoning選項就清掉其語意，更不能改寫opaque。當前context函式依最新inline compaction切出延續視窗，與官方容許的inline接法一致；standalone compact的完整輸出需原樣續接，是另一契約。[Reasoning across calls](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-across-calls)、[Compaction](https://developers.openai.com/api/docs/guides/compaction)

**Unknown：**模型是否受到舊final answer／壓縮延續、當前任務優先順序、工具操作負擔或其他因素影響。沒有公開資料能替這份trace指出唯一內部原因。新增reasoning token為零也不等於沒思考或沒有使用先前狀態。

## 4. 下一步選項：停止重複改提示

| 選項 | 能回答的問題／優勢 | 成本、限制與狀態 |
|---|---|---|
| **A：固定CT25提示、六工具、Memory、Luna／medium，局部對照第一次更正與原歷史續談** | 先分清「目前工具任務也不做」或「在這段延續特別漏做」；不用新產品機制 | 少量隔離呼叫；短context成功仍不能替長訪談過關。**建議下一gate審這項** |
| B：模型工具介面对照官方custom patch形狀 | 測少一層JSON包裝／官方編輯介面是否影響動作選擇 | 須另查provider及框架custom call接線，保持scope／版本／原子發布；本輪未核准，不以共用applier冒充已等價 |

A是**Caliburn針對此反例的診斷實驗，不冒充兩家指定的標準測例或產品context決策**。可用LangChain公開`wrap_model_call`／`request.override(messages=...)`建立只影響該次請求的context view，不改canonical保存層；或使用現有隔離測試入口。不能據此把產品改成每輪短對話。[Context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)

待審實驗輪廓：

1. 同一份stale Memory與同一員工更正，A1以新建的隔離短context提供；不攜帶先前「已回答5日」或opaque，不加「請使用工具」等額外指令。原始完整訪談仍保存且可經既有工具查閱。這是在對照**延續context整體**，不是單獨證明compaction原因。
2. A2用同一基準的歷史延續作成對控制；保留原CT26 FAIL，不替換它。各自從未修改的隔離Memory起點開始，工具若成功可正常執行完整讀→修補→回覆鏈，不能只截第一步。
3. 看實際工具呼叫、正文／導覽发布、舊案例與引用保留；不是只看回答5日。若結果分歧，只能支持續談因素值得再隔離；必要時下一gate再比較canonical可見歷史與opaque延續。若兩者都漏存，不再重跑同義prompt，回來審B或有新證據的方案。
4. 保持`medium／all_turns`、auto tool choice與產品保護；不把`current_turn`當重置鍵、不新增Agent／強制工具／背景補救。呼叫與費用界線在執行前另記，本輪沒有新額度或付費呼叫。

## 5. 可重驗來源與closure

上述網頁於2026-09-08重新讀取。SDK是**本機已安裝0.22.0重現基準，不宣稱最新發行版**。路徑相對`experiments/analysis-agent/.venv/Lib/site-packages/`，未修改套件：

| 官方原始碼 | 核對部位 | SHA256 |
|---|---|---|
| `agents/sandbox/capabilities/memory.py` | capabilities依賴、導覽注入 | `f9e08b5ef09f6a4c7c74f7475ed53c36ee724a3f615a94fd470353b61b0a35ba` |
| `agents/sandbox/memory/prompts.py` | live update提示及read prompt組裝 | `2eb0bf2e2e097a396ca6eba9cbf98c8b0e5e3c72f1cdfc5e7f1ed5194a5f93b0` |
| `agents/sandbox/capabilities/filesystem.py` | 實際建立SandboxApplyPatchTool | `ed298ef9d0cd80e54da8fb208f52cec387f654b7fd1b7fec429ccd69666a2df9` |
| `agents/sandbox/capabilities/tools/apply_patch_tool.py` | 全檔：grammar／CustomTool／解析／路徑驗證／逐筆執行 | `72f3e7a146aabdda705b55f7826dfeef77416e905359d8f293efc95ff759c114` |
| `langchain/agents/factory.py`（1.4.0） | `_make_model_to_tools_edge`無tool call→END | `2e1855c669ed50df9795b1f73ca690d7664d0ef58a1c4080d0f6504076ebea97` |

- **Finding：**C仍缺自然保存效果；沒有framework漏執行的證據。四次同源延續尚未做因素隔離；patch執行共用不等於model-facing工具完全相同。
- **狀態／效力：**研究記錄，不是新增產品決策。CT25接線保留，CT26 FAIL、closed帳本及G8 OPEN不變。
- **重開條件：**新的對照能分辨動作選擇因素，或官方／框架提供可驗證的新機制；不得只因新名詞重開。
- **下一唯一gate：**審閱A的局部診斷，確認後才執行；不延伸重做B時機／整份Memory架構。
- **本輪驗證：**原CT22 SHA256 `932529be827921343ffe5b31e11faeb648c753c0ed35b5760bdc7b12e0d9e3cc`、CT26 SHA256 `ab4583fdf9660cedbae94016d2b00477dd6c4305029e6902f9cb542a53ab103e`未變；無產品src/tests變更。本文21個連結中的本地目標全存在；兩份register的diff check通過。主agent自審修正CT23段落錨點，未做獨立review或產品測試；保存點由主register登記。
