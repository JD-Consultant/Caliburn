# GPT-6 Luna／Responses 零付費接線證據

- 日期：2026-09-23
- 範圍：`codex/gpt6-luna-responses` 隔離分支；正式新 JD App `experiments/jd-relational-app`
- 狀態：**CLIENT／OFFLINE PARTIAL**；非 OpenRouter 服務端或完整成品 PASS
- 本輪外部 provider request：0；費用：US$0；未使用正式文件資料

## 已核對

1. 沿既有 A／B1／B2 model factory 換成 `ChatOpenAI` 的 OpenRouter Responses 接線。實際 `MockTransport` 抓到 `/api/v1/responses`、GPT-6 Luna、high、`store=false`、單次工具呼叫、OpenAI-only／no fallback、無 SDK 自動重試；加密 reasoning item、function call ID 與工具結果在 LangGraph Saver／下一次請求的離線往返成立。沒有新增 Agent、Memory、Domain validator 或第二套狀態。
2. 原 A 的 JD／Memory／Working State／compaction 組裝及工具語意保留。Responses 的 `completed`、`incomplete`、refusal 可經鎖定 adapter 判讀；`max_output_tokens` 的摘要單次覆寫已在實際 request body 核對。
3. P3 原 test-only `GuardedClient`／同一帳本沿用，改驗 Responses endpoint、request shape 與 GPT-6 上限。離線樣本中角色、實際外送數、路由、模型、回應成本與不明成本 fail-closed 成立。回應的 provider 可取 top-level，或唯一被標記 selected 的 `openrouter_metadata` endpoint；兩者都缺或相互矛盾即停止。`incomplete`／error 也停止；App-side compaction 實際以 A 2048、B1／B2 8192 額度送模型時，同一角色／帳本准入並依實際額度預留。
4. 合成 Browser journey 的 HTTP 假傳輸跟隨新 Responses wire，JD read→create→final 與第二輪 final 的相鄰測試通過。`tests/test_ui_chat_server.py`、`tests/test_p3_trial_server.py`、`tests/test_consultant_model.py`、`tests/test_consultant_context.py` 合計 64 passed；P3 spend gate 與 trial entry 合計 48 passed；Responses transport／terminal 4 passed。
5. 本輪完整離線 App pytest 在後續只改 PostgreSQL 測試夾具前得到 **3158 passed、323 skipped、1 failed**。唯一失敗 `test_canonical_profile_is_tied_to_this_fixed_migration`：原版 `0001_jd_relational_initial.py` 的工作區 SHA-256 是 `f12917204846f5a3e2949681b717961f8d486c7f7399152c56010c30d00001c3`，固定 profile 記錄 `4abccba7242a383ef51fe4395eee4606c0e997e23ede9915d67e2238c6d4c2d0`。兩檔均未在本分支修改；此差異與模型傳輸無關，不自行重寫 migration 或權威 profile。
6. 獨立只讀審查指出四項風險；其中 P3 `incomplete`／error 停止、摘要額度、模型與 selected-route 比對已按原帳本／現有角色修正。正式 `AIMessage` 不再保存 provider 屬下述觀察性差異，未宣稱等價。最後受影響零付費集合 **116 passed／0 failed**；只讀審查與修正未擴大到 Domain／Memory。

## 尚未驗證／停止線

- OpenRouter 此模型／OpenAI provider／Responses／high＋工具的**實際服務端接受、回覆、價格及計費欄位**尚未證明。公開 Responses 範例有 usage tokens，但未保證同筆回覆含可對帳的 `usage.cost` 和實際 provider；本地 mock 的該兩欄不是服務端證據。若真回覆缺欄，P3 gate 會把該筆視為費用未知並停止。不能把離線全綠當作付費自然試驗的核准。
- 鎖定的 `ChatOpenAI` Responses adapter 會保留終止狀態及 reasoning/tool items，但不把 OpenRouter 的實際 provider 從 raw response 複製到正式 `AIMessage.response_metadata`。正式業務目前沒有消費該欄，P3 test-only HTTP 帳本會在外送邊界核對 raw provider；這是與舊 Chat adapter 的**觀察性差異**，不是已證實的 JD／Memory 功能錯誤。服務端 smoke 與正式切換前仍要決定是否必須把該證據持久保存；若需要，只在 Responses 傳輸邊界補最窄投影，不另造 route registry。
- P3 目前保守預留採 [OpenAI GPT-6 定價](https://developers.openai.com/api/docs/pricing)的長上下文輸入／輸出上界，A 為 US$0.268644／次，B1／B2 為 US$0.287076／次。這不是已確認的 OpenRouter 實際價格；實際 OpenRouter 模型價格／tier 必須在送出前另核對。不放寬既有 12 次聊天、180 次真外送、US$1.00、無 fallback 的界線。
- PostgreSQL／Saver／B1／B2 的新傳輸合成夾具已同步形狀，但本機 Docker 引擎目前不可連，尚未執行真 PostgreSQL gate；不能沿用 5.6 Chat 的 PG PASS 冒充 GPT-6 Responses PASS。舊 checkpoint 的 provider-specific item 相容性亦尚未證實。
- 真模型、真 Browser、自然長訪談、JD 品質及中斷重開均未在新路徑執行；不得 merge、push 或將此分支宣告為正式路徑已驗收。

## 下一個最小 gate

先恢復既有隔離 PostgreSQL 測試環境，跑受影響的 A／B1／B2 Saver／publication 測試；同時核對 OpenRouter GPT-6 Luna 模型頁／metadata 的實際價格及 Responses 成本／路由證據。若必要欄位沒有可靠來源，停止在此提出有界驗證或費用策略裁決，不改 Domain 或讓 P3 帳本估零。完成後再議單一受控服務端 smoke；不自動外送。
