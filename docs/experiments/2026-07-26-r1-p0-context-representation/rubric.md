# R1-P0 Task Boundary Rubric

本 rubric 在第一個 trial 前固定，四個 Context arm 共用。評審先看 Critical，再看 Secondary；
不能用 secondary 優點抵銷 critical failure。

## 1. Task 定義

可保留的 Task 必須同時滿足：

1. 是員工目前工作，不是過去或純假設；
2. 是本人穩定責任，不是他人責任或偶爾代班；
3. 是可辨識的工作活動，不只是工具、技能、知識或單一步驟；
4. 具有可說明的對象，以及目的、結果或有意義產出；
5. 粒度可作為職務說明書中的工作任務，不因故事細節任意拆碎；
6. 有輸入內可定位的直接支持；資訊不足時寧可保留 uncertainty。

## 2. Critical checks

每案依 `applicable_critical_checks` 判斷。聚合順序見 §2.1，不是「任一非 pass 即 false」。

| Code | 必須成立 |
|---|---|
| `C1_TOOL_BOUNDARY` | Java／Python／HTML、軟體、設備、方法等手段不單獨成為 Task |
| `C2_RESPONSIBILITY_BOUNDARY` | 他人工作、偶爾協助、代班與本人穩定責任正確區分 |
| `C3_MERGE_SPLIT` | 同一穩定工作不因多故事重複建立；不同結果的工作不被錯誤合併 |
| `C4_CORRECTION_NEGATION` | 後說的更正、明確否定與時間範圍優先，不復活被撤回內容 |
| `C5_ZERO_EVIDENCE` | 沒有足夠工作證據時不建立 Task |
| `C6_SOURCE_FIDELITY` | 每個 Task 的 `source_ids` 真正支持該 Task，且沒有輸入外推測 |

### 2.1 三值判定與聚合

每個 check 的允許值：`pass` / `fail` / `unknown`。

`unknown` 用於評審無法從輸出安全判斷的情況（例如敘述含糊、無法確定是否已把某工具排除）。
允許 `unknown` 是紅隊修訂 C-04 的要求（LLM judge 必須有出口，否則會被迫二選一而製造假訊號）。

`critical_pass` 的聚合順序固定，與 [`trials/README.md`](trials/README.md) 一致：

| 適用 checks 的狀態 | `critical_pass` |
|---|---|
| 任一 `fail` | `false` |
| 沒有 `fail`，但存在 `unknown` | `null`（待裁決） |
| 全部 `pass` | `true` |

**`fail` 優先於 `unknown`** —— 已確認的失敗不會被另一項無法判斷的 check 洗成待裁決。

`critical_pass=null` 的 trial **不是通過**，也不得直接丟棄：owner 在 `owner_resolution` 逐項裁決
`unknown` 後重算聚合，定案值才進入 §4.3 的比較與 §5 的 arm 結論。所有 `unknown` 與其人工結論
一律列進 `report.md`；若 `unknown` 集中在某個 arm，本身就是該 arm 輸出可判讀性較差的證據，要在報告指出。

## 3. Secondary scores

每項使用 0–2 分；只在 `critical_pass=true` 的 trial 間比較（`null` 者須先經 §2.1 裁決定案）。

| Code | 0 | 1 | 2 |
|---|---|---|---|
| `S1_TASK_STATEMENT` | 模糊、工具導向或不可用 | 大致可用但缺對象／結果 | 動詞、對象、目的／結果清楚且不過度具體 |
| `S2_NEXT_QUESTION` | 無關、重複或誘導 | 有幫助但不是最高資訊價值 | 單一、自然且直接降低最大不確定性 |
| `S3_UNSUPPORTED_CLAIMS` | 有明顯虛構 | 有輕微未支持擴寫 | 無未支持內容，uncertainty 誠實 |
| `S4_CONTEXT_EFFICIENCY` | 大量重複或噪音且無品質收益 | 負擔可接受 | 在較少／相近輸入下達到同等或更佳品質 |

