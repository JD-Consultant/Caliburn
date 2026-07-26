# R1-P0 Task Boundary Rubric

本 rubric 在第一個 trial 前固定，三個 Context arm 共用。評審先看 Critical，再看 Secondary；
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

每案依 `applicable_critical_checks` 判斷。任一適用項失敗，該 trial 即為 `critical_pass=false`。

| Code | 必須成立 |
|---|---|
| `C1_TOOL_BOUNDARY` | Java／Python／HTML、軟體、設備、方法等手段不單獨成為 Task |
| `C2_RESPONSIBILITY_BOUNDARY` | 他人工作、偶爾協助、代班與本人穩定責任正確區分 |
| `C3_MERGE_SPLIT` | 同一穩定工作不因多故事重複建立；不同結果的工作不被錯誤合併 |
| `C4_CORRECTION_NEGATION` | 後說的更正、明確否定與時間範圍優先，不復活被撤回內容 |
| `C5_ZERO_EVIDENCE` | 沒有足夠工作證據時不建立 Task |
| `C6_SOURCE_FIDELITY` | 每個 Task 的 `source_ids` 真正支持該 Task，且沒有輸入外推測 |

## 3. Secondary scores

每項使用 0–2 分；只在 `critical_pass=true` 的 trial 間比較。

| Code | 0 | 1 | 2 |
|---|---|---|---|
| `S1_TASK_STATEMENT` | 模糊、工具導向或不可用 | 大致可用但缺對象／結果 | 動詞、對象、目的／結果清楚且不過度具體 |
| `S2_NEXT_QUESTION` | 無關、重複或誘導 | 有幫助但不是最高資訊價值 | 單一、自然且直接降低最大不確定性 |
| `S3_UNSUPPORTED_CLAIMS` | 有明顯虛構 | 有輕微未支持擴寫 | 無未支持內容，uncertainty 誠實 |
| `S4_CONTEXT_EFFICIENCY` | 大量重複或噪音且無品質收益 | 負擔可接受 | 在較少／相近輸入下達到同等或更佳品質 |

`S4` 由實驗報告依可見輸入字元數與結果判斷，不要求 subagent 自評。

## 4. Pairwise adjudication

同一 case 的三個 arm 完成後，評審以匿名輸出做 paired comparison：

1. 先比較 critical checks；
2. critical 相同才比較 `S1`–`S3`；
3. 品質仍相同時，以 `S4` 與較少元件者勝；
4. 不以輸出較長、欄位較多或理由較像專家作為勝出依據。

評審備註必須指出具體 `source_id` 與錯誤類型，不能只寫「感覺比較好」。

## 5. Arm 層結論

- `rejected`：出現另一候選沒有的 critical regression。
- `retain_for_confirmation`：相對 Raw-only 多通過至少一個 critical case，且無新增 critical regression。
- `tie_prefer_simpler`：critical 與實質品質持平；依 YAGNI 選 Raw-only。
- `diagnostic_only`：Structured-only 可揭露資訊損失，但不具產品候選資格。

P0 不使用總分選冠軍；`S1`–`S4` 只協助解釋 paired difference。
