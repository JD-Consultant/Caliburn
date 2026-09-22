# Q019 完整 request 預算＋分析 Skills 接線

> Topic `Q019-CONTEXT-SKILLS-WIRING-01` · 2026-09-07 · Owner 已授權隔離實作；不接 JD。
> 執行完成：三項Task已完成，最終514項通過且整批獨立審核Approved；[結果、來源及界線](../specs/2026-09-07-context-budget-and-analysis-skills-results.md)。下文保留施工時的步驟，不能把RED敘述當目前未修問題。
> For agentic workers: use superpowers:subagent-driven-development. Task reports/reviews are scoped to this plan; durable findings go in the results document, not new long discussion histories.

## 目標與有效依據

補 CT-01／SK-01；不重設 Memory。最新指路是主 checkout 的 [current decisions](../../../../docs/current-decisions.md)，不是本 worktree 的歷史 register。承接 [Q019 Runtime](../../../../docs/specs/2026-09-06-analysis-only-agent-runtime-design.md)、[Q019 審核](../../../../docs/specs/2026-09-06-analysis-only-agent-design-review.md)、[前段修復結果](../specs/2026-09-07-runtime-recovery-repair-results.md)。Owner 明確同意本輪先接完整預算與 Skill，審核後再測自然模型／調 prompt。

基準：`3ba74848`，worktree `codex/analysis-only-agent`；2026-09-07 主審重新跑 **427 passed／0 skipped，67.20s**，只有既有 TestClient deprecation warning。専用 PostgreSQL `127.0.0.1:55433/q019_agent_test`，未重啟 Docker，付費呼叫0。

## Global Constraints

- A 主顧問、B1 抽取、B2 整併、C 窄修補及五產物／引用鏈維持；不新增每輪分析筆記或新 Agent。
- canonical 對話不刪、不改、不以有損摘要取代；原生 reasoning／compaction opaque items 原樣延續；只改 effective request view。
- 仍由 `create_agent` 執行模型／工具循環；沿用 SDK transport retry、框架錯誤與呼叫額度。不要修改 private framework converter。
- 不接 JD／UI／production；不讀 `.env` 密鑰內容、不做付費模型測試、不 merge／push。
- 沒有必填 `skill_ids` 或新模型巨型表單。Skill 是按需讀取的方法，不是每回合強制 OPKS／Task pipeline。
- Source facts、框架公開能力與本案組合要分清：不宣稱每家採相同底層或已證明最佳自然模型效果。

## 已核對的機制與局部取捨

### SK-01

