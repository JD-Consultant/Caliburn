# Q019：Context／Tools／Skills／Memory 全接力審核

> 2026-09-06 · 審核對象 `codex/analysis-only-agent`，HEAD `f246f43caa4a6ffb5c555ebcb169519fa5a4eca3`。
> 本輪只做審核、離線驗證與紀錄；不修程式、不呼叫付費模型、不接 UI／JD／production。

> **後續（2026-09-07）：**Owner授權局部修復，BG-01／BG-02／MR-02已經紅綠驗證及獨立review CLOSED；最新370項含專用PG通過。見[修復結果](../../.worktrees/analysis-only-agent/docs/specs/2026-09-07-memory-reference-repair-results.md)。下列OPEN及程式行號保留修復前歷史；SK-01／CT-01及其他能力界線尚未完成，不能因局部修復就整體驗收。

## 1. 本輪邊界與閱讀路由

- **Topic：**`Q019-CONTEXT-MEMORY-AUDIT-01`。
- **Stage：**跨已交付切片的 readiness review；不把 Task4 的 298 項通過當成本輪全部能力已完成。
- **唯一問題：**實際模型輸入、工具、背景產物與引用，是否完整承接已同意的 Q019／OpenAI 機制？
- **Binding：**第一版只分析；每份文件獨立；A 原生延續、B 分段抽取整併、C 按需修補；完整原文保留、按需深讀；不重開架構或恢復舊系統。
- **停止線：**交付可重現缺陷、未完成能力、已接受限制與下一個 gate。需要修正時另行確認，不因 audit 擅自新增功能或更換框架。

先完整回讀 [總覽](2026-09-06-analysis-only-agent-design.md)、[Runtime](2026-09-06-analysis-only-agent-runtime-design.md)、[Memory](2026-09-06-analysis-only-agent-memory-design.md)、[原設計審核](2026-09-06-analysis-only-agent-design-review.md)，並以 [current register](../current-decisions.md) 的 Task4 最新保存點解讀歷史狀態。另回讀 [應用接線](2026-09-06-analysis-only-agent-application-wiring-design.md)、[背景通知／結果接線](2026-09-06-memory-consolidation-request-wiring-design.md)，不把「當時未實作」當成現在未實作。

機制依據：已完整回讀 [OpenAI 系統圖](2026-09-05-openai-conversation-context-and-memory-system-map.md)、[Context／預算核對](2026-09-06-context-window-retention-and-budget-wiring-review.md)、[摘要引用 producer→consumer 研究](2026-09-05-memory-summary-routing-and-deep-read-source-review.md)。獨立 reviewer 另核对[詳記更正 source review](2026-09-06-openai-rollout-summary-correction-source-review.md)及其接法。未讀 Owner 排除的舊產品流程長稿；新網路查核只補原生 reasoning／compaction 的契約疑點。

## 2. 實際 Context，不是概念示意

| 使用者／階段 | 實際取得 | 沒有自動取得 |
|---|---|---|
| A 主顧問，每個 model step | 短顧問規則、Memory 讀取政策、本輪初始小型導覽、系統提供的當前來源 reference；有效原生對話 items；實際 tool schemas | 全部工作理解、全部詳記、B1 候選、分析 Skill 正文 |
| A 的近期／壓縮內容 | 尚無 compaction 時保留 canonical 全歷史視圖；有 inline compaction 時，從最新 compaction item 加其後尚未壓縮的員工／AI／tool call/result items | 不是固定「最近 N 則」，也不再額外放一份自製延續摘要；長 run 的本輪早段也可能已進 opaque item |
| A 的 B 失敗提示 | run 開始時若 B blocked 且仍未涵蓋 target，加入短可用性提示及已保存 `target_reference` | 不灌入整段 B transcript、不偽造員工訊息、不額外喚醒 A |
| B1 抽取 | 自己的抽取規則、`NEW_SOURCE` 完整可見問答、`CONTEXT_ONLY` 消歧前文及技術回合狀態 | 不讀 A 的 opaque reasoning 或 compaction 取代原文；不讀全部舊 Memory |
| B2 整併 | 自己的整併規則、新候選及其真實詳記地址、目前導覽、兩個 Memory 檔案位置；需要時讀暫存正文／詳記；stale 重載時有相關 repair 問答 | 舊正文不是直接全塞 prompt；不開任意 raw 原文工具；不重跑 B1 來解每次 stale |
| C 即時修補 | A 提供已讀內容的精確小批編輯；系統提供 base、operation identity、來源及發布協調；工具結果回 A | C 本身不另呼叫模型、不啟動完整 B、不能初始化一份尚不存在的 Memory |

