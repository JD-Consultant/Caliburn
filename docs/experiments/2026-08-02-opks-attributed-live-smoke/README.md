# OPKS attributed live smoke（2026-08-02）

狀態：**一次呼叫，`verified` 並 committed。花費 US$0.0076584。**

授權：owner 當次核准「最多 1 次 generation call、上限 US$0.20、零 retry」，指定使用目前產品配置
（`.env` 的 `openai/gpt-5.6-luna-pro`）。

driver：[`apps/api/scripts/job_analysis_opks_live_smoke.py`](../../../apps/api/scripts/job_analysis_opks_live_smoke.py)
（commit `9285a0b`，跑之前工作樹乾淨）。raw capture 在 gitignore 的
`output/job-analysis-opks-live-smoke/20260802T071914Z/`。

## 1. 路由與歸因

| 項目 | 值 |
|---|---|
| requested / response model | `openai/gpt-5.6-luna-pro` |
| **selected model** | **`openai/gpt-5.6-luna-pro-20260709`** |
| provider / strategy | OpenAI / `direct`，attempt 1 |
| catalog 實價 | in US$0.10/M、out US$0.60/M |
| `quality_eligible` | **false** |

`quality_eligible` 為 false 的唯一原因是 alias 被解析成 dated snapshot，與 preflight 定價的
endpoint 字串不相等。這是 `docs/plans/2026-07-27-r1-task-discovery-implementation-plan.md` 已記錄的
路由行為，**判準沒有放寬**——照原樣記錄，不改 criterion 去換一個好看的旗標。

## 2. 場景（跑之前凍結）

單一 Task「每月盤點門市庫存並釐清帳實差異」，三句員工原話。兩個刻意設計：

- quote 2 只說「差異超過**一定數量**」，**沒有數字**。prompt 禁止自行補數字 → 若生出具體門檻，
  是可歸因的 grounding 失誤。
- 預種一筆文件層知識「門市報廢與庫存調整單的核准流程」，**只連 task-2、不連選定的 task-1**。
  quote 3 正好講這件事 → 正解是 `reuse_existing`。

## 3. 結果

模型輸出 9 項：2 工作產出、3 行為指標、1 knowledge `reuse_existing`、3 技能。
verifier **0 violations、9 changes**，committed，proposal id 依 `operation_id + kind + index` 決定性鑄出。

### 3.1 守住的

**`reuse_existing` 完全正確。** 模型輸出 `reuse_existing ord=1`、`text` 空，verifier 轉成 `revise`：

```
BEFORE: 門市報廢與庫存調整單的核准流程 | refs=['task-2']
AFTER : 門市報廢與庫存調整單的核准流程 | refs=['task-2', 'task-1']
```

文字未動、只多一個 task ref。**ADR 0048 的文件層 K/S many-to-many 在真模型上成立**，
而且模型只看到 ordinal `[1]`、從未看到 `direct-seed-knowledge-knowledge`。

**沒有捏造數字。** 指標寫「差異超過**一定數量**時」——把員工的模糊說法原樣帶過，沒有變成
「超過 5%」或「10 件以上」。也沒有出現「依公司規定」「適時」這類官樣條件。
兩條 prompt 規則在便宜模型上都守住了。

### 3.2 沒守住的：技能只是指標換句話說，且完全沒生知識

三個技能各自是它配對的行為指標**拿掉評價語氣**後的同一句話：

| 行為指標 | 技能 |
|---|---|
| 每月底的盤點能對出 POS 匯出帳面數量與實際數量，並指出不一致項目。 | 比對 POS 匯出帳面數量與實際盤點數量，找出帳實差異。 |
| 差異超過一定數量時，能查明收貨未登錄、報廢未扣帳等原因，並寫成差異說明交給店長。 | 查核收貨未登錄、報廢未扣帳等原因，並撰寫庫存差異說明。 |
| 對不上時不自行改帳，而是提出報廢或調整單，待店長核准後才生效。 | 依門市報廢與庫存調整單的核准流程提出申請，讓店長核准後生效。 |

三比三，無一例外。另外兩處同類問題：

- 工作產出 [0]「門市庫存帳面數量與實際數量一致，避免補貨誤判」幾乎逐字複製 Task 自己的
  `purpose_result`「讓帳面與實際庫存一致，避免補貨誤判」——packet 裡已有的欄位換句話說。
- 技能 [8] 又把剛 reuse 的那筆知識複述一次。

