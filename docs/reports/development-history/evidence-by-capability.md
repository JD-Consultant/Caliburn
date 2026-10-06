# 按研究能力找 Caliburn 的歷史證據

本頁供團隊按研究方法找材料：文獻判讀、領域分析、控制變因、評分校準與程式診斷。早期分類依據見[系所／教授公開資料研究](../../history.md#source-518e00bdc0f3f08d2efa)；時間線見[演進入口](README.md)，結果以各原件為準。

盤點基準：2026-10-02，`target-rebuild@edba0685` 與可達 Git 歷史。本輪只讀證據、整理引用，沒有重新執行實驗。下列「結果」均指原紀錄；不同時期的模型、環境、資料與產品要求不能直接合併比較。

以下九組歷史材料保留已修正、未執行及證據較弱的短例；近期接續另列於頁末。

## 文獻判讀、領域分析與研究倫理

### 1. 論文測量方法不等於適合上線的產品介入（8/1）

- **材料經過：**早期研究曾建議在員工候選清單混入假造能力項目，據接受情況判斷回答品質；後來撤回，理由包括測量與介入混淆、缺乏有效門檻、污染回答及信任風險。同時把「task anchoring 已驗證」修正為「原論文建議、此處尚無實證」。
- **去哪裡查：**[效度研究 §3.2，判準3-B第2、4點](../../research/work-analysis/2026-08-01-opks-raw-validity-and-ai-regulation.md)的更正／撤回框（第408–425行）。這是前次 OPKS 演進節點尚未展開的研究判讀材料。
- **可說／不可說：**能呈現閱讀證據、接受審查與撤回過度推論的過程；不能說替代方法已被本產品驗證。此處只引用修正紀錄，不承接同檔全部歷史法規摘要或舊架構規則，也不能把歷史研究代理的判斷自動算成團隊成員的獨立發現。

### 2. 比較十份雇主文件後，決定不再堆欄位（9/9）

- **材料經過：**為判斷 JD 是否過於簡略，比較機構職位描述、公司職族及招聘頁。辨認主導／協助／代理、特定工作對象與條件；結論是應追問實際職責，而非把不同文件所有欄位加總成模板，也不抄外部工作當員工事實。
- **去哪裡查：**[十份文件比較 §1–2、§4–6](../../research/work-analysis/2026-09-09-employer-job-document-comparison.md)；[跨國證據 §4–6](../../research/work-analysis/2026-09-09-job-analysis-international-evidence.md)保留共同點、差異及舊研究更正。
- **可說／不可說：**是目的性取樣、來源適用性分析與做減法的材料；不是具代表性的跨國調查，也未證明這樣寫 JD 就能提升招聘或工作績效。原比較建議當時不新增固定欄位，沒有新的員工資訊就不改稿。

### 3. 先宣告資料，再雙向檢查成品有沒有漏寫或擴權（9/9）

- **材料經過：**建立15筆明示虛構職位情境，先查每筆資訊在 JD 的去處，再從 JD 查回依據。審查發現「服務端部署」被擴大成整體發布責任、兩種逾時處理混淆等，修正版保留責任及條件差異。
- **去哪裡查：**[樣稿依據 §2–5、§8、§10](../../guides/2026-09-09-jd-sample-basis-and-review.md)及[成品樣稿](../../guides/2026-09-09-frontend-engineer-jd-sample.md)。來源、成品與審查分開可讀。
- **可說／不可說：**可展示如何把「完整、精簡、不虛構」轉成可檢查的內容關係；是樣稿及審閱紀錄，不是真人訪談、領域專家盲評或 LLM 自動生成通過。文中「人工語意核對」不作團隊成員或特定人類專家參與的證明，實際分工仍須依證據核對。

## 量測可信度、控制變因與反證

### 4. 先發現評分程式錯誤，而不是把失敗都算給模型（7/18）

- **材料經過：**當時18個 trial、27次推論的未完成批次，記錄9個提交、8個輸出／本地schema無效、1個路由污染；另查到線上評分與離線重評傳入的失敗原因不一致。批次標為 `harness_invalid`，沒有正式 precision／recall／pass³ 結論，先停止付費呼叫。
- **去哪裡查：**[true-live 診斷 §23](../../history.md#source-adde91251a1a00660e92)；修正提交 `bc24a25c` 的 `apps/api/tests/test_interview_vnext_turn_eval_runner.py`，`test_grading_golden_paths_are_online_offline_byte_equal` 與 `test_tampered_bundle_fails_integrity_or_grader_drift`。
- **可說／不可說：**可展示量測系統也要驗證、三種結果路徑比對、重評不改原件及竄改偵測。這裡核對了當時報告與測試程式，沒有重跑；不能把整批失敗當模型失敗率，也不能沿用當時嚴格路由政策當現在產品需求。

### 5. 把資訊刪減與表示方式拆開，避免把答案塞給模型（7/26–27）

- **材料經過：**原 Hybrid 設計同時改表示與省略對話，無法歸因；人工 claim 又含受測模型應判斷的責任／更正等欄位。修訂保留全文、加入 Raw＋Spans 比較，並移除答案型欄位，分辨重貼原句與額外結構的作用。
- **去哪裡查：**[P0 §2–3.2與結案說明](../../experiments/2026-07-26-r1-p0-context-representation/README.md)；[組裝測試](../../experiments/2026-07-26-r1-p0-context-representation/test_assemble_context.py)的 `test_hybrid_differs_from_raw_plus_spans_only_by_claim_table`；[案例驗證測試](../../experiments/2026-07-26-r1-p0-context-representation/test_validate_cases.py)的 `test_rejects_answer_label_fields_in_claim_table`。
- **可說／不可說：**是控制變因、資料洩漏檢查與否證設計材料。**零 trial 執行**；最後依外部研究與YAGNI結案，不能說實驗證明結構化無效、兩組持平或品質較佳。程式與六份凍結案例留存，不等於有結果。

### 6. 校準答案也會錯；校準通過也不代表正式評分可靠（7/27）

- **材料經過：**只要求澄清、沒有提出 Task 的候選，原 gold 把來源支持設為 `pass`，後改成無可評 claim 的 `unknown`。後續 R1a 正反序評分完整，仍將違反凍結整併期望的三個方案全部判為通過。
- **去哪裡查：**[實作紀錄「Grader calibration 修訂紀錄」](../../history.md#source-7661202d166acae889f4)；[TI-R1-04 原案例與 expected](../../experiments/2026-07-27-r1-task-discovery/cases/TI-R1-04.json)；[R1a結果 §2–3](../../experiments/2026-07-27-r1-task-discovery/r1a-results.md#2-model-grader-結果不能直接當結論)。Git `bf52f713:apps/api/evals/professional_consultant_r1/live_batch.py` 的 `CALIBRATION_GOLD` 只校準兩個維度，可檢查它沒有涵蓋所有正式判準。
- **可說／不可說：**深化原 R1a 節點，呈現 gold 審查、評分覆蓋範圍與假通過。正式漏判是原紀錄由 Codex 依凍結期望複核，不是人類SME驗收；缺少原 capture 時也不能冒稱本次重新確認每個模型輸出。

## 早期資料與程式診斷

### 7. 保留失敗產物供診斷，但不讓 CLI 假報成功（5/18–19）

- **材料經過：**前身 PDF 解析專案改動資料模型後，另有 validator 同步修正；CLI 再補上「可以輸出 JSON 供檢查，但驗證失敗仍以非零退出碼結束」，區分檔案產生與有效資料交付。
- **去哪裡查：**Git `7592c2f0`（模型）、`a2066ce7`（validator）、`4d7e4ec5`（CLI）；原路徑為 `src/jd_pdf_to_json/core/models.py`、`validators/schema.py`、`cli.py`。[現存CLI](../../../apps/pdf-to-json/src/jd_pdf_to_json/cli.py)的 `validation_failed`／`typer.Exit(1)` 可閱讀；精確歷史仍以提交為準。
- **可說／不可說：**這是較弱的補充短例，可說明契約演進與成功／失敗控制流。已核對修正程式，沒有取得該次CLI專用回歸測試及執行log，不能包裝成完整實驗，也不由這三筆提交推定中間每次執行結果。

### 8. 修掉重複 key 後，仍須解決「位置不是物件身分」（6/21–22）

- **材料經過：**多職類任務撞號造成重複 React key，先修分組與編號；之後拖曳仍有目標定位、重排不更新等問題。再用隨項目移動並保存的 `_uid`／`_tid` 定位，而非 `task:0:1` 這類位置，分開物件身分與目前索引。
- **去哪裡查：**[D27 e2e bug log第2、4、5項](../../history.md#source-82781f19e3677da73e3b)；提交 `e9c97dc3` → `4a4ece94`，後者 `frontend/src/components/interview/v3/JobDocTable.tsx` 的 sortable IDs／`resolve`，以及 `frontend/src/lib/ocsDoc.ts` 的 `ensureIds`。
- **可說／不可說：**可展示為何局部修補沒有處理完資料身分、UI狀態與保存的關係。當時日誌寫使用者確認正確，但只有文字紀錄與改動可查，沒有本次瀏覽器重驗；日誌標6/21、提交日期6/22，兩者分開保留。

### 9. 測試通過，真實資料卻仍掉值（6/23）

- **材料經過：**D29先記indexer與後端測試通過，使用者對照原始JSON才發現：`job_categories` 本是多組代碼／名稱，normalizer漏名稱，後續投影又與另一個單值職類名稱欄混淆。修正跨 normalizer、payload、service及schema，已遺失的存量資料須重新匯入，不能只修UI。
- **去哪裡查：**[D29 I1／V1及「使用者比對原始 JSON 抓到」修正段](../../history.md#source-82781f19e3677da73e3b)；Git `cb175732:tests/test_service_profile.py` 的 `test_get_profile_projects_metadata`、`test_get_profile_tolerates_missing_codes`，及同提交 `tests/test_builder_profile.py`。原反例含職類名稱空值與多組分類。
- **可說／不可說：**可呈現跨層資料追蹤、基數與名稱語意、真實資料校驗和測試盲點；前面的50／141測試通過數字是**修正前**紀錄，不是修正後驗收。此處核對報告及回歸程式，尚不宣稱當時重新匯入完成或本次重新測試。

## 近期接續：同一方法用在新的反例

| 方法 | 2026-10-04 至 10-06 的接續材料 | 判讀界線 |
|---|---|---|
| 控制變因與歸因 | [Memory 選讀、內容單位與維護](memory-and-context.md#2026-10-04-至-10-05從保存得到進一步比較選讀與使用) | 相同 Memory 的讀取比較與改寫 Memory 的比較分開；兩批後續對話成本方向相反 |
| 缺失定位與條件式比較 | [公版候選召回與主要工作涵蓋](retrieval.md#2026-10-04-至-10-05找主要職位參考分開診斷各階段) | 已知來源／面向只是部分標註；同批探索與敏感度分析不構成新 holdout 或全庫 Recall |
| 反例追蹤與平台契約核對 | [刪除後的遲到保存](engineering-and-verification.md#9-取消已提交仍須等真正保存結束) | 框架 Task 退出不保證實際保存結束；真 PostgreSQL 反例與部署版本分開 |

這些接續補充原有方法的使用情境；量化結果與原件路由集中在各主題，避免將同一批實驗重複計成多項成果。

## 後續取材方式

每例先回讀原章節、程式與結果檔；團隊分工另核對各成員提出、修改、實作或判讀的部分。

Git 定位形式為 `提交:當時路徑`，可在 repo 用 `git show <提交>:<當時路徑>` 唯讀查看，不需要切分支或恢復舊程式。例如：

```powershell
git show cb175732:tests/test_service_profile.py
git show bc24a25c:apps/api/tests/test_interview_vnext_turn_eval_runner.py
```

對外引用程式片段須標明固定提交；部分模型 capture 尚未入庫，連結可查不表示全部材料已備份。[程式演進](code-evolution.md)可補查資料流、責任變更與反例測試；只有程式差異時，不補寫實驗改善幅度。

## 本輪核對範圍

2026-10-02：新增兩份文件、調整三個入口；五份文件的相對連結／章節定位及差異格式檢查通過。九組材料均回讀原章節；列出的歷史提交已確認可讀，並核對相關程式／測試片段。

該次為材料與引用核對，未重跑產品／模型實驗；歷史研究中的論文與法律主張也未因此全部重驗。
