# 0042. 停止 R1 架構實驗、A6 作第一版實作預設

- 狀態：**Accepted**（owner 於 2026-07-27 裁定「不要再跑了，我們就直接研究加做，太浪費時間了，時間很緊迫」）
- 日期：2026-07-28
- 範圍：R1 快篩的收束、第一版實作預設、仍然有效的品質防線、尚未量測項目的誠實記錄
- 部分修正：
  [0040](0040-professional-consultant-engine-and-r1-validation-contract.md)（決定 9 的 exit gate
  **暫停其阻擋效力**；決定 6 的六 arm 矩陣第一版不再執行；其餘一律不變）、
  [0041](0041-r1-p0-closure-first-version-context-and-holdout.md)（決定 11 的**論證禁令仍然有效**，
  見下方決定 4）
- 權威文件：
  [R1a 架構快篩結果](../experiments/2026-07-27-r1-task-discovery/r1a-results.md)、
  [Task 邊界／merge-split／同一性研究](../specs/2026-07-28-task-boundary-merge-split-and-identity-research.md)

## 脈絡

R1a 已用真 provider 跑完 A1／A6／A2 三個 arm、8 案、24 個 observation，成本 US$1.77。結果是：
A6（full harness + light schema + one-stage）有兩個可辨識改善且無新 regression，two-stage 沒有取得
實質改善，`TI-R1-03`／`TI-R1-04` 的 merge/split 缺口三個 arm 都沒過。A3／A4／A5 未執行。

owner 於 2026-07-27 裁定：時程優先，不再跑 R1b、不補 A3／A4／A5、不再跑六 arm 或 pass³，
改以權威研究收斂判準後直接實作。

若不記錄這個裁決，會出現三種誤用：下一位實作者以為還有實驗待補；把 owner 的成本裁決寫成
「研究已證明 A6 最好」；或反過來把「沒跑完」讀成 ADR 0040 的品質防線一併失效。

## 決定

### 1. R1 架構快篩就此收束

1. 第一版**不執行** R1b、A3、A4、A5、20–30 案擴充與 shortlisted critical pass³。
2. 這是 **owner 的時程／成本裁決**，不是實驗結論，也**不是永久禁令**。
   若日後產品品質不足或要降本，重新測試的路徑保留（升 experiment revision）。
3. ADR 0040 決定 9 的 exit gate **暫停其阻擋實作的效力**；它的判準本身沒有被否決。
   **不得宣稱 R1 已通過**，也不得宣稱 Task Discovery 已完成。

### 2. A6 是第一版實作預設

4. 第一版採 **A6：最強模型 ＋ light portable schema ＋ one-stage ＋ full harness**。
   依 ADR 0040 決定 7 的「持平選較簡單者」，two-stage 不進第一版。
5. 可從 A6 promotion 的只有這些**性質**：最強模型、light portable schema、單次呼叫、
   full harness（Task policies、Current Work Model context、state-change 能力）、local deterministic verifier。
6. **實驗欄位不得直接當 production contract**
   （`evals/professional_consultant_r1/assembler.py` 檔頭已自述 not production contracts）。
   第一版必須另定版本化契約：`TaskAnalysisContext.v1`、`TaskAnalysisResult.v1`、`TaskChangeProposal.v1`、
   Task identity／lineage 規則、delta 與完整現況的責任邊界、verifier 規則。
   欄位形狀由該契約與其 plan 決定，不寫進本 ADR。
7. 每個新增欄位都讓形狀離 A6 的已驗證配置更遠，而第一版已無實驗預算校正。
   因此只增加**可機械檢查，或能直接診斷核心錯誤**的欄位，其餘不加。
   （第二類的存在理由：identity 判斷本身無法機械驗證，但少了它就無法分辨
   「認錯同一性」與「認對同一性卻切錯邊界」兩種失敗。）

### 3. 截至第一版未量測的項目

8. 以下**維持未量測**，並且**不阻擋第一版實作**：heavy schema 是否有幫助、便宜模型是否足夠、
   two-stage 在修正判準後是否會勝出、typed Work Model 的獨立效益
   （ADR 0041 決定 12 已禁止把它歸因到任何單一 arm）。
9. 措辭紀律：只能寫「截至第一版沒有實驗結果」，**不得寫「永久 unknown」或「已證明無效」**。

