# Job Analysis OpenRouter 歸因與最小 live smoke：研究紀錄

日期：2026-07-31
狀態：owner 已核准最小方案與 US$0.75 上限；待依實作計畫執行

## 1. 問題與目前證據

`app/job_analysis` 已接通本機 Web、PostgreSQL Current State／Journal、one-stage Task Analysis、
deterministic verifier、Proposal 與 reload；離線測試與 scripted smoke 保護的是資料流與不變量，
**還沒有證明目前產品 prompt、Context、Claude Opus 5 與真 OpenRouter 路由合在一起時能產生可用結果**。

目前 production adapter 已固定：

- model：`anthropic/claude-opus-5`；
- provider：`anthropic`，`order`／`only` 各只有一個值；
- `allow_fallbacks: false`、`require_parameters: true`；
- `reasoning.effort: high`、不回傳 reasoning；
- one-stage、strict portable JSON Schema、單次 HTTP、沒有 retry。

但回應只檢查頂層 `model`，沒有啟用 OpenRouter router metadata，也沒有保留該次呼叫的 provider、
attempt、pipeline、token 與 cost。若直接看模型回答，無法分辨是 prompt 問題、route 受到中介處理、
schema／verifier 問題，或 application commit／reload 問題。

R1a 曾以 8 案比較 A1／A6／A2，接受 A6 作第一版風險預設；當時 generator 是
`openai/gpt-5.6-sol-pro`，而且 TI-R1-03／04 仍有 Task 邊界缺口。它不能替代目前產品路徑的
Opus 5 live smoke，也不能被改寫成「Task Discovery 已通過」。

## 2. 最新官方資料與現行 catalog

以下來源均於 2026-07-31 查核：

