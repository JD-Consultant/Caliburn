# Hybrid Candidate Loop 真實 API smoke

- 執行日期：2026-08-21
- 狀態：**通過**
- 性質：付費整合 smoke，不是正式品質 eval
- 模型：`openai/gpt-5.6-luna`，實際 provider 固定為 `OpenAI`，fallback 關閉
- 範圍：候選 JD 編輯、員工審核、下一輪核准／拒絕記憶；不接 RAG、不生成能力級別／A、不啟用 auto-accept

## 1. 要驗證的產品閉環

本 smoke 使用合成的採購專員訪談內容，驗證下列完整路徑：

1. LLM 按需讀取 Task、Output、Performance Indicator Skills；
2. LLM 呼叫唯一的 `job_document_candidate_edit` Tool，application 真正套用並驗證候選；
3. final Structured Output 只引用已成功的 candidate revision／digest／action IDs，不重送另一份文件草稿；
4. 候選發布後只進 review queue，核准 JD 仍為空；
5. 員工接受 Task 與 Indicator、拒絕 Output 後，只有接受項目進核准 JD；
6. 下一輪同一位顧問同時看見核准內容與拒絕記憶，不把拒絕項目當成事實或偷偷重提；
7. 測試結束只刪 disposable 文件，五張相關資料表回到執行前計數。

## 2. 為何仍採目前的框架組合

2026-08-21 再次核對官方文件後，沒有出現需要翻案的新機制：

- OpenAI 將 GPT-5.6 Luna 定位為成本敏感、高流量工作負載，且原生支援 Function Calling 與 Structured Outputs；本輪因此用它驗證工具閉環與成本，不把一次 smoke 當成專業顧問品質冠軍的證明。
- LangChain `ToolRuntime` 會在執行時注入 state、context、Store 與 tool-call identity，且不把這些 application-owned 欄位暴露給模型；Tool 可回傳結構化結果或 `Command`，讓模型看見真實執行結果。
- LangChain 對支援原生 structured output 的 provider 優先使用 `ProviderStrategy`，由 provider 強制 schema；這適合 final publication receipt，不適合取代需要 action→observation→repair 的候選編輯。
- LangGraph checkpoint／interrupt／`Command(resume=...)` 提供 durable human-in-the-loop primitive；Caliburn 只保留員工文件 authority、Evidence、read-set、Task／Duty／OPKS invariant 等產品政策。

這與 ADR 0063 的混合方案一致：成熟框架負責通用 agent loop、Tool 注入、typed final、checkpoint 與 resume；Caliburn 不重寫這些機制，只保留框架不知道的職務分析語意。

## 3. 測試輸入與員工決策

第一輪合成員工明確提供：

- Task：「彙整採購需求並建立請購資料」；
- Output：「完成可送審的請購資料」；
- Performance Indicator：「請購資料在當日完成且內容可直接送審」；
- 要求先形成待審候選，不得直接修改正式 JD。

候選發布後，測試模擬員工接受 Task 與 Indicator、拒絕 Output。第二輪明確要求沿目前核准 JD 繼續、不得把剛拒絕的候選當成事實，且只問一個仍缺少的完成標準問題。

## 4. Profile 診斷

### 4.1 Max 不適合作為目前互動 profile

`reasoning=max`、`max_output_tokens=16384` 的真實 run 在五次 primary model step 加兩次 summarization call 後觸發 `ModelCallLimitExceededError`，沒有形成可供員工審核的 final publication：

- 實際 route：每次皆為 `OpenAI / openai/gpt-5.6-luna`；
- 已知成本：約 USD 0.01988928；
- 經過時間：約 80 秒；
- 清理：disposable 文件 `0653c119-406b-449c-a1cb-686bbaf6aca7` 已刪除，相關表回到 0。

沒有為了讓 Max 勉強通過而提高五步 hard ceiling。這個 ceiling 是防止失控成本的產品預算，不應由單次模型行為反向改寫。

### 4.2 Medium 在提示修正前已證明 error→repair 閉環

第一次完整 `reasoning=medium` run 成功完成兩輪，但第一個 candidate batch 因未使用的 `integer_value` 帶內容而被 Tool 拒絕；模型讀到 actionable error 後提交第二個完整 batch並成功發布。這證明真實 Tool result→模型修正→final publication 路徑成立。

- 總成本：USD 0.01281577；
- primary latency 合計：約 43.7 秒；
- 員工接受 Task＋Indicator、拒絕 Output；
- 第二輪核准文件未改變；
- disposable 文件 `e11955e7-531a-4a97-b7c7-bb59b3081dac` 已清理。

根因是 required-only wire 使用 sentinel，但 prompt 沒明列所有未使用 slot 的 neutral 值。新增規則與回歸測試後，候選 batch 第一次即成功，不再浪費一次修正迴圈。

## 5. 最終 medium 成功收據

