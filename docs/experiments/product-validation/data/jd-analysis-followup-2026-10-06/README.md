# 顧問增量整理：職責分組、跨欄更正與收尾

本次改善既有顧問的 JD 整理方法，不新增角色、資料表或審核流程。使用者已確認把方法寫入既有顧問 Prompt，不另加 Skill 載入機制。完整指引已在本機主題分支修改，22 次真模型對照完成，尚未更新運行中的 Docker 產品。[結果與判讀](results.md)分開列出初版、一次修正及反例回歸，不把全部執行成功當成全部品質通過。

## 問題如何發現

前批 [完整訪談結果](../full-interview-rag-2026-10-06/results.md)形成一項職責、七項任務，知識／技能仍為空。供應商退貨更正先進入任務與協作內容，卻直到員工在最後指出問題才同步到職務目的和職責範圍。年度盤點由員工在收尾後補充，不能算成顧問自己發現。

進一步核對原 `provider-trace.jsonl`：第五次員工輸入的模型回應 `resp_00933d1a394bb439016ac4c0aa0af087d0be37b155f0727122` 所在 Step 已讀取 `read_jd(map)`，結果包含完整的錯誤職務目的與職責範圍，之後卻只新增／修訂任務及協作對象，沒有修訂目的或職責。本批因此針對更正範圍的分析指引，不把原因歸咎於未載入資料。整批沒有 `move_jd_item` 呼叫；工具已存在並註冊，不能把「未選用」寫成能力缺失。這些是可觀察行為，不推測模型的內部思考。

## 方法及研究取捨

