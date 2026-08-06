# 0059. AI 輔助主要職責：只做暫定框架、獨立 operation、輕量候選、第一版不接 reference

- 狀態：Proposed
- 日期：2026-08-06
- 依據：[`docs/specs/2026-08-06-ai-assisted-duty-research.md`](../specs/2026-08-06-ai-assisted-duty-research.md)
- 操作化：[0055](0055-hybrid-job-discovery-and-ttop-formation.md) 決定 2（暫定職務框架）——
  0055 只固定分析語意與順序、明言「不建立 API、資料表或 Web route」，本 ADR 補上實作形狀
- 沿用：[0049](0049-opks-derived-axes-evidence-whitelist-and-document-authority.md)（獨立 operation ＋ 獨立 wire schema 的先例）、
  [0042](0042-r1-screening-stop-and-a6-first-version-default.md) 決定 7（只加可機械檢查的欄位）
- 翻案：[`docs/plans/2026-08-05-job-analysis-duty-and-task-competency-level-plan.md`](../plans/2026-08-05-job-analysis-duty-and-task-competency-level-plan.md)
  §4「第一版 AI 不參與 Duty」——該節自述「若日後要翻案需先有真實使用摩擦的證據」，
  本 ADR 以 owner 產品裁決翻案，**據實標註此非使用摩擦證據**

## 脈絡

owner 於 2026-08-06 要求員工能先做 Duty、且 Duty 要有 AI 輔助。

「先做 Duty」今天已經成立——`DutyEditor` 獨立於訪談，Duty 切片 T6 已交付。真正的新需求是 AI 輔助，
而它不牴觸任何既有裁決：ADR 0055 決定 2 明文允許「依職位範圍、既有 JD 與職能基準建立暫定職務框架」，
現況純手動是 Duty 切片 plan §4 選的保守子集。

研究紀錄釐清了三件先前被混為一談的事：

1. **有兩種 AI-Duty，前提完全不同。** (i) 暫定職務框架（ADR 0055 決定 2，不需要任何 Task）與
   (ii) 從穩定 Task 歸納 Duty（決定 4，需要 Task 已穩定）。owner 要的是 (i)。
2. **`app/job_analysis` 對 reference 的存取是零**（實測），但 reference 語料是真的
   （908 個官方 OCS JSON、Qdrant `ocs_v4` 9,449 points、status green）。
3. **錨定風險兩邊都沒有證據。** ADR 0055 與其研究都明說「先自由敘事、後顯示 taxonomy」
   是待驗證假說，官方資料裡沒有直接比較試驗。

## 決定

### A. 範圍

1. **只做 (i) 暫定職務框架，不做 (ii) 歸納 Duty。** (ii) 的價值與可行性取決於真人訪談實際產出多少
   Task、有多穩定——那是 R9 pilot 才知道的事，現在做是在猜（Duty 切片 plan §4 理由 3 對 (ii) 仍然成立）。
2. **不動 `task_analysis_result_v2` 與其 Static Instructions。** 新能力走**獨立 operation ＋ 獨立
   wire schema**，比照 OPKS（ADR 0049）。這讓 ADR 0042 決定 7 的顧慮不適用——A6 的已驗證配置
   一個欄位都不改，也就不需要再做一次付費模型複驗。

### B. 候選承載形狀

3. **候選採輕量清單，不建第三種 Proposal。** operation 回一組候選職責敘述，UI 呈現為可勾選清單；
   員工勾選即走**既有 `add_duty()`**，Journal 照常記錄該筆 direct edit。
   理由：`Proposal` 全綁 `TaskId`（ADR 0050 已因此另建 `OpksProposal`），Duty 同樣不能複用；
   但 Duty **沒有 evidence／lineage／stale 語意**，六態狀態機大半空轉。
   更關鍵的是——ADR 0048／0049 那套 Evidence 白名單是為了防止把「員工按了接受」記成行為證據，
   而 **Duty 是結構分組、不主張任何能力**，沒有這個風險。
4. **候選在被員工接受前不是 Current JD 的一部分**，不落庫、不進 `JobAnalysisState`
   （ADR 0055 決定 2：參考候選不得冒充員工工作證據）。
5. **不得自動套用。** 職責切分是語意判斷，verifier 攔不住；候選必須逐條由員工決定。

### C. 第一版不接 reference

6. **第一版只用文件既有的 `title` 與 `JdHeader.work_description` 產生候選，不接 indexer。**
   理由：這能在零新基礎設施下驗證核心問題——「AI 建議 Duty 對員工到底有沒有幫助」。
   若答案是否定的，接了 reference 也救不了；若是肯定的，第二版再接就有真實回饋可以判斷值不值得。
7. **未來要接 reference 時，`app/job_analysis` 自帶 port**（`application/` 的 Protocol ＋
   `providers/` 的 adapter），**不共用 `app/core/knowledge_dto`** 的型別——沿用 greenfield 既有慣例，
   避免與 legacy core 產生新耦合。降級行為屆時依 ADR 0018（reference enrichment 可回部分結果）。
8. **即使日後接上 reference，也不得把 reference 帶回的 `職能基準代碼`／`職類別代碼` 寫進本文件的
   header 欄位**（ADR 0052 決定 8）。那是 reference 自己的識別，不是本文件的。

### D. 不擋任何既有路徑

9. **候選是可整批忽略的輔助，不是必經步驟。** 空手建 Duty、先訪談後建 Duty、完全不用 AI 建議，
   三條路徑都必須照常可行。
10. 這條不是保守，是**因為順序問題沒有證據**：ADR 0055 與其研究都明說「先自由敘事、後顯示 taxonomy」
    是待驗證假說。既然不知道哪個順序好，就不該用實作把任何一種鎖死。O\*NET 的實務也是既有清單與
    開放新增並存，並鼓勵清單外的 write-ins。
11. UI 必須讓員工看得出候選**是 AI 產生的建議、不是他自己說過的話**。

## 後果

### 正面

- `task_analysis_result_v2` 零改動，A6 已驗證配置不受影響，不需要重跑付費複驗。
- 不建第三種 Proposal，省下一整套狀態機、決策 route 與 stale 規則；Duty 的薄型別維持不變。
- 第一版不接 reference，讓「AI 建議 Duty 有沒有用」這個問題能單獨被驗證，不會跟
  「reference 檢索品質好不好」混在一起。
- 三條路徑並存，讓 R9 pilot 有機會**實際觀察**員工偏好哪種順序——這正是目前兩份文件都缺的證據。

### 負面／代價

- 選項 A 失去「AI 建議了 5 條、員工只採 2 條」的完整稽核軌跡。Journal 只記錄實際建立的 Duty，
  沒有被忽略的候選。若日後需要這個資料來評估建議品質，要另外補。
- 不接 reference 意味著候選品質完全依賴模型先驗知識，對冷門職類可能明顯較差。
  這是刻意的取捨，不是疏漏。
- 本 ADR 翻案 Duty 切片 plan §4，而該節要求「先有真實使用摩擦的證據」。
  **這次翻案的依據是 owner 產品裁決，不是使用摩擦證據**，據實標註。
- 候選出處（來自哪個官方基準）在選項 A ＋ 不接 reference 的組合下不存在，
  日後接 reference 時若要保留出處給員工看，`Duty` 型別沒有欄位放它，會需要 migration。

## 不在本 ADR 範圍

- (ii) 從穩定 Task 歸納 Duty。
- reference port 的實際建置（決定 7 只定了形狀，沒有授權施工）。
- 候選品質的評估方法與門檻。
