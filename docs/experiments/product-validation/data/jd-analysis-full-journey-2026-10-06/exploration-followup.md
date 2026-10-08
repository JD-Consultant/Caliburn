# 工作條件探索：漏問診斷與指引校準

2026-10-07。使用者已確認先改善既有顧問 Prompt 的缺口判斷，不新增角色、資料表、固定問卷或收尾 gate。本機指引已修訂；後續完成[22 次局部真模型對照與接續](../jd-condition-exploration-2026-10-07/results.md)，尚未證明三項漏問已解決，未更新運行中的 Docker。前批訪談已結案；新批使用另行確認的 US$0.10／20 分鐘界線，不沿用前批額度。

## 1. 問題在哪裡

[完整旅程結果](results.md)及 [turn-20-result.json](turn-20-result.json) 保留 17 輪有效訪談。冷藏環境、錯儲位與旺季風險未被員工揭露，也未寫入 JD；這是探索缺口，不是已知原話被 Memory 遺漏。

| 面向 | 可觀察行為 | 尚未取得的資訊 |
|---|---|---|
| 工作環境 | 正式對話 23、25 問搬運設備及堆高機適用作業；員工提供證照要求與 15 公斤 | 是否進出不同工作環境、哪些條件改變做法 |
| 常見差錯 | 對話 15、17 取得正常上架及掃碼確認品項 | 錯儲位如何發現、本人處理到哪裡 |
| 工作量變化 | 對話 19、21 探索其他周期／偶爾工作，帶出年度盤點 | 月底或促銷前工作量變化與上架不及 |

原指引已提到環境、旺季及容易出錯的情況，但未明確連接到轉向／收尾時的缺口判斷。這支持先校準指引，不足以單獨證明某一句就是全部成因。前批舊指引曾問出這三個面向，見[原旅程](../full-interview-rag-2026-10-06/results.md)；兩批適應性對話不同，不合算為受控改善率。

## 2. 本次採用的範圍

- 正常流程已清楚，不等於相關工作條件都已探索；轉向或收尾前，選最相關、會改變責任或重要要求的缺口追問。
- 分清已問但答不出與尚未探索。前者無新線索不重問；一項未知不代表其他面向也都未知。尊重員工停止。
- 公版查漏不限於新增職責，也可提供環境、異常及負荷的線索；線索不能直接成為事實。
- 條件及異常通常補進既有任務；有獨立責任才另立任務，不硬拆成三項工作。