| 來源 | 現行要求／觀察 | 對本產品的含意 |
|---|---|---|
| [OpenRouter Router Metadata](https://openrouter.ai/docs/guides/features/router-metadata) | 以 `X-OpenRouter-Metadata: enabled` opt in；成功回應帶 requested、strategy、attempt、selected endpoints、attempts 與 pipeline；cache hit 不帶 metadata；未知 pipeline type 須當 opaque | 每次真測須取得 metadata；缺失或無法解讀時，該次品質觀察不具歸因資格，但不能讓一般產品回合故障 |
| [OpenRouter Response Caching](https://openrouter.ai/docs/guides/features/response-caching) | cache 預設關閉，`X-OpenRouter-Cache: false` 可明確覆蓋 preset；cache hit usage 為 0 | live smoke 明確送 `false`；不能把 cache replay 當真 provider 樣本 |
| [OpenRouter Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs) | 能力以 endpoint 為單位且會變動；`require_parameters: true` 只路由到支援參數的 endpoint；不同 provider 的 strict 保證不同 | 付費前必須查 live catalog，不能把 2026-07-31 的能力寫成永久常數；local verifier 永遠保留 |
| [OpenRouter Provider Routing](https://openrouter.ai/docs/guides/routing/provider-selection) | `only` 限制 provider slug；base slug 可能涵蓋多個 variant，`allow_fallbacks: false` 與 `require_parameters: true` 各有獨立責任 | catalog 與回應 metadata 要一起看；request body 固定規則不變 |
| [OpenRouter API overview](https://openrouter.ai/docs/api/reference/overview) | non-streaming 回應有 native token usage；`usage.cost` 可直接記錄實際 credits 成本 | 預算與結果使用回應 cost，不靠估價回推實際費用 |
| [OpenRouter Reasoning Tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens) | reasoning token 是計費的 output token；Anthropic 的 effort budget 由 `max_tokens` 比例換算，high 約 80%，且仍須保留 final response 空間 | cost reserve 用完整 configured output 上限；若真的截斷，先歸類 output budget，不先怪 prompt |
| [Anthropic Opus 5 prompting](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5) | 先以 high effort 建品質基線，再依自己的 eval 調整；scope 與輸出要求要明確 | 本輪先保持 high，不做 effort sweep；有具體 transcript 失敗才調 prompt |
| [Anthropic agent evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) | task／trial／transcript 要分開；少量人工閱讀適合早期診斷，但單次結果不能宣稱穩定品質 | 三回合只做故障發現與方向判斷，不做統計或 shipping gate |
| [Anthropic Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | 使用最小、高訊號 Context，避免以脆弱硬規則取代模型判斷 | 不為這次 smoke 新增 retrieval、compaction、graph 或大量案例框架 |
| [OpenAI Evaluation Best Practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices) | eval 應 task-specific、保留 log、結合人工判斷，避免只憑「看起來不錯」；現行頁面亦公告舊 Evals 平台將於 2026-11-30 關閉 | 使用 repo 自有的小型 capture，不接將退場的 OpenAI Evals／Prompt Optimizer 平台 |
| [OpenAI Model Selection](https://developers.openai.com/api/docs/guides/model-selection) | 先以最強模型建立 accuracy baseline，再做成本／延遲優化 | 不在未取得產品 transcript 前換便宜模型 |

2026-07-31 對公開 `GET /api/v1/models/anthropic/claude-opus-5` 的實際查詢得到：

- exact model ID 存在；
- endpoint array 中有且只有一個 `tag = anthropic`，`provider_name = Anthropic`、`status = 0`；
- 該 endpoint 支援 `reasoning`、`reasoning_effort`、`max_tokens`、`response_format`、
  `structured_outputs`；
- prompt／completion 價格分別為每 token `0.000005`／`0.000025` 美元。

這只是有日期的 snapshot。實作者仍須在每次付費 smoke 前重查；若 endpoint、能力或價格改變，先停線，
不得拿本段舊數字繼續跑。

## 3. 比較過的三種做法

### A. 只在 Web 手動聊幾輪（不採）

最快，但沒有 route、pipeline、usage、cost 與輸入輸出 capture。回答不好時無法定位責任，回答好時也無法證明
跑到設定的 upstream。它只能做 UX 體感，不能形成工程證據。

### B. 搬用 R1／vNext 的完整 harness（不採）

舊 harness 有 catalog、Capture、grader、矩陣與多 trial，但新引擎的 greenfield 邊界禁止 production import
`evals`／`interview_vnext`。搬入還會把第一個 live smoke 擴成 provider framework、grader platform 與模型矩陣，
增加維護面而沒有回答更多第一版問題。

### C. 最小 route attestation ＋一個三回合 product smoke（採用）

只增加兩項可丟棄的診斷能力：

1. smoke 專用 transport wrapper opt in metadata，並用純函式把 catalog／route／usage 正規化；
2. 一個 CLI 以真 PostgreSQL 與現行 `submit_employee_turn()` 跑固定三回合，保存 gitignored raw capture，
   再由人閱讀 transcript 與 Current State。

不新增模型、grader、case matrix、Graph、agent、資料表或 UI。

## 4. 最小設計

### 4.1 Router metadata 是診斷證據，不是產品真相

一般產品 adapter 不改，也不要求 metadata。只有 live smoke 的 recording transport 在送出前加入 metadata／no-cache
headers；一般產品回合仍依現有 `model`、parse 與 verifier 判定是否可提交。metadata 缺失不得讓員工回合失敗，
也不得寫進 PostgreSQL、Work Model、JD 或 Journal。這避免為一次診斷讓所有日常回合永久多帶未使用的 telemetry。

live smoke 另行判定該 trial 是否具品質歸因資格。至少須滿足：

- `requested` 與 response `model` 都等於 configured exact model；
- strategy 是 `direct`，成功 attempt 是 1；
- 恰好一個 selected endpoint，provider／model 與 preflight catalog 相符；
- usage 含可解析、非負的 cost；
- pipeline 為空，或只有資料明確顯示未 flag／未 detect／未 block 的 guardrail inspection。

任何 compression、response healing、plugin、server tools、blocked／flagged guardrail、未知 stage、metadata
缺失或矛盾，都只讓該 trial 成為 `diagnostic_only`；不得把輸出拿來判 prompt 好壞。parser 必須忽略未知欄位，
但不能把未知 stage 猜成無害。

### 4.2 付費前 catalog preflight

CLI 以 configured model slug 呼叫公開 model detail endpoint，找到 `tag == provider_order[0]` 的 active endpoint，
並確認本 request 用到的能力仍存在。這是零 generation call 的可變外部狀態查核。

若 exact endpoint 不唯一／不存在、狀態非 active、能力不足、price 無法解析或 model ID 改變，付費前停止。
不做自動換 provider、換 model 或 fallback。

### 4.3 三回合場景

使用純 synthetic 內容，固定同一份新建 local document，三次各只送一次：

1. **多工作＋工具**：員工描述週報、資料匯入與協助部署，提到 Python、Excel、Java；工具不得成為獨立 Task。
2. **更正責任**：員工更正正式環境部署不是本人責任，只做上線前測試；舊理解／提案不得繼續當可執行現況。
3. **途中新增工作**：員工補充每月檢查門市帳號權限；新工作不能讓前面尚未結束的 Task／issue／Proposal 消失。

每回合保存模型實際看到的 rendered packet、raw response、route evidence、operation ID、Current State 前後與
active question。語意由人逐回合閱讀，不用字詞相似度假裝成職務分析 grader。

### 4.4 預算與呼叫上限

硬上限：US$0.75、最多 3 次 generation call、沒有任何自動 retry。

每次呼叫前，使用 live catalog 的該 endpoint 單 token 價格估算保守 reserve：

```text
input upper tokens = UTF-8 request JSON bytes
reserve = input upper tokens × prompt price
        + configured max_output_tokens × completion price
```

BPE token 數不會高於承載它的 UTF-8 byte 數，因此這是偏大的 input 上界；reasoning 與 visible output 共用
configured output 上限。若 `actual spent + next reserve > 0.75` 就在 HTTP 前停止。每次完成後改以
`usage.cost` 累計；cost 缺失則停止剩餘回合並標成無法核算，不以猜測補值。

### 4.5 Capture 與報告

raw request／response／state snapshot 寫到已 gitignore 的
`output/job-analysis-live-smoke/<run-id>/`。不得寫 Authorization header 或 API key。

Git 只追蹤一份簡短 experiment report：commit SHA／dirty state、catalog snapshot、prompt／schema hash、
三次 operation 與 route facts、token／cost、deterministic outcome、人工語意裁決、已知限制與下一步。

## 5. Strongest case：這個方案仍可能錯

1. **三回合不是品質驗證。** 它極易漏掉 merge／split、長對話、短答、一次性支援等失敗；最多證明一條
   synthetic 路徑沒有明顯壞掉。
2. **同一場景會對 prompt 過度友善。** 場景由設計者知道判準後撰寫，不能代表真員工分布。
3. **單 trial 受模型變異影響。** 一次成功或失敗都可能是 run-to-run variance，不能比較模型或宣稱穩定率。
4. **metadata 只能說 OpenRouter 回報了什麼。** 它不是 Anthropic 獨立簽章；本輪接受 gateway 官方 telemetry
   作路由歸因，沒有做 direct-vendor 對照。
5. **high effort ＋ 4096 output 可能截斷。** 若真的 `finish_reason=length`，應先分類為 output budget 問題，
   不能誤判成 prompt／Task 邊界問題。
6. **CLI 不是瀏覽器 E2E。** 它走真 application＋PostgreSQL＋OpenRouter，但不驗 UI 點擊、CORS 或前端錯誤顯示。

這些攻擊不推翻此方案，因為本輪問題只是「目前產品路徑是否能用、下一個最值得修的是哪一層」。它們限制了
可宣稱的結論，並說明為何不得在這一步加入更多架構。

## 6. 可下與不可下的結論

三回合完成且人工閱讀通過，只能寫：

> 在指定 commit、2026-07-31 當下 catalog、Opus 5／Anthropic direct route 與這一個 synthetic 三回合場景中，
> 產品路徑可完成 verified commit／reload，未觀察到所列明顯失敗。

不得寫成：

- Task Discovery／專業顧問品質已通過；
- Opus 5 優於其他模型或 high effort 最佳；
- prompt 已最佳化；
- 長對話、真員工、O/P/K/S/A、公版匯出或完整 JD 已驗證；
- 可因此刪除 local verifier、SourceLink、Current Work Model 或人工確認。

若觀察到 semantic failure，先以 transcript 指出是哪條判準失敗，再另做最小 prompt/rubric 修正；同一個付費 run
不邊看邊改、也不自動再跑。若是 provider／schema／verifier／commit 故障，先修該層，不拿 prompt 背鍋。

## 7. 本輪不做

- 不開新 ADR：沒有改變既有 authority，只完成 ADR 0035／0040 已要求的 provider attribution 與小型實證；
- 不 import／搬移舊 `evals`、`interview_vnext` 或 `job_authoring`；
- 不做 grader、模型矩陣、effort sweep、正式統計、prompt optimizer 或 OpenAI Evals 平台；
- 不做通用 provider registry、retry framework、背景工作、Graph、多 Agent 或新資料表；
- 不把 route metadata 寫入產品 DB 或顯示給員工；
- 不在看到 transcript 前修改 prompt、schema、model 或 max output。

實作步驟見
[2026-07-31 Job Analysis attributed live smoke plan](../plans/2026-07-31-job-analysis-attributed-live-smoke-plan.md)。
