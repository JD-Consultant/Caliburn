# 執行與驗證紀錄

## 修改前基準

修改前的主 Prompt 與公版 Prompt 已和前批 `live-01/sources.zip` 逐位元核對：

- 主 Prompt SHA-256：`1d01fcaa1e70c948b12e25755caf383d297866f640b884c6ebf609aefd4b09e4`。
- 公版 Prompt SHA-256：`ce478f74b30e79a509ef3cebf07b92ce802c8b9757c7bd0b9d96001acd790770`。

舊版已有探索條件，不把比較寫成「有規則 vs 沒規則」。本次集中三種判準，刪去重複轉題／收尾段落；Context、工具、保存及 Memory 未改。既有職責分組、知識技能、數值與引用方法保留。

## 準備時的環境權限

第一次 `prepare` 在 Windows sandbox 無法開啟 Docker named pipe，`docker inspect` 被拒絕。當時只建立 `live-01/sources.zip`，沒有 manifest、資料庫 schema 或模型外送。這是環境權限，不是模型或產品行為的失敗；保留該未啟動包，不覆寫。

後續準備改用 `live-02`，只取得已確認的隔離測試容器身分與連線，新增唯一 schema，不啟停既有服務。外送必須由完整 manifest 及單次 admission 控制。容器 healthy、綁定 127.0.0.1:55441；新 schema 為 `jd_prompt_e28e803547614502bd214403bc355366`，16 個獨立檔案已準備。

## 已完成的離線檢查

`apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/unit/test_role_prompt_contracts.py -q --basetemp .research-tmp/pytest-jd-question-selection`：19 passed in 1.71s。pytest cache 權限產生一個警告，未影響測例執行。這些是角色接線、權限及文字契約回歸，不是新選問品質已通過，也不是語意 TDD。

主／公版 Prompt 及薄接線腳本的 Ruff 格式與 lint 通過。之後再依實際外送前版本核對；不新增「包含某句話」來冒充改善行為。自然語言品質以固定原話、舊／新實際回覆及 JD 判讀。

既有研究護欄及凍結測試：第一次因 sandbox 暫存權限未能進入測例，改用新隔離目錄並取得權限後，51 passed in 1.57s。未放寬測試或修改護欄。凍結包 334 筆檔案雜湊、16 個起始身分、兩版工具相同、Luna／high 及 US$0.10／1,200 秒均核對；私人完整回答未出現在可見案例或公版 fixture。

## 外送及續談

`live-02` 完成 16 次首段；原計時由 `2026-10-06T17:59:41.751624+00:00` 開始。工程代理依實際問題和原回答規則選擇七段接續，先保存 `continuation-decisions-02.json`，再用 `continue_comparison.py live-02 live-03 continuation-decisions-02.json` 執行。只有舊版軟體案問到目標面向，其餘按已知範圍回答未知；已收尾的案例不強行補送。

`live-03` 七段完成後，舊版帳務案新問到差錯及決定權，依 `continuation-decisions-03.json` 續一段，使用 `continue_comparison.py live-03 live-04 continuation-decisions-03.json`。這是預定最多三段內的接續，不移植別組答案或重建檔案。新版未問到私人目標面向，因此沒有揭露後的私人內容改稿測試。

三個執行程序均 exit 0；生成回應 96 次、輸入計數 104 次，沒有失敗、限流、壓縮、未決預留或護欄停止。含階段間判讀 1,047.01 秒、估算占用 US$0.073042255。第三段完成即結案，不使用剩餘額度試其他版本。各階段只沿原截止與剩餘費用，不重置 20 分鐘或 US$0.10。

## 核對與不採用決定

離線 `verify_evidence.py` 核對三包各 334／339／343 筆檔案雜湊、16＋7＋1 個完成紀錄、同檔案接續、既有任務身分、首段私人完整回答及案例 ID 未預載、原始 usage 加總與費用／截止。另逐一讀回實際回覆、軟體及帳務揭露後的 JD 與來源，結果見 `first-turn-review.md` 及 `results.md`。原件不因後續判讀而回寫。

一次性 trace 投影的前兩次查詢因包含不帶 `arm`／`path` 的控制事件而產生 `KeyError`，當時沒有更動 trace、沒有外送。改為先依端點及事件種類篩選後，完成首段 16 筆實際 input 與用量核對；此本機分析錯誤不列為模型、產品或付費外送失敗。

本批不支持新版穩定改善。僅用局部 `apply_patch` 撤回本輪主／公版 Prompt 重排，不用 `git checkout` 或回到 HEAD。還原後兩份文件與本輪修改前凍結包逐位元一致，SHA-256 仍為本頁開頭兩值。先前已確認的工作稿、其他人的變更及校準指南三種判準均保留；被測新版在 `sources.zip` 保持完整。

本次是自然語言行為假設對照，不是新增程式功能的 Red–Green–Refactor；不以測試含有特定字串宣稱選問改善。沒有新資料表、角色、問卷、程序 gate 或產品 Context 變更。隔離 schema 保留，未刪資料或啟停 Docker，未提交或推送。

## 結案回歸

還原後執行 `apps/api/.venv/Scripts/python.exe -X utf8 -B -m pytest apps/api/tests/unit/test_role_prompt_contracts.py -q -p no:cacheprovider --basetemp .research-tmp/pytest-jd-question-selection-restored`：19 passed in 1.44s。主／公版 Prompt 與三份實驗腳本共五檔的 `ruff format --check`、`ruff check` 均通過。

最後重算三階段 evidence 通過，輸入 1,502,916、輸出 69,864、推理 52,719、cached input 1,392,583，與結果表一致。八份相關 Markdown 的 220 個相對檔案連結均有目標；此檢查不驗外部網址或所有歷史章節錨點。`git diff --check` 無錯誤，只有 repository 的 LF／CRLF 提醒。回歸與文件檢查不代表選問品質通過。

另由獨立上下文作一次唯讀複核，檢查預定方法、接續選擇、實際問句、揭露後成品、來源、用量及還原基準，未找到需修正的證據錯誤。確認三個倉庫條件仍未取得、其他有價值的問題不改算目標成功、新增來源不代表舊引用已對齊。此複核不是新樣本或真人盲評；未審新議程候選、其他未提交變更、實際帳單及運行環境，也沒有外送或資料庫操作。