權威方法寫在[訪談校準指南](../../../../guides/2026-09-09-customized-jd-depth-and-interview-calibration.md#正常流程清楚仍須辨認尚未探索的條件)。程式只改 `apps/api/src/caliburn/agents/job_consultant/instructions.py` 與 `reference_instructions.py` 的自然語言指引；模型、工具參數、Context、Memory、資料保存與恢復流程不變。不加入本次私人答案，也不接入另案的候選議程設計。

研究借鑑：

- [O*NET Content Model](https://www.onetcenter.org/content.html)：工作情境與活動分開描述，包括環境、錯誤後果及時間壓力。本案只借分析面向，不導入其完整問卷。
- [GOV.UK 深度訪談](https://www.gov.uk/service-manual/user-research/using-in-depth-interviews)：主題導覽、開放中立問題、實例及自然追問，不僵化依清單提問。
- [OpenAI 模型最佳化](https://developers.openai.com/api/docs/guides/model-optimization#write-effective-prompts)：明確描述預期效果並用 eval 迭代。這不是指引寫入後效果必然改善的保證，也不改用其頁面推薦的其他模型。

## 3. 對照設計

沿用正式 Runner 與現有隔離評測工具。舊組取本資料包 `freeze/sources.zip` 的指引，新組取本次兩份指引；工具、可見原話、起始 JD、Memory、模型 Luna／high 及輸出上限固定相同。先做局部配對，不重跑已完成的整份訪談。付費及時間界線須另行確認，這份案例表不構成外送授權。

| 案例 | 起始狀況 | 應觀察的效果 |
|---|---|---|
| 環境 | 已知倉庫流程及搬運；場所差異未說 | 中立探索工作場所；揭露後保留條件，不猜溫度、頻率或裝備 |
| 差錯 | 已知掃碼確認品項與正常上架 | 探索常見錯誤及處理分工；不宣稱掃碼會核驗儲位 |
| 負荷 | 已知盤點周期，工作量變化未說 | 探索忙碌時段及影響；不把忙季另立任務、不猜優先順序 |
| 非倉庫的異常 | 帳務人員已說正常核對流程，例外未說 | 能探索差錯或例外，不套搬運、冷藏等詞 |
| 非倉庫的負荷 | 軟體維護工作已說日常處理，尖峰未說 | 能探索需求量／時限變化，不假定旺季存在 |
| 已確認無差異 | 員工已確認場所固定、工作量穩定，沒有新線索 | 沿用答案，不為湊面向重問 |
| 答不出 | 一項重要細節已換問法仍不清楚，其他面向未探索 | 不重問同一未知；能選不同且相關的面向，不代填答案 |
| 明確停止 | 員工要求本次先結束 | 尊重停止，不強制補完面向，不宣稱全部細節已確認 |

外送前固定每案可見原話、私人後續回答與判準。顧問只收到可見資訊；判準與待揭露事實由評估者另持，只有中立問題確實涵蓋對應面向時才回答，不靠關鍵字觸發。每次只回答當前問題，避免員工替顧問一次補齊三項。後續新批的[首輪結果](../jd-condition-exploration-2026-10-07/first-question-review.md)與[追加接續](../jd-condition-exploration-2026-10-07/continuation-plan.md)分開記錄，不用後者改寫前者。

每案分開記錄「是否中立探索」「揭露後分析／JD／來源是否正確」「是否保留未受影響的細節」「是否尊重未知及停止」。允許多種合理問題和工具路徑；不要求問出指定句子、不將工具呼叫或欄位非空算成功。另記追問量、讀取及 token，不用更多問題冒充品質改善。局部案例若通過，再視實際需要驗完整訪談的自然轉向與收尾。

## 4. 本輪驗證層級

只做受影響的角色準備、工具註冊及既有契約測試，以及格式／文件連結檢查。它們確認接線仍成立，不證明顧問已問出三項條件。沒有新增關鍵字斷言或假 TDD；本次自然語言效果以後續真模型對照判讀。

在 repo root 執行；`$conditionTestTemp` 是 `S:\caliburn\.research-tmp` 下當次新建的 GUID 目錄，不重用其他批次暫存。沒有模型外送、資料庫連線或金鑰讀取。

```powershell
$conditionTestTemp = Join-Path 'S:\caliburn\.research-tmp' ('condition-exploration-' + [guid]::NewGuid().ToString('N'))
apps/api/.venv/Scripts/python.exe -X utf8 -B -m pytest apps/api/tests/unit/test_role_prompt_contracts.py apps/api/tests/unit/test_consultant_tools.py apps/api/tests/unit/test_reference_tool_registration.py apps/api/tests/unit/test_jd_write_wire.py apps/api/tests/unit/test_jd_item_movement_wire.py apps/api/tests/unit/test_jd_item_revision_wire.py apps/api/tests/contracts/test_jd_item_creation_wire.py apps/api/tests/contracts/test_jd_item_revision_schema.py apps/api/tests/contracts/test_jd_source_actions_wire.py apps/api/tests/unit/test_job_analysis_quality_fixtures.py -q -p no:cacheprovider --tb=short --basetemp $conditionTestTemp
apps/api/.venv/Scripts/python.exe -X utf8 -B -m ruff check apps/api/src/caliburn/agents/job_consultant/instructions.py apps/api/src/caliburn/agents/job_consultant/reference_instructions.py
apps/api/.venv/Scripts/python.exe -X utf8 -B -m ruff format --check apps/api/src/caliburn/agents/job_consultant/instructions.py apps/api/src/caliburn/agents/job_consultant/reference_instructions.py
git diff --check
```

初次為 117 passed、3 failed：失敗來自既有測試要求保留「容易出錯」「頻率與旺季」「環境、體力、證照」的特定措辭。確認沒有要撤銷這些分析面向後，保留原表述再補上缺口判斷，不刪除或放寬測試。這個文字檢查失敗不是顧問行為的 Red，也不當成品質對照。

修訂後 120 passed in 1.88s；兩份指引 Ruff lint／format 通過。四份受影響文件的 174 個本機檔案連結存在，未驗外部網址及頁內錨點。沒有跑與本次自然語言修改無關的全套 PostgreSQL／瀏覽器／真模型旅程。

為後續比較記錄兩份指引的 SHA-256；舊件從原凍結包讀取，新件為本輪本機內容。凍結包、manifest、原始 trace 與前批結果均未修改。

| 指引檔 | 舊件 SHA-256 | 新件 SHA-256 |
|---|---|---|
| `instructions.py` | `69d3ba309d0a559104a102b0b40f3924941ccaba47fa3c589e9ae8cd0202d734` | `1d01fcaa1e70c948b12e25755caf383d297866f640b884c6ebf609aefd4b09e4` |
| `reference_instructions.py` | `5e392fa41c1ff40f902a578bd11246c1494e09f6bab99669f41a0bf784983ced` | `ce478f74b30e79a509ef3cebf07b92ce802c8b9757c7bd0b9d96001acd790770` |

本輪沒有 commit、push、merge 或 Docker 切換。既有已保存的角色指引不因本機改字而換版；後續對照必須在隔離的新角色準備中固定選用兩版，不拿舊職務檔案直接重試來冒充新指引。
