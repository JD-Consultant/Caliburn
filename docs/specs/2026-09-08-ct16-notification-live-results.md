# CT16：通知指引局部真模型複測

2026-09-08 · `Q019-MEM-CADENCE-01`／`CT15-R07` · **局部複測完成並封存，品質G8仍OPEN。**

後續：[CT17短更正校準與複測](2026-09-08-ct17-correction-persistence-calibration.md)已完成；新更正經B保存，但漏存更正的重述仍未補存，G8保持OPEN。本頁原實验／失敗不改寫。

結論：實質補充有真通知；原容量阻擋與B2步數不足已用隔離參數對照定位。接續後發布rev3，先前晚期資訊已整理。但「10日前→5日前」短更正及其後重述只反映在回答，沒有進Memory；**不能宣稱通知已穩定或完整訪談驗收通過**。

證據：[完整input/output／方法及hash](evidence/2026-09-08-ct16-notification-live.json) · [本次可見逐字稿](evidence/2026-09-08-ct16-notification-live.transcript.md)。本頁是結論入口，不重貼全部Memory與研究沿革。

## 本輪邊界與驗證方法

Owner：「同意，優化，並且測試。」承接[已核准指引、職務分析研究與官方來源](2026-09-08-ct16-consolidation-notification-diagnosis.md)，不重開 Memory 架構。唯一問題：通知能否在實質訪談進展後適時送出並由既有背景鏈承接，而不是每輪例行通知。

- 保存點 `b5c3f488`，只在 CT15 已關閉長訪談的專用 PostgreSQL 複本續談。保留原 Conversation／opaque continuity／詳記／Memory 及來源地址，不回填 CT15 原失敗，不以手工假通知觸發背景。
- Luna／medium，新帳本最初24次／US$0.10保守預留，之後Owner核准提高至0.20，仍24次（下方保留變更時序）。主顧問／B2沿用原實驗8192輸出，**B1仍4096**；compaction12000，不改產品預設。字數備援仍關閉，避免把它當成提示成功。保留SDK正常重試，每次嘗試均計入。這是自設的小額本輪護欄，不是Owner的產品限制。
- 第一情境：新的工作細節，觀察正常回答、真實通知／收據、B1/B2 與新 processed cursor；同時檢查原本 T15/T16 待整理內容是否納入。
- 第二情境：明確短更正，觀察更新或既有 live repair／背景路徑，不要求為同一更正強制做兩遍。
- 第三情境：沒有新增資訊的重述，觀察是否無需新整理；若尚有早先實質資料待處理，不把補整理誤判成冗餘。
- 每次完整閱讀回答、詳記、候選、正文與導覽；機械引用／游標檢查與語意審閱分開，不以關鍵字命中或離線假HTTP冒充完整品質通過。主顧問有近期 Context，不能當成純 Memory 回查成功。
- 假設推翻或出現新的產品取捨，回到局部診斷／Owner討論；不添加timer、分類器、schema、模型或修改正式產品。到護欄停止並保留原失敗，不無限追加。

