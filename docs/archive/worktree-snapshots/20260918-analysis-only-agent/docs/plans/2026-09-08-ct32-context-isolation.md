# CT32：只隔離舊可見問答與壓縮延續

> 狀態：G5 對照、保存驗證及獨立審核完成；帳本closed，G8 OPEN。非產品變更計畫；本地保存由本次commit／tag標識。

**Goal:** 查「答應改為5日，但持久 Memory 仍為10日」是否與兩種既有 Context 各自相關。
**Architecture:** 沿用 CT28 的 FastAPI／LangChain／PostgreSQL 實際服務；兩個 CT16 合成資料副本，只在模型 request view 選取舊 context。背景整理同樣暫停，原始保存不變。
**Tech Stack:** 現有 Luna／medium、Responses、LangChain request override、LangGraph Saver／Store。
**Spec:** [CT32 研究／結果](../specs/2026-09-08-ct32-context-factor-isolation.md)；不得重開 CT28／CT31 帳本。

## 1. 離線先驗

- [x] 測試先行：保留目前員工輸入以後全部 reasoning／tool call／result／phase；不變更 canonical messages；兩組只差舊 context。
- [x] 預算沿用已驗證 ledger，總20次／US$0.10（含重試），封閉帳本不得再呼叫。
- [x] 每次 wire request 檢查 CT25 提示／工具契約與初始導覽；不強制 tool，不增加完成檢查 Agent。

## 2. 兩組各跑一次

- [x] `visible_only`：舊可見問答＋本輪完整鏈，無舊 compaction block。
- [x] `opaque_only`：舊 compaction block 原樣＋本輪完整鏈，無舊可見問答尾段。
- [x] 只對副本送出原 CT28 更正；因基礎设施／API／護欄錯誤停止，不為了成功自動重跑；語意未修補仍保留失敗並可測另一組。

## 3. 審核交付

- [x] 比對實際 tool receipt、正文／導覽 revision 與差異、原42則問答、詳記回查來源；重開服務驗證保存。
- [x] 保存可見 wire、opaque hash、脚本與 hash、費用／呼叫數；不保存金鑰或不透明推理內容。
- [x] 更新 CT32 與 current register；只報對照證據，不把一次結果當穩定成功率或唯一根因。
- [x] 若仍需要新行為／完成檢查，回報討論，不自行接入產品。
- [x] 獨立唯讀審核（無阻擋性發現）。