程式入口：[provider](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/provider.py:32)、[request view](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/runtime.py:15)、[非破壞 compaction](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/context.py:6)、[A 接線](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/service.py:116)、[A 導覽](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/live_memory.py:69)、[B 提示](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/scheduling.py:193)。

這個分層符合已選 OpenAI 概念：原始訪談、原生延續與可修訂知識各司其職；不是每次深讀到底。**不是聲稱逐欄複製 Codex 的完整私有 Context。** 原文仍在官方 Checkpointer；compaction 只裁模型視圖。Store 保存五產物對應內容，SQLAlchemy head／receipt 管發布，不是另一份工作理解。

## 3. 模型實際可用的工具與 Skill

| 階段 | Tool／模型要填的主要參數 | 實際責任 |
|---|---|---|
| A | `ls(path)` | 列可見虛擬目錄；不是搜尋電腦 |
| A | `grep(pattern, path?, glob?, output_mode?, max_count?)` | 文字搜尋、返回可讀定位；不是向量搜尋 |
| A | `read_file(file_path, offset?, limit?)` | 讀選中的正文／導覽／詳記，沿頁面續讀 |
| A | `read_conversation(reference, offset?)` | 沿 Runtime 已提供的引用讀完整可見問答；每頁最多 3,000 字 |
| A | `repair_memory(edits[])` | 每項只填 `path／old_text／new_text`；修目前兩個 Memory 檔，不填版本、時間或 Skill ID |
| A | `request_memory_consolidation()` | 無參數通知；固定短收據回 A，背景另行處理，不等 B 完成 |
| B1 | 無工具；三個結構化文字欄位 | `rollout_summary／raw_memory／rollout_slug`；不要求模型填來源 ID／地址 |
| B2 | `ls／grep／read_file／write_file／edit_file／validate_memory` | 暫存區的讀寫、詳記唯讀、格式／引用驗證；完成才發布 |

A 的六個 tools 是固定小清單；「按需」是模型選擇是否呼叫，不是已做動態 tool discovery。讀取使用 Deep Agents 公開 Filesystem tools／backend，來源 reader 與 C／通知是已同意的應用接線。沒有 shell、JD 編輯或子 agent 委派工具。