**現行 verifier 依設計看不到這件事**：`entity_kind` 不同，`(kind, text)` 的精確重複鍵天生撞不到，
文字也不逐字相同。這正是 `docs/design/task-analysis-engine.md` 畫的「語意問題，不做相似度服務」
那條線的另一側。

### 3.3 沒測到的

`uncertain` 一次都沒出現，精確重複規則也沒被觸發（模型正確 reuse 了）。
**這是場景設計的限制，不是模型的發現**——三句原話覆蓋了整條工作流程，沒有製造出真正的
依據缺口，所以這次無法判斷 `uncertain` 是否可用，也沒拿到整批拒絕的 blast radius 資料。

## 4. 最重要的發現：預算 reserve 模型不成立

這條與模型品質無關，關於**我們自己的付費防護**。

| | reserve 假設 | 實際 |
|---|---|---|
| prompt tokens | 3,744（＝request body bytes） | **12,168** |
| completion tokens | 4,096（＝送出的 `max_tokens`） | **10,736**（含 9,211 reasoning） |
| 金額 | US$0.0028239 | **US$0.0076584** |

實際是 reserve 的 **2.7 倍**。兩個假設各自被推翻：

1. **`job_analysis_live_smoke.py` 的 docstring 寫**「BPE token 數不會超過承載它的 UTF-8 byte 數，
   所以拿 byte 數估價一定偏保守」。**這條錯的原因不是繁中字節多**——是計費用的是模型自家的
   tokenizer，本機只有 HTTP body 的 byte 數，**byte 數對 token 數根本不構成上界**，與語言無關。
   OpenRouter 也沒有公開的輸入 token 預估端點可以在送出前查。
2. 同一份 docstring 寫「reasoning 與可見輸出共用同一個 output 上限，所以整條上限都算進來」。
   **送出 `max_tokens: 4096`，實際計費 completion 10,736**——reasoning token 是要計費的 output
   token，而且在這條路徑上不受該上限約束。

   **這第 2 點只成立於實測過的那條路徑**（OpenAI `openai/gpt-5.6-luna-pro`，舊 `max_tokens`
   參數），**不可泛稱到所有 provider**。Anthropic 官方明定 Claude 的 `max_tokens` 涵蓋 thinking
   且是硬上限，因此 Opus 路徑預期不會有同樣的 output 溢出。輸出上限管不管得住 reasoning，
   **per-provider 不同，各自實測**。第 1 點（byte 數不是 token 上界）則與 provider 無關。

`reserve_or_raise()` 的用途是**在 HTTP 之前**擋下會超額的呼叫。它系統性低估，這次約 2.7 倍。
這次無害（US$0.0077 對上 US$0.20 上限），但**同一個 guard 也守著三回合那支 US$0.75 的 smoke**
——照這個倍率，那裡的 US$0.75 授權可能實際花到約 US$2。

### 4.1 已修（commit `1bd22c7`）

- `reserve_or_raise()` → **`precheck_or_raise()`**，並在碼與文檔裡明講它是估算。
  真正的保證只剩三條且只宣稱這三條：**呼叫次數上限、零 retry、每次回應後照實際 cost 結算停線**。
  新增回歸測試：估算低估時，停線責任確實落在回應後的結算上。
- **輸出上限參數名改由 catalog 決定。** OpenRouter 已 deprecate `max_tokens` 並建議
  `max_completion_tokens`，但 **per-endpoint 的 `supported_parameters` 還沒跟著更名**——
  這次抓回的 `openai/gpt-5.6-luna-pro` 只列 `max_tokens`。因為 request 帶
  `require_parameters: true` 且 `allow_fallbacks: false`，送一個沒宣告的名字不是被路由拒絕
  就是被靜默丟掉，**後者等於輸出上限整個消失**，比留著舊名更危險。
  所以 `OpenRouterEndpointSnapshot` 現在帶 `output_cap_parameter`，adapter 照它送，
  preflight 對兩個名字都沒宣告的 endpoint 直接停線。免費 preflight 現在會印出選中的名字。
- wire invariant 測試原本**完全沒有斷言輸出上限那個 key**，所以改它不會被發現。現在有了。

沒有加通用 tokenizer、provider framework 或複雜預算系統。

#### 生效範圍（不要誤讀成 production 已經動態選參數）

