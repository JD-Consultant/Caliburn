# T14 小型工作分析品質資料集 v3

這是 **13 個全合成案例的評測素材與待人工校準 rubric**，不是模型通過紀錄。11 個 development、2 個 holdout_candidate；保留候選未用來調整 prompt，但編寫者已看過，不能稱盲測、獨立樣本或代表真實流量。v1 的九例未改 prompt；v2 新增兩例並小幅澄清 B1 背景取捨指引，當時只有離線契約驗證。v3 將真模型旅程發現的跨輪來源選擇問題縮小為兩個回歸素材；原旅程、候選對照與實際保存結果見 [T17 證據](../../../../../docs/plans/2026-09-29-target-rebuild/evidence/t17-course-administrator-journey.md)，不等於這十三例皆已跑模型或通過。

## 文件與責任

- [cases.json](cases.json)：情境輸入與前置草稿；只有各例的 `input` 可交給既有流程作測試資料。`id`／`split`／`risks` 是評測 metadata，不傳模型。
- [oracles.json](oracles.json)：**reviewer only**。有根據、必保留／不得斷言、A／B1／B2 各自正反例、hard failures 與允許的其他解法；絕不混進模型 context。
- 本文件：如何準備、觀察、評分及解讀。沿既有 pytest、角色 runner、Memory parent 與資料 owner，不增加模型評測平台或產品契約。
- [T14 evidence](../../../../../docs/plans/2026-09-29-target-rebuild/evidence/t14-job-analysis-quality.md)：本切片來源、實際檢查及未驗邊界；不另勾任務完成。

內容責任仍是 [工作分析指南](../../../../../docs/specs/2026-09-09-complete-work-analysis-guide.md)、[JD 寫作指南](../../../../../docs/specs/2026-09-09-jd-field-and-writing-guide.md)、[訪談校準](../../../../../docs/specs/2026-09-09-customized-jd-depth-and-interview-calibration.md)。oracle 的 `analysis`／`writing`／`interview` 數字對應這三份文件章節。本文不是第二份指南，也不以案例中的格式／件數定義所有職位。

## 案例各辨別什麼

| case id | 要辨別的失敗 | 不應被錯罰的行為 |
| --- | --- | --- |
| `correction_keeps_other_case` | 更正青禾卻連帶消除嵐月檢，或把月檢套到全部案件 | 不同任務分組；保留有意義條件即可 |
| `missing_subject_is_not_authority` | 流程沒有主語，卻讓助理核准／付款 | 中立追問本人哪一段；B 保留未知 |
| `ten_percent_is_not_whole_job` | 理解一成案例就自造其餘工作或宣告完整 | 先寫有據局部工作，再探索廣度 |
| `rare_responsibility_survives_routine_update` | 新增日常核單就忘掉少見但有效的通知責任 | 合理分組；不要求每次事件各建任務 |
| `manual_draft_is_not_employee_fact` | 人工公版及不相符引用被洗成事實／已對齊 | 根據明確更正直接修稿，不重問同一問題 |
| `unknown_scope_stays_unknown` | 印象升確定、未知變不存在、代班／願望升現職 | 保留未知、換問可答部分；B 可完成階段 |
| `daily_vs_month_end_recount_scope` | 每日現場複點泛化成全職位本人不複點，吞掉月底本人先複點 | 同任務分條件或分項；共用 collaborator 不必複製 |
| `shared_work_background_is_not_per_case_profile` | 全部情境只剩動作，漏掉已知角色／服務範圍；或每案強塞相同 profile | 適當情境承接共用背景，各案保留必要局部範圍即可 |
| `unconfirmed_background_is_not_a_profile_blank` | 用稱呼猜正式職稱、用工作交接猜匯報或單位 | 背景未知可保留，已知工作照常承接，不造必填 profile |
| `historical_fact_keeps_historical_source` | 本輪寫入的舊事實錯指 current_input，或猜正式序號 | 延後寫入仍回指歷史原話；多來源按支持範圍選擇 |
| `current_correction_keeps_other_sources` | 只更正主管卻把職稱／單位來源也改成本輪；新主管仍引舊說法 | 各欄分別處理，局部更正不污染其餘來源 |
| `known_work_does_not_need_forced_rewrite` | 為展示動作重複新增／逼問，或刪掉已確認期限 | 不改準確現稿；保留有據數字 |
| `one_off_event_does_not_change_regular_scope` | 顧問假設蓋過更正，一次清窗升為每日或被完全抹除 | 保留案例但不升成固定 JD 責任 |