**SK-01／P2／未完成能力：**尚未註冊 Skills middleware、只讀分析 Skill 目錄或方法檔案。API 只有[簡短顧問 prompt](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/api.py:133)，不能說已接入研究過的專業分析方法。[Runtime §5](2026-09-06-analysis-only-agent-runtime-design.md#5-給模型什麼哪些不是模型填的)原本明列要整理方法 Skill；目前是待接線／Prompt 工作，不是已完成的 Skill 品質驗收。可用的現成 primitive 已有[官方 Skills middleware](https://docs.langchain.com/oss/python/deepagents/skills)，不需要因此另造一個 Skill 判斷模型。本輪不決定最終方法文字或擅自搬舊 Prompt。

## 4. 五產物與引用接力

```text
canonical 原始問答（Checkpointer）
  → B1：詳記 rollout_summary ＋ 候選 raw_memory ＋ 可讀標題 rollout_slug
  → Runtime 保存 summary.md／candidates.md，補真實來源 header
  → B2：讀候選，必要時沿 summary_path 開詳記
  → 發布 knowledge.md（目前理解）＋ guide.md（小型導覽）
  → A：導覽 → grep 正文 → 選讀詳記 → 必要時 read_conversation
```

- `raw_memory` 不是正式知識、不例行注入 A；候選檔保存指向同批詳記的地址。
- `rollout_slug` 只是標題素材；路徑身份由 Runtime 產生，不以模型命名當唯一 ID。
- 詳記 header 包含實際來源範圍、可選消歧前文、明確分隔；不是逐句證據或模型推理。
- `knowledge.md` 對應 `MEMORY.md`；`guide.md` 對應 `memory_summary.md`，沒有另造第六份 Memory 導覽。
- B2 prompt 明示保留適用情況、關鍵詞、案例差異、未知與詳記引用；語意相關性由模型選，不是 Store 自動理解。
- 同來源重抽另存新詳記；跨段更正進新詳記並更新目前理解／引用。**不自動改所有舊詳記**是已同意界線，不列新缺陷。

依據：[Memory §1–4](2026-09-06-analysis-only-agent-memory-design.md)、[OpenAI 引用建立與漸進讀取 §2–4](2026-09-05-memory-summary-routing-and-deep-read-source-review.md)、[實際產物保存](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/memory.py:115)、[B1 prompt](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/extraction.py:35)、[B2 prompt／輸入](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/consolidation.py:22)。

## 5. 確認缺陷與待補能力

### BG-01／P2／OPEN：合法詳記引用會因 Markdown 強調被誤拒

- **位置：**[memory.py:182](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/memory.py:182)。
- **重現：**`P` 是剛由 Runtime 保存且可讀的 summary 路徑；裸 `P` 通過，`__P__` 卻回 `Memory reference is unavailable in this document`。Regex 把結尾底線算進地址，清理只移除句點。
- **影響：**B2／C 可能因合法 Markdown 被退回；B2 若最終仍無效，卡在交付驗證，原樣 resume 不會自動多叫模型修好。
- **要求：**處理正確地址邊界並補合法格式回歸。不是叫模型避免正常 Markdown、不是放掉不存在引用。主審已用真實 StoreBackend 與 validator 重現；獨立 B reviewer 另走 B2 圖確認。

### BG-02／P2／OPEN：B2 未檢查正文裡的原始對話引用

- **位置：**[memory.py:177](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/memory.py:177) 的共同 validator 只檢查 `/interviews/`；[C 的額外驗證](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/repair.py:87)則有讀 `conversation:`，兩路不一致。
- **重現：**格式正確、同文件但 checkpoint 不存在的 `conversation:` 地址，可被 `validate_texts`／`save_memory` 接受，並經真實 PublicationStore 發布到 revision 2；之後同一 source reader 拒讀，回 `Conversation source is unavailable; do not substitute latest text`。
- **影響：**成功發布不代表原話引用可回查。跨文件引用也可能混入文字，但 reader 仍拒讀；**不是證明跨文件資料洩漏**。
- **要求：**對實際存在的原文引用使用既有來源解析／reader，在可修正的驗證階段及發布前一致檢查。不要求逐句必填引用、不新增語意判真模型、不開放 B2 任意原文搜尋。獨立讀取與 B reviewer 同根 finding 合併，不重複計數。
- **同根補例（獨立 reader 審核）：**C 的 regex 對 `conversation:???` 完全不擷取，故仍能發布；空目標 `/interviews/` 也漏驗。不能只修 B2 或只測合法編碼的不存在目標，還須涵蓋有受控引用前綴卻格式損壞的情形。

### MR-02／P2／OPEN：前輪只有工具、沒有可見回答時，C 的更正來源漏掉前文

- **位置：**[sources.py:156](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/sources.py:156) 的 `capture_input()` 往前找顧問文字，但遇到上一個 HumanMessage 就停止。
- **重現：**先前顧問問「是由主管核准嗎？」；員工 h1 說「不是主管，是處長。」；模型本輪只讀工具，之後因額度安全結束，沒有可見 AI 回答。h2 說「對，剛剛說的是 A 案」，C 才將主管改為處長。已發布 receipt 的來源只含 h2，沒有真正提供更正的 h1 及顧問問題。
- **影響：**原文沒有刪除，但沿 C 的來源引用／B2 stale 時的 repair 問答回讀，拿不到應有更正脈絡。這是來源定位缺口，不是已證明自然模型一定會覆寫錯誤。
- **要求：**來源定位需處理安全封閉、無可見 AI 的中間回合，保留必要問句及其間員工回答；先沿既有 B1／source primitives 核對，不放寬仍未結束來源或另存一份原文。依據：[C 來源約定](2026-09-06-analysis-only-agent-live-memory-results.md)、[Memory §6](2026-09-06-analysis-only-agent-memory-design.md)。
- **既有測試盲點：**`test_limit_then_short_correction_keeps_real_question_not_technical_source` 刻意有一段 AI commentary 問句，所以通過不能涵蓋本反例。
- **主審複核：**相同 compiled root／Agent／Store／PublicationStore 探針得到 `first_status=limit`、`revision=2`，來源只有 `user：對，剛剛說的是A案。`；獨立重現成立，未修改程式。

### CT-01／P2／未完成能力：完整 request 預算尚未接線

現行入口已要求部署明訂 compaction threshold、timeout、output limit，並有 model／tool 次數上限；不是完全沒有限制。但 `runtime.py` 只裁有效 items，沒有按[Runtime §4.3](2026-09-06-analysis-only-agent-runtime-design.md#43-預算與快取)核對規則＋工具 schema＋導覽＋對話／結果＋輸出餘裕的完整 request。

[API 輸入](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/api.py:34)也沒有長度／模型容量上限。這裡記錄**既定要求未完成**，不是已觀察到真 API 超窗；不能宣稱「有 compaction 就任何單次輸入都安全」。沿既有[官方 counter／adapter 能力研究 §2](2026-09-06-context-window-retention-and-budget-wiring-review.md#2-完整-request-預算可直接重用的官方能力)補接線，具體門檻另核對，不自行增加摘要 Agent 或偷偷截掉原話。

## 6. 已排除的誤判與能力界線

1. **`store:false` 未指定 `include` 不是缺陷。**本輪重新開啟 OpenAI [Preserve reasoning without stored responses](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-without-stored-responses)：目前 stateless 預設返回 `encrypted_content`，`include` 舊寫法仍相容但非必填。因此撤銷最初疑點；不可依舊認知加「修復」。離線測試只證明收到後能 round-trip，不替真服務／模型品質背書。
2. **「近期訊息」不是固定 N 則。**目前採 inline server compaction；官方允許 request 丟掉最新 compaction 以前的 items。Standalone compact 的整個 output 才須原樣傳下去，不能混用規則。[OpenAI Compaction](https://developers.openai.com/api/docs/guides/compaction#server-side-compaction)
3. **背景 blocked 的原文可達。**`notice()` 包含實際 `target_reference`，A 可交 `read_conversation`，不是只有一句空泛的「必要時回查」。但尚未排程、無任何可達詳記／reference 且舊 QA 已離開直接視窗時，A 沒有通用原文搜尋／鄰近範圍擴展工具；原文仍存，不代表模型必定可自主定位。這是 coverage gap，需先討論是否補官方 primitive 接法，不立即新造工具。
4. **grep 是文字匹配。**寫入關鍵詞與導覽幫助模型定位，但沒有證據保證任何同義問法都命中。無命中不等於不存在；全量盤點也不能用 top-k 代替。v1 沒有 mandatory 自動混合召回是已選策略，不因舊稿曾提到而列回歸缺陷。
5. **C 更新後的固定初始導覽。**read head 與工具結果可以受控刷新，初始 system prefix 保持不變。若同輪再 compaction，仍需真模型驗證延續內容與新版路由的效果；不能只憑 opaque item 推定必然遺失或必然正確。
6. **Prompt 規則不等於品質保證。**未知、案例差異、去重與引用選擇已有 B 指示，但腳本化輸出不證明自然模型會完整做到。仍依既定小額 Luna／medium 驗收及第四步 Prompt 優化，不重建大型 eval。
7. **MR-03／P3／查找提示不一致。**backend 固定每次搜尋總共最多四筆 grep 命中，但官方工具截斷提示可能叫模型提高 `max_count`；提高後仍四筆，會浪費額度。正文仍能以 `read_file` 分頁完整讀取；四筆限制是既定成本取捨，不是要取消限制。需要讓提示與實際能力一致，這不阻擋原文保存／全量列舉。**2026-09-07文字勘誤：**原寫「每檔」不精確；已核對locked Deep Agents `BackendProtocol.grep` 的 `max_count` 為 total cap，`ReadOnlyFiles.grep` 沿此參數限4，不是每檔4。
8. **文件里程碑不能混成現況。**Runtime 的「入口尚未接上」及通知稿的「Task4 尚未施工」是舊保存點；當前 API 已強制要求 compaction 配置、worker 已接好。最新狀態依 register／Task4 結果及本稿，不能重新施工已完成能力。

## 7. 驗證證據與交付界線

- 主審：`test_native_continuity.py`＋`test_agent_runtime.py` **11 passed**；真實 adapter／SDK／graph，僅 HTTP 回覆為合成資料。覆蓋原生 reasoning／工具／phase、序列化、下一輪、compaction 非破壞、有效 call/result 配對。
- 主審另跑 `test_memory_read_path.py`、`test_live_memory.py`、`test_extraction.py`、`test_consolidation.py`：**94 passed（19.40s）**。合計本輪主審 105 項既有測試通過；新反例尚未入 regression，所以不能以全綠抵銷上述 finding。
- 主審 wire 探針：A Memory 清單為五個讀取／修補工具，通知由根 conversation 再加入；本輪新輸入只出現一次。Runtime identity 不進 repair schema，只有 `edits`。
- 主審引用探針：真實 InMemoryStore／StoreBackend／PublicationStore＋記憶體 SQLite 重現 BG-01／BG-02，沒有連實際產品 DB 或 provider。
- 獨立 B reviewer：B1 既有測試 **33 passed**、通知／來源邊界選測 **9 passed／6 deselected**，另有 B2 圖探針；不是新 PG 整合或真模型測試。
- 獨立讀取 reviewer：分兩批 **51＋8 passed**，補原文引用／C 短答／grep／C 後 compaction 探針；測試與主審有重疊，不相加成唯一案例總數。PG 測試只審讀，未重跑。
- 本輪未驗：真模型語意召回、壓縮後分析品質、自然內容取捨、長訪談費用；不把之前 298 項或上述腳本測試替代這些效果。

## 8. Closure

**Finding：**整體 A/B/C 及五產物接力仍符合已選方向；3 項 P2 引用／來源缺陷（BG-01、BG-02、MR-02）待修，2 項 P2 能力（SK-01、CT-01）未接完。另有 P3 查找提示、原文可達性及真模型效果界線，不能直接宣稱分析底座已完整驗收。

**Status：**READ-ONLY AUDIT，OPEN findings 待討論修正；不是修改授權、不是 G8 pass。

**Next gate：**先報告缺陷／能力邊界，確認修正範圍；以局部離線回歸補引用和既定接線，再安排 UI／小額真模型驗收。只在反例、官方契約改變或 Owner 改範圍時重開已定概念；不重選 Memory 架構、不重做 OpenAI 全套研究。