### 4. 誠實性邊界

10. ADR 0041 決定 11 禁止的是「**以研究已有結論為由**縮減或跳過 arm」。本 ADR 縮減 arm 的理由是
    **owner 的時程裁決**，不是研究已回答架構問題。該禁令對論證方式仍然有效：
    任何文件都不得把 §2 的預設寫成研究或實驗證明的結果。
11. [R1a 結果](../experiments/2026-07-27-r1-task-discovery/r1a-results.md) 的狀態更新為：
    **owner 已接受 A6 作第一版方向與相關風險；逐案語意稽核不是 SME 正式驗證，Task Discovery 尚未宣稱通過。**
12. `TI-R1-01`–`TI-R1-08` 的 **case revision 1 不改寫**（R1a 結果引用它）。
    新判準寫進研究與 production contract；若日後要再用這些案例，建立 revision 2 並記錄判準為何改變
    （ADR 0041 決定 15）。

### 5. 不因簡化而移除的品質防線

13. 第一版不建 vNext 那套 Evidence Engine（claim-per-row、Receipt、hash chain、artifact manifest、
    事件重播），但下列一律保留，且**不得以「不做 Evidence Engine」為由移除**：

    - source anchor 必須存在且 quote 可回原文核對；
    - correction target 與 Task ID 引用必須合法；
    - local deterministic verifier 永遠執行（ADR 0040 決定 25–26）；
    - exact model slug 與 endpoint、`require_parameters: true`、禁 fallback、禁隱藏 retry；
    - K/S/A 與 Indicator 支持度四級；`unsupported` 不得寫入正式 JD（ADR 0040 決定 29–32）；
    - 不得自造官方職能基準代碼；匯出標示只採 iCAP 版型（ADR 0040 決定 33–34）。

14. Task 的來源回溯必須涵蓋三類 Source（顧問回合、員工直接編輯、員工對提案的決策），
    不得只連 `turn_id`（ADR 0041 決定 9）。

### 6. 名詞：兩個「三層」必須拆開

15. 後續文件不得再出現兩套「三層架構」。固定為：

    | 名稱 | 內容 | 用途 |
    |---|---|---|
    | Runtime Context Stack | Source Layer → Current Work Model → Operation Context Packet | 決定**餵給模型什麼**（ADR 0041 決定 5） |
    | Product Authority Model | 原始紀錄／目前工作分析／員工核准的 Current JD | 決定**誰是產品真相**（ADR 0040 決定 18–19） |

16. 公版比對結果沿用 **match／partial／no-match／conflict** 四值。
    其權威來源是現行顧問流程文件（[roadmap §11](../specs/2026-07-25-professional-consultant-architecture-realization-roadmap.md)、
    [final red-team](../specs/2026-07-25-professional-job-analysis-consultant-process-final-red-team.md)），
    **不是**已失效的 0038；production contract 仍須重新寫清楚，避免實作者四處找文件。
    第一版不查公版，但保留此四值語意。

### 7. 第一版交付順序

17. Task Analysis 是唯一在做的核心；順序固定為：

    ```text
    Task 資料形狀與 identity 判準
      → Context Packet 投影欄位
      → proposal 形狀
      → Work Model 更新與保存
      → 最小 Task Analysis Core + 少量 smoke
      → 之後才談 OPKS、JD、local Web
    ```

18. 只做必要 unit test 與少量 plumbing smoke，不再跑付費架構矩陣。

## 後果

### 正面

- 下一位實作者不會以為還有實驗待補，也不會把 A6 讀成實驗優勝者。
- 判準改由權威職務分析來源收斂，成本近零且可複核。
- 品質防線與未量測項目分別寫明，簡化不會靜默吃掉安全線。

### 負面與風險

- **A6 沒有通過原定 exit gate**。第一版是在「無 unseen 證據、merge/split 缺口未修」的狀態下起造，
  這是 owner 明確接受的風險。
- 判準是否被模型遵守，只有實作後的少量案例檢查能看出來；那不是 eval，不能宣稱通過。
- 未來若要降本換便宜模型，沒有任何第一版資料可依據，必須重跑實驗。
- 新契約欄位（identity、lineage、結構化 Task 語意欄位）沒有實驗校正，可能過重或過輕；
  這是決定 7 要求「只加可機械檢查的欄位」的原因。
