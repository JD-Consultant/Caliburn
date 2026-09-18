# R1a 架構快篩結果

- run：`r1a-20260727T120447Z`
- 狀態：**批次完整；owner 已於 2026-07-27 接受 A6 作第一版方向與相關風險**
  （見 [ADR 0042](../../adr/0042-r1-screening-stop-and-a6-first-version-default.md) 決定 11）。
  下列逐案語意稽核**不是 SME 正式驗證**，Task Discovery **尚未宣稱通過**；
  R1b、A3／A4／A5 與 20–30 案擴充依同一裁決不執行。
- suite hash：`6c8863863a233830a9216a3ebae46389c91082f097b337c25404400bc93694f7`
- 比較：A1（minimal one-stage）／A6（full one-stage）／A2（full two-stage）
- 未執行：A3／A4／A5；因此不能回答 heavy schema 或 economical model

## 1. 硬事實

| 項目 | 結果 |
|---|---:|
| observations | 24 / 24 |
| generator calls | 32 |
| formal grader calls | 16（每案正序／反序） |
| calibration calls | 2 |
| local verifier outcome | 24 `completed`，0 invalid |
| formal run cost | US$1.6658400 |
| 連同兩次中止嘗試 | **US$1.7712050**（owner 上限 US$2.50） |

生成器固定為 `openai/gpt-5.6-sol-pro-20260709`／`openai/flex`，grader
固定為 `anthropic/claude-opus-5-20260723`／`anthropic`。所有請求皆為 direct、
attempt 1、單一 selected endpoint、無 fallback、無 retry。

call 43 的 OpenRouter metadata 出現 `guardrail/moderation`，但
`data.flagged=false`，回應內容沒有被阻擋或改寫。依 owner 裁決，本實驗只允許這一種
未命中、非變異的 inspection，並留下 `inspected_nonmutating: moderation` limitation；
`flagged=true`、未知 guardrail、plugin、compression、healing 或其他 pipeline 仍 fail closed。
其餘 7 次 grader 從既有 capture 接續，沒有重送 32 次 generator。

這個例外依據 OpenRouter 對 pipeline 與 guardrail metadata 的官方定義：

- <https://openrouter.ai/docs/guides/features/router-metadata>
- <https://openrouter.ai/docs/guides/features/guardrails/overview>

## 2. Model grader 結果不能直接當結論

正反序盲評完整，但人工逐案檢查發現至少三個重要漏判：

1. `TI-R1-03`：三個 arm 都把「主持每月改善追蹤」先建立成 Task；凍結期望要求先
   clarify 完成邊界。A2 雖有追問，仍同時建立了該 Task。
2. `TI-R1-04`：三個 arm 都拆成「資料匯入」與「驗證規則調整」兩個 Task；凍結期望要求
   整併為同一個資料匯入／品質維護 Task。grader 卻全部判
   `merge_split_boundary=pass`。
3. `TI-R1-05`：A1 在缺少產出與範圍時直接建立「執行應用測試」；grader 沒有把
   `meaningful_outcome` 判 fail，只在 `next_question_value` 判 fail。

因此本 run 證明 grader plumbing 可用，**沒有證明 grader 足以取代 owner／SME
裁決**。後續 grader rubric 必須加強「證據不足不得先建 Task」與跨情境 merge/split
判準；這是 grader 問題，不能拿來改寫已凍結 case 期望。

## 3. 逐案語意稽核（待 owner 確認）

| Case | A1 | A6 | A2 | 稽核重點 |
|---|---|---|---|---|
| 01 工具不是 Task | 通過 | 通過 | 通過 | 都未把 Java／HTML／Python 建成 Task |
| 02 工具可存在於完整 Task | 通過 anchor | 通過 anchor | 通過 anchor | 都形成一個升級 Task，沒有步驟過拆；三者都沒補成功標準追問 |
| 03 一段故事多個工作 | 未完全通過 | 未完全通過 | 未完全通過 | 都過早建立改善追蹤 Task；A2 追問較好但沒有撤回候選 |
| 04 多情境整併 | 未通過 | 未通過 | 未通過 | 都拆成兩個 Task，違反凍結 merge 期望 |
| 05 過去工作 | 未通過 | 通過 | 通過 | A1 過早建立應用測試；full arms 正確 clarify |
| 06 他人責任 | 較弱 | **最佳** | 較弱 | A6 排除維運部署、保留本人驗證並追問完成責任；A1 過拆、A2 過度保守且問題過長 |
| 07 一次性代班 | 通過 anchor | 通過 anchor | 通過 anchor | 都拒絕建立供應商請款 Task；A1 說明較弱但核心決策正確 |
| 08 更正 | 通過共同語意 | 通過 | 通過 | 都排除本人部署；A6/A2 另正確 `withdraw task-existing-001` |

這張表是 Codex 依凍結 `expected`／rubric 做的審查草案。owner 已接受它作為第一版方向的依據
（ADR 0042 決定 11），但**它不是 SME adjudication**，不得當成模型品質已驗證。
`TI-R1-01`–`TI-R1-08` 的 case revision 1 不改寫；新的 Task 邊界判準見
[Task 邊界／merge-split／同一性研究](../../specs/2026-07-28-task-boundary-merge-split-and-identity-research.md)。

## 4. 可下到什麼程度的暫定判斷

### A1 vs A6

A6 在 `TI-R1-05` 與 `TI-R1-06` 有兩個可辨識改善，且兩個 locked anchors 沒有
新增 regression；可標成 **`screening_signal_n2`，值得進下一階段**。

這只能歸因於整個 full harness bundle（Task policies、Current Work Model 能力、
state-change 契約等），**不能**宣稱 typed Work Model 單獨有效。

### A2 vs A6

A2 在 `TI-R1-03` 提出較有價值的追問，但仍犯相同的 premature Task 錯誤；
A6 在 `TI-R1-06` 明顯較好。沒有形成至少兩案、無 regression 的實質改善，
且 A2 每案多一次生成呼叫。因此依預先登記規則，**暫定保留較簡單的 A6
one-stage，不讓 two-stage 進第一版**。

### 不能宣稱

- 不能說 A6 已勝出或可直接 shipping；
- 不能說 Current Work Model 單獨有效；
- 不能說兩階段永遠無效；
- 不能回答 heavy schema 或便宜模型；
- 不能說 Task Discovery 已完成：`TI-R1-03`／`04` 顯示 merge/split 仍是核心缺口。

## 5. 建議的下一步

owner 若確認上面的逐案稽核：

1. 第一版 production 候選採 **A6：full harness + light schema + one-stage**；
2. 先只針對 `TI-R1-03`／`04` 修正 Task 邊界 rubric／prompt，不擴建 graph 或第二階段；
3. 用少量新增案例確認「故事內多工作」與「多情境同一工作」兩種相反邊界；
4. 再擴到 20–30 案與 shortlisted critical pass³，才決定是否進 R2。

原始 prompt、context、request、response、usage、route metadata 與匿名 review packet
保存在 gitignored：

`apps/api/output/professional-consultant-r1/r1a-20260727T120447Z/`
