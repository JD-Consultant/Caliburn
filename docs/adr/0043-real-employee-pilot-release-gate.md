# 0043. 真實員工試用是第一版發布門檻

- 狀態：**Accepted**（owner 於 2026-08-03 確認）
- 日期：2026-08-03
- 範圍：何時可把本機 Web release candidate 稱為可供員工使用的第一版成品
- 延伸：[0040](0040-professional-consultant-engine-and-r1-validation-contract.md)、[0042](0042-hybrid-job-discovery-and-ttop-formation.md)
- 研究：[真實員工試用 release gate 研究](../specs/2026-08-03-real-employee-pilot-release-gate-research.md)

## 脈絡

原路線圖同時把 R8 稱為「可用成品」、把實際員工試用列入 R8 exit gate，又把 R9 安排為 R8 之後的真實試用，造成
發布語意互相矛盾。自動測試、合成案例、高擬真 transcript、LLM grader 與專家離線審閱可以驗證已知規則與內容候選，
但不能證明目標員工是否能在接近實際的條件下完成訪談、辨認並修正 AI 錯誤，以及得到忠實反映本人工作的 JD 草稿。

## 決定

1. R8 交付的是可供受控試用的**本機 Web 發布候選版**；技術與模型 gate 通過，只授權進入 pilot，不足以宣稱第一版已是
   可供員工使用的成品。
2. R9 的小規模真實員工試用是第一版發布的必要 gate。核心參與者必須是第一版的預期操作者，並以本人目前實際從事的工作
   完成端到端旅程；主管、HR、顧問或 SME 可補充內容審閱，但不能取代 incumbent 的實際操作。
3. 模擬 persona、產品團隊自測、歷史或高擬真 transcript、合成 eval、LLM grader 與非操作者專家審閱都只能作前置或補充證據，
   不得被計入「已通過真實員工試用」。
4. Pilot 必須觀察至少五個面向：端到端 outcome、互動理解、T–T–O–P／KSA 內容品質、安全與員工 agency、provenance／
   文件真相。滿意度只能作輔助訊號，不能抵銷 false-success、重要缺漏／捏造、資料損毀、不可恢復或來源斷裂。
5. 試用前須固定 release scope、招募條件、rubric、severity 與 pass／rework／invalid decision rule；試用後保留 protocol、
   consent／data plan、版本與 session evidence、內容驗證、issue register、release decision 與去識別化 regression candidates。
6. 樣本數、情境覆蓋、數值門檻、零容忍 blocker、獨立 SME 與最終 release authority 另由 owner 在 pilot 執行計畫核准，
   不由本 ADR 代定。沒有預先定義門檻或可追溯證據時不得判定通過。
7. Gate 未通過時回到受影響的 R1–R8 階段修正並重測；在 gate 通過前，產品文件與里程碑不得稱其為「員工可用成品」。
8. 本決策不建立企業正式核准、多人口簽核或 SaaS 能力。通過 gate 仍只代表經真實員工驗證的 employee-confirmed JD draft
   產品，不代表組織級效度或主管／HR 核准。

## 後果

R8 與 technical cutover 可以產生完整 release candidate，供受控 pilot 使用；R9 通過後才到達第一個員工驗證成品里程碑。
工程 eval 與真人試用成為互補的兩層安全網，且真人發現的 failure pattern 要去識別後回灌 regression suite。

代價是首發時間必須包含招募、同意、資料處理、觀察、內容審閱與重測；若 scope、參與者或證據無效，即使沒有觀察到錯誤也
不能放行。這個 gate 也不保證所有職務、產業或組織都已被驗證；第一版宣稱必須受 pilot coverage 限制。