catalog 自動選參數**目前只接在兩支 live-smoke script 上**。正式 FastAPI 的
`get_job_analysis_adapter()` 建 `OpenRouterConfig` 時**不帶 `output_cap_parameter`**，
因此沿用預設值 `max_tokens`，而且**production 路徑沒有 catalog preflight**——員工的每一次
回合不會為了查參數名多打一次外部 API。

這是刻意的取捨，不是遺漏：production 目前跑的 endpoint 本來就只宣告 `max_tokens`，
預設值與 catalog 的答案一致。等到哪個要用的 endpoint 只宣告 `max_completion_tokens`，
`get_job_analysis_adapter()` 才需要處理，屆時再決定是加設定值還是啟動時查一次。

## 5. 這次能與不能宣稱

**能：** OPKS 管線對真 provider 完成一次 generate → verify → commit；`reuse_existing` 與
grounding 兩條規則在真模型上成立；wire schema 被 provider 接受；成本可核算。

**不能：** 任何顧問品質結論。這是**本機開發模型的單一 trial**，依既有紀律
（開發用 Luna-Pro、上線切 Opus，**判斷層不准用它驗**），OPKS 的品質債**沒有**因此清掉。
Opus 那次仍要跑，而 §3.2 的軸線混淆正是屆時最該看的地方。（已於 Run 2 執行；最終裁決見 §9。）

---

# Run 2：Opus 5，同一凍結場景（2026-08-02 08:50 UTC）

狀態：**一次呼叫，`verified` 並 committed，未截斷。花費 US$0.037715。**

授權：owner 當次核准單次上限 US$0.60。條件：同一凍結場景、Opus 5 精確 ID、Anthropic direct
route、high reasoning 不變、`JOB_ANALYSIS_MAX_OUTPUT_TOKENS=16384` 只覆寫本次執行、
最多 1 call、零 retry、preflight 狀態或價格改變即停、即使 truncated 也不補跑。
付費前重跑免費 preflight 確認 status 0 與 $5/$25 未變。

capture：`output/job-analysis-opks-live-smoke/20260802T085031Z/`

## 6. 實際用量與成本

| | Luna-Pro | **Opus 5** | 倍率 |
|---|---|---|---|
| prompt tokens | 12,168 | **1,523** | **0.13x** |
| completion tokens | 10,736 | **1,204** | 0.11x |
| ├ reasoning | 9,211 | **189** | 0.02x |
| 單價 in／out | $0.10／$0.60 /M | $5／$25 /M | 50x／42x |
| **成本** | $0.0076584 | **$0.037715** | 4.9x |

`1,523 × $5/M + 1,204 × $25/M = $0.037715`，與回報值逐位相符。

**核准前的預估全數失準，而且方向一致：** 預期 ~$0.33、最壞 ~$0.47，實際 **$0.0377**。
原因是雙方都假設 Opus 會用掉與 Luna 相近的 token 量。**同一份 packet，Opus 的 prompt tokens
是 Luna 的 1/8**（先前紀錄推測的 3.1x tokenizer 差距，實測是 8.0x），而 reasoning 只用了
189 tokens——Luna 用 9,211。

因此**先前擔心的截斷風險沒有發生，而且前提本身是錯的**：`max_output_tokens=16384` 完全用不上，
連原本的 4,096 都綽綽有餘（實際 1,204）。提高上限是白付的保險，不是必要條件。

## 7. 四軸：模型問題還是結構問題？（結論：結構保留）

同一份 prompt、同一份 packet，只換模型。Opus 出 12 項（3 O／3 P／3 K／3 S），Luna 出 9 項。

### 7.1 模型就能解決的（Opus 用同一份 prompt 直接修好）

**工作產出不再是把 `purpose_result` 換句話說。** Luna 的 O[0]「門市庫存帳面數量與實際數量一致，
避免補貨誤判」幾乎逐字複製 Task 欄位。Opus 三項全是可交付物：比對結果、差異說明、
經核准生效的調整單。

**知識與技能分開了。** Luna **一項新知識都沒生**，還把「依核准流程提出申請」寫成*技能*——
等於把剛 reuse 的知識再講一次。Opus 另外生出兩項真正的知識，且都是名詞化的領域知識：

- 「POS 系統庫存報表匯出方式與帳面數量欄位意義」
- 「門市帳實差異的常見成因（收貨未登錄、報廢未扣帳）」

技能則全是可操作動作（以 Excel 比對、追查並撰寫、填製並送核准）。**名詞 vs 動作的分界，
Opus 自己就守住了。**

### 7.2 P／S 語意相鄰是**預期**，不是缺陷

