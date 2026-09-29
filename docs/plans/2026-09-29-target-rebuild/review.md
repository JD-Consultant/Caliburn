# 實作規劃審查紀錄

- 日期：2026-09-29；範圍：本計畫、實作文件與入口修改；各階段按下列章節區分。
- **§1–3 是施工授權前的歷史規劃審查**：當時產品／provider／PostgreSQL 測試全部未執行。該階段 PASS 只適用文件檢查，不覆蓋後續施工；目前進度見[任務表](tasks.md)，Goal 整理見 §4。

## 1. 本次審查修正

| 發現 | 修正與理由 |
|---|---|
| 新目標 `apps/api`／`apps/web` 與舊退役路由易被混讀 | AGENTS／register／入口明確「重新使用路徑，不接回舊架構」；ADR0077 保持現行，T18 才正式切換 |
| SDD 容易再複製 requirements／design／tasks 三份產品規格 | 原架構唯一描述效果，實作文件描述機制，task 直接引用；schema 生成來源再管 wire |
| 把框架 checkpoint 當成所有業務成功 | E01–E15 分別落任務；原 R 保存、候選提交、Graph 採用及正式完成分開 |
| B 私有 subgraph 每次呼叫可能意外換 namespace | T06／T10 明驗同批回交保留歷史；推薦明確角色 thread，由 Parent 轉譯，不複製 private state |
| title 正規化可能暗改已定精確選擇語意 | 上位驗收修成「既定 title 精確比較接線」，只校正模糊敘述，未增加強制 read／參照 |
| 規劃只列功能，未包含最後可交付流程 | 加入 PDF、公開中間訊息、條件撤回、safe startup／cutover；V25 真實 ROI 與技術 gate 分開 |
| 一個生成器被誤寫成同時產 Python／TS | 核對官方支援範圍，改為 datamodel-code-generator 與 json-schema-to-typescript 各司其職、同讀唯一 schema；不自造生成器 |
| 只在後期做 provider gate，可能太晚發現協定不相容 | T06 備少量全合成 preflight；另有當次外送授權才提前執行，T16 完整驗收仍保留 |
| 容量檢查可能被理解為自己估 opaque tokens | 明列官方 input token count 機制及其外送、失敗與計量責任，T06／T16 驗所選模型；不把 API 文件當成帳戶已通過 |

## 2. 不應誤稱已解決的項目

- 鎖定套件組合、官方 parser 的可重用範圍、原生 item 序列化、strict schema 真接受，仍須 T01／T05／T06／T16 實際證據。
- 新工作 thread／有效歷史基底、業務與 checkpointer 的中斷接縫必須通過 T12，不因文件選定就宣稱可恢復。
- B 輪前門檻、呼叫／重試上限有明示校準初值；費用／時間依當次外送 manifest，不預設無限或已獲授權。
- V4A 唯一模糊匹配只能減少定位歧義，不能證明模型的語意修改正確。工具與品質 eval 各自驗。
- 新程式資料夾與命令目前尚未建立；無產品程式、依賴、schema、資料刪除、付費請求或新提交。

## 3. 文件檢查

| 實際檢查 | 結果與邊界 |
|---|---|
| 文件範圍與連結 | PASS：11 份新文件及 7 份責任／入口修改；182 個本機連結與錨點可解析。current-decisions／docs README 僅查本次相關入口，不冒稱審完全部歷史 |
| Markdown／空白 | PASS：範圍內 fences 成對、無行尾空白；`git diff --check` 通過。沒有新增 JSON schema 示例，正式 shape 留唯一契約來源，未因此執行 codegen |
| 任務依賴 | PASS：T01–T18、27 條前置依賴無循環，圖與任務 metadata 一致；各項具契約、完成條件與非目標，全部仍未勾選 |
| 驗收追溯 | PASS：V01–V28、E01–E15、JDT-01–09 全部有任務對照。這是 52 項覆蓋的文件檢查，沒有執行這 52 項產品測試 |
| 圖面 | PASS：兩張新圖以 Mermaid 11.17.2、隔離 headless Chrome 實際渲染；檢視 10 個程式責任節點、18 個任務節點，標籤與箭頭可讀，未裁切。第一輪 sandbox 啟動遭 EPERM，經工具授權的隔離重跑成功，未使用使用者瀏覽器設定 |
| 權責與限制 | 人工／AI 共用領域規則；native items 不改成文字摘要；Memory 無逐引用核對；JD 保留兩種核對基準；新命名／路徑不復活退役接線；相容性與品質風險保留為實測 gate |
| 工作範圍 | 只有 Markdown／AGENTS 路由變更；未修改產品程式、schema、lock、DB、啟動入口；未發付費模型、刪資料、commit、push 或 merge |

