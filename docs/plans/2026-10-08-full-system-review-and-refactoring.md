# 全系統程式、資料與架構審查及重構

> 執行方式：依本次使用者授權，由主代理規劃、分派 subagent、整合與驗證；沿 `superpowers:subagent-driven-development` 的獨立實作與審查方式。工程方法依[開發規範](../implementation/development-standard.md)，本計畫不重建產品規格。

**Goal：** 完整審查現行 Caliburn，修正可證實的正確性及工程設計缺口，讓前後端、資料、測試、Log 與架構文件保持清楚、可維護且可驗證。

**Architecture：** 以完整工作區實況及成熟官方契約比較方案；模組、資料表與接線均可重新設計。保留必要產品行為，工程品質獨立驗收；跨層改動先定責任與資料權威，再分批落地。

**Tech Stack：** 先核現行 FastAPI／SQLAlchemy／PostgreSQL、LangGraph／Responses、React／TanStack Query／Vite 與鎖定依賴；具體替換由審查證據決定，不預設全面換框架。

**Spec：** [工程與驗證規則](../implementation/development-standard.md)、[程式組織](../implementation/code-organization.md)、[程式撰寫與 Log](../implementation/coding-standard.md)、[架構責任](../target-architecture-map.md)、[全系統研究](../research/engineering/2026-10-08-full-stack-engineering-practices.md)。產品契約依責任文件查閱；舊設計可修訂，歷史 ADR 保留演進。

## 授權、基準與驗收

- 2026-10-08 使用者授權全系統 review 及實作重構，含資料表／架構重新設計；自主分派子任務。高內聚、低耦合、可讀、可測、可觀測及維護性是工程基線，不以 JD 品質提升為前提。
- 後續追加：設計前研究相應領域的當前官方規範；同步維護架構文件及必要圖面。圖按種類遵守節點與連線語意，避免雙寫、過時規則及候選冒充現況。註解使用中文；文件依 `better-documents` 與 `humanizer-zh-tw` 整理用途、順序及文字。
- 工作區：`S:\caliburn`，分支 `consultant-jd-analysis`，起始 HEAD `6ec52822ee475876ed20e57d818c8db298c42928`。以既有大量未提交 Plan、Prompt、工具、測試及文件修改為基準，不 reset、丟棄或用 HEAD 覆蓋它們。
- 審查現行 `apps/api`、`apps/web`、根交付腳本與設定。獨立 RAG 審 App 接縫與部署權責；不把退役程式重新納入產品。
- 保留金鑰及私人原件的存取／外送邊界。資料設計與遷移可調整，但驗證使用隔離資料；不用清掉現有資料掩蓋錯誤。
- 完成包含：各面向有審查結論與證據；本輪修正通過相應測試與獨立審查；文件、圖、schema／生成物及程式一致；剩餘限制明示。離線測試不冒充真模型品質驗收。
- 本輪不預設 push、merge 或向外部觀測平台上傳資料。

## Review focus

- 同時有多份職務工作、取消或切檔：資料、工具及畫面不混用作用域。
- COMMIT 後回應丟失、背景工作恢復：核對正式結果，不新增重複效果或宣稱未知為成功。
- 模型首次呼叫失敗、取消或只有部分 checkpoint：仍能查已捕捉請求及當時綁定，未知明標。
- 更換 Prompt／Tool／策略：對照配置可確認，測試與真人入口共用正式規則。
- 文件或圖沿用過時設計：只保留單一現行責任來源，圖種類及箭頭不混淆靜態依賴、執行或資料關係。

## 任務與分工

| 任務 | 責任／輸出 | 狀態 |
|---|---|---|
| R0 基準與完整審查 | 三個子代理分審資料與領域、前端、測試／Log／交付；主代理審 Agent 執行、權限與整合。發現、覆蓋及基準測試只記[審查證據](evidence/full-system-review-2026-10-08.md) | 已完成本輪範圍 |
| R1 修正設計與切片 | 對實際缺口核官方來源，明定負責檔案、介面、反例與檢查；不把只需品質整理的問題誤記為 runtime bug | 六個切片及整合反例已收斂 |
| R2 實作與回歸 | 寫入範圍分開；行為修正先 Red，再最小 Green／Refactor；效果等價整理重用適當基準測試 | O1／F1／D1／E1／D2／L1 已完成 |
| R3 架構與圖面維護 | 核現行架構、實作責任文件及必要流程／時序／ER 圖，按圖種與用途修正。來源規範集中、其他位置引用 | 已完成；33 張渲染及視覺核對，移除兩份重複圖源 |
| R4 整合及交叉審查 | 非實作者核主要改動；執行受影響單元／契約、真 PG、前端及必要瀏覽器旅程，檢查生成、lint／type／build 與文件 | 已完成；原失敗與修正後重驗分開保留 |

