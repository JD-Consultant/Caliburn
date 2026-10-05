# 公版參考工具與確認資料

狀態：**獨立工具與保存切片完成**。當輪使用者授權「可以做好 tool 等等，但先不接到模型」，並要求依架構文件施工；以下保留該輪成果。後續已授權的可選角色接線另見[接線計畫](2026-10-05-occupation-reference-agent-integration.md)。沿用含已授權 RAG 變更的 `jd-app-docker` 工作目錄，保留其他未提交工作，不另複製一份未提交基底；未 commit／push。

## 最新接續：工具契約 hardening

使用者授權「優化審核 debug」，接續修正[契約審核](evidence/2026-10-05-occupation-reference-tools/tool-contract-audit.md)三項反例：完整選用集合的替換說明、各工具的合法錯誤下一步、新寫入只回固定小型成功結果。完整 state 仍按需讀；舊 captured request 保留原成功格式，不重寫 native output。獨立審查另外找到重複唯讀工具可通過完整 bundle 檢查，已補反例與修正。

搜尋仍沿現行完整目錄；三層概覽是另案比較。沒有重啟共用服務、改環境檔、套正式 migration 或付費模型外送。契約、回歸、獨立審查與原件見[hardening 驗證](evidence/2026-10-05-occupation-reference-tools/hardening-verification.md)。下方數據保留各輪驗證時間，不能互換為本輪驗收。