官方提示方法依據是 [OpenAI Function calling](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions) 的明確用途／何時使用與不使用、不要填程式已知參數，以及 [Anthropic Define tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools#best-practices-for-tool-definitions)。本次工作進展判準是已核准的領域映射，不冒稱廠商內建同一套判準。費用估算沿用[官方價格表](https://developers.openai.com/api/docs/pricing)，非帳單保證。

## 結果

第一情境已完成兩次HTTP200/completed，主顧問真通知及收據成立，但背景在B1呼叫前阻擋。唯讀重播確認是必要前文容量，不是通知丟失／schema／API錯誤：T17顧問可見文字2669字，下一分窗需要此前文，超過context_chars=1500；T18顧問文字3156字同樣可能超限。原資料與rev2保留。

### 同題發現：抽取容量初值阻擋長回述

來源：[安全封閉結果R01](../../../../docs/specs/2026-09-06-analysis-only-agent-safe-turn-closure-results.md#6-獨立審核與修復)說明為避免省略短答的必要問句，完整必要前文超額明確拒絕；[B1切片結果](2026-09-06-analysis-only-agent-extraction-results.md)將6000／1500明示為可調初值，不是大廠共識最佳數字。本例確認保護按既定設計運作，但初值不足以正常處理長訪談收尾。

只讀原失敗資料、沿原planner對照：6000／3000仍拒絕；12000／6000及18000／9000皆可用一個完整窗口覆蓋9060字新來源＋595字前文。**選較小可行的12000／6000做參數對照**，不聲稱這是全域最佳值；不用裁切原話、刪除失敗回合、另產生摘要或添加新演算法。接在既有B1公開容量參數，整體native Context管理、輸出與工具預算不變。

後續實驗另複製同一CT15基準，第一失敗資料庫不改；仍使用同一24次／US$0.10帳本，不增加額度。此參數只在診斷runner中覆寫，**不寫入產品預設**。容量對照不等於提示A/B：兩個分支皆使用已校準提示，模型輸出有隨機性；只有planner失敗可無模型精確重現。原始記錄將另存evidence，不在本頁重貼長逐字稿。

### 容量對照與中斷續測（沿革；非產品預設）

- #3–4：同一補充，正常通知／回答成立。#5：B1成功，包含紙箱標籤不足、補序號及破損照片、月報全部售後範圍／10日前／案件編號去重／匯款與收款確認區別；產品仍是石橋吸塵器，未知物流核定者沒有擅自填答案。
- #6–11：B2讀取及編輯，尚未發布。工具有兩次不同失敗：`- -`把diff前綴與Markdown項目符號混用導致Context不匹配；另一筆附上完整patch envelope而非工具所需單檔diff body。各有錯誤回傳，原失敗patch沒有寫入；不把此兩錯藏進成功率。
- #12之前被**實驗HTTP費用預留**攔住，實際usage估US$0.02148609／11次，不是API拒絕／消耗US$0.10。Owner核准US$0.20、仍24次。沿B2公開`resume()`接續，B1不用重跑。這是診斷手動續接，不聲稱dispatcher會自動解除blocked。
- #12–13：讀導覽／修改導覽之後，framework的`ModelCallLimitMiddleware`在第9次B2模型呼叫前拒絕；已用8步，沒有final，所以不可發布。全帳本13次／US$0.02414095。只在此既有B2工作的診斷續測將上限8→12，不清零既有count、不重建新job、不改Tool12或全帳本24／0.20。其他正常turn仍使用產品原本B2預設。

**官方與程式核對：**[LangChain Model call limit](https://docs.langchain.com/oss/python/langchain/middleware/built-in#model-call-limit)明定thread計數跨invoke保存、上限可配置；本機`langchain/agents/middleware/model_call_limit.py`的`before_model`比較保存count與配置，`after_model`遞增。這解釋模型收到工具錯誤後的修正也占用額度，但**不支持12是官方最佳數字**。採較多步是本例隔離診斷，產品值仍待有效性／成本一起決定。checkpoint續接依[LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)，實際是否保留B1、暫存內容與計數另由本次trace驗證，不能只憑框架名稱下結論。

**獨立審查邊界：**容量分支從原CT15重新複製，沒有測第一分支blocked B1在新容量下恢復；`diagnose`只對產品資料唯讀，仍會寫實驗記錄；B1成功不等於整併發布或processed cursor已推進。三點均保留，不改寫成完整鏈通過。

## 最終結果與尚未修好的部分

| 檢查 | 實際結果 | 不能延伸宣稱 |
|---|---|---|
| 實質补充通知 | 原容量與容量對照均由模型呼叫空參數通知，收到收據後正常回答 | 不是未校準／已校準同input的嚴格A/B，也不是所有情境必通知 |
| 背景完整鏈 | #14可選預檢、#15正常final後發布rev3，B1 checkpoint未改；B2總10次model／9次tool（3讀取、5patch、1預檢）。processed cursor到本複本T19，當時pending source為空 | 需要診斷容量／步數與明示續接；不能宣稱原預設正常，也不是自動從blocked恢復 |
| 工作內容保真 | 新正文保留原型號差異、退款權限、FAQ、帶教等內容；新增石橋證據核對與月報去重／匯款待確認。正文與導覽均引用新詳記 | 沒有消除CT15既有「技師爭議未知→無經驗」與導覽標題不一致等問題；沒有用關鍵字命中充當完整語意驗收 |
| 短更正（#16） | 完成回答，明說每月5日前；**0 tool，沒有C、沒有B通知，Memory仍10日前** | reasoning／近期context記得新話，不等於長期Memory更新 |
| 無新增重述（#17） | 完成回答，仍說5日前；0 tool，Memory仍10日。兩輪共有440字元可見問答待整理 | 此前已有未處理更正，所以不是「已全部整理後，純重述不應通知」的乾淨負例 |
| 問答與引用（0模型） | 原36則＋新增6則，42則員工／AI可見問答全等；4份正文／導覽詳記地址，source及context頁面文字逐段對canonical全等 | 引用可讀不等於模型會自動沿引用搜尋；本次沒另跑Memory-only reader |

本輪付費 **17次HTTP200／completed，usage估US$0.03597248**；未耗盡24次／0.20上限，因結果足以定位問題而主動停止。所有錯誤保留；HTTP皆completed也不代表工具／workflow全成功。#16的output4587中包含4448 reasoning tokens，不能只用可見139 tokens評估輸出需求或費用。本輪不改模型、provider或reasoning設定。

離線接線回歸：`uv run --frozen --offline pytest -q --tb=short tests/test_consolidation_request.py tests/test_scheduling.py tests/test_api.py tests/test_extraction.py`：**66 passed／0 skipped，16.97s**；1項既有Starlette／AnyIO deprecation warning。假HTTP測的是接線，不證明通知語意通過。真測與原文核對使用專用PG複本，不觸碰原CT15庫或production。CJK控制台顯示不影響以UTF-8封存的逐字稿。

### 下一個唯一gate：短更正的保留路由（待Owner審閱，不自動施工）

短更正時，`repair_memory`與`request_memory_consolidation`都實際在模型tools中，guide還有10日前；原始員工訊息含5日前。可排除本例「工具未提供」或「更正未送到模型」。可見回答說更正不影響工作內容／責任理解，但**不能據此猜隱藏推理**。

**待驗推論：**目前工具說「明確更正或確認若改變既有工作理解…值得通知」，可能讓具體期限更正與「共同工作模式是否改變」混淆。建議仍只校準既有提示：期限、頻率、案例條件等目前資料的實質更正也需保留，即使共同模式沒變；沿現有B通知或C成功修補處理，不重複做同一更正。這不是另設更正表單、詞彙偵測器或新Agent。先用原失敗證據作基準，再做局部對照；不能直接宣稱一句提示一定能保證保存。官方方法來源仍是上方OpenAI／Anthropic清楚工具用途、使用與不使用時機的指引，不再重開同一廣泛研究。

原容量初值與B2步數的產品配置取捨、patch格式錯誤、字數備援／短尾生命週期，保留為同題已定位的後續項；**本輪沒有將12000／6000、12步設為產品新預設**，也沒有擅自啟用每輪整理或timer。這些參數對照是證據，不是G6／G7新施工授權。

Closure：帳本已關閉；隔離結果與引用已保存。主訪談能完成本次三種輸入，但長期Memory未採用短更正，因此「穩定完成完整職位訪談」仍未驗收通過。下一步先審閱本地最小通知修正，不追加整套長訪談或憑名稱改框架。

最終獨立唯讀審查無需修正的實質finding。再次核對：`pending_source=null`只屬#15發布瞬間；封存時是440字未整理，不得混用。Markdown本地引用可解析、UTF-8證據及17次帳本計量通過核對；`src/`與`tests/`相對`b5c3f488`無diff，`git diff --check`通過。