採已鎖 Deep Agents0.7.13 的 `SkillsMiddleware`：發現 metadata，模型按需用既有 `read_file` 讀正文。以 `FilesystemBackend(virtual_mode=True)` 僅掛載隨套件提供的 skill assets，經 `CompositeBackend` 與 Memory reader 共用唯讀工具。Middleware 掃 metadata 可用官方 download primitive，但模型不獲得任意 host filesystem／write／execute。來源：[Skills](https://docs.langchain.com/oss/python/deepagents/skills)、[Backends](https://docs.langchain.com/oss/python/deepagents/backends)。

三份精簡方法參考：工作範圍／案例訪談、案例比較／共同工作模式、產出／成功判準／知識技能深入訪談。不是三個新 Agent。只吸收舊研究的方法，**不移植 iCAP 固定版型、旧 evidence schema、Task 穩定後才分析 OPKS、A／能力級別或 deterministic 語意黑名單**。研究依據：主 checkout `2026-07-28-task-boundary-merge-split-and-identity-research.md` §3.5 的 O*NET 2025 redundancy/overlap、`2026-08-01-opks-raw-performance-indicators.md` 的目的／可觀察性原料及最新 Q019 目標。每份 Skill 一個實例、清楚觸發條件、自然訪談而非逐欄填表；來源與取捨放結果文件。

依 Owner 順序，本輪只做方法初稿、載入／隔離／實際 wire 測試；自然模型的觸發率、問答品質與內容微調留下一 gate，不能把腳本模型照做視為 Skill 效果已通過。

### CT-01

一般 LC 近似訊息計數無法確定 opaque reasoning／compaction 的實際容量；已安裝 `ChatOpenAI.get_num_tokens_from_messages` 也明示忽略 tools。採 HTTPX 公開 request hook，在 SDK 完成 serialization、送出 `POST /v1/responses` 前檢查實際 body，使用另一個沒有此 hook 的 OpenAI SDK client 執行 `responses.input_tokens.count`。這涵蓋 A/B1/B2，包含 tools／Skill metadata或讀取結果／guide／input／B1 `text.format`，不重寫 converter。來源：[HTTPX hooks](https://www.python-httpx.org/advanced/event-hooks/)、[OpenAI count API](https://developers.openai.com/api/reference/resources/responses/subresources/input_tokens/methods/count)、[SDK3.8 counter source](https://github.com/openai/openai-python/blob/v3.8.0/src/openai/resources/responses/input_tokens.py)。

預算 `input_tokens + final max_output_tokens <= configured context_window_tokens`；output上限包含 reasoning，不重複扣。只傳 count API 支援的欄位，不以 `extra_body` 塞入 create 的全部其他參數。`truncation=disabled`，完整可核對才放行；超限或計數失敗不悄悄刪資料、不送未核對的生成請求。來源：[Responses](https://developers.openai.com/api/reference/resources/responses/methods/create)、[Context window](https://developers.openai.com/api/docs/guides/conversation-state#managing-the-context-window)。

這是 **本案保守的 preflight**，不是 OpenAI 強制每次額外計數；會增加一次網路請求／傳輸及延遲，是否縮減要以後續實測討論。計數 endpoint 不接受 `context_management`，所以不預測同一 request 尚未產生的新 compaction；既有 inline compaction 繼續提早觸發，超大單次跳增明確停住。來源：[OpenAI compaction](https://developers.openai.com/api/docs/guides/compaction)。不聲稱免費、零延遲或所有長度都可繼續。

部署提供正的 `Q019_CONTEXT_WINDOW_TOKENS`，與 output／compact_threshold 有一致性驗證；不用硬猜模型容量。純 fake單元建構可不配置，但 `open_service` 真實路由必須接齊，不能預設漏關。

hook 的本地阻擋 exception 使用公開 `OpenAIError`＋LC `ContextOverflowError`／`ModelInvalidRequestError` 型別：SDK3.8 對前者原樣傳播、不把本地政策失敗偽裝 connection error重試；LC 公開 ModelError 支持 provider多重繼承。Counter transport failure沿內層 SDK及LC既有分類，不疊外層 retry。來源：[SDK3.8 send](https://github.com/openai/openai-python/blob/v3.8.0/src/openai/_base_client.py)、[LC exceptions](https://reference.langchain.com/python/langchain-core/exceptions/)。需以實際SDK合成HTTP驗，不能只mock guard。

**施工前小探針已通過：**真 ChatOpenAI→SDK→HTTPX hook，counter回100、output預留30、capacity120；自訂公開雙基類 exception 成為不可重試 ModelError。counter1次、generation0次、無SDK包裝或重試。合成HTTP非真provider驗證；初次uv cache權限／直接python缺PYTHONPATH是執行環境問題，改用既有venv＋`PYTHONPATH=src`後通過。這證明接點，不代替Task2完整測試。

## Task 1: 按需分析 Skills 與既有讀取接線

Files: 新 `experiments/analysis-agent/src/analysis_agent/skills.py`、同 package `skills/*/SKILL.md`、`tests/test_analysis_skills.py`；修改 `memory_tools.py`、`live_memory.py`、`service.py`、必要的 README。只做此task，暫不碰provider預算。

1. RED：實際 create_agent／Service初次無 Memory也有三份metadata；完整方法正文尚未進輸入；`read_file`後下一model step才含正文。缺接線時先失敗。
2. 用官方 SkillsMiddleware＋trusted asset backend；同一 `ls/grep/read_file` 不重複註冊。MemorySession重綁版本後仍能讀skills，Memory reader仍pin正確版本；不得破壞 trusted read recovery。
3. 三份方法短稿（方法非舊schema），無網路fetch／execute／JD寫入工具。預設服務啟用；非Store測試路徑也只讀同資產，不暴露專案根／.env。前台才能拿analysis skills，B1/B2不自動拿。
4. 測 path traversal／絕對主機path被拒、不能修改assets、沒有名稱衝突；原生 reasoning／tool pairing／canonical retained；讀取後自動body含方法。用真framework＋合成SDK response，不自稱自然模型會自動正確選skill。
5. focused回歸→全套單次→自審→一個local commit；寫task report含紅綠／實際命令／警告／變更檔案。Controller獨立spec＋quality review後進Task2。

## Task 2: 每次實際 Responses 的完整預算

Files: 新 `src/analysis_agent/budget.py`、`tests/test_context_budget.py`；修改 `provider.py`、`api.py`、`service.py`、`scheduling.py`及契約測試／README。路徑均相對上述實驗package。

1. RED：真ChatOpenAI＋SDK＋HTTP mock，counter收到與生成一致的可计input/schema；超限時生成0次而非重試；normal A工具回傳之後重新核對；B1 native schema、B2工具定義都算。不能只測一個手寫dict。
2. 建立同步公開hook、獨立countclient、有限timeout與生命週期關閉。精確匹配本配置 Responses origin/path；不攔其他host或count本身；不記錄prompt／secret。計數回應正整數（空input可0），失敗failclosed。
   API 裝配時兩 client 必須使用同一已解析的模型 endpoint；以 SDK 公開 `base_url` 等接點核對，不能硬寫default URL卻因環境變更讓實際生成跳過預算。自訂 endpoint 未支援官方 count 就明確失敗，不聲稱相容或靜默退回近似值。
3. output上限取final payload；model不一致／缺上限／不合法context設定啟動或呼叫前清楚拒絕。用公開SDK count參數，不自解密原生items。若出現未被此計數接法涵蓋的遠端prompt模板等內容來源，不可直接忽略後宣稱完整；本版明確拒絕未支援的內容路徑，不新增模板功能。
4. 非可重試超限使用清楚 error_code，同既有安全close、解鎖及不誤收原文；背景blocked不每tick重試。不要新增一套外層無限修正。若需要新的terminal狀態，先核對所有目前允許值／恢復分類並保持最小改動。
5. 同步 A/B1/B2含structuredoutput／tool retry、native encrypteditem、current+oldmessages、threshold及count失敗、明確輸出reserve、SDK不額外重試本地reject。增加integration regression。
   既有 `tests/test_postgres_service.py::test_pg_default_api_lifespan_owns_real_clients_and_configures_provider` 直接替換 HTTP client.send，會繞過新request hook；須改為底層 MockTransport，讓真client與hook實際執行，並同時隔離計數與生成兩個HTTP client。測試不能意外發真實請求或因繞過hook而假綠。
6. focused→全套單次→自審→local commit；report與獨立spec＋quality review。若API或SDK能力與研究矛盾，停下回報，不造fallback冒稱精確。

## Task 3: 整體審核、文檔與交付

1. Controller跨接點review：實際API預設同時接Skills＋budget，動態tool讀取及C刷新後的下一call也被核對，B1/B2仍只拿各自背景規則；來源／原生延續不被計數或Skill修改。
2. 最終全套含專用PG、compileall、offline lock、diffcheck；不重啟／清空Docker。證據不與baseline相加；付費仍0。
3. 寫 `docs/specs/2026-09-07-context-budget-and-analysis-skills-results.md`，短述機制、官方來源、測試、限制與下一prompt實測gate；README只放運行接線，register只指路。已知其他未接gap不要冒稱完成。
4. 全branch最後獨立review，修重要finding後保存localcommit/tag，不merge/push。白話回報功能、代價與未測效果。