接續文件維護依[決策流程](../decision-process.md)及[開發規範](../implementation/development-standard.md)，以[架構討論規範](../architecture-discussion-standard.md#6-作為持續維護的架構與開發文件)的分層閱讀原則核對受影響範圍。架構入口、系統責任與資料流、保存／執行／部署、工具契約、驗證及報告入口已同步；新請求、舊請求與已保存結果分別說明，搜尋概覽仍標為待比較。Accepted ADR 與實驗原件不改寫；[連結、錨點與文件版本檢查](evidence/2026-10-05-occupation-reference-tools/architecture-maintenance-check.json)保留本輪結果。

使用者接續要求各層整體敘述更清楚，已整理 22 份主要文件：入口說明各層責任與閱讀路徑，專題拆開資料資格、提交與恢復，架構報告按使用流程說明合作關係，檢索比較按變因列出原件。原標題、程式區塊、既有連結及數據保留；純文件核對另見[敘述維護檢查](evidence/2026-10-05-occupation-reference-tools/architecture-prose-maintenance-check.json)，不替代上面的工具與模型驗證。

接續更新 19 份 README、架構短入口與 RAG 總覽：拆開產品功能、操作與驗證範圍，依 ADR0079／0080 修正過時的產品及公版接線狀態。主 README 引用既有產品循環與部署圖；RAG 的舊 profile／task 資料流收合為歷史，現行公版參考流程另行說明。原有命令、JSON 範例及解析欄位語意保留，並保留並行測試更新的實驗索引列。純文件檢查見[README 維護紀錄](evidence/2026-10-05-occupation-reference-tools/readme-maintenance-check.json)；本輪未操作服務或外送模型資料。

## 前輪接續：Memory 唯讀與專題報告

新增 `read_excluded_work({})` 及 `ExcludedWorkReadTools`，只讀現有獨立排除範圍。沿既有 Memory binding 取得持久 F／stage，不複製資料、不讓模型提供上界，後輪更正不回流舊批次。原顧問與新讀取共用正式 state 查詢。schema 沿現有生成機制，保持未註冊 A／B1／B2；[責任契約](../specs/2026-10-04-public-reference-completion-design.md#memory-的排除範圍唯讀入口未接模型)。

新工具 25 項 unit、新讀取 11 項 PostgreSQL；最終完整 unit/contracts **1,313 passed**、受影響 PostgreSQL **55 passed**，Ruff／Mypy／生成檢查與 build 通過。獨立審查發現保存錯誤映射遺漏，已以 Red／Green 修復。完整命令及未驗範圍見[唯讀驗證紀錄](evidence/2026-10-05-occupation-reference-tools/memory-read-verification.md)。

既存檢索研究已整理至[專題報告 §6.3／B.14](../reports/project-report/report.md#b14-主要職位參考的廣蒐與精搜)，保留原始數據、樣本及敏感度，不將隔離工程驗證當成顧問收尾品質。

## 最新調整：只保存否認範圍

使用者確認回答來源不用，目的是避免重問，否認內容也不放 Memory。state 改成 `selected_reference_ids + excluded_work`，一般確認／回答來源工具已移除，以 `update_excluded_work(add, remove)` 保存或解除具體否認範圍。最新責任見[目前契約](../specs/2026-10-04-public-reference-completion-design.md#工具與保存契約未接模型)。

已完成模型／serializer／未發布 migration、workflow、schema／生成物與工具的對應調整；保留原候選／重播／回復方式，不加進顧問或 Memory。**1288 項 unit/contracts、37 項真 PostgreSQL 回歸通過**，Ruff／Mypy 通過；獨立審查無實質 finding。完整資料見[新驗證紀錄](evidence/2026-10-05-occupation-reference-tools/excluded-work-verification.md)。

下方保留第一版的施工紀錄與驗證數字，**confirmations／回答來源部分已被本次修正取代**，不是目前介面。原實驗輸出不回寫。

## 前版責任與驗收（沿革）

產品語意以[參考 state 設計](../specs/2026-10-04-public-reference-completion-design.md#公版參考-state先選主要參考再按需核對)為準；模組依[程式組織](../implementation/code-organization.md)、保存依[持久化](../architecture/persistence.md)、模型參數依[契約策略](../contract-strategy.md)。

- `adapters/occupation_references.py`：獨立 RAG HTTP 契約與錯誤，借用 caller 的 HTTP client。
- `features/occupation_references`：兩項業務 state、每 Turn 候選、不可變操作結果、重播及回復 fencing；只操作自己的資料表。
- `workflows/occupation_references.py`：檔案／writer 鎖、正式資格、員工來源與外部參考驗證。
- `transport/model_tools/occupation_references.py`：五個未註冊工具；schema 由正式 JSON Schema 生成 Python／TypeScript，不手改生成檔。

state 只保存 `selected_reference_ids` 與 `confirmations(subject, answer_refs)`。技術用的 Turn、generation、revision 與 operation 身分由 App 提供，不給模型填。來源內存穩定 UUID，工具以 `current_input` 或正式員工訪談序號定位。相同事項原字串再次登記合併去重來源，不作語意歸類、不輸出完成結論。

保存沿用既有背景整理 intent 的資格規則：只有 completed execution 且具有對應正式員工 exchange 的候選，才可成為後續 Turn 的 base；取正式訪談序號最新者。取消、失敗或只有已保存輸入不能生效。選取、重新搜尋及 Memory 更新不清除 confirmations。回復只接受同一 Turn 可達 revision，換 generation 撤銷舊操作。此切片不掛接顧問 runner／checkpoint／完成流程；接模型前仍須把候選位置加入 runner 回復範圍並驗旅程。

## 切片與紀錄

1. [x] HTTP adapter：正常／空結果、逾時、服務錯誤、結構與身分錯誤；47 項 Red → Green。
2. [x] state feature：空選取語意、來源合併、原操作重播、競爭 revision、跨 scope、restore；12 項純函式及 7 項真 PostgreSQL。
3. [x] workflow：只接受當前輸入／固定 frontier 內員工來源，跨 Turn 正式資格、取消及來源投影；11 項真 PostgreSQL。
4. [x] tools：5 工具、9 份正式 schema 與生成物，App 身分綁定、可序列化 prepare／execute；40 項 unit 及 1 項真 tools／HTTP fixture／PG 旅程，未加入模型清單。
5. [x] 完整後端 unit/contracts **1274 passed**；受影響真 PostgreSQL **36 passed**；全量 codegen drift、TypeScript／Vite build、Ruff、Mypy 通過。獨立審查的兩項 P2 已修復與重驗，沒有剩餘實質 finding。

不呼叫模型、不改檢索策略、不套用正式資料庫 migration、不建立完成分數。離線／資料庫測試只驗工具契約和保存，不表示顧問能正確選公版或收尾。

完整命令、環境失敗、反例、修正及未驗範圍見[驗證紀錄](evidence/2026-10-05-occupation-reference-tools/verification.md)。正式接線仍須將 reference position 納入既有 runner 的候選回復，再驗模型選擇與收尾效果。
