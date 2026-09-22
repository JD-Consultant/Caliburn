# Q019 設計審核與來源：從零、只分析的 Agent

> 2026-09-06 · **文件設計交付；不是實作／效果測試通過。**
> 閱讀入口：[方案總覽](2026-09-06-analysis-only-agent-design.md)。這裡只持有比較、證據、差異與驗收，不複製完整 Runtime／Memory 規格。

## 1. 本輪怎麼審，哪些已經讀過

遵守 [Decision-to-Product](../decision-process.md)：先對齊最新目標，再看完整資料流，最後檢查 adapter、保存／查找及寫入並行等接點。以下是設計階段的研究紀錄；Owner 後續已回覆「可以繼續了，有問題提出來討論」，准許隔離開發，不代表 production 切換或測試通過。

本輪完整回讀的核心設計／機制資料：

- [單訪談 Memory 流程與五產物](2026-09-05-work-understanding-memory-flow-working-design.md)：用途、單 thread、A/B/C、引用、漸進停止。
- [Framework source／summary primitives](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md)：原文在哪、request-view 與持久替換、reader、成對工具限制。
- [Context retention／budget](2026-09-06-context-window-retention-and-budget-wiring-review.md)：三種壓縮接法、預算、原生推理前置條件。
- [框架整體接力提案](2026-09-05-memory-framework-end-to-end-composition-proposal.md)：持久 owner、tool／Skill、兩階段及成本。

定向核對的需求／證據：

- [能力研究 §5.2–5.3](2026-08-31-perfect-jd-llm-capability-and-mechanism-working-research.md)：M1–M11；不是將舊資料結構當需求。
- [OpenAI 系統圖](2026-09-05-openai-conversation-context-and-memory-system-map.md)、[summary routing 固定 source 研究](2026-09-05-memory-summary-routing-and-deep-read-source-review.md)：CLI 與 SDK 的差別、抽取 producer／consumer、關鍵詞與引用。
- [B/C 既有研究](2026-09-05-memory-background-live-repair-coordination-research.md)：Store API 不等於 atomic publication。

沒有以舊 production 施工計畫約束新設計；沒有讀 Owner 排除的 `2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md`。新的官方補查只針對原生 reasoning、compaction、原生 SDK 替代、公開框架接點及發布交易，不重做全部 OpenAI Memory 原理。

## 2. 原生 OpenAI SDK 也已納入，不把框架當前提

Owner 本輪補充：框架難用可改原生 OpenAI SDK 或其他方案。以下是**三個整體方案**，不是從名稱判斷。

| 方案 | 能直接重用的部分 | 仍需處理／與目標差異 | 本輪結論 |
|---|---|---|---|
| **LangChain／LangGraph＋原生 Responses** | Agent loop、middleware、Saver／Store、durable steps、filesystem／Skill primitives | 原生 item adapter 要驗；原文 reader、背景觸發、發布 seam 要組合；長 message channel 有 DB 成本 | **推薦**。這版需要完整 B/C、來源回查與按需方法，不只一個聊天 loop；可使用同一框架生態承接較多接點 |
| **普通 OpenAI Agents SDK＋Session** | 原生 OpenAI Runner／tools、typed output、原始 response items、SQLAlchemySession、輸入 filter | 自訂長期 Memory 產物／工具／背景續做仍需要；一般 Session 不是 Memory 生成器；選 compaction wrapper 要另解來源保留 | 正式替代。若 LangChain 原生 reasoning round-trip 不合格，改它，不勉強 adapter |
| **OpenAI SandboxAgent＋Memory capability** | 真正兩階段、五產物、導覽、按需 shell 查找、live update、workspace lifecycle | beta；讀 Memory 依賴 Shell、live update 依賴 Filesystem；預設 session close 後整理，長抽取輸入會截短，有限候選有淘汰；本案仍需改生命周期／完整分段／隔離與並寫 | 不直接照預設採用。目的相近，不表示開 `Memory()` 就符合全部細節效果 |

