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

### 3.2 沒守住的：四軸塌陷

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
   所以拿 byte 數估價一定偏保守」。繁中在 GPT tokenizer 下**每 byte 超過 1 個 token**，
   這裡是 3.25 倍。
2. 同一份 docstring 寫「reasoning 與可見輸出共用同一個 output 上限，所以整條上限都算進來」。
   **送出 `max_tokens: 4096`，實際計費 completion 10,736**——reasoning 被計費但不受 `max_tokens` 約束。

`reserve_or_raise()` 的用途是**在 HTTP 之前**擋下會超額的呼叫。它現在會系統性低估，
低估幅度在這個模型／語言組合上約 2.7 倍。這次無害（US$0.0077 對上 US$0.20 上限），
但**同一個 guard 也守著三回合那支 US$0.75 的 smoke**——照這個倍率，那裡的 US$0.75 授權
可能實際花到約 US$2。

尚未修。修法應該是拿 catalog 的實際計價欄位而不是 byte 數，且不假設 `max_tokens` 涵蓋 reasoning。

## 5. 這次能與不能宣稱

**能：** OPKS 管線對真 provider 完成一次 generate → verify → commit；`reuse_existing` 與
grounding 兩條規則在真模型上成立；wire schema 被 provider 接受；成本可核算。

**不能：** 任何顧問品質結論。這是**本機開發模型的單一 trial**，依既有紀律
（開發用 Luna-Pro、上線切 Opus，**判斷層不准用它驗**），OPKS 的品質債**沒有**因此清掉。
Opus 那次仍要跑，而 §3.2 的四軸塌陷正是屆時最該看的地方。
