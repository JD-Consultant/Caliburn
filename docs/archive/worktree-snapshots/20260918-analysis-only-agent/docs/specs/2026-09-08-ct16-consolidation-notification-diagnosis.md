# CT16：段落通知沒有再次觸發的診斷

2026-09-08 · `Q019-MEM-CADENCE-01`／`CT15-R07` · **隔離通知指引已校準，33項離線接線回歸通過；語意效果仍待真模型驗證。**

最新：提示校準後的[CT16真測結果](2026-09-08-ct16-notification-live-results.md)已封存；實質補充通知成立，但短更正未入Memory，G8仍OPEN。本頁§5–6是校準實作；§1–4保存修改前診斷，不重新詢問已核准修正。

## 本輪問題與邊界

Owner 問：「是不是段落通知有問題？」先區分模型未呼叫、工具執行失敗、收據未保存、背景未承接，不以增加門檻／排程掩蓋根因。

既有策略仍是「主顧問段落通知＋未整理文字量備援」。以下 §1–4 是核准前的診斷階段：當時未改 ABC、模型、工具 schema、prompt、排程或資料；沒有付費測試。後續僅提示校準見 §5–6。5,000 字元未定案；不新增 90 秒閒置、每輪強制整理或額外判斷 Agent。

詳細沿革只從以下文件閱讀，不重抄全部 Memory 設計：

- [整理時機與成本／效果研究](../../../../docs/specs/2026-09-06-memory-generation-cadence-and-continuity-review.md)：官方時機差異與既有 Owner 限制。
- [通知工具接線設計](../../../../docs/specs/2026-09-06-memory-consolidation-request-wiring-design.md)：通知不是立即整理，回合安全結束後由背景承接。
- [CT15 結果](2026-09-08-ct15-grounding-and-whole-interview-results.md)：品質 G8 OPEN；不是原文遺失。
- [封存實驗證據](evidence/2026-09-08-ct15-full.json)：本輪只讀，不重寫原失敗與模型輸出。

## 1. 已確認的資料流事實

核對隔離程式保存點 `848160b39c0b315db9e6c2dc68e58cfd1d5b68a1` 與 CT15 真實 input/output：

| 檢查位置 | 證據 | 能下的結論 |
|---|---|---|
| 模型送出通知 | request #6、#23 各有一次 `request_memory_consolidation({})`，對應 T4、T13 | 不是模型從未知道或無法使用工具 |
| 工具回傳 | request #7、#24 的 input 有對應 call ID 的「收到整理請求」收據 | 兩次呼叫不是只有可見文字宣稱通知 |
| 背景處理結果 | 兩批自然整理成功，產生三份詳記、Memory revision 2，處理至 T13 | 這兩次通知→背景鏈可運作；不代表所有失敗分支已無 bug |
| 後期模型輸入 | #33／#34／#35／#43 仍提供通知工具，system 仍有通知指引 | 本例不是後期工具被卸載或通知指引消失 |
| 後期模型輸出 | 上述後期 request 沒有再呼叫通知工具 | 缺口發生在「是否提出新整理請求」，不是新請求送出後遭背景漏接 |
| 備援配置 | 封存資料 `text_threshold=null` | 只測到模型通知，沒有測到啟用文字量的完整組合 |

程式位置：[通知與收據](../../experiments/analysis-agent/src/analysis_agent/consolidation_request.py)、[工具接入](../../experiments/analysis-agent/src/analysis_agent/conversation.py)、[排程判斷](../../experiments/analysis-agent/src/analysis_agent/scheduling.py)。`BackgroundDispatcher._step()` 在沒有新通知、文字量備援又未啟用時，直接略過；此處沒有呼叫 B1/B2，因此不能稱為背景模型失敗或重試耗盡。

晚期 T14／T15／T16 的未整理可見文字累積分別為 1,402／1,914／2,581 字元；包含補充石橋案例與月報狀態。收尾中斷後重新送出才達 8,630，裡面也包含顧問回述與收尾文字。**不能把 8,630 全稱為員工新事實，也不能說設 5,000 就會在 T15／T16 及時整理。** 原文仍保留，未整理不等於資料被刪除。

## 2. 提示是主要待驗假設，不是已證明的唯一原因

