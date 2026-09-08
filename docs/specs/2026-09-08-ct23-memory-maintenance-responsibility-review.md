# CT23：必要記憶維護不能只靠自願選工具——責任與選項

2026-09-08 · Q019-MEM-CADENCE-01／CT15-R07 · **G2研究完成、G3待Owner選擇；G8仍OPEN。沒有實作或付費測試。**

## 1. 本輪preflight與閱讀路由

- **唯一問題：**CT22再次零工具結束後，要繼續接受自主工具的可靠性界線，還是讓Runtime負責觸發必要的記憶處理？
- **觸發重開：**[CT22§6–7](2026-09-08-ct22-memory-prompt-contract-results.md)的自然更正反例；不是看到新名詞就重選架構。Owner最新「OK」授權研究選項，不授權修改。
- **Binding：**只分析、每份文件隔離；原始訪談可靠保存；A對話／推理延續、B背景抽取整併、C按需修補；有損整理不取代原文；低成本、保留工作相關細節。任何新時機／硬完成條件須先討論。
- **已完整回讀：**主repo [register](../../../../docs/current-decisions.md)最新gate、[decision-process](../../../../docs/decision-process.md)、CT22、[CT20官方提示審核](2026-09-08-ct20-official-memory-tool-prompt-audit.md)、[CT18診斷](2026-09-08-ct18-live-repair-selection-diagnosis.md)，以及[原整理時機](../../../../docs/specs/2026-09-06-memory-generation-cadence-and-continuity-review.md)與[通知接線](../../../../docs/specs/2026-09-06-memory-consolidation-request-wiring-design.md)全文。
- **不做：**再堆prompt、改模型、force tool、分類器／驗證Agent、排程改碼、新Memory層、JD／production；不沿用已closed的測試額度。未讀Owner排除的2026-08-12舊產品流程長文。

## 2. 先把問題說精確

CT22的員工更正與可見回答已保存，AI回答也採用5日；**不是整句對話遺失，也不是本輪已忘記新日期。**失敗是已發布的Memory仍為10日，模型沒呼叫C或B通知，因此沒有寫入錯誤可回饋重試。不能把這次歸因於patch、strict schema、資料庫、工具上限，或聲稱已知道模型內在原因。

須分開三種結果：

1. **原話保存：**已成立，包含短更正；不依賴LLM選工具。
2. **整理有執行機會：**目前只靠模型通知，或配置中的文字量後備；CT22後備未啟用。
3. **整理後內容正確：**即使啟動並成功發布，仍須驗更正、範圍、未知與案例差異；不能用「job成功／游標前進」代替語意驗收。

本題主要是第2項。若要求第3項在**本輪回答前**成立，那是更強的完成政策，不是加一個排程開關就能保證。

## 3. 官方事實：不同產品，不混成同一套保證

| 來源 | Official fact | 不可延伸的結論 |
|---|---|---|
| OpenAI Sandbox Memory [O1][O2] | 執行期間收集run segments，session關閉時由Runtime啟動抽取／整併；另提供同輪live update指令及可寫工具 | 背景產生不需要主模型先叫「通知整理」工具。**同輪修補指令仍不是Runtime自動辨識語意矛盾的程式保證。**Session關閉亦非每則員工訊息 |
| Codex local memories [O3] | 對符合資格的既有聊天做背景產生，會等待足夠閒置，並依配額略過某次產生 | 不保證每次回答前Memory已新鮮；不將其閒置／短session篩選照搬成Caliburn政策 |
| Claude Code auto memory／Claude Memory tool [A1][A2] | 前者由Claude選擇值得保留的知識，不是每個session都寫；後者專用工具會自動附記憶讀寫指引。Claude Code明示instructions是context而非硬強制設定 | 沒有查到「任意短更正必定同輪寫入」保證；不能說Anthropic已證明我們的零工具反例不會發生，或它與OpenAI共用同一排程 |
| LangChain／Deep Agents [F1][F2] | 官方區分hot-path與背景；背景可由應用邏輯或排程啟動。Deep Agents範例由獨立整併Agent處理，提醒過密整理會浪費token | 這提供不依賴主模型通知的路徑，不代表官方內建Caliburn段落判定；範例的六小時lookback也不是完整訪談保留規則 |

**可以學的共同責任界線：**對話與可修訂Memory分開；模型負責資訊取捨，Runtime負責實際執行及保存。**「何時必須啟動／是否必須同輪更新」沒有各家統一答案。**不能把「同輪＋背景」這個已有依據的組合再宣稱為每家完全相同的底層。

### 3.1 OpenAI底層補查：不是只看Memory元件名稱

本輪讀本機官方Agents SDK **0.22.0**，與2026-09-08現行[O1]交叉核對；不宣稱套件為最新發行，也不等同Codex閉源內部：