實作切片的檔案及驗證在發現確認後直接更新下節；同一問題只在 evidence 保留完整根因與結果，不在計畫或架構中複製流水帳。

## 已確認切片

### O1 一般 Log 與原始執行查閱

- 已有證據：Uvicorn 現行設定不輸出應用 logger 的 `extra` 欄位；診斷投影忽略沒有 response 的已保存 request，且沒有投影 `initial_context` 的 Memory／Plan 綁定。
- 責任：應用日誌組裝與輸出、`diagnostics` 唯讀投影及其查閱入口；原業務與 checkpoint 保存繼續由現有負責模組裁決。
- [x] 確認具體介面、輸出策略與測試；只給安全 metadata 進一般 log，敏感正文沿受控診斷。
- [x] 以 request-only checkpoint、不同綁定版本、並行 ID 及 logger handler 反例驗證修正。
- [x] 完成實作、lint／型別、相關單元／真 PG 查閱測試及 runbook／架構維護。

`observability_refactor` 負責 `adapters/logging.py`、`diagnostics/`、後端啟動與診斷腳本、migration 0027 及對應測試。採標準 logging、有限佇列與有限關閉；`configure_logging` 回傳可關閉 handle，`bind_log_context` 以 contextvars 綁定安全識別。主代理整合 HTTP／背景工作的事件與關聯。診斷保留原 request-only 狀態、原始 Memory／Plan 綁定及後續回應來源，CLI 支援選定執行查閱。

### F1 前端讀取與編輯基準

`frontend_refactor` 負責 `apps/web`：共用本機 QueryClient factory、`InlineEditor` 的開啟基準、完成 Turn 的刷新生命週期及相應行為測試。依 TanStack Query 當前契約及鎖定原碼處理：離線不暫停 localhost 操作；完成後先取消舊讀取再刷新，失敗可明確重試；編輯 dirty 與版本用同一基準。驗證延遲首次 GET、StrictMode、刷新失敗與背景改稿，不另建全域狀態框架。

### D1 有界來源與 Plan 讀取

`data_query_refactor` 負責 Memory 選中成員的窄查詢、JD 來源查讀及 Plan 最新合法投影。SQLAlchemy／PostgreSQL 原生 SELECT／JOIN 完成過濾，避免全量歷史或成員來回搬運。各 owner 提供具名唯讀 selectable，`workflows/interview_plan_queries.py` 組合跨域資格，不新增 Plan head 權威。真 PG 驗 scope、sealed、歷史來源、固定上界、取消／失敗及最新空 Plan；查詢參數與取回內容須有界。JD 複合編輯另作切片，不混入讀取重構。

### L1 本機程序生命週期

主代理完成 `scripts/run-app.mjs`、程序 helper 與 Node 反例；`experiment_composition` 接續修正獨立審查重現的 Windows uv wrapper 退出但 Python 仍存活。以短命 uv 完成既有依賴同步及 interpreter 定位，再直接持有服務程序，不依名稱或埠號停止其他工作。驗同步 spawn 失敗、非同步 error、close、清理失敗、自訂 venv 與真程序退出。

### E1 可維護的對照組裝

`experiment_composition` 完成角色的不可變 `ConsultantConfiguration`、正式 App 的 `AppComposition` 與 `evaluations` 入口；由明示配置替換提示、工具說明及 JD 讀取容量，原 captured 工作維持原值。SDK／checkpointer 的建立及關閉由正式 lifespan 擁有。獨立審查的 mutable DTO／manifest 漂移已以首次等待前固定整批候選修正，沒有改 module-global 或 import 歷史 runner。使用及輸出見 [evaluations README](../../apps/api/evaluations/README.md)，證據沿本輪 evidence。

### D2 JD 複合編輯

`jd_compound_refactor` 負責四類模型編輯的 owner 用例：profile、任務、一般項目新增／修訂及其依據關係。workflow 只保留跨域准入、來源解析與外層交易，JD feature 一次計算及保存最終修訂，回傳具名結果，不再由集合差推導新物件。migration 0028 在既有原操作保存必要結果身分；不是新增回執系統。驗一次工具至多一個新修訂、末段失敗整體回滾、提交結果不明重播、舊已保存 checkpoint 只讀恢復及正式完成／撤回。

## 驗證紀錄與接續

本輪工程工作已完成。命令、結果、獨立審查修正及未驗範圍由[本輪證據](evidence/full-system-review-2026-10-08.md)維護；這是本次覆蓋範圍的結案，不代表不存在其他缺陷或 JD 品質已達標。程式與資料 migrations 尚未部署至原共用服務，原未提交工作保留；後續品質議題仍沿架構驗證文件，不重開本輪切片。