**SDK 的重要區分：**普通 Session 會保存 conversation items；`session_input_callback` 可以只改模型輸入視圖。但 `OpenAIResponsesCompactionSession` 會 clear／rewrite 底層 Session，不是只有 request trimming。若把唯一完整訪談包進後者，不能再宣稱原文一定完整保留。[官方 Session／Compaction 行為](https://openai.github.io/openai-agents-python/sessions/)

Sandbox Memory 的 SDK 與 Codex CLI 是相關但不同的公開產品。研究日官方標示 beta、關閉觸發、抽取截短與候選淘汰；它們是本輪選型理由，不是說原生 SDK 不可靠或無法擴充。[官方 Sandbox Memory](https://openai.github.io/openai-agents-python/sandbox/memory/)

**為什麼不是原生就一定較好？**原生減少 provider adapter 接線；LangGraph 則提供本案已需要的持久 workflow／Store 生態。要比較總體接合成本及效果，不能只比較呼叫 LLM 那幾行。也不能因已研究 LangGraph 就禁止更換：如果小型驗證顯示 adapter 或 snapshot 儲存的代價超過整合收益，就按替換條件重選，不造大量兼容補丁。

## 3. 最新官方補查與能支持的結論

| 來源 | 本輪核對什麼 | 不能據此宣稱什麼 |
|---|---|---|
| [OpenAI reasoning](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-across-calls) | all_turns、適用 family、完整 opaque items、stateless 延續 | 每種模型都支援、永久記得所有分析、可編輯隱藏思考 |
| [OpenAI compaction](https://developers.openai.com/api/docs/guides/compaction) | server-side 與 standalone 行為、有效視窗、encrypted item | 摘要等於原文，或壓縮不用錢 |
| [Anthropic preserved thinking](https://platform.claude.com/docs/en/build-with-claude/preserved-thinking) | 保留 prefix／signature 的模型特定規則 | OpenAI 與 Claude opaque state 可直接互換 |
| [LC OpenAI adapter](https://docs.langchain.com/oss/python/integrations/chat/openai) | Responses、reasoning、compaction 的公開參數與 content blocks | 選定套件與帳戶已實測合格 |
| [LC adapter source](https://github.com/langchain-ai/langchain/blob/master/libs/partners/openai/langchain_openai/chat_models/base.py) | opaque output／phase 轉換與 response_metadata 的暴露範圍 | 動態 HEAD 是已安裝版本、每個頂層欄位都保留到 metadata |
| [LangGraph Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers) | 持久 channel、DeltaChannel 的版本／beta 邊界 | latest feature 可不經測試直接取代標準 message reducer |
| [LangGraph Store](https://docs.langchain.com/oss/python/langgraph/stores) | namespace、讀寫、列舉與可選 semantic search | Store 普通 put 就是跨檔 CAS；向量搜尋可證明全量看過 |
| [Deep Agents backends](https://docs.langchain.com/oss/python/deepagents/backends)／[Skills](https://docs.langchain.com/oss/python/deepagents/skills) | StoreBackend、虛擬路徑、公開擴充接點、按需讀 Skill | 安裝整包才可用；必須帶 planning／subagent／shell |
| [LC structured output](https://docs.langchain.com/oss/python/langchain/structured-output)／[middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in) | 小 schema、錯誤回報及 call limits | strict 能判定語意正確，或 retry 保證成功 |
| [SQLAlchemy versioning](https://docs.sqlalchemy.org/en/20/orm/versioning.html)／[PostgreSQL isolation](https://www.postgresql.org/docs/current/transaction-iso.html) | ORM 版本檢查、短交易、並寫可見性 | 能在 LLM 工作期間自動做語意合併 |
| [Anthropic context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | 適量 Context、just-in-time、按需工具／檔案 | keyword 永遠勝過向量，或不同家方法必然相同 |

閱讀日為 2026-09-06。可用模型／API 參數依最新文件與帳戶核對；沒有沿用舊模型限制表作現行事實。框架 source 某些是官方動態分支，**不是鎖定套件的可重現執行證据**。進入施工時才鎖具體相容版本並保存 lockfile，不將未安裝視為已驗證。

「通用／成熟」在此指公開、有實際元件的模式。整套方案、資料路由、觸發閾值與 publication schema 是有來源支持的本案組合，**沒有足夠證據說各大廠逐項都採相同底層實作，更不能證明本案是全球最佳效果**。

## 4. 相對前輪設計的明確變化

| 變化 | 原因／狀態 |
|---|---|
| 第一版只有分析；不做 JD 編輯、核准／Diff／匯出 | Owner 最新範圍，已確認；不是忘記舊需求 |
| 原生 reasoning＋native compaction；不另造每輪分析筆記 | Owner 已同意目的；實際接線提案，待小型 round-trip |
| LC／LG 仍推薦，但原生 SDK 是實質替代 | Owner 允許自由選框架；沒有以舊 Work Model authority 為理由拒絕替代 |
| v1 導覽＋按需 keyword／引用讀取，暫不強制每輪向量召回 | **本輪新調整提案**；若同義案例查找不足便重開官方 semantic search，未假裝 Owner 先前已核准刪除自動召回 |
| 不直接套 Sandbox Memory 預設 truncation／recency pruning | 完整細節可回查的目標不同；有界分段處理完整新範圍 |
| B/C 改以資料庫版本＋提交回執發布 | **本輪新接法提案**；解決 process lock 跨重啟／不確定提交不足，不增加另一个語意 store |
| 背景 idle／批量、run call limit 有初值 | 可調工程參數，非既有承諾／大廠統一最佳值 |

上述接法現作為 Owner 已同意的隔離 Working Design；可依實際反證提出修訂，不能擅自改掉目的。舊 Accepted ADR／production 尚未改變。

## 5. 從需求到設計的覆蓋核對

依能力研究 M1–M11，這版檢查的是 Memory／分析底座：

| 能力 | 設計承接 | 尚不能聲稱 |
|---|---|---|
| M1 長訪談、關閉後延續 | 完整 checkpoint＋原生有效 context＋持久 Memory | 永不重新分析 |
| M2 細節不永久失去 | canonical 原文保留、詳記引用、分頁 reader | 詳記等於無損記憶 |
| M3 工作範圍可盤點 | 完整來源處理範圍、所有正文可列舉 | 已完成 JD 的語意全涵蓋 |
| M4 理解可修訂 | B consolidation＋C live repair | 背景無論如何都會立刻更新 |
| M5 未知、未答與矛盾 | 相關內容自然語言保留、詢問員工 | 每個未答問題必有專用 workflow record |
| M6 關聯與條件 | rich content、不同案例條件及可回讀詳記 | 所有關聯都需知識圖譜 |
| M7 案例與一般模式 | 詳記保存案例，正文提煉共同工作與有意義差異 | 每案例必產一項工作 |
| M8 按需取用 | 導覽→搜尋正文→詳記→原文，足夠就停 | 搜不到即沒有、向量已接好 |
| M9 全量檢查底座 | 固定版本分頁列舉到 EOF | 每次分析必讀全部 |
| M10 可回查來源 | 可信來源位置、真實問答、無 quote offset 填表 | 機器驗證等於語意真實 |
| M11 文件隔離 | runtime 固定 namespace／source scope | 做成全使用者共同 Memory |

Native reasoning 是額外的多輪推理延續能力，與 M1/M4 有幫助但不取代上述長期資料。B 看不到 A 私有 reasoning；它仍須從可見訪談整理，成本不是免費複用 A 全部思考。

## 6. 自我審核發現與修正

| ID | 問題／影響 | 處理與狀態 |
|---|---|---|
| Q019-F01／P1 | 只保 `.text` 會丟原生推理／工具及 compaction items | Runtime 明定完整 items；**需施工短測** |
| Q019-F02／P1 | 將通用 summary 視為原生推理延續 | 改原生 compaction，不疊通用 summarizer；文件已修正 |
| Q019-F03／P1 | 存在 compaction 功能不等於原文未被改 | 釐清 request view 與 SDK wrapper 的實際 rewrite；本方案 canonical 不清空 |
| Q019-F04／P1 | Store put／程序鎖不能保證 B/C 不丟更新 | 改 DB CAS＋immutable artifacts＋receipt；**需並寫／斷線短測** |
| Q019-F05／P1 | 發布時新載入 head 就用新版本硬寫舊結果 | 明定 expected analysis base 先比對，再由 ORM flush 防競爭 |
| Q019-F06／P1 | ambiguous commit／只保最後 operation 會重播舊效果 | 同 ID／同內容重查、持久 receipts、同交易更新；不猜 timeout 一定失敗 |
| Q019-F07／P2 | 只看近期 tail 或摘要會遺失抽取中段 | B 分完整問答視窗，不丟中段；原文 retained |
| Q019-F08／P2 | 超大 tool output／全規則未算入預算 | 每次 actual model call 前算完整 request、工具有界續讀 |
| Q019-F09／P2 | 框架數量／技能數量被當成功效果 | 以能力與下面情境驗收，未做項目明列 |
| Q019-F10／P2 | 說「最新」但沒有指定可執行版本 | 文檔來源日與 install／live 驗證分開，不假報已通過 |
| Q019-F11／P2 | C stale 後要求重讀，但 reader 仍固定舊版 | 補受控 head／guide 刷新、Command 更新 state；v1 A 工具序列化；需短測 |
| Q019-F12／P2 | 重啟只按 dirty 重排，找不到 B1／B2 attempt | 補穩定 B workflow 路由、Runtime job checkpoint 欄位、先對帳 receipt 再恢復；需短測 |

另作過 read-only B/C 與四稿整體交叉審核：expected-base、ambiguous receipt、artifact 封存、C 讀取刷新與 B job 恢復五處接點已補入設計。它不是執行測試，也不是 Owner approval。

## 7. 開發時的最小驗收，不建大型 eval

| 情境 | Pass／Stop 觀察 |
|---|---|
| 兩輪模型、工具再回模型、關閉重開 | 完整 native items 可 round-trip；工具配對正確；不是只靠兩句文字答對就通過 |
| 長 Context 原生 compaction | 後續有效 window 可呼叫；原本遠處真實問答仍可讀；未把 summary 當原文 |
| 前幾輪尚無 Memory | 能靠近期內容／原生 reasoning 繼續訪談；不強制填工作理解巨型 schema |
| A／B 都是網站接案但條件不同 | 正文能提共通工作而不機械複製；指定案例特有條件可沿引用找回 |
| 明確更正 vs 不確定矛盾 | 明確者可修補；不確定者詢問，不採最後一句永遠贏 |
| B 未完時 C 成功 | B 舊版發布被擋；B2 重讀新版本與來源，不把更正蓋回去 |
| 發布成功但回覆／checkpoint 前斷線 | 同 operation 可回復原結果，不重複發布；receipt 不隨後續版本消失 |
| 工具、provider、儲存失敗／取消 | 不宣稱成功，不永久鎖聊天，重試不重複新增來源 |
| 背景重啟／no-op | 新來源未漏處理，已完成範圍不反覆付費整理 |
| 大量資料／全量列舉／隔離 | 不把 top-k 當全部；可走到 EOF；另一文件資料不可讀 |

先以 fake model／小資料庫測接線與錯誤，再經核准做極少 Luna／medium 真實回合，記錄實際費用與觀察。**本輪沒有跑這些測試、沒有花 API 費用。** 對需要付費才能證明的 reasoning／分析效果，不拿文件檢查冒充實測。

## 8. Closure／下一個 gate

- **Decision：**有完整、單一推薦的 analysis-only 設計；三方案已有實質比較，不再維持無限開放框架清單。
- **Status：**`OWNER ACCEPTED FOR ISOLATED DEVELOPMENT`；不是實作通過、不是 production authority。
- **Why：**同時處理原生延續、長期記憶、來源可回查、成本及並寫；不只湊元件名稱。
- **Affected artifacts：**本輪四份 Q019 文件＋current decision register；舊研究只保留追溯入口。
- **Reopen：**Owner 修改目的；原生 adapter 不相容；來源／查找／長訪談成本檢查反證；官方元件有足以消除自訂接點的新能力。
- **Next gate：**按[第一切片計畫](../plans/2026-09-06-analysis-only-agent-native-continuity-slice.md)分段接線／驗證。遇到反證先記錄並討論相應接點，不重做全部研究。