`S4` 由實驗報告依可見輸入字元數與結果判斷，不要求 subagent 自評。
**`S4` 必須註明 `raw_plus_spans` 與 `hybrid` 的 spans 是重複計入的字元**：
同一句話出現兩次會同時推高字元數，因此不得把「字元較少」直接讀成「效率較高」，
也不得把「字元較多」讀成「架構較好」。

## 4. 盲評程序

### 4.1 評審者

盲評由**獨立 reviewer subagent**（`codex-auto-review`）執行：

- 不讀生成器的 rationale，也不知道 arm 名稱；
- 一次比較**同一 case 的四份匿名並打亂的輸出**，避免不同 reviewer 之間尺度漂移；
- 收到該 case 的 transcript 與凍結的 `adjudication`（判 `C6_SOURCE_FIDELITY` 必須看得到原文）；
- 輸出每份的 `C*` 三值判定、`S1`–`S3` 分數，以及指名 `source_id` 的理由。

### 4.2 上線前校準

owner 先人工裁決**至少 1 個 case** 的四份輸出，再與 reviewer subagent 的判決比對：

- 不一致以人工為準；
- 給 reviewer prompt **一輪**修正後重跑該 case；
- 校準後才用 reviewer 裁決其餘案例。校準記錄寫進 `report.md`。

未做校準的 LLjudge 就是另一台自誇機器（C-04）。「每個維度各一個 judge」在 P0 規模刻意不做，
列為限制。

### 4.3 Pairwise adjudication

1. 先比較 critical checks。仍為 `unknown` 的項目**先送 owner 裁決**（§2.1），未定案前該 case
   不進入 arm 層比較；不得把 `unknown` 當成 pass，也不得當成 fail；
2. critical 相同才比較 `S1`–`S3`；
3. 品質仍相同時，解盲後才評 `S4`，以較少元件者勝；
4. 不以輸出較長、欄位較多或理由較像專家作為勝出依據。

評審備註必須指出具體 `source_id` 與錯誤類型，不能只寫「感覺比較好」。

### 4.4 殘留解盲

輸出一律只能引用 `turn-*`（見 README §6），因此 claim ID 不會洩漏 arm。
但被餵 spans 的 arm 會不成比例地引用那幾個 turn ID，arm 身分仍部分可推測。
此通道無法根治，列為限制，不得聲稱完全盲測。

## 5. Arm 層結論

- `rejected`：在**重複組案例**（CR-01／CR-03／CR-05）出現另一候選沒有的 critical regression，
  且達 3/3 同方向。
- `retain_for_confirmation`：相對 `raw_only` 多通過至少一個 critical case，且無新增 critical regression。
- `tie_prefer_simpler`：critical 與實質品質持平；依 YAGNI 選 `raw_only`。
- `diagnostic_only`：`structured_only` 可揭露資訊損失，但不具產品候選資格。
- `inconclusive`：重複組案例的三次重複未達 3/3 同方向（README §10.1）。
- `flagged_n1`：差異只出現在 **n=1 案例**（CR-02／CR-04／CR-06）。

**`flagged_n1` 不足以單獨支持任何 arm 結論。** CR-02／CR-04／CR-06 每格只跑一次，
單一二元事件落在 run-to-run 變異範圍內，因此在這些案例觀察到的 regression 或 improvement
只能列為正式 R1 的待查項，不得據以 `rejected` 或 `retain_for_confirmation`。
`CR-04` 的責任邊界因此在 P0 **沒有可下決策的證據強度**，這是重複組選擇 CR-03（merge/split）
換來的代價，必須寫進 `report.md`。

P0 不使用總分選冠軍；`S1`–`S4` 只協助解釋 paired difference。
任何 arm 結論都受 README §3.2 的射程限定：P0 判的是**字面 claim table**（literal-claim layer），
不是 typed Work Model；`rejected` 只能否決前者。