設定：`reasoning=medium`、`max_output_tokens=8192`、五次 model-step ceiling。

### 5.1 第一輪

模型先在同一個 response 平行呼叫三個 `read_file`，接著呼叫一次 `job_document_candidate_edit`：

| 結果 | 值 |
|---|---|
| Tool status | `applied`，沒有前置 rejected batch |
| candidate revision | `1` |
| revision digest | `a968f77bfc01542d3046424b90b59b3e913247a554c220aea8f7af1f131e3c83` |
| Task action | `a8b4fa9f-9a5d-5871-99cf-9f2829e705b3` |
| Output action | `bb997586-772b-58ff-9cb5-f126f0de9a45` |
| Indicator action | `45795bd4-6aaf-5246-98ba-f01fa3a579b5` |
| Tool issues | `[]` |

三個 final handles 與 review queue 完全相同；Task 由 application 配置 stable ID，O／P 都連回該 Task，沒有模型自填 document ID、authority revision 或正式 entity UUID。

員工決策結果：

- `accepted=2`：Task＋Indicator；
- `rejected=1`：Output；
- 核准 JD 最後只有一個 Task 與一個 Indicator；被拒絕 Output 不在核准 JD。

### 5.2 第二輪

- `approved_context_seen=true`；
- `rejected_context_seen=true`；
- 沒有呼叫 candidate edit Tool；
- 顧問明確說本輪沒有新文件事實、不採用被拒絕候選，只針對仍缺少的完成標準問一題；
- `approved_document_unchanged=true`。

這直接證明「員工不接受就不進文件」與「下一輪記得員工已拒絕什麼」同時成立。它不是把 pending／rejected overlay 偷偷合併成真實 JD。

### 5.3 Route、usage、成本與延遲

| 回合 | model attempts | tokens | latency | cost |
|---|---:|---:|---:|---:|
| 第一輪 | 3 | 26,203 | 25.548 秒 | USD 0.00762805 |
| 第二輪 | 2 | 16,820 | 15.935 秒 | USD 0.00400057 |
| 合計 | 5 | 43,023 | 41.483 秒 | **USD 0.01162862** |

五次 attempt 的 requested／actual model 都是 `openai/gpt-5.6-luna`，actual provider 都是 `OpenAI`，每次都有 usage、cost、latency 與 finish reason；沒有 silent fallback。

## 6. 診斷過程中的非產品問題

1. 一次 post-fix run 的 PTY 輸出超過桌面工作階段可保留大小；程序已完成清理，但因結果不可複核，沒有把它算成通過證據。之後 runner 改成只輸出安全摘要。
2. 一次精簡 run 的第一輪 candidate 已直接 applied，但第二輪以 `ConsultantVerificationError` fail closed；舊診斷格式只保留 exception class，沒有留下 message。相同輸入立即重跑完整通過，因此沒有猜測根因、沒有放寬 verifier，也沒有將這次隨機輸出失敗誤判為架構缺陷。該 run 文件 `7766e4c4-5681-40d6-877d-b5f7466b350d` 已清理。
3. runner 隨後補齊 failure message、第二輪 Tool trace 與 durable run receipt，以便未來若重現可直接定位；這是 ignored 本機 smoke 工具，不是 production logging 擴張。

## 7. 清理證據

最終成功文件 `edceb651-712f-4e0b-8517-9fda4c331817` 先走 runtime 的 document delete path，再只 hard-delete同一 owned catalog row。執行前後計數完全相同：

| Table | before | after |
|---|---:|---:|
| `consultant_documents` | 0 | 0 |
| `checkpoints` | 0 | 0 |
| `checkpoint_blobs` | 0 | 0 |
| `checkpoint_writes` | 0 | 0 |
| `store` | 0 | 0 |

沒有 broad database delete，也沒有碰其他文件；這些 disposable 資料不可恢復，但全部都是本輪合成測試資料。

## 8. 結論與界線

真實 provider 已證明五項核心能力能一起工作：按需 Skill、真實候選 Tool result、provider-native final publication、員工逐項 authority、下一輪核准／拒絕記憶。最終 run 也證明補充 neutral payload 規則能少一次模型修正迴圈。

本 smoke 不證明 Luna 已達專業顧問最佳品質，也不取代產品完成後的代表性 eval。Max 在目前互動預算下不適合；medium 是現階段可用的整合基線。RAG／Reference、能力級別／A、auto-accept、multi-agent 與正式 eval 仍按 owner 決定延後。

## 9. 第一方來源

- [OpenAI — GPT-5.6 Luna model page](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
- [LangChain — Tools、ToolRuntime 與 Command](https://docs.langchain.com/oss/python/langchain/tools)
- [LangChain — Structured output](https://docs.langchain.com/oss/python/langchain/structured-output)
- [LangChain — Built-in middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [LangGraph — Interrupts、checkpoint 與 resume](https://docs.langchain.com/oss/python/langgraph/interrupts)