第 7 例由 Owner 回報真 API 合成旅程的範圍風險轉成可重跑材料。原回報是訊息 2 月底「我先複點」，訊息 4 每日請現場複點；此處重寫為完整合成問答，不冒充 snapshot 的原始逐字匯出，也未判定該 snapshot 已出錯。

第 8、9 例是 G1 後續的一般化正反方向：課程行政的已知背景與設備窗口的未確認背景，不是重演庫存 Demo 字句。兩例都屬 development，oracle 仍是 reviewer only；只缺背景正文落點可判 partial，不能因不是逐字複述或原話仍可回查，就誤判捏造／來源破壞。反過來，引用存在也不免除保留有影響的角色與服務範圍。

## 準備與可見範圍：不要把 oracle 當角色輸入

1. 每案例／trial 使用獨立測試職務檔案及專用測試 DB schema，沿既有 integration fixture 的清理與資格；不接 production。沒有本輪 provider manifest 就只跑離線測試。
2. `formal_interview.sequence` 是合成歷史的定位，不是讓模型產生的 ID。用既有 interview／completion 測試機制建立前置狀態，保留說話者與問句；App 實際回傳的 identity／sequence 要建立對照，不能直接寫資料庫冒充成功訪談。
3. `seed_work_situations` 是刻意提供的舊情境 fixture，參數沿既有 create-work-situation 契約；以既有候選／發布 owner 建立前置狀態。它們不是待評模型已產生的好結果。新舊矛盾由原話與更正判讀，不能假設種子永遠正確。
4. `jd_draft` 是前置文件敘述，不是新增 API wire schema。沿現有 JD owner 建立有意義的項目／細節；標記 human 的項目用人工編輯路徑保留 pending。`source_sequences` 只描述它掛著哪些來源，**不保證內容受支持**；manual 案例特意掛了不支持核准權／KPI 的原話。
5. **A** 使用正式舊歷史、目前可見 map、現有 JD 按需讀取與 `current_input`。當次輸入仍 pending，不能預填正式序號；預期答案、判準、未發生的下一輪不能洩漏。不要把 `input` 整包 JSON 直接冒充 A runtime 的正式投影。
6. A 成功完成後，**B1** 沿 parent 所固定的合法 `(K,F]` 與必要前問、情境 map 開始；不提供 JD 稿、理解正文或 oracle。**B2** 由實際 B1 結果取得兩層 map、既有 diff 與按需原話；不替 B1 塞 oracle 的理想結果，也不讓 B2 修改情境。
7. 逐階段記錄：A 原回答＋實際 JD 候選／正式結果與來源；B1 情境正文／引用；B2 理解正文／情境關係及必要的 situation-only gap；parent 真正發布結果。只看最後答覆、Graph END 或 `complete` 不算已保存／發布。
8. 若只單獨評 A 或 B1／B2，明示 seed 前置狀態及未觀察階段。不得以單角色案例宣稱整條旅程成功。各角色有多種合法工具路徑，不鎖 write 數、唯一序列或每例固定幾輪。

現成接線範例在 `tests/integration/test_consultant_runner.py`、`test_memory_analysis_runners.py`、`test_memory_parent_roles.py`、`test_consultant_memory_http_journey.py`。這些既有 synthetic transport 測試是機制證據；換真 provider 必須另有 T16 manifest，不能把它們預寫的回應當自然品質成果。本切片沒有另寫 provider runner／retry／評測服務。

## 人工 rubric：先判有沒有根據，再判寫得好不好

`oracles.json` 的正反例是**工程代理依指南編寫的候選評分錨點**，不是人類專家已一致判定的 gold labels。後續由熟悉工作分析的人逐項檢查原話、實際產物及來源，必要時先修正有歧義的題目／版本，再評模型。

每個適用維度標 `pass`／`partial`／`fail`；該階段沒執行或沒有足夠證據標 `not_observed`，不可當 pass。留一段可定位的原話與實際輸出／狀態作理由，不只給分數。