本次未發現需要 Owner 重新裁決產品語意的阻塞；**不承諾計畫沒有任何實作風險**。下一步是 T01 的工具鏈／相容性與可測邊界，不能越過 gate 一次建完全部底層。工程測試發現反例時，先依上位契約修正相應機制；只有必須改產品效果時才回到決策討論。

## 4. Goal 分層整理與覆蓋審查

日期：2026-09-29；Owner 要求整理長 Goal 並提供短 `/goal` prompt，不減少既定工作、不重置 T01。本次只維護文件，沒有替換執行中的 Goal。原長 Goal 是本次 Owner 授權的來源紀錄；其分節要求按以下責任歸屬維護，不另複製一份完整 prompt 作第二套規範。

| 原 Goal 要求 | 維護位置及保留界線 |
|---|---|
| §一 產品目的／成果 | [計畫 §1／5](README.md)、[產品概念](../../product-concept.md)：員工訪談即可逐步形成專業、完整、高訊號 JD，不以人工代寫補救為 gate |
| §二 正式依據／狀態 | [計畫入口](README.md)、[AGENTS](../../../AGENTS.md)、[目前決策](../../current-decisions.md)：區分現行、目標、候選、歷史；不只讀摘要施工 |
| §三 範圍／取捨 | 計畫 §1／3、T01–T18：重建不遷移底稿、必要診斷可補、不造第二套平台；精確切換不等於刪舊資料 |
| §四 研究／選型 | [開發規範 §1／2／5](../../implementation/development-standard.md)、[選型](../../implementation/technology-decisions.md)：官方／原碼／多方做法／有限驗證，選受支援相容方案後鎖定；可研究改良而非永久鎖死 |
| §四之一 分析／Prompt／Tool／Context | 開發規範 §7、三份分析指南與相應工具責任契約、T14／T16／T17：分責、按需、型號契約、基準／保留例及真模型共同驗收 |
| §五 SDD／TDD | 開發規範 §2–4：有效 Red、Green、Refactor、整合及小切片；不得刪測例降低標準 |
| §六 程式／命名 | [程式組織](../../implementation/code-organization.md)、[契約策略](../../contract-strategy.md)：角色／共用執行／流程／領域／UI 分責、唯一 schema、不建空泛抽象 |
| §七 核心邊界 | [架構路由](../../target-architecture-map.md)、[驗證對照](../../implementation/verification-plan.md)與 T02–T12／T15：來源資格、快照、引用、候選、原生接續、短交易、取消／恢復各驗，不新抄狀態機 |
| §八 真 API／憑證／費用 | 計畫 §3：直連合成、有界自主測試、秘密保護、禁止任意私人外送；明顯高額擴張仍提問 |
| §九 驗證／交付 | 計畫 §5、驗證對照、[介面交付](../../implementation/interface-and-delivery.md)：真 PG／原生 API／故障／UI／長訪談／品質／可重現啟停，不以 mock 或 Dockerfile 代替 |
| §十 文件／問題與報告 | [架構文件規範](../../architecture-discussion-standard.md)、開發規範 §6／8、計畫 §4／5：單一責任、圖實際渲染、問題取捨可追溯、報告不虛構 ROI |
| §十一 Git | 開發規範 §9：不用 codex 前綴、Conventional Commits、本地授權、精確 staged；不 push／merge／PR／tag／外部部署 |
| §十二 自主／提問 | AGENTS、開發規範 §10、計畫 §3／4：效果等價細節自主，重大語意／安全／不可逆／費用衝突提問；不阻塞無關工作 |
| §十三 長任務 | 開發規範 §10、任務 evidence：驗實況、保留下一步、重用有效證據，不每輪全讀歷史、不另建進度權威 |
| §十四 完成／交付回報 | 計畫 §5 保留全部 12 項退出條件及回報要求；任務表依實測勾選，不能把本次文件完成當產品完成 |
| 後續補充 | 計畫 §1：API／Web 不強制命名；可依研究採更好實現，但不能改掉已確認概念與保證 |

修正了有效入口的「尚未施工」、舊 `.env` 全面禁止、T06 重複請示授權及前端 package 舊名。歷史 §1–3 保留當時狀態，未重寫 ADR0077；T01 實測失敗與下一步移入[該任務 evidence](evidence/t01-foundation.md)。沒有變更產品語意或新增外送範圍。

本次實際文件檢查：13 份相關文件（大型索引／決策紀錄只檢查本次入口區塊）、158 個本機連結、29 個錨點、fences／行尾空白均通過；T01–T18 的 27 條圖面依賴與任務 metadata 相符，沒有誤勾完成。`git diff --check` 通過，僅提示既有 Git LF／CRLF 轉換；未追蹤新文件另由上述文字檢查涵蓋。原 Goal 各節與 12 項完成條件逐項對照如上。沒有改 Mermaid 圖內容，未重做渲染；沒有因文件改動重跑產品／付費測試，也沒有 commit／push／修改 Goal 狀態。
