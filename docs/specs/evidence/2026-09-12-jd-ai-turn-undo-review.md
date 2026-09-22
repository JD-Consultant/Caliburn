# 整輪 JD 撤回與改動呈現：研究及文件審查

- 日期：2026-09-12；Topic：JD-R002；範圍：HR-02／CV-01，未實作產品。
- 責任稿：[整輪撤回](../2026-09-12-jd-ai-turn-undo-design.md)、[改動呈現](../2026-09-12-jd-change-visibility-design.md)、[需求 §12–13](../2026-09-12-jd-relational-editing-requirements.md)。

## 1. 證據與裁決

Owner 重開最近一步快捷，選整輪 AI 的全部 JD 修改；不隨之撤回 Memory、案例與原話。root 核 AWS idempotency、PG16 row locks、Claude SDK filesystem-only rewind 與 OpenAI Code review 正文；`jd_command_semantics_review` 另核 Claude checkpoint／Desktop／VS Code／Artifacts。root 與 reviewer 均核 W3C 顏色指引。適用版本、狀態與商業產品參照限制在責任稿，不把 SDK 檔案恢复推成 JD 資料庫契約。

`jd_storage_audit` 唯讀核現有 RunRow／service 的持久 run ID、HumanMessage／binding、jd_store 的缺 run 欄及 close／resume；發現 model-view notice.start 不是本輪起點、暫態 jd_bindings 會清除，不能拿來做永久整輪分組。root 採一個可信 ai_run_id 欄及全體 committed parent 鏈，不加另一份起终 snapshot 或 run 表。reviewer 初步提單操作較少增量，但 Owner 隨後已選整輪，root 沒把較簡單建議當已採用。

## 2. 獨立唯讀審查

| Reviewer／範圍 | 結果 |
|---|---|
| `jd_storage_audit`：undo 初稿、既有 closure／resume 接點 | PASS；全部 run committed 與完整 parent 集合及 head identity 能拒絕尾段誤撤；receipt-first 可回已成功結果；manual 新版本與原 AI 回執分開，Memory／原話不倒退。現行 completed／cancelled 不可 resume，不為此修改 resume |
| `jd_command_semantics_review`：visibility 全稿、需求 §12–13 | PASS；直接保存與查看分開、唯一可編稿、全部結構差異／改回事件保留、較晚人工／非連續／未知結果分清；A 仍是推薦候選，不是 Owner 已選 |
| `jd_storage_audit`：schema §4.3／6.5、工具通知、history supersede、autosave／editor、visibility 的歸屬與淨差異 | 窄複核 PASS；可信 run 納入意圖／同交易保存、receipt-first、新 manual 還原一致；非連續只列自身事件、較晚手改不混入；無新模型工具或另一份 authority |

靜態核對 **11 份文件、138 個本地連結、48 個 anchors，0 問題**；只檢入口本輪新增狀態，不挾帶既有無關編輯。差異空白檢查通過。上述 PASS 是文件與既有程式唯讀核對，不是產品 DB、瀏覽器、模型或員工驗收。

合成互動另用獨立 headless Edge 檢查：展開／收合、欄位內改前、整輪 JD 撤回示意後目前敘述／成果／分組恢復、歷史三項仍保留；736／320 外框宽度（內框 704／288）及 light／dark 無水平溢出，0 JavaScript errors。已查看截圖。首啟動因 sandbox spawn EPERM 未啟動瀏覽器；同一唯讀本機檢查經執行權限後成功，沒有改產品來迎合環境。這只證明示意互動，不能當正式保存／來源／Memory 驗收；host 的可選 Tweak 控制未在此獨立 renderer 內驗收。

## 3. 完成界線

HR-02 是已選有界功能；CV-01 的直接改稿／可見差異已定，具體呈現待讨论。AU／CV 情境尚未執行。示意使用合成 JD，未傳送真實訪談、呼叫產品 provider 或連資料庫；互動示意不能當產品可用。整體 G4 Needs revision／ADR0075 Proposed／production0060 保持。
