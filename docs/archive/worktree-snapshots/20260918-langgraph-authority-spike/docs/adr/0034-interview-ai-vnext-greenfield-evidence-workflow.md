# 0034. Interview AI vNext：greenfield evidence workflow，不整合 v3 LLM internals

日期：2026-07-16

狀態：Accepted（方向已核准；runtime 尚未實作）

Supersedes：

- 0024 的 `LlmPort.select_schema`、OpenRouter/Pydantic AI 優先選型與舊受限解碼 wiring；
- 0026 的固定 `model_interview=gpt-4.1-mini` 角色決策；
- 0027 的 consultant/scribe/ledger/backstop 四組件；
- 0030 的 v3「scribe 唯一文件寫入口」、六個舊 prompt 規則與舊 model wiring；
- 0033 的 consultant agenda tools、`harvest.py` 與既有 op pipeline 實作。

部分保留：

- 0023 的全新實作、不整合更舊引擎、quote provenance 與停止保險原則；
- 0030 的 `_pending` 追蹤修訂 Web 載體、人工 accept/reject authority、確定性驗證與 eval-first 原則；
- 0033 的 episode 作為訪談／分析單位；不保留其 v3 tool/harvest 實作。

完整規格：
[`../specs/2026-07-16-interview-ai-vnext-greenfield-architecture.md`](../specs/2026-07-16-interview-ai-vnext-greenfield-architecture.md)

## 脈絡

v3 依序經歷 stateless turn、consultant/scribe、tracked changes、episode agenda 與 harvest 擴充。設計文件看起來完整，但實際訪談仍出現工作產出與行為指標漏失、長延遲、資料只在文件 mutation 中存在、歷史狀態不可重播，以及同一模型 pass 同時承擔聊天、抽取、文件寫入與自我驗證等問題。

2026-07-15 的 database audit 進一步確認：現有 capture 可作 failure audit，但不足以還原可信的 turn-zero baseline；繼續替 v3 補 provider trace 或在原 stage 上增加 C1 會延長舊責任切法，而非證明新的職務分析方法有效。

2026 最新一手資料出現明確共識：

- OpenAI 把 agent primitives 分為 model、tools、state/memory 與 orchestration；需要細粒度控制時使用 Responses API，multi-agent 不應作預設；
- Anthropic 區分預定 code path 的 workflow 與開放 autonomous agent，並把 durable session/context storage 與當次 model context 分開；
- Google ADK 區分 predictable workflow pipeline 與 adaptive routing；
- Microsoft Agent Framework 建議能寫成函式就不要變 Agent，明確步驟使用 workflow；
- Anthropic Interviewer 採 planning、adaptive interviewing、analysis，並由完整 transcript/quotes 支持分析；
- OpenAI Assistants API 和舊 Evals platform 已有 2026 關閉時程，不能再作新架構基礎。

產品的手動 JD Web、OCS 契約與人工審閱流程可用；需重做的是 LLM 分析與訪談 runtime。

## 決定

1. **greenfield package**：在 `apps/api/app/interview_vnext/` 建立全新 runtime。它不得 import、包裝、雙寫或逐 stage 對齊 v3 `consultant/scribe/harvest/select` internals。
2. **明確 workflow + 有限 agentic nodes**：固定執行 Turn Interpreter → deterministic Evidence Reducer → Sufficiency Engine → Question Policy；episode close 時執行 Episode Coder，session finish 時執行受限 Consolidator 與 deterministic OCS/JD Projector。
3. **一個 conversation owner**：初版不做 multi-agent。Interpreter、Question Policy、Coder、Consolidator 是獨立 typed LLM operations，不是會自主協商的 agents。
4. **應用程式擁有 state**：transcript、events、evidence、inference、episode、gap、candidate job model 與 review state 持久化在自有 DB。provider conversation/session ID 只作 adapter metadata／傳輸最佳化。
5. **LLM 只提 proposal**：每個 operation 使用獨立 Pydantic/JSON Schema；只有 deterministic reducer 能改 domain state，只有 deterministic projector 能產生 `_pending` proposal。
6. **來源分層**：employee evidence 與 OCS/O*NET reference 使用不同 channel。reference 可支援 taxonomy、normalization 或 gap，不得成為員工實際工作的證據。
7. **外部產品 seam 保留**：現有 Web、OCS/JD schema、tenant/profile identity 與人工 review authority 繼續使用；這是產品契約相容，不是 v3 LLM internals 相容。
8. **provider-neutral port**：OpenAI 使用 Responses API adapter；Anthropic 使用 Messages API adapter。domain 不含 provider SDK object，不採 Assistants API，也不先依賴任何大型 agent framework。
9. **Capture vNext**：使用 architecture/workflow/version、open-string stage、step/model/tool/state/outcome event envelope 與 immutable artifacts；不沿用封閉 v3 stage enum，也不綁 provider dashboard。
10. **eval-driven promotion**：v3 只作黑箱 outcome baseline。vNext 必須經 fixed component replay、branching conversation、真人／domain review、多 trial、hard gates 與盲測 pairwise 才能切 production。
11. **複雜度需取得資格**：Workflow Graph、multi-agent、fine-tuning、額外 session vector store 只有在具體 failure trace 和 ablation 顯示穩定收益時才加入。
12. **切換後刪舊**：vNext 通過 gate、rollback window 結束且沒有 active v3 session 後，移除 v3 runtime、prompts、專屬中間 state 與 dead configuration；不維持永久雙軌。

## 後果

- 新版可以推翻舊 prompt、stage、DB 中間欄位與模型分工，不再為相容性犧牲分析品質。
- 現有 Web 與人工審閱不用重做；切換只需要一個薄 HTTP/application seam。
- 一個 employee turn 通常需要 Interpreter 與 Question Policy 兩次模型操作；episode close/finish 會有額外分析操作，需以 operation-level routing 和 eval 控制延遲／成本。
- 新增 Evidence/Inference/Gap/Candidate Job Model、event/outbox/artifact 的持久化與 schema 維護成本，但每個 claim、state transition 與 failure 變得可回查、可回放、可替換模型。
- 不導入 agent framework 代表初期要自行寫少量 workflow/checkpoint code；換來清楚的 transaction、idempotency、provider 和刪除邊界。
- v3 不再獲得新的架構功能；只修阻斷 baseline/fallback 的安全或營運缺陷。
- spec 中仍可保留未定參數，例如 operation 模型、context budget 與 Consolidator 是否必要；它們由預先定義的 eval 裁決，不回頭改變本 ADR 的 greenfield 邊界。
