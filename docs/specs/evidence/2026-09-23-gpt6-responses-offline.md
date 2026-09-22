# GPT-6 Luna／Responses 接線與首次服務端證據

- 日期：2026-09-23
- 範圍：`codex/gpt6-luna-responses` 隔離分支；正式新 JD App `experiments/jd-relational-app`
- 狀態：離線接線通過；首次服務端 smoke 因 `provider_model_mismatch` 停止；非工具往返或完整成品 PASS
- 下列離線階段外部 provider request：0；費用：US$0；首次付費 smoke 的數據另記於本文末段；未使用正式文件資料

## 已核對

1. 沿既有 A／B1／B2 model factory 換成 `ChatOpenAI` 的 OpenRouter Responses 接線。實際 `MockTransport` 抓到 `/api/v1/responses`、GPT-6 Luna、high、`store=false`、單次工具呼叫、OpenAI-only／no fallback、無 SDK 自動重試；加密 reasoning item、function call ID 與工具結果在 LangGraph Saver／下一次請求的離線往返成立。沒有新增 Agent、Memory、Domain validator 或第二套狀態。
2. 原 A 的 JD／Memory／Working State／compaction 組裝及工具語意保留。Responses 的 `completed`、`incomplete`、refusal 可經鎖定 adapter 判讀；`max_output_tokens` 的摘要單次覆寫已在實際 request body 核對。
3. P3 原 test-only `GuardedClient`／同一帳本沿用，改驗 Responses endpoint、request shape 與 GPT-6 上限。離線樣本中角色、實際外送數、路由、模型、回應成本與不明成本 fail-closed 成立。回應的 provider 可取 top-level，或唯一被標記 selected 的 `openrouter_metadata` endpoint；兩者都缺或相互矛盾即停止。`incomplete`／error 也停止；App-side compaction 實際以 A 2048、B1／B2 8192 額度送模型時，同一角色／帳本准入並依實際額度預留。
4. 合成 Browser journey 的 HTTP 假傳輸跟隨新 Responses wire，JD read→create→final 與第二輪 final 的相鄰測試通過。`tests/test_ui_chat_server.py`、`tests/test_p3_trial_server.py`、`tests/test_consultant_model.py`、`tests/test_consultant_context.py` 合計 64 passed；P3 spend gate 與 trial entry 合計 48 passed；Responses transport／terminal 4 passed。
5. 本輪完整離線 App pytest 在後續只改 PostgreSQL 測試夾具前得到 **3158 passed、323 skipped、1 failed**。唯一失敗 `test_canonical_profile_is_tied_to_this_fixed_migration`：原版 `0001_jd_relational_initial.py` 的工作區 SHA-256 是 `f12917204846f5a3e2949681b717961f8d486c7f7399152c56010c30d00001c3`，固定 profile 記錄 `4abccba7242a383ef51fe4395eee4606c0e997e23ede9915d67e2238c6d4c2d0`。兩檔均未在本分支修改；此差異與模型傳輸無關，不自行重寫 migration 或權威 profile。
6. 獨立只讀審查指出四項風險；其中 P3 `incomplete`／error 停止、摘要額度、模型與 selected-route 比對已按原帳本／現有角色修正。正式 `AIMessage` 不再保存 provider 屬下述觀察性差異，未宣稱等價。最後受影響零付費集合 **116 passed／0 failed**；只讀審查與修正未擴大到 Domain／Memory。
7. 2026-09-23 重新核對本機 Docker Desktop 與隔離 PostgreSQL 18.6：既有 `caliburn-jd-relational-test-postgres-1` 於 `127.0.0.1:55436` 可連，原先「Docker 引擎不可連」是當時 sandbox named-pipe 權限的觀察，**不是現在的環境阻塞**。以正式新 App 與 Responses `MockTransport` 執行 A／context／P3 B1／B2 真 PostgreSQL 回歸，第一批 **7 passed**，沒有付費模型請求。後續跨程序與 C 測試只對齊歷史測試夾具：Responses 的 `input`／`function_call_output`、已發布 C 的本回合穩定讀取基準，以及已採用的 model-facing `basis_evidence_keys`；未改產品程式。合併受影響的 10 個 PostgreSQL 測試模組重跑為 **23 passed／13 skipped／0 failed**（143.56 秒）；舊兩檔 C 的 FH05 不能證明現行 layered C，列為歷史 skip，不能冒稱新 C 跨程序驗收。另查 `support/openai_replies.py` 的 GPT-5.6 預設只供歷史正向對照；GPT-6 測試入口在送入 MockTransport 前均覆寫為 `openai/gpt-6-luna`，因此不改該夾具。
8. [OpenRouter 公開模型清單](https://openrouter.ai/api/v1/models?q=gpt-6-luna)及[該模型端點清單](https://openrouter.ai/api/v1/models/openai/gpt-6-luna/endpoints)於 2026-09-23 可在**不使用金鑰**下核對：標準 OpenAI 端點為輸入 US$0.10／百萬 tokens、輸出 US$0.50／百萬 tokens，另列 flex／fast 等不同價端點及長上下文費率。候選請求固定 `provider.only=["openai"]`、不要求其他 tier；公開 metadata 能確認標價與候選端點，**不能替代實際回覆的 provider／tier／cost 證據**。
9. 上述完整離線套件的唯一失敗已另行定位並修正：`test_canonical_profile_is_tied_to_this_fixed_migration` 修前重現第一版 migration hash 不符；不是 Windows CRLF（該檔 Git 與工作區皆 LF），第二版 migration 與 schema helper hash 均正確。固定 `0001` migration 的離線 DDL 與現行 metadata 一致，並用它在隔離 PostgreSQL 18.6 建立一個**保留的合成測試庫**，安裝相容性檢查成立，合計 **32 passed**。因此只更正 `ddl_profile_v1.json` 的第一版 migration 來源 hash，未改 migration、約束、資料表或 Runtime；原失敗窄測轉為 **1 passed**，完整新 JD App 零付費套件隨後為 **3167 passed／323 skipped／0 failed**（74.45 秒）。這關閉離線套件的來源追溯失敗，不代表 GPT-6 OpenRouter 服務端或自然品質已通過。
10. 後續核對 P3 test-only 帳本發現 Responses 正文 `id` 被誤標成 `generation_id`，但 Saver 對應的是正文 Response ID，OpenRouter generation metadata 則使用回應標頭 `X-Generation-Id`。先以獨立合成 ID 寫反例，確認原帳本缺 `response_id`；另以缺 `usage.cost` 的回應確認 fail-closed 時會遺失標頭 ID。只在同一 test-only 帳本改記 `response_id` 與可取得的 `router_generation_id`；費用未知仍保留全額預留並停止，不自動查 metadata 或續送模型。兩個反例由紅轉綠；帳本／試跑入口 **49 passed**，B1／B2 真 PostgreSQL／Saver 對帳 **1 passed**，完整新 App 離線套件 **3168 passed／323 skipped／0 failed**（73.35 秒）。首次一般 sandbox 遇 pytest 暫存 ACL，改用受控測試暫存路徑執行；未影響測試語意。這只修正測試證據標籤，**不證明真 Responses 的標頭、成本或路由欄位一定存在**。

## 尚未驗證／停止線

- OpenRouter 此模型／OpenAI provider／Responses／high＋工具的**實際服務端接受、回覆、價格及計費欄位**尚未證明。公開 Responses 範例有 usage tokens，但未保證同筆回覆含可對帳的 `usage.cost` 和實際 provider；本地 mock 的該兩欄不是服務端證據。若真回覆缺欄，P3 gate 會把該筆視為費用未知並停止。不能把離線全綠當作付費自然試驗的核准。
- 鎖定的 `ChatOpenAI` Responses adapter 會保留終止狀態及 reasoning/tool items，但不把 OpenRouter 的實際 provider 從 raw response 複製到正式 `AIMessage.response_metadata`。正式業務目前沒有消費該欄，P3 test-only HTTP 帳本會在外送邊界核對 raw provider；這是與舊 Chat adapter 的**觀察性差異**，不是已證實的 JD／Memory 功能錯誤。服務端 smoke 與正式切換前仍要決定是否必須把該證據持久保存；若需要，只在 Responses 傳輸邊界補最窄投影，不另造 route registry。
- P3 目前保守預留 A 為 US$0.268644／次，B1／B2 為 US$0.287076／次；這高於公開模型清單列出的標準 OpenAI 費率，以全 context 與長上下文輸出上界估算。US$1.00 閘門在前筆費用未結算時最多只容許少數請求，不能預先宣稱足以完成 12 輪自然訪談。公開 [Responses API 回應範例](https://openrouter.ai/docs/api/api-reference/responses/create-responses)顯示 token usage，沒有保證同一筆回覆含 `usage.cost`；[generation metadata API](https://openrouter.ai/docs/api/api-reference/generations/get-generation)另列 `total_cost`／`provider_name`，但目前帳本未使用第二次查詢。OpenRouter 的[回應快取文件](https://openrouter.ai/docs/guides/features/response-caching)稱 `X-Generation-Id` 在每個回應都有，且將 Responses 列為支援端點；查 generation metadata 應使用這個 `gen-*` 標頭 ID，不能假設 Responses body 的 `id` 可直接代入。**這是官方文件提供的有界備案，不是本模型／端點已實測的 header 或查詢結果。**若真回覆缺 cost，現有帳本會保留預留並停止；是否在同一預算與實際外送數內補一筆唯讀 metadata 查詢，應先核對 header、查詢結果及授權，再作最小調整。不得用本地估算代替實際結算，亦不得把舊 P3 金額上限當新路徑的完整自然試驗已可執行證明。
- GPT-6 Responses 的隔離真 PostgreSQL A／B1／B2 合成回歸已部分通過；**服務端與真模型未驗**，不能沿用 5.6 Chat 的付費證據冒充 GPT-6 PASS。舊 checkpoint 的 provider-specific item 相容性亦尚未證實。
- 真模型、真 Browser、自然長訪談、JD 品質及中斷重開均未在新路徑執行；不得 merge、push 或將此分支宣告為正式路徑已驗收。

## 下一個最小 gate

> 以下保留離線階段寫下的下一關；其第一次執行與新的停止點見下節，不再把這段「未授權外送」當成最新狀態。

受影響真 PostgreSQL 測試與合成回覆模型身分已核對；下一關是在既有 P3 帳本下提出**單一受控服務端 smoke**：只回答 GPT-6 Luna／Responses／high＋工具能否實際往返，以及同筆回覆的 route／tier／cost 是否足以結算。送出前另核明確實外送上限、保守預留與 Owner 費用授權；若要查 generation metadata，該唯讀外送也計入請求上限。本文件不授權外送。若缺欄則依現有 fail-closed 停止，先核實 `X-Generation-Id` 與官方 metadata 查詢是否可對應同筆，再決定是否需最窄帳本補線；不改 Domain、不估零、不自動進入自然 P3。

## 首次有界真服務端 smoke

- 日期：2026-09-23。Owner 在離線接線後核准此獨立小 gate：最多 2 筆 GPT-6 Luna 模型請求，另可 1 筆唯讀 generation metadata 查詢；保守預留上限 US$0.54；只用合成資料與本機無副作用 `read_case` 工具，不准自動重試、fallback 或切正式 App。這不是自然 P3 或 Browser 授權。
- 前置：正式新 App 隔離分支 `9cf68db5`、乾淨工作樹；Credential Manager 有 OpenRouter key（未輸出）；2026-09-23 唯讀公開端點清單列出 OpenAI 標準 `openai/gpt-6-luna` 端點，1.05M context 及標準／長上下文費率。OpenRouter [Service Tiers](https://openrouter.ai/docs/guides/features/service-tiers) 說明未指定非預設 tier 的請求不進 flex／priority 端點。現行 test-only `LunaBudgetPolicy` 對 A 的每筆最壞預留為 US$0.268644，兩筆共 US$0.537288。
- 實際外送：`P3SpendGate`／正式 A role model 只送 **1 筆** `/api/v1/responses` POST（合成工具要求，high、`store=false`、OpenAI-only、no fallback、`max_output_tokens=8192`、非串流；此 request contract 由帳本在外送前檢查），回 HTTP **200**。帳本在 `validate_response` 的 `provider_model_mismatch` 停止；SDK 未取得該回覆，也沒有送第 2 筆模型請求。因此不能宣稱工具呼叫、reasoning continuation、final 已通過；後續 provider／cost 欄位可能仍有獨立相容問題。
- 使用該回覆標頭 `X-Generation-Id` 做核准的 **1 筆**唯讀 `GET /api/v1/generation?id=…`，HTTP 200，返回同筆 ID、`model=openai/gpt-6-luna-20260922`、`provider_name=OpenAI`、`service_tier=default`、`total_cost=US$0.0000269`、119 input／8 output tokens。這證明 OpenRouter 記錄的實際路由與費用；原始 Responses 正文的 `model` 值未被帳本保存，只能確定它不等於目前白名單的未帶日期 slug。metadata 的 `api_type=completions`、`streamed=true` 與客戶端已驗的 Responses POST／非串流 request 不同層，暫不猜其內部含義。
- 帳本精確停在 `attempt_count=1`、`spent_usd=0`、`retained_unknown_usd=0.268644`、`stop_reason=provider_model_mismatch`；唯讀查詢取得的實際費用**沒有**回寫或解鎖帳本。沒有 production code 修改、正式資料寫入、第二次模型請求或額外 metadata 重試。
- 下一個停止點：先確認 dated model ID 是否為本次 alias 的可接受正式版本，以及如何在 test-only gate 保留原始回覆 model／provider／tier／cost 存在性的安全診斷；不能單憑 GET 成功就放寬所有檢查或重送模型。若需另一筆付費驗證，另核準確費用與請求上限。完整自然 P3、B1／B2 真模型、Browser、JD 品質與 main 切換仍 OPEN。

## OpenRouter 別名核對與零付費閘門修正

- 2026-09-23 再以**公開、無金鑰**的 [OpenRouter model lookup](https://openrouter.ai/api/v1/model/openai/gpt-6-luna) 核對：`id=openai/gpt-6-luna`、`canonical_slug=openai/gpt-6-luna-20260922`，標準 [OpenAI 端點清單](https://openrouter.ai/api/v1/models/openai/gpt-6-luna/endpoints) 的名稱也含同一 dated snapshot。這是 OpenRouter 的實際公開對應，與首次 smoke 的 generation metadata 相符；[OpenAI GPT-6 Luna 模型頁](https://developers.openai.com/api/docs/models/gpt-6-luna)仍以 `gpt-6-luna` 指示請求，未在該頁公開上述日期版。不能把前次 mismatch 解讀為已證實錯 provider，也不能反過來假稱原始 Responses 正文其他欄位已通過。
- 責任點是 **P3 test-only** `LunaBudgetPolicy.validate_response` 將回覆 `model` 與送出 slug 做字串全等比較，並對 selected endpoint 重複同一限制。新增兩個獨立離線反例：正文回 canonical，以及正文仍為 alias 而 selected endpoint 回 canonical；修前均因 `provider_model_mismatch` 紅燈，修後均通過並完成成本記帳。只在回覆白名單固定接受該已驗 snapshot；request slug、未核准 snapshot 拒絕、provider／tier／cost、帳本 fail-closed 皆保留。
- 零付費相鄰 `test_p3_spend_gate.py`、`test_p3_trial_server.py`、`test_gpt6_responses_transport.py` 共 **55 passed／0 failed**；首次一般 sandbox 的 pytest 暫存目錄遭 Windows ACL 拒絕，改於可存取環境以同一反例確認預期失敗及通過。隔離 PostgreSQL `127.0.0.1:55436` 目前不可連，未為 test-only 更動啟動或重建 DB；先前真 PG／Saver 證據不冒稱本次重跑。新增外部模型請求 **0**，原 stopped ledger 仍保留，不回寫 metadata 成本、不續送剩餘請求。
- 此修正只清除一個**以公開 mapping 與離線反例證實可重現**的測試閘門誤判；首次真回覆的原始 `model` 值未保存，故不能斷言它就是當時唯一停止原因。服務端 Responses 正文的 route／tier／cost 完整形狀、SDK tool item、加密 reasoning 延續及 final 仍需另一次有界真模型請求才能驗；送出前再定實際外送與費用授權。自然 P3、完整 JD 品質、Browser 與 main 切換保持 OPEN。