封存主提示為：「一段訪談已有值得整理的資訊時，可通知背景記憶整理；不必每回合通知。」工具描述另說可以仍有未答問題、不要求主題全部完成。

**Inference：**「值得整理／可通知」留給模型較大的選擇空間；雖已有不要等全部完成的說明，但沒有很明確地交代持續补充、更正、轉向或收尾時該如何判斷新的整理機會。這是值得局部校準的候選原因。不能讀取或猜測模型隱藏思考，也不能只凭沒呼叫就聲稱模型忘了、把通知當成功整理、或一定是某個字造成。

同版後期工具和指引仍可見，排除了「工具根本沒接上」這個本例假設；但提示改好能否可靠觸發，仍要以局部對照確認，不能用字數備援的成功冒充提示本身已修好。

## 3. 官方依據：可學的方法與不可冒稱的共識

- **Official fact — OpenAI：**[Function calling／Best practices](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions) 要求工具目的清楚，system 說明何時使用及何時不使用；並建議將程式已知的工作交給程式，不叫模型填已知參數。本例空參數通知不必改成另一張表。其 [Tool choice](https://developers.openai.com/api/docs/guides/function-calling#tool-choice) 明確區分預設模型自行選擇與強制工具；工具可用、schema 正確，不代表每個適當時機必然呼叫。
- **Official fact — Anthropic：**[Define tools／Best practices](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools#best-practices-for-tool-definitions) 同樣要求具體說明工具何時應用／不應用及限制。這支持先修正工具使用指引；不代表應把 prompt 無限加長或每輪強制用工具。
- **已研究的時機差異：**[Codex local memories](https://learn.chatgpt.com/docs/customization/memories) 是合格 session、避開活躍 session 的背景政策；[Sandbox Agents Memory](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs) 有 session 關閉後抽取整併；[LangChain Writing memories](https://docs.langchain.com/oss/python/concepts/memory#writing-memories) 將背景時機作為應用取捨。詳見父研究，不將 session 關閉等同員工每輪輸入。

**沒有查到 OpenAI／Anthropic 共同要求「段落通知＋5,000 字」的規格。** 共同依據是明確工具指引與應用控制；目前組合策略是已討論的 Caliburn 選擇，不是兩家逐項相同的底層。

## 4. 建議的收斂次序（歷史待審；局部提示修正現已核准）

1. **先局部檢查通知提示的觸發條件，保留現有工具與背景接線。** 只做判斷指引，不讓模型重寫詳記、理由、ID，也不強制每輪整理。具體文字在 Owner 確認方向後再定。
2. **把文字量備援視為另一條保障，不當成通知已修復的證據。** 可分開觀察「模型是否通知」與「備援是否啟動」。本輪不選數值、不提高額度、不重跑長訪談。
3. **留下短尾端邊界：**沒有通知且不足門檻時，光降低文字門檻仍不能保证所有末尾補充入 Memory。是否另外需要生命週期／補整理時機，是同題後續待決，不偷偷加入 timer 或員工按鈕。

診斷階段停止點：本例斷點已定位，官方已直接支持先改善何時用工具的指引，不必重新研究整個 Memory。當時下一 gate 為 Owner 審閱，現已核准；提示有效性仍屬後續最小對照，不先宣稱修復。

診斷階段 Closure：研究與記錄完成，0 次付費請求／US$0；當時程式、配置與原始實驗證據未改，CT15-R07／品質 G8 仍 OPEN。

## 5. Owner 核准後：依高品質 JD 研究校準通知（2026-09-08）

Owner：「同意，這部分要寫好，建議回看如何製作出滿分職務說明書的文檔。」本次是既有兩處提示的局部修正，不是新增工作分類器／狀態欄位／排程器。

完整回讀[高品質 JD 能力研究](../../../../docs/specs/2026-08-31-perfect-jd-llm-capability-and-mechanism-working-research.md)，並核對[成品研究 §18.9–18.12](../../../../docs/specs/2026-08-28-llm-authored-field-contract-audit.md)及現有三份分析 Skills。只承接職務分析目的，不搬回歷史 schema 或已被後續討論取代的流程。

| 研究要求 | 通知判準的映射 | 不能誤解為 |
|---|---|---|
| 工作廣度與細節可得（L1/L2、M2/M3） | 新範圍、案例中本人做法、成果、頻率、條件或交接有可保留進展 | 只有常見工作才值得保存，或只用字數判斷價值 |
| 案例與穩定工作並存（L5/L6、M7） | 類似案例帶來的新條件／例外仍有整理價值 | 每個案例各建Task，或沒有新增Task就不通知 |
| 完成判準与專業判斷（L5、M6） | 新釐清的品質判準、判斷依據及知識技能也算進展 | 一定要問出獨立產出或填滿OPKS才能整理 |
| 可修訂與未知保留（M4/M5） | 有實質影響的短更正／確認可通知，未解問題可如實保存 | 短句沒有價值、未知等於沒有、一定要問到答案才保存 |
| 成本與持續性（L10） | 零碎補充可成段整理，純重述不重複通知；轉向／收尾前注意未通知的新進展 | 每輪強制通知，或換話題本身就是新資訊 |

**官方方法依據：**[OpenAI GPT-5.6 提示指南](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6#simplify-prompts-first)要求保留成果、判準、證據與必要工具路由，精簡重複指令；其 outcome-first 段落對判斷性工作建議 decision rules，而不是一律 ALWAYS／NEVER。[Function calling](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)及[Anthropic Define tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools#best-practices-for-tool-definitions)要求清楚的使用／不使用時機。職務內容的依據仍是上述本地研究與 [OPM Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/)，不是聲稱 OpenAI 定義了哪些員工工作重要。

**改動面：**[api.py](../../experiments/analysis-agent/src/analysis_agent/api.py)僅替换末尾含糊通知句，指向實際工具；[consolidation_request.py](../../experiments/analysis-agent/src/analysis_agent/consolidation_request.py)說明新進展、短更正、轉向／收尾、不要例行重複與收據語意。工具參數、回傳內容、artifact、主顧問其他指令、Skills、B1/B2/C及背景判斷不改；工具只通知，不叫主顧問重寫記憶或等待整理。

驗證分兩層：既有 CT15 是修改前真實行為失敗證據；離線回歸只證明空參數工具、收據、同回合去重、排程／API等接線未退步，不以搜尋prompt文字或假模型「照劇本通知」冒充語意修復。真模型對照要另用小額未關閉帳本，只重現後期補充／短更正／無新增重述，先保持字數備援關閉以辨識通知效果；本輪不使用先前已關閉帳本或新增付費請求。

## 6. 隔離實作與驗證結果

已依 §5 僅修改主提示末尾通知路由及工具 docstring。判準集中在工具描述，主提示不重複整份清單。框架仍將它送作空參數工具；返回的通知收據和 artifact、成功判斷、排程、背景整理均未改。沒有新增模型呼叫、資料欄位或分析 Skill。新增提示本身仍有少量輸入 token 成本；實際整理頻率與總費用須用後續真測觀察，不能宣稱零成本或一定省錢。

在 `experiments/analysis-agent` 執行：

```text
uv run --frozen --offline pytest -q --tb=short tests/test_consolidation_request.py tests/test_scheduling.py tests/test_api.py
```

- 修改前：33 passed；修改後：33 passed，0 skipped。兩次均有1項既有 Starlette／AnyIO deprecation warning，沒有藉此升級依賴。
- 首次受限環境執行受 Windows 暫存／uv cache 權限阻擋；取得執行權限後，同一離線命令通過。這是環境阻擋，不當成產品失敗或提示的 red/green 證據。
- 真實框架 agent/tool loop 使用假 HTTP 回覆，覆蓋空參數、通知收據保存與安全對外內容、同輪通知合併、已處理游標、取消／中斷、API／背景接線。它**不證明模型會主動選對通知時機**，也不是新 PostgreSQL 耐久性或完整長訪談驗收。
- `git diff --check` 通過；原始 CT15 trace、未整理資料、模型／上限、文字量備援與正式產品均未更動。0 次付費請求／US$0。

**下一唯一 gate：**以後期新資訊、短更正、無新增重述做局部 Luna／medium 真模型對照，另行確認小額測試範圍，再決定是否需要調整備援。不重新討論已核准的 Memory 分層。`CT15-R07`／品質 G8 保持 OPEN；沒有通知且低於備援門檻的尾端情況仍是已知限制。