> **2026-08-02 owner 裁決（推翻本節初稿）。** 初稿把「行為指標與技能一對一貼合」寫成
> 結構嫌疑，那是誤讀：行為指標描述「做到什麼程度才算合格」，技能描述「為達到該標準所需的
> 方法、技巧或工具運用」。**兩者本來就會圍繞同一個工作行為**，不需要刻意寫成互不相關——
> 這與英國 NOS 的品質準則、ESCO 的 skill 定義、iCAP 職能基準的分工一致。
> 要求兩軸互不相關才是錯的期待。

下表的一對一對應**不構成問題**，保留是為了記錄兩個模型的實際差異：

| 行為指標 | 技能 |
|---|---|
| 每月底盤點時，將 POS 匯出的帳面數量與門市實際清點數量逐項對應完成比對 | 以 Excel 比對 POS 匯出帳面數量與實地清點數量，找出差異品項與差異量 |
| 差異超過一定數量時查明成因，並寫成差異說明交店長 | 追查差異來源並撰寫可供店長判讀的差異說明 |
| 不自行更改帳面數量，差異一律以報廢單或調整單送店長核准後才生效 | 填製報廢單或庫存調整單並送店長核准以更正帳面數量 |

Opus 版的技能帶了方法與工具（Excel、可供店長判讀），指標則保住判準語氣（逐項對應完成、
一律送核准後才生效）——**這正是兩軸該有的分工**。Luna 版的技能則是把指標拿掉評價語氣、
不含任何方法，那才是退化。

### 7.3 真正該盯的：技能退化

**第三項技能「填製報廢單或庫存調整單並送店長核准以更正帳面數量」比較像工作步驟，
不像可重用技能。** 它描述的是這條流程裡的一個動作，換一個職位就不成立；相對地，
「以 Excel 比對…找出差異品項與差異量」是帶得走的能力。

這是 **prompt／rubric 的微調問題，不足以推翻架構**。收斂後的結論是：

> **P／S 語意相鄰屬預期；需防止技能退化成完整指標或流程步驟。**

**不因 n=1 改 schema 或 verifier。** 等真實使用中再次出現「流程被寫成技能」，
再只調整一小段 prompt／rubric，不新增欄位或架構。

### 7.4 兩個模型都守住的

- **`reuse_existing` 正確**：同樣輸出 `ord=1`、text 空，verifier 轉成只加一個 task ref
  的 `revise`，文字未動。
- **沒有捏造數字**：指標寫「差異超過一定數量時」，原樣帶過員工的模糊說法。
- **沒有官樣條件**：無「依公司規定」「適時」。
- verifier **0 violations**，12 changes 全部 committed。

### 7.5 仍未測到

`uncertain` 依舊零次，精確重複規則依舊沒觸發。**場景設計的限制**：三句原話覆蓋了整條流程，
沒有製造出真正的依據缺口。要測這兩項需要另一個刻意留白的場景。

## 8. 歸因

| 項目 | 值 |
|---|---|
| requested / response model | `anthropic/claude-opus-5` |
| **selected model** | **`anthropic/claude-opus-5-20260723`** |
| provider / strategy | Anthropic / `direct`，attempt 1 |
| `quality_eligible` | **false** |

與 run 1 相同的原因：alias 被解析成 dated snapshot。**判準未放寬。**

---

## 9. 最終裁決（2026-08-02，owner）

**第一版帶著現有結構往下走。不再付費測試，不改四軸資料結構。**

| 項目 | 裁決 |
|---|---|
| O／P／K／S 結構 | **保留** |
| 第二個 Opus 場景 | **不跑** |
| schema／verifier | **不因 n=1 修改** |
| `quality_eligible: false` | **維持原樣**，不為了取得漂亮標籤而放寬歸因規則 |
| P／S 語意相鄰 | **屬預期**（NOS／ESCO／iCAP 皆如此分工） |
| 待防範 | **技能退化成完整指標或流程步驟** |

處理方式：等真實使用中再次出現「流程被寫成技能」，**只調整一小段 prompt／rubric，
不新增欄位或架構**。

### 這兩次 run 真正證明的

不是四軸完美，而是：**最強模型能在現有架構下產生可用的 OPKS、正確重用既有知識、
不捏造數字，而且完整流程可提交。** 管線、契約、identity gate、決定性鑄 ID、
文件層 K/S many-to-many 都在真 provider 上成立。

第一版可以往下走。