`run.py finally → SandboxRuntime.enqueue_memory_result → manager.enqueue_rollout_payload → session pre-stop hook → manager.flush → Phase 1 → Phase 2`

- `run.py:2106–2140`正常完成／例外收尾路徑會嘗試交接；不是只有模型使用Memory工具才進入。
- `sandbox/runtime.py:108–188`串流cleanup交接及manager取得條件；需已啟用生成能力及有效session／rollout，並非任意普通Agent自帶。
- `sandbox/memory/manager.py`**全文讀取**：累積寫入rollout；註冊`register_pre_stop_hook(self.flush)`；`flush`封閉此manager並跑B1/B2。不要把它当作可無限重複呼叫的普通periodic flush API。錯誤有記錄／catch、抽取可跳過無效產物；不提供「必定成功、崩潰自動耐久重试、所有語意必保留」的保證。
- `sandbox/memory/prompts.py`**全文讀取**：同輪修補是render出的指令，不是讀取所有員工文字並自動執行patch的guard。

來源均在`experiments/analysis-agent/.venv/Lib/site-packages/agents/`；SHA256：manager=`c270a4992d19b302ba25c8656ff9c55a2e916d59fc48a7563682c066b77f4495`；runtime=`e00bfee54efab9b99877f0121c41986a613162d993f359744dbad412322d53b8`；prompts=`2eb0bf2e2e097a396ca6eba9cbf98c8b0e5e3c72f1cdfc5e7f1ed5194a5f93b0`。只對上述完整模組／指定收尾路徑下結論，未聲稱重審整個SDK。

## 4. 現有框架能承接什麼，不能替我們決定什麼

| 能力 | 框架／目前接線 | 邊界 |
|---|---|---|
| 程式知道有新原文未整理 | 既有canonical reader＋publication cursor；`scheduling.py`的`unprocessed_source` | 是範圍判定，不是另一個語意分類器；原文pending不等於Memory已吸收 |
| 不靠模型選擇的執行接點 | LangChain `after_agent`，或LangGraph預定的workflow node [F3][F4] | hook不是耐久背景佇列；例外／取消不能假定都走成功`after_agent`。本案應沿既有安全封閉與恢復接點，不在hook直接無管理地另開thread |
| 合併背景工作、批次執行 | 現有APScheduler單worker＋B checkpoint／receipt／來源cursor | `service.start_background`本來就在定期tick，但tick只是檢查；`_step`仍會因零通知且字數不足返回。**縮短tick間隔不能修復目前問題** |
| LangMem延後整理 | `ReflectionExecutor.submit`＋manager是官方範例 [F5]，由應用提交，不由主模型挑工具 | 此頁用debounce與舊模型示例；不複製舊model／秒數、不重引入Owner排除的idle策略。也不因有Executor就推論已符合本案耐久恢復／引用／五產物，不建議換掉既有B |
| 約束模型回傳形狀 | OpenAI `tool_choice` [O4]、LangChain `ProviderStrategy`／`ToolStrategy` [F6] | `required`只保證呼叫某工具，可能只是讀；指定repair仍需正確目標與內容。必填`memory_action=none`也可能判錯；格式驗證不能證明「不需存」的語意正確 |

文字量後備是早已WORKING但數值未定的設計，不是新發明。**它只能補較大積壓，不能解決短更正之後再也沒有新訊息的尾段。**為此新增補齊時機或改完成政策，均需Owner確認，不能偷偷設成另一個90秒idle。

## 5. 三個實質選項

| 選項 | 能改善什麼 | 成本／限制／是否需翻案 |
|---|---|---|
| **方案1：維持自主C＋通知B，只補已討論的文字量後備** | 持續長聊達量後，即使漏通知仍可整理 | 改動最少；短尾段仍可能不處理，CT22同輪失敗不能因此關閉。不建議把方案1當本題完成方案 |
| **方案2：保留按需C，Runtime另外負責背景處理機會（建議方向，未選）** | 沒有工具通知也不讓新原文永久只停在待處理；可合批，主顧問不用等B | 必須選一個**不依賴模型再次提醒／新訊息才會發生**的尾段處理條件；文字量單獨不夠。正常前台不固定加模型call，但B仍花錢。**不是本輪回答前一定改好Memory**，須明確接受延後保存的界線 |
| **方案3：記憶維護成為回合必經workflow** | 程式安排維護步驟，而非容許主模型直接略過；失敗與未完成可觀察 | 維護模型／工具工作會增加前台時間與token，資訊很少也需判斷no-op。依然不能保證語意全對。若同輪完成是硬要求，需研究方案3；不是每輪強制覆寫，也不直接force所有工具 |

**建議方案2的理由是本案取捨，不是官方保證最佳：**符合已選的主顧問／背景分工、累積後整理及成本目標，且直接處理「漏通知就沒人處理」；無需再增加一個整理判斷Agent。當前C修補仍可優先執行，不撤其用途／正確操作規則。但若Owner要求每個明確更正在回答前必須發布，方案2只能補救，**不能當成方案3的等價替代**。方案編號不改原有A／B／C流程名稱。

