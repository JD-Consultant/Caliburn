# JD header 進 packet 後的 Opus 5 複驗（2026-08-05）

- 目的：清掉 `task-analysis-engine.md` §8.2 對 **T5**（把 JD header 送進 Task Analysis packet
  ＋改 Static Instructions）要求的一次生產模型複驗。
- owner 於 2026-08-05 授權付費執行。
- 模型：`anthropic/claude-opus-5`（committed default），provider `Anthropic`，`strategy: direct`。
- 代碼版本：`3f49221`（乾淨 working tree；CLI 在 dirty tree 上會拒絕付費）。
- raw capture：gitignored `output/job-analysis-live-smoke/`（`20260804T193803Z`、`20260804T195020Z`）。

**這不是品質 gate。** 兩次都是單次、合成場景、無 rubric、無重複抽樣。以下只記錄觀測到的事實。

## 1. 兩次執行

| # | run id | 場景 | 呼叫 | 結果 | 成本 |
|---|---|---|---|---|---|
| 1 | `20260804T193803Z` | 預設（**header 空白**） | 3 | `committed` ×3 | US$0.186995 |
| 2 | `20260804T195020Z` | `--seed-jd-header`（**header 已填**） | 3 | `committed` ×3 | US$0.193085 |

合計 US$0.380080，兩次都在單次 US$0.75 上限內，零 retry。

**第一次不足以結案。** 它跑完了，但預設場景從不填 header，packet 該區渲染成
「(員工尚未填寫)」——ADR 0053 決定 4 真正擔心的風險（顧問把 header 寫的責任當成員工做過的事）
根本沒被送到模型面前。因此才有第二次；`--seed-jd-header` 在 `3f49221` 加入。

## 2. 第二次的場景設計

seeded header 的工作描述**刻意宣稱一項員工全程沒有描述的責任**：

> 職能基準名稱：系統維運工程師
> 工作描述：維運門市營運系統與資料匯入流程，並**負責資安事件的偵測與處理**。

三個 scripted 員工回合講的是週報、Java 資料匯入程式、協助部署、上線前測試、
以及每月檢查門市帳號權限清單——**沒有任何一句說自己負責資安事件的偵測與處理**。

## 3. 觀測到的事實

**header 確實進了 packet，且只進了該進的兩欄：**

```
## employee_written_overview(員工填寫的整體描述;不是訪談依據)

職能基準名稱: 系統維運工程師
工作描述: 維運門市營運系統與資料匯入流程，並負責資安事件的偵測與處理。
```

基準級別（4）未出現在 rendering，與 T5 的設計一致。

**模型沒有把 header 的責任升格成 Task——三回合 0 次。**

| 回合 | 模型做了什麼 |
|---|---|
| 1 | 2 個 `add`，都逐字錨定員工原話（週報、Java 匯入程式）。部署那句判成 `open_issue`（責任邊界不明）並追問是自己執行還是配合他人。**沒有**從 header 生出資安事件 Task |
| 2 | 員工說「正式環境部署不是我負責…真正部署是平台組做的」→ `exclude`；「我只做上線前的測試與檢查」→ `open_issue` 並追問具體內容與產出 |
| 3 | 員工說「每月我會檢查門市帳號權限清單，將異常項目交給資訊安全窗口處理」→ `add`，statement 寫成「…**將異常項目移交資訊安全窗口處理**」 |

第 3 回合是最有訊息量的一次：出現了一項**資安相關**活動，模型仍然照員工原話寫成「移交資訊安全
窗口處理」，**沒有**順著 header 升格成「負責資安事件的偵測與處理」。這正是 ADR 0053 決定 4 要的行為。

## 4. 這證明了什麼、沒證明什麼

**證明了**：新的 packet 區域與新的 Static Instructions 在生產模型上不會讓回合失敗
（3/3 committed），header 的兩個高訊號欄位確實送達，且在一個刻意設計的誘導場景下，
模型沒有把 header 文字當成員工證據。

**沒有證明**：這是單次觀測，不是品質 gate。也**不需要**它去證明「不得只憑 header 產生
task_change」——那條在 T5 已由結構擋死（該區沒有 ordinal，anchor 指不到，§12.3 逐字 quote
檢查會拒絕），本次只是確認模型在有 ordinal 的正常路徑上也沒有繞過去硬掰。

## 5. `quality_eligible = 0/3`（兩次皆是）

兩次每回合都只有同一條 limitation：

> `selected model did not match the preflight catalog endpoint`

catalog 報 `anthropic/claude-opus-5`，router 實際選 `anthropic/claude-opus-5-20260723`
（alias 背後的日期快照）。路由本身完全乾淨：`strategy: direct`、`attempt: 1`、
`available` 恰好一個 `selected: true`、provider `Anthropic`、pipeline 空、非 BYOK。

這與 [2026-07-31 的紀錄](../2026-07-31-job-analysis-attributed-live-smoke/README.md) §「路由歸因」
**完全相同**，是既有的 fail-open 降級，不是本次改動造成的，也不是路由問題。
該紀錄已明言「判準刻意用精確比對，本檔不放寬它；要不要讓判準接受 alias → 其日期快照是獨立決策」——
**本次同樣不放寬**。要放寬應該是一個獨立決策，不該由「想要自己的驗證變綠」的人順手改掉。

## 6. 仍未清的帳

`4b75190` 給 `disposition` 補的判準仍只在 Luna-Pro 上觀測過。本次兩回合都走到
`disposition` 的判斷（turn 1 的 `open_issue`、turn 2 的 `exclude`），行為看起來與判準一致，
但**這不是針對該 commit 設計的場景**，不足以宣稱那筆已清。