- [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)：工具說明交代用途、時機、參數及結果；分析方法留在角色指引。既有參數已能表達所需操作，因此不擴工具清單或 schema。
- [OpenAI evals](https://developers.openai.com/api/docs/guides/evaluation-best-practices)：用具體任務及反例比較實際效果，保留失敗，不以指引出現特定字句判定改善。
- [Anthropic tool engineering](https://www.anthropic.com/engineering/writing-tools-for-agents)：觀察最終成果、工具選擇、錯誤與耗用；允許多種有效讀取／修改路徑，不要求單一標準工具順序。
- [OPM 主要職責](https://support-class-usadata.opm.gov/hc/en-us/articles/51115834989843-Major-Duties-Statements-Overview)及既有[欄位指南](../../../../guides/2026-09-09-jd-field-and-writing-guide.md)：按有意義的工作目的／責任描述，不按案件數湊分組。本案不照搬其工時比例要求。

採用的有界修改是：資訊增加後重評分組；更正查相關任務、職責與目的；從確認的工作提煉共用知識／技能並連結任務；收尾時自然探索未涵蓋的周期與低頻工作。仍保留按需讀取、未知不猜、有效細節及引用核對規則。未採用固定分組數、自動語意補全、逐欄必填或額外全稿審核 Agent。

## 本次比較設計

初輪使用 [cases.json](cases.json) 的五個情境，另加 [holdout-cases.json](holdout-cases.json) 的資訊不足及非倉庫職位兩題，新舊各一次。基準是 `6ec52822ee475876ed20e57d818c8db298c42928` 的 A 與公版條件指引，候選是本次完整改寫；**兩組工具 schema 與說明均固定為相同的本機版本** ，不把工具說明差異混入 Prompt 對照。候選涵蓋輪廓、分析焦點、按需深入、JD 欄位、增量修訂、引用、候選保存及收尾，並非只加一項分組要求。

固定 Luna／high、16,384 輸出上限。正式 A Runner 使用真 PostgreSQL、原生 checkpoint、正式 JD 候選工具及完成交易；不讓模型只口頭承諾修改。十四份職務檔案在 `caliburn_docker_test` 的全新獨立 schema 建立，不動運行中的產品。種子訪談由 fixture 保存原話及固定的「已記錄」回覆，種子 JD 透過既有編輯 API 建立，任務引用指向種子原話；不把它們冒充先前真模型訪談。

公版工具啟用，但 HTTP 回傳固定為同一份合成參考，保留正式讀取／選用契約，不新增外部檢索變因。它只用於觀察公版使用時機與事實邊界，**本批不驗 embedding、重排序或真實職能標準涵蓋度** 。Memory 工具仍可用，但沒有啟動背景整理工作；不把本批當成 Memory 品質驗證。

收尾題只有答覆提出相關周期、年度、低頻或特殊期間的疑問時，才提供預先固定的年度工作，隨後提出暫停；觸發詞及後續原話在執行前凍結。先判讀實際問法是否中立，再判讀揭露後整理，不能只憑觸發詞命中算成功。本批兩組均轉向例行揀貨的深問，沒有觸發年度原話，因此沒有執行這份私人後續回答，也不能宣稱年度工作已被找出。

資料包含已累積的 JD 與可見訪談，不從空白重跑完整長旅程，也不把判準、私人後續回答或期待結果送進模型。模型只看產品組裝的原話、參考資料及工具回傳；評測者另持判準。舊新交錯執行，各有獨立檔案與候選，不互相沿用改稿。非倉庫題初輪作為保留例；觀察初輪後，它與能力題共同用於一次有界修正對照，故後續不再視為未見的保留例。最後再用單一工作及資訊不足兩題回歸。這是小型探索性對照，不宣稱具統計代表性。

判讀成品及來源，而不是只數呼叫：

| 面向 | 判讀重點 |
|---|---|
| 職責分組 | 不同責任能被辨認；同一目的且工作少的反例不強拆；既有任務身分、內容與引用保留。沒有固定名稱或組數標準。 |
| 跨欄更正 | 任務、職責及目的不再相互矛盾；未涉及的客戶退貨、精確值與責任保留。 |
| 知識／技能 | 名稱與說明能回到已確認方法，必要項目與任務建立關係；不推造資格或把任務清單機械改名。 |
| 收尾 | 未談的低頻面向有中立探索機會；已知未知不循環逼答；尊重暫停且不假稱所有工作已發現。 |
| 引用與耗用 | 指定引用是否支持目前內容、是否仍待核對；另外報讀取、修改、拒絕及輸入／輸出 token，不以少讀取冒充品質改善。 |

每個判準記完整、部分或未符合，附對話／工具／成品位置。研究上限、限流及未完成另列，不把停止記為品質失敗，也不補跑直到得到想要結果。這批是小型方法對照；不等同重新驗完整真人訪談或所有職位。

## 本機修改與離線驗證

分支 `consultant-jd-analysis`；原實驗資料及主線未提交變更保留。原生工作樹因 Windows 的歷史檔案路徑過長建立失敗，改以主題分支隔離，不刪除歷史證據。

修改位置：`apps/api/src/caliburn/agents/job_consultant/instructions.py`、`apps/api/src/caliburn/agents/job_consultant/reference_instructions.py`、`apps/api/src/caliburn/transport/model_tools/jd_writes.py`。沒有改參數、資料庫、Context 組裝、恢復流程或 Memory 角色。新指引只在新的角色 preparation 使用；既有已保存的角色模板不靠重試換提示。

以下在 repo root 執行，沒有模型外送、資料庫連線或金鑰讀取：

```powershell
apps/api/.venv/Scripts/python.exe -B -m pytest apps/api/tests/unit/test_role_prompt_contracts.py apps/api/tests/unit/test_consultant_tools.py apps/api/tests/unit/test_jd_write_wire.py apps/api/tests/unit/test_jd_item_movement_wire.py apps/api/tests/unit/test_jd_item_revision_wire.py apps/api/tests/contracts/test_jd_item_creation_wire.py apps/api/tests/contracts/test_jd_item_revision_schema.py apps/api/tests/contracts/test_jd_source_actions_wire.py -q -p no:cacheprovider --tb=short
apps/api/.venv/Scripts/python.exe -B -m ruff check apps/api/src/caliburn/agents/job_consultant/instructions.py apps/api/src/caliburn/transport/model_tools/jd_writes.py
git diff --check
```

初次結果：62 passed in 2.62s；Ruff、diff check 通過。這些驗證角色指引與正式工具能正常組裝、操作格式仍成立，不證明模型已改善分組或收尾。此次只改自然語言指引與工具描述，沒有以關鍵字斷言製造 TDD 行為 Red；品質需依上方對照判讀。

獨立唯讀審查核對兩份程式差異及工作分析指南，未發現新增要求與既有工具、按需讀取或來源契約衝突；不把此審查當成真模型效果或費用驗證。前批原件、判準及 trace 均未改寫。

最後檢查先發現顧問指引檔有混合換行，經 Ruff 格式化後再跑相同 62 案，結果為 62 passed in 1.72s；Ruff lint／format 及 diff check 通過。五題 JSON 可解析、案例鍵唯一、各任務選取的種子來源皆存在。四份受影響文件的 167 個本機檔案連結存在；此檢查不包含外部網址及頁內錨點，不冒稱完整連結驗證。

## 完整指引的本次驗證

最新人工確認的界線為新增最多 US$0.10／20 分鐘，已核准，與前批已結束的授權分開。`live-01/manifest.json` 與 `sources.zip` 在外送前凍結兩組 Prompt、共同工具、七題材料、合成公版、程式及依賴。`started.json` 只允許一次啟動；護欄在每次請求前查時間、同一份 token 計數與費用預留，失敗或上限即停止，不自動重跑。金鑰不輸出、不寫入資料包；opaque reasoning 只在去敏 trace 留雜湊。

執行入口為 [run_comparison.py](run_comparison.py)，`prepare` 不送模型、`execute` 才使用已確認授權。只在隔離實驗程序選用新舊指引，不修改正式執行中的設定。已保存的產品角色模板不被此比較換掉。

本次相關角色組裝、引用工具註冊及 JD 契約 91 案通過；沿用的研究護欄與凍結紀錄另 51 案通過。前者不是語意品質證據，後者不是產品恢復驗證。準備時發現歷史公版字串有 `.strip()`，讀基準的腳本已正確解析；護欄測試先受 Windows 沙盒及預設 CP950 影響，再以明確 UTF-8、工作區專用暫存目錄驗證，未修改原護欄或放寬判準。

獨立唯讀審查未發現確定的 P1／P2 衝突；指出「不重問未知」可能過廣，已限定為員工明確答不出且沒有新線索的同一問題，重要缺口仍可用具體例子或交接方式釐清。初輪後新增的兩段亦經唯讀審查，未發現與按需讀取、保留來源或不硬填欄位衝突。這是靜態審查，不代替真模型判讀。

## 本批結案與原件

| 階段 | 改動與目的 | 完成的正式 Turn | 費用護欄占用估算 |
|---|---|---:|---:|
| [live-01](live-01/result.json) | 完整初版與舊指引，七題各一配對 | 14 | US$0.030637010 |
| [followup-01](followup-01/result.json) | 澄清「沒有新事實」不代表已整理完、任務分項不等於職責分組；能力與客服兩題各一配對 | 4 | US$0.014475330 |
| [regression-01](regression-01/result.json) | 不再改 Prompt；回歸單一工作與資訊不足兩題 | 4 | US$0.005332320 |
| 合計 | 同一批 US$0.10／20 分鐘界線，沒有重新起算 | 22 | US$0.050444660 |

後兩段使用原始開始時間加 1,200 秒的截止點，各只取得剩餘時間及金額；接續關係保存在相應 manifest。最後四個 Turn 在回歸階段 131 秒護欄內完成，沒有再開付費批次。所有原始 trace、manifest、凍結程式與成品保留，另以 [analyze.py](analyze.py) 產生 [measurements.json](measurements.json)，人工判讀及剩餘範圍見 [results.md](results.md)。

此次沒有 commit、push、merge 或 Docker 切換。隔離資料庫 schema 保留供回查；未啟停其他人的產品程序。

### 最終離線驗證

以下命令在 repo root 執行。`$taskTemp` 是本次新建且先驗證位於 `S:\caliburn\.research-tmp\` 下的 GUID 路徑，不重用既有測試目錄；因 Windows 沙盒暫存權限，測試以核准的權限執行，沒有模型外送。

```powershell
apps/api/.venv/Scripts/python.exe -X utf8 -B -m pytest apps/api/tests/unit/test_role_prompt_contracts.py apps/api/tests/unit/test_consultant_tools.py apps/api/tests/unit/test_reference_tool_registration.py apps/api/tests/unit/test_jd_write_wire.py apps/api/tests/unit/test_jd_item_movement_wire.py apps/api/tests/unit/test_jd_item_revision_wire.py apps/api/tests/contracts/test_jd_item_creation_wire.py apps/api/tests/contracts/test_jd_item_revision_schema.py apps/api/tests/contracts/test_jd_source_actions_wire.py docs/experiments/product-validation/data/early-interview-recall-2026-10-05/test_study_guard.py docs/experiments/product-validation/data/early-interview-recall-2026-10-05/test_study_manifest.py -q -p no:cacheprovider --tb=short --basetemp $taskTemp
apps/api/.venv/Scripts/python.exe -X utf8 -B -m ruff check apps/api/src/caliburn/agents/job_consultant/instructions.py apps/api/src/caliburn/agents/job_consultant/reference_instructions.py apps/api/src/caliburn/transport/model_tools/jd_writes.py docs/experiments/product-validation/data/jd-analysis-followup-2026-10-06/run_comparison.py docs/experiments/product-validation/data/jd-analysis-followup-2026-10-06/analyze.py
apps/api/.venv/Scripts/python.exe -X utf8 -B -m ruff format --check apps/api/src/caliburn/agents/job_consultant/instructions.py apps/api/src/caliburn/agents/job_consultant/reference_instructions.py apps/api/src/caliburn/transport/model_tools/jd_writes.py docs/experiments/product-validation/data/jd-analysis-followup-2026-10-06/run_comparison.py docs/experiments/product-validation/data/jd-analysis-followup-2026-10-06/analyze.py
git diff --check
```

結果為 142 passed in 2.52s（產品接線／契約 91、研究護欄／凍結紀錄 51），五份 Python 檔案 Ruff lint／format 通過，diff check 通過。沒有以語意關鍵字測試宣稱真模型通過，也沒有重跑與本次自然語言修改無關的全套產品旅程。

六份本題文件共 214 個本機檔案連結均存在；未驗外部網址及頁內錨點。現行 A／公版指引檔案的 SHA-256 均與 followup-01、regression-01 凍結內容相同。資料包文字的 API key 格式掃描沒有命中；這是特定格式檢查，不宣稱任意秘密皆已偵測。