### 5.1 方案2獲准後才細化的界線

- 沿原有原文／cursor辨認待處理，不新增一份Memory或「已保存」模型旗標，不解析回答中的「收到」當保存收據。
- 模型的段落通知可保留為提早處理的訊號，但不再是唯一入口；具體保留與否在局部設計對齊成本，不本輪偷刪tool。
- 尾批必須有不會被持續新訊息無限推遲的處理機會；服務關閉時原文保留，重開能續。**何時啟動、單批量、成本上限與超限／失敗的處理還未定。**不復活idle90秒、不指定任意N輪或5000字。
- 發布前主顧問不能把舊Memory當最新；沿既有對話延續、最新輸入及回查。是否補當前未整理範圍的Context提醒，需核對後設計；目前`notice()`主要針對blocked，不能宣稱idle積壓已全提示。
- 既有B/C協調、來源引用、原子發布與重試分工保留；有新原文不等於每輪重整。背景正常運作、預算可用才有處理機會，不承諾服務關閉時仍執行或錯誤時必定成功。

## 6. 官方來源與適用邊界

下列2026-09-08實際開啟／fetch；優先沿既有研究補缺，不引用搜尋片段作結論：

- [O1 Sandbox Agents／Memory](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)：Session與Memory分離、run segments、關閉後產生及live update；底層補查見§3.1。
- O2：§3.1本機官方SDK固定版本及hash；不是未公開Codex原碼的推測。
- [O3 Codex local memories](https://learn.chatgpt.com/docs/customization/memories#how-local-codex-memories-work)：資格、閒置、背景及配額策略；本案不照搬篩選。
- [O4 OpenAI tool choice](https://developers.openai.com/api/docs/guides/function-calling#tool-choice)：auto可零次、required／指定工具的真實約束。
- [A1 Claude Code memory](https://code.claude.com/docs/en/memory#auto-memory)：選擇性保留；同頁CLAUDE.md vs auto memory說明context與enforcement差異。
- [A2 Claude Memory tool prompting](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#prompting-guidance)：專用工具的自動提示，不擴大為所有模型工具的保證。
- [F1 LangChain writing memories](https://docs.langchain.com/oss/python/concepts/memory#writing-memories)：hot-path多工及延遲取捨、背景trigger選項；不以其轉述ChatGPT作OpenAI內部直接證據。
- [F2 Deep Agents background consolidation](https://docs.langchain.com/oss/python/deepagents/memory#background-consolidation)：獨立背景Agent／cron與過密成本；Deployment範例不能誤認本機OSS自帶託管scheduler。
- [F3 LangChain custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom#node-style-hooks)：`after_agent`與state hooks能力，不保證外部job耐久。
- [F4 LangGraph workflows／agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents)：預定執行路徑與自主工具循環的區分；只核對這個原則，不把joke示例当產品方法。
- [F5 LangMem delayed processing](https://langchain-ai.github.io/langmem/guides/delayed_processing/)：應用submit與debounce功能。含過時模型示例，只作既有能力核對，不作最新模型／本案時機依據。
- [F6 LangChain structured output](https://docs.langchain.com/oss/python/langchain/structured-output)：schema捕捉／驗證與provider支援条件；不自動驗證Memory內容或是否需寫。

## 7. Closure／下一個唯一gate

Finding：CT22證明單靠自主工具的候選未滿足原自然保存驗收；原文保存沒有壞。官方可支持Runtime觸發背景與自主live update並存，但無同輪必存的共同保證。

Status：**G2完成、G3 OPEN；方案2只是建議，沒有任何方案新獲核准。**已有CT22反例不因本稿改成PASS，候選維持封存、不promote。選方案2若調整驗收時間點，必須明記為新政策並另驗背景追上，不改寫舊失敗。

Why／Sources：§2實測沿革、§3–4官方及本機唯讀trace。Affected：本研究及兩份register閱讀路由；產品src/tests/prompt、DB與API設定均未動，0次付費生成。Reopen：Owner選擇責任政策、官方契約反證或後續限定驗證失敗。

本輪自審已將選項改用1／2／3，避免與既有A／B／C角色混淆；局部文件連結全可解析，diff check通過，src/tests diff為空，CT22證據SHA256保持原值。沒有執行新模型測試或重跑產品suite，不借舊綠燈宣稱本方案效果已證實。

**下一唯一gate：Owner是否接受「C盡力即時修補＋Runtime安排B補齊，容許Memory短暫落後」，或要求「回覆前必須完成必要維護」。**先回答這個效果差異，再設計時機／框架接點；不用先請Owner決定秒數／欄位，也不為已知零工具反例再做一輪同prompt測試。
