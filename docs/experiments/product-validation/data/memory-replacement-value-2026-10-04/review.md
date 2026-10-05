# 比較方法與執行檢查

## 外送前的檢查

此比較只使用合成訪談匯出，不改正式資料庫或產品程式。新研究腳本放在本資料包，沿用前批的提案收集、原生同格接續及估算用量機制；資料包以外的未提交修改不在本次工作範圍。

1. 正式 `read_recent_interviews` 使用 `(covered, frontier]`，起點是員工時加一則前問。固定來源的 covered=104、frontier=105，因此近期是顧問發話 105。另以 covered=103 的反例驗證前問 103 加員工 104、顧問 105；這個假定界線只用於離線測試。
2. 兩組可回查同樣的正式原話 1–105；讀取 106 被拒。近期投影只變起始訪談範圍及 Memory 導覽，不修改原文、共同 JD 或題目，不追加舊 native items。
3. `offline-02` 的更正題：完整組有 105 則原話，近期組只有序號 105 這一則；App 參考資料分別為 28,051／12,566 字元。共同 JD 與題目逐項相同。這是字元與組裝檢查，不是實際 token 或品質結果。
4. 共同研究指引改為「提供可用材料，完整原文可按需回查」，不再說兩組起始都已有完整原話。產品顧問方法與凍結評分準則不變，沒有固定讀取順序或 Memory 偏好。
5. 執行從 manifest 取得本批費用、時間與先前占用，避免沿用前批 US$0.20／30 分鐘。SDK 自動重試關閉；reserve 先於外送，未知費用保留預留，provider 失敗停止。

本研究使用獨立資料目錄與非主線的既有工作分支，沒有另建 worktree、agent 框架或資料表。研究紀錄與凍結原件在本資料包保存，不為遵循施工形式另造一份進度權威，也沒有 commit／push／merge。

## 離線反例與格式檢查

新增近期投影與較低費用界線的反例，先以原附加價值組裝／固定護欄執行：**4 failed、3 passed**。四個失敗分別是近期仍包含全部 105 則、員工起點沒有依範圍保留前問、無效覆蓋界線沒有拒絕，以及 manifest 的較低費用沒有阻擋外送。不是匯入或環境錯誤。

修正後，連同前批全部研究測試，**16 passed，10.95 秒**；Ruff 通過。1200 秒的較低時間界線測例是參數化後補上的覆蓋，並非全部測試都先經 Red。原有的早期讀取測例一開始即通過，因為本批未修改該能力。

命令（本次使用既有 venv，避免 uv cache 權限問題）：

```powershell
apps/api/.venv/Scripts/python.exe -X utf8 -B -m pytest docs/experiments/product-validation/data/memory-replacement-value-2026-10-04/test_replacement.py docs/experiments/product-validation/data/memory-added-value-2026-10-04/test_support.py docs/experiments/product-validation/data/memory-added-value-2026-10-04/test_runner.py -q -p no:cacheprovider --basetemp=S:/caliburn/.research-tmp/replacement-green-02
```

測試的暫存目錄只用於離線研究，不連 provider。Windows sandbox 暫存 ACL 問題以已授權的本機離線執行處理，沒有重新啟動服務或清除既有資料；重跑必須換新的 basetemp。

這 16 項只檢查研究素材與腳本，不是後端全套測試，也不驗分析品質、真 DB 交易或新輪前摘要。真模型產物與語意判讀另列。

## 原件保存

前批 `support.py` 在護欄參數化前已保存為其 `live-01/executed-support.py`，SHA256：`8387874887d6bfb171982dab7304c0b9350d4fca7b97080f27204276d1d049e1`，與前批 manifest 相符。前批原執行碼另有 `executed-experiment.py`，兩批結果不得混算。

本批 `live-01` 保存 manifest、實際共同指引、兩組工具及各格 initial、trace、提案與總用量；`executed-protocol.md` 保存外送前的方法全文。後續說明不追改凍結的 manifest 或 trace。用量指標可由原件重算，語意判讀則須另對照原話與正文。

## 獨立腳本審查

另一位工程代理已唯讀核對近期範圍、共同 JD／題目、原話讀取界線、原生／未來資料排除、manifest 新界線及前批原件；未發現 Critical 或 Important。審查期間也核對新 live manifest 與授權一致，並以純記憶體核對費用、時間、累計、首次失敗及未知 usage 行為。這不是新增 provider 請求或資料庫測試。

兩項非阻塞建議保留，不在凍結執行中追改程式：

- **共同研究指引的字串替換較脆弱：**現版確實已替換，沒有謊稱近期組已預載完整原話；日後共用文字變更，宜加入替換成功檢查。若替換失敗會誤導模型對已讀資料的判斷。
- **限流等待採固定估量：**沿用 25,000 輸入及等待 helper 的 4,096 輸出估量，而本批輸出上限為 8,192；可能影響等待或速率風險，不繞過費用與時間護欄。本批無限流失敗，仍把等待與生成分開，不以總耗時推論服務端性能。

本批十份來源在執行後、結果文件更新前核對相符。`live-01/source-files/` 保存九份來源原件，協定以 `executed-protocol.md` 保存；檢查後續文件時使用這份原件，不要求會更新的 README 永遠與外送前相同。

腳本審查沒有替代語意核對或評估統計效力；真 provider 的價格／取消保證、正式產品及 DB 不在其判斷範圍。本批沒有切換、合併或提交動作，也不需要進行開發分支合併流程。

## 結案複核

