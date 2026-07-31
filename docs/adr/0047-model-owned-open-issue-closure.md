# 0047. 模型可關閉自己提出的 open issue

- 狀態：Accepted
- 日期：2026-07-31
- 補充：[0044](0044-partial-jd-task-reconciliation-and-human-confirmation.md)（放寬其
  `resolves_open_issue_ordinal` 的適用範圍，不推翻其 reconciliation 規則）
- 實證：[attributed live smoke](../experiments/2026-07-31-job-analysis-attributed-live-smoke/README.md) §0c

## 脈絡

0044 為「員工直接新增、尚未分析的 JD-only Task」建立 reconciliation open issue，並讓模型以
`resolves_open_issue_ordinal` 關閉它。該欄位**只**服務這一種 issue。

模型自己在分析中提出的 open issue（`責任邊界不明`／`證據不足`／`矛盾未解`／
`task_boundary_uncertain`）沒有任何關閉路徑：`transition.py` 只在 reconciliation 路徑
`remove(issue)`，`next_question` 指向它僅更新 `last_asked_turn_id`。

2026-07-31 的付費 live run（`20260731T123344Z`）在 turn 2 直接撞上：員工更正
「正式環境部署不是我負責，真正部署是平台組做的」，模型同時輸出 `exclude / 他人工作`
與「關閉上一輪那個 `責任邊界不明`」——**判斷正確，契約不允許**，整輪被
`RESOLUTION_OPEN_ISSUE_NOT_RECONCILABLE` 拒絕，付費呼叫與員工那一輪都作廢。

不關閉的代價不只是那一次拒絕：

- open issue 單調累積，而**每一輪 Context Packet 都要重新渲染全部 open issue**。實測一則
  約 200 bytes；十幾輪訪談後就超過我們剛把 schema 從 6,818 壓到 4,818 所省下的量。
- Static Instructions 要求 `next_question` 優先處理「仍可取得答案的 open issue」。已被回答
  卻仍在清單上的 issue 會排擠真正的缺口——這對職務說明書品質是**確定**的損害，
  而不是假設性的。
- open issue 未暴露於 web，員工無從清理；唯一的消費者就是模型自己。

## 決定

- `resolves_open_issue_ordinal` 的適用範圍擴及**全部** open issue。
- **reconciliation issue（帶 `reconciliation_task_id`）的規則完全不變**：仍只接受
  `no_match + add` 或帶合法原因的 `exclude`，仍由 application 以原 JD `task_id` 物化或
  提出 withdraw Proposal。0044 的判準一字不改。
- **一般 open issue**：任何 disposition 皆可關閉；application 移除該 issue **並照常套用
  該訊號本身的效果**（reconciliation 路徑則維持「取代原本效果」的既有語意）。
- 關閉一般 open issue 要求該訊號的 `anchors` 含**目前這一輪的員工回合**
  （新增 `RESOLUTION_MISSING_CURRENT_TURN_ANCHOR`）。與 supersession 沿用同一條不變量：
  改寫既有結論必須基於當下這次回答，不能用舊證據批次清單。
- 不新增欄位、不新增 enum、不新增員工 gate。open issue 是分析中的工作狀態，不是
  Current JD；關閉它比模型已經能做的 `withdraw` 一筆 Task 影響更小。
- 若不確定性仍在，模型應在同一輪輸出**新的** open issue；不做「重開舊 issue」的機制。

## 依據

只有處理該回合答案的模型知道自己上一輪的問題有沒有被回答；application 沒有可靠的判準
（文字相似度在 0044 已被明確否決）。

先例：Anthropic 2026-07-24〈The new rules of context engineering for Claude 5 generation
models〉把「模型擁有自己工作清單的生命週期、harness 只負責確定性地persist」當成 tool 介面
設計的示範（status enum ＋ 「keep one item in_progress」的約束提示）。本決定同構：
模型提出並關閉自己的待答問題，application 仍是唯一寫入者且經 verifier 驗證。

## 後果

正面：

- 訪談的 Context 不再單調成長，`next_question` 的優先序不被已回答的 issue 排擠。
- 契約表面沒有變大：沿用既有欄位，新增的只有一條與 supersession 對稱的 anchor 不變量。

負面／風險：

- 模型可能過早關閉仍未釐清的 issue，等於少問一題。緩解：關閉必須錨定當回合答案；
  不確定性仍在時同一輪可輸出新 issue；Journal 保留完整結果可回溯。
- 被關閉的 issue 不在 Current State 留下墓碑（只在 Journal）。第一版接受；若日後需要
  「哪些疑問被關掉、憑什麼」的產品級追溯，另開 ADR。
- 一般 open issue 的關閉沒有員工 gate。這與 Work Model 既有的 identity gate 一致
  （明確 identity 直接寫入、不明確才提 Proposal），且 open issue 不影響 Current JD。