| 維度 | pass 的可觀察證據 | fail 的典型證據 |
| --- | --- | --- |
| 事實與更正 | 新舊範圍區分正確，沒有把推測、顧問問題、人工稿當員工事實 | 未提供的職責、KPI／資格；採舊說法忽略明確更正 |
| 責任與條件 | 本人／團隊、日常／月底、特定案／全部、現在／歷史／願望不混淆 | 局部敘述看似正確，但共用 collaborator 或其他任務反向泛化 |
| 未知及訪談廣度 | 已知與待確認都可辨；局部清楚不冒充全職位完成 | 「印象中」變肯定，未提供變不存在；一成案例被宣稱完整 |
| 有效工作保留 | 重要低頻、其他案及既有責任有去處，未談不等於撤銷 | 新批補 A 刪 B；只保留最近或高頻工作 |
| 內容粒度／精簡 | 讀得出工作、對象、判斷、結果及必要邊界；可查下層細節 | 工具名當任務、通用職業句、逐案重複，或把整段原話重抄成理解 |
| 引用與效果 | 真實支持主張的來源位於正確 owner，實際產物與宣稱一致 | 只說「已改」；錯原話、錯案、引用洗白、B2 繞情境直接建正式訪談關係 |
| A 引導 | 回應當前資訊，對有影響缺口中立追問；已知可回查，答不出可保留 | 誘導答案、反覆逼猜、固定空格問卷、每輪硬改或永不敢寫 |
| B1／B2 分工 | B1 保留情境與合法原話；B2 提煉必要範圍，僅必要情境問題回交 | B1 看理解／B2 改情境，傳私人推理，為完成形式無限互審 |

**不得平均掉的錯誤：**無據的責任／標準、錯案或錯範圍更正、關鍵有效工作遺失、錯誤引用／資格、未知升確定，以及宣稱未實際保存／發布的效果。任何此類錯誤，案例即為 fail；文字流暢、欄位全滿、較少 tokens 或其他例高分不能抵銷。`oracles.hard_failures` 補各例精確反例。

`partial`：沒有上述重大錯誤，但省略一項必要辨識細節或引導仍不清；引用可回查不能自動補足理解正文必要邊界。純措辭風格差異只記 minor，允許語意等價答案。B `complete` 是本階段完成，並不承諾所有未知消失或整份 JD 已完善。

### 對照與復核

- **不要只獎勵追問：**無主語例應釐清；已充分說明的圖書館例不必重問。人工稿已明確被否認，不要求再問一次才准修。
- **不要只獎勵寫入：**一成案例可以先寫有據部分；準確無變動的草稿可保留。增刪工具數不是品質分。
- **不要只獎勵保留／刪除：**確定的低頻通知責任須保留；一次清窗可留情境而不升為每日職責；已確認18點期限應保留，未確認月周期不能補猜。
- **不要只看任務本身：**每日／月底例還看共用協作對象正文、任務關係說明、全職位邊界及其他引用處。同一人不同情境有不同分工，不是自動矛盾；語意範圍清楚才可合併。
- 至少抽取一個成功、一個失敗及有爭議案例，由第二位人工評者不看第一位 verdict 重評；保留分歧與依據，不讓模型自己宣告合格。尚無人工評者時結果標待評，不由本 rubric 作者冒充獨立人審。

## 後續 T16／T17 的最小記錄

先固定資料版本、input／oracle／實際指引／tool definition 指紋，再依有效授權另訂模型、推理設定、每例 trial 數、總 count／generation／retry／compact／時間／費用上限及停止條件。不可拿這份 fixture 當新付費授權。

每例保留 case id、trial、階段、資料及 prompt hash、App execution／revision 參考、公開對話及實際結果證據、各維度 verdict、hard failure、評者／分歧、工具錯誤、用量、成本與延遲。缺資料就標 unavailable；不保存／解讀 opaque reasoning，不輸出秘密。不新增另一個產品保存 owner。

固定同一版本比較基準／候選；保留每次失敗及 `not_observed`，不要只報多次中的最佳一次。11 個 development 可用於調整；2 個保留候選一旦用來調 prompt 就改列 development，補真正未參與調整的案例。十三例只能揭露定向風險，不足以估計普遍成功率、節時 ROI 或代表全部職業；T01–T18 原 gates 與最終 Goal 不縮減。

## 官方評測建議如何採用

查閱日 2026-09-30，先搜尋、再取得官方正文：

- OpenAI 建議用任務特定案例、明確成功條件及人類回饋校準評分；同時指出模型評分有偏好冗長等限制。本案將可確定契約交 pytest，內容交上述逐項人工 rubric，不在本輪啟用模型評分。[Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)
- Anthropic 建議分清執行軌跡與最終成果、設正反方向案例、檢查 transcript，避免用唯一工具序列排除合法方案；模型 grader 需與人工校準。本案用來源與實際產物交叉核對，接受多種合法分組／路徑。[Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- Anthropic 文件也強調明確、可量測、多面向成功條件與 edge cases；其較大量自動化評測建議不能被本資料集的少量候選錨點冒充達成。不聲稱官方替這些工作分析答案背書。[Define success criteria and build evaluations](https://platform.claude.com/docs/en/test-and-evaluate/develop-tests)

官方提供的是評測方法，不決定 Caliburn 的 JD 內容或員工事實；上述角色規則與反例取自本案責任指南。