- 以新的 `.research-tmp/replacement-green-03` 重跑同一組離線測試，**16 passed，11.02 秒**；未連模型或資料庫。
- 十份保存來源的 SHA256、實際指引及兩組工具的指紋均與 manifest 相符；trace 雜湊維持不變。
- 四對實際起始請求的 JD 與題目相同：完整組有 105 則歷史訪談，近期組只有序號 105。每格均為兩則 user 輸入，各次重複與準備檔一致。
- 八格衍生用量、修改後欄位及累計占用均可由結果原件重算；結案更新後，四份說明文件的 12 個本機連結均存在。
- 語意判讀另經獨立工程代理複核，主結論維持；已補明冷藏規則仍存在於原稿，只是同任務的欄位未對齊。詳見[語意判讀第五節](semantic-review.md)。

結果說明已精簡重複敘述並統一為繁體中文；執行協定、原始資料、程式原件、trace 與判準未修改。

## 比較後的閱讀策略調整與 GPT-6 指引審核

本節記錄比較結束後的修改，不回寫 `live-01` 的方法或結果。使用者確認：Memory 正文足以支持本次判斷，就使用它；有具體缺口才往下查。產品規則已寫入 [Memory 閱讀與停止條件](../../../../specs/2026-09-27-memory-read-and-source-navigation-contract.md#a-顧問的閱讀與停止條件)，並同步至 [A 顧問指引](../../../../../apps/api/src/caliburn/agents/job_consultant/instructions.py)。不變更工具、模型、Context 組裝或來源權限。

### 發現與修正

前次 trace 顯示模型讀過理解與情境後，仍大量回查原話。提示中「編輯前先定位支持內容的員工發話」與「Memory 可作來源」並存，又沒有明確的停止條件，可能促使模型把查原話當成必要程序。這是可指出的指令衝突與行為關聯，不宣稱已證明模型選擇的唯一原因。

| 審核面向 | 原有問題 | 本次處理 |
|---|---|---|
| 來源與引用 | 原話優先的表述容易遮蔽 Memory 的直接來源資格 | 原話是原始事實紀錄；已讀的理解或情境正文可直接支持 JD，不必另加整條來源鏈 |
| 工具使用與停止 | 有向下回查能力，卻未定義何時已足夠 | 理解足夠就停；具體缺口才讀情境，再視缺口回查訪談，不展開全部引用 |
| 新資訊與未知 | 省讀取若被解讀成只信 Memory，可能漏掉更正或補猜未知 | 本次輸入與近期原話可直接支持 JD；更正按範圍判斷，未知仍保留，必要時查詢或追問 |
| JD 核對 | 停止深入不應被當成來源自動對齊 | 保留人工修改、換版與衝突重評；讀取充分不等於確認引用完成 |

審核依 [GPT-6 官方提示指南](https://developers.openai.com/api/docs/guides/latest-model#prompting-best-practices)檢查指令一致性、角色界線與表達清楚程度，並依 [Function calling 指南](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)明示何時使用、何時不再使用工具。GPT-6 指南以 Astra 的觀察提出家族起點，仍要求在所選模型與工作上評估；本產品維持 Luna／high，未將 Astra 的行為視為 Luna 保證，也未搬入編碼代理的擴權或委派指令。

### 本次驗證與待驗證效果

以既有角色組裝、顧問工具分派及 Memory 讀取契約測試檢查接線，**43 passed，2.33 秒**。Ruff 檢查、格式檢查與修改差異檢查通過。本次沒有增加比對提示字串的品質測試；這些結果只支持新指引能送入既有角色組裝、工具契約未受本次修改影響，不證明模型已停止重複回查。

```powershell
apps/api/.venv/Scripts/python.exe -X utf8 -B -m pytest apps/api/tests/unit/test_role_prompt_contracts.py apps/api/tests/unit/test_consultant_tools.py apps/api/tests/contracts/test_memory_read_tool_dispatch.py -q -p no:cacheprovider --basetemp=S:/caliburn/.research-tmp/memory-reading-prompt-01
apps/api/.venv/Scripts/python.exe -m ruff check apps/api/src/caliburn/agents/job_consultant/instructions.py
apps/api/.venv/Scripts/python.exe -m ruff format --check apps/api/src/caliburn/agents/job_consultant/instructions.py
```

後續有界對照應保持同一素材、題目、Luna／high、工具與原判準，只改此閱讀策略，另存指引與指紋。除完整保留精確數值、責任、例外與未知外，還須檢查：理解足夠時能否停止並引用理解、缺少細節時是否只讀相關情境、缺口或矛盾時是否回查適當原話，以及新輸入能否直接支持修訂。回查更少或工具成功不能代替答案與改稿品質；同一任務的相關欄位是否一致仍另作語意判讀。

本次未送新的付費請求，未測 Luna 的自然遵循或成本改善，也未修改既有比較的結果。真模型對照須另確認有效費用與時間界線。

獨立唯讀複核未發現阻塞問題；逐項核對停止條件、未知與更正、來源直接引用、JD 核對及 B1／B2 權限，未提出 Critical／Important／Minor 修正。複核沒有執行模型或取代上述回歸。兩份 Markdown 文件的 30 個本機連結均存在；連結檢查只確認目標檔案，未逐一驗證既有錨點。工作基準為 `13c0663a7d42e2e73b5c2ef45d20faa9e1b1fa11` 加本節所述未提交修改；本次顧問指引檔 SHA256 為 `a4865cc5ca115a6d4dd42f95e188a8758e80f3ccb856d5fde385fe4aa001de8b`。

### 後續同材料驗證

使用者另授權的新舊指引比較已獨立結案，見[閱讀停止條件對照](../memory-reading-policy-2026-10-04/results.md)。只改顧問指引、保持材料及工具後，新組四格交付，舊組三格交付，累計 input 少 60.1%；跨欄一致性仍有反例。這是新的八格結果，不回寫本資料包原始執行或把兩批合為同一次比較。
