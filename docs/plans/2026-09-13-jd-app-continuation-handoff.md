# JD App 接續施工與交接計畫

更新：2026-09-13；Topic JD-R002／OI-01、OI-02。**H2–H3 已提交為 `7181db63`，Owner要求的提交後複核見[審查結果](../specs/evidence/jd-memory-repair-integration/submitted-integration-review.md)。**先前方向審核保留當時首敗，不再代表目前停點。下一施工是H4採用映射；這次複核沒有開始H4。

本文件負責「下一位從哪裡接、分步怎麼做、如何驗收」。產品總範圍仍由[總施工計畫](2026-09-13-jd-relational-app-implementation.md)負責，未解事項由[唯一清單](../specs/2026-09-13-jd-app-open-issues.md)負責，入口只維護[目前決策](../current-decisions.md)。不要重新讀完整舊聊天才能開工。

## 1. 先讀這一頁：現在停在哪裡

**既有不含 JD 的訪談顧問與 Memory 已有真模型限定驗收成果；新關聯式 JD App 的完整採用及自然產稿驗收尚未完成。**已有真正的六章管理、人工保存、聊天與當輪 JD 改動接點，Memory即時修補C的Agent／取消／恢復接合已完成。下一採用既有B1／B2，不是重新開發顧問的理解能力。既有 CT49／CT50 完成依據及適用界線見前次審核稿 §2。

本輪取得的重要反例：把 C 子圖藏在工具函式內，即使提前建立，也不能經公開的原生子圖觀察讀到原發布請求。已用官方文件及有限實測選定：**工具將控制權交回根流程的固定 `memory_repair` 節點，該節點呼叫既有 C 子圖，完成後回顧問。**不增加第二個 Saver、資料表或通用定位引擎。

**H2–H3 已完成（2026-09-13），結果見[App 接合結果稿](../specs/2026-09-13-jd-memory-repair-app-integration-slice.md)。**CA-01「call 已存、binding 未存」與 CA-02「C 停在原生 START」已修並各有真 PG 回歸；真新 Windows 程序的 C 回覆遺失查回（FH05）、adoption／wheel 乾淨安裝與獨審已收尾。**唯一下一施工單位改為 §5 的 H4**：採用已驗 B1／B2 與顧問方法，先交採用映射。不要重做已接 H1–H3，也不能把日常 `enable_chat` 打開代替驗收。下方 §3 的檔案狀態與 §5 H2／H3 的「還要完成」是當時交接界線，以本段與結果稿為準。

| 工作區事實 | 交接值 |
|---|---|
| repo／branch | `S:/caliburn`；`refactor/current-only-architecture` |
| 目前接續施工基準 | `7181db63f345b2ec91618cc169a29c624414afc2`；前一核心基準 `8403d7e2` |
| 對應本地 tag | `jd-memory-repair-app-integration-20260913` |
| 新 App | `experiments/jd-relational-app`；不是舊 Plate 的 `experiments/jd-editor` |
| 獨立 Memory 套件 | `packages/consultant-memory`；新 App 已以正常 package 依賴使用 |
| H2–H3 提交範圍 | 已提交34檔；其餘既有dirty不屬本段，不reset或混入下一施工 |
| 正式產品 | ADR0060 不變；ADR0074／0075 仍 Proposed；沒有正式切換 |
| 模型費用 | 本輪 0 provider；固定模型／MockTransport 不等於真模型。日常 `enable_chat=False` |
| 新增資料庫結構 | 本輪沒有新增表、migration 或 setup；原設定／真資料未清除 |

## 2. 不可再誤解的產品需求

1. 員工以持續聊天為主，AI 理解某項工作足夠後才寫或改 JD；純訪談可以完全不改稿。不把每一輪都寫稿當成功。
2. 這是管理職責、任務、成果、要求、共享知識／技能的 **CRUD App**，不是自由文章編輯器。員工不開 AI 也能完整建立 JD。App 統一排版，欄位寫文字／換行，沒有要求欄內富文字。
3. 職責一對多任務；任務可未歸職責；任務底下分列多筆成果及多筆工作執行要求，兩者不強制配對。知識／技能可由多個任務共享引用。以[完整格式](../specs/2026-09-10-jd-format-review.md)、[欄位充分性審核](../specs/2026-09-13-jd-field-sufficiency-audit.md)、[十三表契約](../specs/2026-09-12-jd-relational-schema-and-write-contract.md)為責任來源，不另發明一份格式。
4. 聊天與唯一 JD 工作稿同畫面，AI 直接改，員工不用逐筆接受。**只要看得出當輪 LLM 改了什麼，不做從舊聊天挑選歷史 AI 回合的介面。**既有保存歷史保留；原話／回執恢復的技術讀取與「新增歷史選輪 UI」是不同事項。
5. 本輪 JD 改動使用實際保存前後的欄位／關係／刪除內容，不能只顯示 AI 自己寫的摘要。逐字高亮、動畫、拖曳捷徑可延後。
6. 前景 AI 執行時暫停手改；手改已保存後，下一輪 AI 必須得知變化，不能依舊印象覆寫。通知是 App 資料，不冒充員工原話，不自動改 Memory。
7. JD、Memory／工作理解、案例詳記、原始對話各有保存責任。**撤回整輪只撤 JD，絕不撤回 Memory、案例或原話。**取消執行也不等於撤回已保存結果。
8. 本機單一操作者、多份隔離文件；不加入登入、ACL、多租戶、雲端、RAG、多人協作或舊資料搬移。Excel／真人交付／其他電腦安裝延後。
9. JD 是該員工真實工作，不是招募規格、訓練課表或 KPI。主要及重要低頻工作、條件與邊界要保留；未知不補造、案例不直接變永久責任，資料不足可先保留尚未完整任務。

框架為實現需求的選擇，不是 Owner 的永久偏好。已有[適用性比較](../specs/2026-09-13-jd-app-stack-selection.md)及鎖定版本，不因「最新」二字無據升級或重選；有反證才重開。

## 3. 接續基準與前次交接歷史

**現況：**原call結果、固定C位置、CA-01／02及無checkpoint但有原生位置的收尾、FH05新宿主查回、adoption／wheel已在`7181db63`完成。下一先做H4映射。實作者完整紀錄見結果稿，提交後獨立窄跑與封裝複核見審查結果；不累加重疊測試數字。

**下表僅為提交前的交接歷史，不是現行待辦。**相對路徑從repo根起算；其「當時未完成」已由上述成果收尾，禁止照表重做。保留為首敗與實作責任對照。

| 檔案／範圍 | 交接當時已有 | 交接當時未完成（現已由H2–H3收尾） |
|---|---|---|
| `packages/consultant-memory/src/caliburn_memory/repair.py`、`tests/test_repair_graph_factory.py` | 公開 factory；原流程共用同一六節點；完整套件最後130 PASS | adoption hash、乾淨 wheel 依賴驗證與本次獨審 |
| `memory_repair_records.py`／`test_memory_repair_records.py` | 原call binding、edits、原request、content/artifact的嚴格核對；含 `not_published` | 配合 CA-01 明確表示無 binding 的原call未執行；不可用假發布結果補缺失 |
| `memory_repair_session.py`／`test_memory_repair_session.py` | 本輪 session、parent handoff、固定 C wrapper、結果投影、有限失敗次數 | CA-01／02 的停止收尾；本輪 `_prepared` 不可用於新程序重建意圖 |
| `consultant_context.py`、`consultant_tools.py`、`memory_context.py`、`runtime_checkpoints.py` | bindings狀態、context、原生middleware、固定節點、15工具；初始notice與後續固定讀版分開 | 只核實未覆蓋的讀取／錯誤情境，不再把這四檔當未接線 |
| `ai_checkpoints.py`／`test_memory_repair_checkpoints.py` | 原生固定 C checkpoint 與binding觀察、close材料保留；接受START | START原input與binding核對、停止位置證據及恢復端一致性 |
| `ai_runtime.py` | 另核 C 的原request／publication receipt；同owner drain、未知門閘、終局查回 | CA-01／02；C真新宿主恢復；不混JD receipts |
| `tests/test_consultant_memory_postgres.py` | 8 PASS：真PG＋固定SDK正常C、查回、故障、取消；重新開資源 | 同程序重開不算新程序；unknown中的稍後receipt由測試輔助建立，不是延遲真交易證據 |

路徑未列前綴者位於 `experiments/jd-relational-app/src/jd_relational` 或對應 `tests`。前次交接數字為App435／套件130／PG8；兩案當時仍失敗，見[歷史審核 §3–4](../specs/evidence/jd-memory-repair-integration/continuation-audit.md)。它們不是本次最終驗證，也不代表H2／H3仍未完成；現在的结果見頁首路由。

歷史首敗保留：交接前session缺模組，接著3 FAIL／1 PASS（15.18s），三案先止於`invalid_tool_session`；checkpoint首跑12 FAIL／10 PASS。這些已不是目前停點。接续另修過正常C終局誤回`run_recovery_required`與測試資料形狀；不能刪掉真scope／owner檢查只求綠燈。

前置證據仍在本目錄：[原生觀察](../specs/evidence/jd-memory-repair-integration/native-observation-preflight.md)、[原call／結果](../specs/evidence/jd-memory-repair-integration/records-results.md)、[factory](../specs/evidence/jd-memory-repair-integration/graph-factory-results.md)、[停止分類](../specs/evidence/jd-memory-repair-integration/closure-preflight.md)。其中較早推薦由下節已採接法取代，不與最新狀態並列成兩個指令。

## 4. 已收斂的 C 接合設計

### 4.1 正常流程與責任

```text
同一前景 owner 准入、保存本輪原話與初始 Memory view
  → 原生 consultant model 回 repair_memory(edits)
  → after_model 綁原 AI message/call、App operation/base/source 並同步保存
  → 真 ToolNode 回 Command.PARENT，將當前必要 Agent state 交 root
  → root 固定 memory_repair wrapper
  → 既有 C：seed → edit（逐筆）→ validate → save → prepare → publish
  → 同 call ToolMessage（短 content＋內部 artifact）
  → 回 consultant：後續讀取使用此次 C 明示的固定版本
  → 已停止／已核效果／原生閉合後，owner 才解除手改限制
```

- C graph 直接捕捉於固定 node wrapper 閉包，讓 LangGraph 靜態發現。不要在 ToolNode 函式內動態建圖，也不要保存自猜 namespace。
- 根流程仍只需要 consultant 與 memory_repair；wrapper 直接回 ToolMessage，不另加通用 result engine。C 的 `files/material/version/request/outcome` 留在子圖，不複製到 root。
- 核心 factory 收 `resolve_workflow(runtime)`；App 從 `runtime.context` 取本輪資源，檢 scope／Store／owner。build、inspection、get_state 不應執行 resolver 或開模型。
- 唯一新增的專用持久 root／agent 欄位是 `jd_memory_repair_bindings`。原 `jd_memory_view` 是開場選定版本，不被 C 改寫；讀版及失敗次數由本輪配對的 C 結果投影，避免再持久保存另一份 head／counter。
- `RepairBinding` 有 format、dataset/doc/run、message/call、App operation、原 args digest、base、source；LLM 只提供 `edits[{path,diff}]`。沿原兩路徑、1–8筆及12000 diff字元，不讓模型算版號、SQL ID、來源窗口或保存成功欄位。
- 原結果 artifact 保存 operation／input digest／outcome（移除重複 changes）／原 PublishRequest；content 只給 status、detail、guide、read_paths、retryable。artifact 是內部資料，**不是 DB 保存成功的權威**。
- 原始來源沿既有 owner；C 可用進行中本輪已保存原話，不能因而放寬 B1 必須取完成窗口的規則。

### 4.2 同輪讀取與失敗限制

初始 H1 → C applied/read H2 → 背景另發 H3：本輪後續讀 H2；下輪才取 H3。若 C 自己發布 H2，但其回覆時已明示讀到 H3，則本輪固定讀 H3，不繼續追後面的 H4。

初始 system guide 保持開場事實，新的 guide 由 C 結果提供。不得因選新版而替換員工訊息、改寫早先工具回覆或把歷史工具結果當現在控制資料。

`invalid_edit`、`stale`、`no_memory` 每個原 call 累計一次；第一個失敗可讓模型讀新資料後更正，第二個 `retryable=false`，第三次直接 `repair_limit`，不執行 C。成功不重置失敗次數，新回合重置。格式错误即使沒進工具函式，也須產生原 call 的同一套有界回覆；未知 I/O／source／SQL 不算模型可修次數。

[早期 read-refresh 前置](../specs/evidence/jd-memory-repair-integration/read-refresh-preflight.md)的「另外持久保存讀 head／failure counter」及固定包裝方式只屬前置推薦，**由本節的 artifact 投影方式取代**。它的讀版／失敗情境仍可作驗收材料，不直接複製其舊 ABI。

### 4.3 取消、未知結果與恢复

取消政策採有限接合：wrapper 開始 C 前檢 stop；**已開始的這次有限 C 讓保存完成**，同 owner 等真 Future，然後阻止下一模型／工具啟動。畫面可先顯示正在停止，但不能立即宣布未保存或解鎖。不要新增逐節點取消／補償引擎，不按等待逾時推定工作已死亡。

| 固定觀察 | 必須採取的處理 |
|---|---|
| 原 call 已存，但有確切原生／停止證據證明 C 尚未開始 | 可回本 call 的未執行結果；不能掉進 JD 通用 `_not_executed` 當成 JD operation |
| C 已開始，尚未有 prepared request | 只有確認原保存位置、真 worker 已停止及沒有發布的證據，才能判尚未發布；不可只看 latest overlay 或缺 receipt |
| 原 prepared request 存在，結果未明 | 取公開 task 給的固定 config，讀同一原 request；核綁定後 `RepairWorkflow.reconcile(request)`。不重新 patch／save／prepare／publish |
| 原 receipt 不存在／查詢失敗／不匹配 | 保持 `run_recovery_required` 與原操作；沒有原證據不能推定安全重播。若會造成無法操作，記具體反例再解，不以通用重試補洞 |
| 原 receipt 已確認，工具回覆遺失 | 配對同 call，保存真實結果；只讀查回不能增加發布次數 |
| ToolMessage 已保存，背景稍後又變版 | 核原 applied receipt、原 input digest／source。保留這筆既有 feedback 當時的 read head／guide，不能要求其逐字等於現在 reconcile 讀到的新版本 |
| root close 回覆遺失 | 一次原生更新後核 exact readback；不重播 Agent、C 或模型 |
| 新程序接手 | 沿既有真舊程序退出證據及 inspection graph；找原 call／原 task／原 request，不使用已消失 RAM cache 當原始意圖 |

`next=publish` **不是**尚未發布證明：資料可能已提交而回覆遺失。`applied_head`（此操作真正發布）與 `head`（本次提供讀取）要分清。JD 撤回永遠不反向操作 Memory publication 或原話。

## 5. 接續施工：有界工作包與檔案責任

### H1｜完成正常 C 接線與同輪讀取

**狀態：主要接線已存在，以下保留為驗收責任，不是要求重寫。**從 §3 的實際 diff 與既有通過結果檢查；只補缺口。原 C 核心與原 JD session 檢查都保留。

1. `consultant_context.py`：state 增 bindings；context 增 `memory_repair_session`。初始 guide 投影仍用初始 session。所有 model request 的 scope、原話、notice驗證保留。
2. `consultant_tools.py`：after_model 在原 AI call 檢查後識別 C 並綁其原材料；wrap_tool_call／async 路徑接真正 C tool，仍保持 inspection-only、stop、多 call、未知工具及原 JD 行為。C 不借用 JD operation bindings，也不加入 `MEMORY_READ_NAMES`。
3. `runtime_checkpoints.py`：DocumentState 增 bindings；`build_document_graph` 掛固定 wrapper 和回 consultant edge。保留 consultant→END 與原 manual close 的相容性；以已驗 `Command.PARENT` 語意測，不自己寫執行迴圈。
4. `memory_context.py`：`build_consultant_tools` 納 C；一般只讀工具從已驗本輪結果選固定 reader；初始 model notice 有明確獨立取初始版的方法。`read_file/grep/ls/read_conversation` 四者一致，不只改一個工具。
5. `ai_runtime.py`：用既有 owned Store／Memory engine／source 建本輪 session、注入 context；新 run 輸入重置 bindings=[]。與原 JD AiToolSession 共存、共用 foreground，不增 writer／executor。
6. 用真正的本輪來源與 App middleware，核 C→read→C／JD、兩次失敗、另一文件及下一輪；晚 B 與四讀工具若缺實際接合證據再補窄案。先查現有案例，不重做已修 fixture；保留實際 model input／ToolMessage／保存結果。

**完成條件：**正常原生 Agent 操作通過、scope與參數錯誤先於副作用、root無 staging副本、初始view不變、四讀工具確實更新；錯誤不外露原診斷。H1 未包含取消／重啟，不能先啟用日常 AI。

### H2｜完成原結果收尾、取消與重啟

**狀態：已完成並提交。**下列H2a–c保留實作規範與驗收依據，不是要求下一位重新執行整段。只有新反例才重開，不新增另一層通用恢復系統。

#### H2a｜先把兩個審核探針轉成期待正確行為的紅測

1. 讀[兩個反例及診斷腳本](../specs/evidence/jd-memory-repair-integration/continuation-audit.md)。它目前斷言會阻擋；直接跑到 PASS 不等於修好。
2. 在現有 App runtime／session 測試新增兩個命名清楚的案例：`source_before_binding`、`repair_child_start`。使用真正 Agent／Saver，不以手拼「沒有副作用」的snapshot代替原生執行證據。保留原call、原run及原資料庫版本。
3. 將期望改為：真正工作已停止後，原回合有明確失敗／未發布終局；`effects_settled` 為真但不聲稱Memory更正成功；後續手改及新回合可准入。模型仍1次、seed／publish為0，JD／原話／Memory正文不被改寫。
4. 首跑保存具體斷言失敗，不能用`raises(Exception)`或手動釋放owner讓測試過關。只在實際已有停止證據的路徑測解鎖，不偽造`proof-of-death`。

#### H2b｜閉合兩個已知未執行位置

| 責任檔 | 有界修改與不得省略的核對 |
|---|---|
| `ai_checkpoints.py` | 保留固定root/source/C三個觀察界線；只讀原生回傳的固定config。為CA-01提供足以辨識原`after_model`尚未成功完成的停止材料；為CA-02讀固定START的原輸入。若目前投影缺必要欄位，先用既有探針查實際原生形狀，再只加必要投影，不掃任意namespace。 |
| `memory_repair_records.py` | 若CA-01需要專用結果型別，用同一內部結果契約明確區分「尚無binding、未執行」與「已有binding的更正結果」。無binding不能假造operation、base、source或PublishRequest；不加新資料表／另一回執權威。LLM仍只填`path/diff`。 |
| `memory_repair_session.py` | 原call／原參數摘要配對；已知無binding的未執行結果不更新Memory讀版、不算模型格式錯誤重試，也不能觸發C。既有已綁定結果與失敗次數投影維持，不能放寬所有decode。 |
| `ai_runtime.py` | CA-01只在原生位置能證明handler未進、原Future已停止時關閉同call；CA-02核START payload的文件／operation／base／source／edits與原binding一致。通過才回明確未執行／未發布；含request而沒有可信outcome或receipt仍為未知。`_repair_evidence`、`_verify_saved_results`、`_settle`、get／lookup／recover／startup使用同一判定，不各寫一套規則。 |

必要拒絕案例只涵蓋相鄰邊界：錯call／跨文件、START輸入不符、已到publish但查無原receipt。這些仍`run_recovery_required`，且無第二次模型／patch／publish。不能把缺binding、缺checkpoint、缺receipt任何一項單獨當作「安全未執行」。

close完成後查回應同時保留原run、messages、JD bindings、Memory view、repair bindings及固定關係；若ACK遺失只做原生exact readback。查證實際adapter如何保留，不能只因root顯示terminal就呼叫`finish_foreground`。取消只阻止後續工作，已開始C仍排空，沒有改成撤回Memory。

若公開原生材料不足以證明其中一種情況，保留門閘，將缺哪項證據記在CA項下；先完成另一案及独立工作。不得以新增通用事件引擎、重新執行prepare／graph或假成功填洞；會改產品恢復語意的替代才交Owner討論。

#### H2c｜補真正跨程序 C 查回，收束驗證

1. 延伸 `tests/test_ai_host_restart_postgres.py`／`tests/ai_host_recovery_worker.py` 的既有Windows helper；注入同配置的Memory engine、Store與原話source，使用目前固定子圖。現有helper只有JD資源不能當C證據。沿原HostLease與舊程序退出核對，不另造程序管理器。
2. 原helper以合成固定SDK產生C，真PG提交已完成但原結果回覆遺失，保存原call／binding／request；以既有有界故障閘門使原程序在native結果閉合前退出。先核停點與程序身分，不能拿已正常close的回合重開代替此案。新Hidden程序只建inspection圖、沿原證據恢復，禁止provider／model／patch／save／publish重播。
3. 驗原operation僅一筆receipt、Memory版本與內容正確、JD及既有原話不回退、原run可查且後續准入恢復。第二次查回仍同結果。若首案已覆蓋root close ACKlost則不重建等價大型情境。
4. 對已確認的正常C、取消drain、commit ACKlost跑窄回歸。晚B只補一個會改讀版判斷的固定情境：核原applied receipt，後來Memory head變了不讓原結果失效或倒退；不用重跑全部舊背景實驗。
5. 結果標明「真SDK固定回覆／真PG／真新Windows程序」，仍不是自然模型。unknown測試若由test建立稍後receipt就如實標注，不叫延遲原交易。

**完成條件：**終局查回的 `effects_settled` 確實涵蓋 C；原 JD receipts 僅包含 JD 效果。每個 gate 解除有實際停止＋保存證據，恢復不重播，未知有可理解出口。無法處理的確切情境集中記 OI-02，不能隱藏。

### H3｜封裝、獨立審查與本段收尾

**狀態：已完成；下列為保留的收尾規範。**本次提交後複核再次核對來源hash、乾淨venv與wheel，詳見審查結果。

- 僅跑受影響核心／App／真 PG／Windows 新程序案例；範圍見 §7。有新失敗才擴測，不機械重跑幾千案例。
- `packages/consultant-memory/adoption.json` 已更新實際檔hash／factory調整並保留採用來源commit；wheel已重建。後續修改來源才重新更新hash／封裝，不沿用舊產物冒稱新版本。
- 乾淨venv依App lock導出的限制安裝wheel及依賴；缺cache先記缺件，沿現有依賴補必要取得，不無據升級。核`caliburn_memory`確實從新wheel載入，沒有`analysis_agent`或舊checkout依賴；只建圖／import不開provider。先前借用App site-packages只算模組隔離smoke，不算此項完成。
- 安排非作者審查 bindings／context／恢復／scope，修後窄複核；記首敗、最終結果及未驗層級。先確認可驗收再精確提交／本地tag，不混入無關dirty，不merge／push。
- 結果寫 `docs/specs/` 並連 evidence；更新總計畫／OI-02／App README／package README，入口只短記狀態與下一步。這些完成只代表C接合，不等於整個產品。

### H4｜既有 B1／B2／詳記、完整來源窗口及顧問指引

**這是採用已完成顧問，不是從零研究顧問。**先讀[CT49完整長訪談](../../.worktrees/analysis-only-agent/docs/specs/2026-09-09-ct49-fixed-long-interview-results.md)與[CT50已測配置](../../.worktrees/analysis-only-agent/docs/specs/2026-09-09-ct50-tested-profile-results.md)，找其固定來源及已接受能力；再按實際接點讀[Memory設計](../specs/2026-09-06-analysis-only-agent-memory-design.md)、[產生節奏與連續性](../specs/2026-09-06-memory-generation-cadence-and-continuity-review.md)、[即時更正成果](../specs/2026-09-06-analysis-only-agent-live-memory-results.md)及[詳記更正](../specs/2026-09-06-interview-summary-correction-routing-proposal.md)。較早文件不是推翻最新完成版的指令。

先交一張採用映射：已驗來源symbol／commit → 正常package落點 → 新App source／owner adapter → 沿用案例 → 只因新接點需補的案例。原prompt、詳記／候選、B1/B2工作規則及模型配置先保持已驗語意；JD新增工具與成稿方法另列差異。舊checkout提供來源，正式／新App不得直接import研究路徑；不整批複製另一套host、source或業務權威。

**映射已交付（2026-09-13）：**[B1／B2 與顧問方法的採用映射](../specs/2026-09-13-jd-consultant-b1-b2-adoption-mapping.md)。三項須先知道的結論：(1) 顧問層的已驗來源是 `4f94fbfb`（CT50 profile），`622e548d` 之後的 2853 行是**舊 JD 編輯器，不採用**；(2) B1／B2／C 與 Memory 相關的 13 個模組在 `309eaf21..033540ce` 全程 blob hash 相同，`adoption.json` 現有 hash 對 CT 已驗狀態同樣成立；(3) 最大差距是**完成窗口 source port**——新 App 的 `ConversationSourceService` 只有本輪 scope，B1 需要的跨輪範圍／待整併清單／游標都還沒有，且回合完成的權威改用更嚴格的 AI run record，不移植舊 `closed_turns`／`_turn_status` 推斷。施工順序見該稿 §6，下一步是完成窗口 source port。

- B1 从**已完成的訪談窗口**產生詳記及工作資訊候選；C 的本輪source不是B1完成窗口。保留原文位置、案例條件／更正、低頻工作，不建第二原話庫。
- B2 將候選整併成目前工作理解與導覽，沿既有 PublicationStore/CAS；C更正不能被晚到的舊B候選蓋回。保留已研究的詳記重抽與來源關係，不退化成每輪一段聊天摘要。
- 先核原流程與新 source port／owner／完整窗口、故障重開與背景排空的差距，再用正常套件抽出必要部分；不因旧檔大量存在就整批import，不重新發明Memory。
- 顧問指引从[工作完整分析](../specs/2026-09-09-complete-work-analysis-guide.md)、[客製化深度](../specs/2026-09-09-customized-jd-depth-and-interview-calibration.md)、[欄位寫作](../specs/2026-09-09-jd-field-and-writing-guide.md)及[品質門檻](../specs/2026-09-10-jd-product-quality-acceptance.md)映射新JD工具。
- 要會「資料不足追問、局部足夠撰寫、晚期更正、工作→JD／JD→依據核對」，不加讓LLM填滿大量內部欄位的要求。最後訪談尚未進Memory時，收尾仍核最新原話。

**完成條件：**零provider的固定完整旅程能初始化、反覆修正、保留早期工作與案例、重開續談；即時／背景資料權責一致，所有工作可排空。還不是自然品質PASS。

### H5｜App完整旅程與日常交付，再做自然验收

按[唯一收尾清單](../specs/2026-09-13-jd-app-open-issues.md)推進，不平行造第二張問題表：

| 後續包 | 最小可交付效果／驗收 |
|---|---|
| OI-01/02 | 接日常模型設定及明示啟用、完整來源閱讀、專業指引；員工能開始自然訪談，不能只開旗標 |
| OI-03/04/07 | 在支持的瀏覽器集中驗「開始→訪談→看當輪變更→更正→保存→重開」；Fetch只取得新證據後診斷；繁中IME、選區、晚回與刪除原文均實際操作 |
| OI-05 | 接已有長上下文／完整來源讀取策略；超過256祖先／缺鏈不能當原請求不存在。以有限合成長旅程驗後再跑自然長訪談 |
| OI-06 | 既定整份還原與符合條件的整輪JD撤回形成新版本；晚於該輪的修改不能被蓋掉；Memory／案例／原話不動，不做任意歷史局部拒絕引擎 |
| OI-08 | 日常啟停／缺設定／服務異常提示；包含JD、Saver、Store、Memory與歷史的實際備份還原、更新及版本不合停止；最后ADR/G6正式採用 |
| OI-09 | 先提出首份自然案例的資料、模型、呼叫數及費用上限並取得涵蓋授權；先1份，再3職位各2次＋長訪談。保存真輸入、結果、用量、首敗，不能調低標準迎合輸出 |
| OI-10 | Owner安排3名目標員工自行操作；顧問核准不是產品功能。未實做不標PASS；可先準備觀察材料 |

## 6. 實作規範與研究停止規則

- **業務規則單一：**人與LLM endpoint可不同，必須轉入同一domain／application／保存流程。Web不重算關係不變量；LLM不判交易是否成功。Current是十三表關聯rows，revision snapshot供歷史，不建立另一條整份文件JSON寫入authority。
- **標準元件、有界接合：**React／Next／MUI、FastAPI／Pydantic／SQLAlchemy／Alembic、LangChain／LangGraph／DeepAgents等以已驗版本及能力使用。沒有產品必要不自建通用repository、patch matcher、Agent loop、namespace掃描、undo engine、重試框架或額外背景服務。
- **官方依據可追：**LLM查OpenAI／Codex／ChatGPT與Anthropic／Claude；業務重試與責任查AWS；保存／框架查各自官方。文件→必要原碼／測試／版本；主張分官方事實、共同原則、本案取捨、未知。用一個vendor的實作不能宣稱所有大廠共識。
- **本題已足夠：**[官方子圖觀察](https://docs.langchain.com/oss/python/langgraph/use-subgraphs#view-subgraph-state)、[ToolMessage artifact](https://docs.langchain.com/oss/python/langchain/messages)、[OpenAI patch](https://developers.openai.com/api/docs/guides/tools-apply-patch)、[Anthropic editor](https://platform.claude.com/docs/en/agents-and-tools/tool-use/text-editor-tool)、[AWS安全重試](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)已支持本輪接法，查閱2026-09-13；套件版本／授權及限制見各責任證據。不再為同一問題廣搜，只有新反例才重開。
- **保存與錯誤：**原operation＋原意圖摘要；同key不同意圖拒絕；当前內容／revision／receipt同交易；手改autosave保持原輸入世代。回覆遺失先查原結果，不新建key重送。結果投影失败不能改稱SQL沒有成功。
- **資料與source：**所有關係／refs含同文件及用途驗證；來源讀取不可換成最新內容；無效地址和服務I/O分流；不把模型工具回覆、摘要或內部reasoning當員工原話。
- **程序與費用：**只使用已確認scope的owner／Future／host，等待者取消不等工作停止。0provider核心；MockTransport使用合成資料及離線假key，禁外送trace。Claude既有持續授權範圍是舊指定目錄，**不自動擴至新 `experiments/jd-relational-app`／package**；需外傳本批時重新核有效範圍，可用本機子代理而不阻工程。
- **技術判斷不反覆丟回Owner：**已定格式／免費開源／當輪呈現不重問。只有改變產品語意、資料權責、费用或不可逆結果才停下討論；先完成無依賴部分並給具體選項。
- **分工與收尾：**同檔一個writer；代理回報須核實。重要接合獨審，不為低風險文案寫覆述測試；每段保存首敗／結果／限制。沒有通過的測試、真模型或真人不能記完成。

## 7. 接手操作與驗收命令

先做唯讀狀態確認，不能 `git reset --hard`／clean／restore所有改動，也不要 `git add .`。工作區有大量本次之外的歷史文件與實驗dirty。

```powershell
Set-Location S:/caliburn
Get-Location
git branch --show-current
git rev-parse HEAD
git status --short --untracked-files=all -- experiments/jd-relational-app packages/consultant-memory
git diff -- experiments/jd-relational-app/src/jd_relational/ai_checkpoints.py packages/consultant-memory/src/caliburn_memory/repair.py
```

本機已驗 Python3.12.13、Node24.19.0；新App鎖定 LangChain1.4.0、LangGraph1.2.11、DeepAgents0.7.13、openai-agents0.22.0、OpenAI3.13.0。Web實際依賴以 `web/package.json`／lock 為準。這是交接基準，不聲稱長期固定或全市場最新。不要自行使用全機舊Python／npm wrapper，既有venv先不sync／upgrade。

```powershell
Set-Location S:/caliburn/experiments/jd-relational-app
$env:PYTHONUTF8='1'
# 先讀審核反例；下列session是既有回歸，CA-01/02須另補期待正常收尾的红測。
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -q -p no:cacheprovider tests/test_memory_repair_session.py --tb=short
# 相依基礎與checkpoint回歸；本次修正後只重跑受影響範圍。
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -q -p no:cacheprovider tests/test_memory_repair_records.py tests/test_memory_repair_checkpoints.py tests/test_ai_checkpoints.py tests/test_memory_read_recovery.py tests/test_consultant_memory_context.py
# 跨App/package目錄測試用App的pytest設定，保留src導入路徑。
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -c pyproject.toml -q -p no:cacheprovider ../../packages/consultant-memory/tests
```

AiRuntime接合後另選既有 `test_ai_runtime.py`、原話來源、inspection、原run查回與重啟的受影響案例；新增原生SDK wire案例驗 artifact不出站及C→read。正式schema或HTTP變動才跑對應generate/check／Web型別與build；不得手改generated檔。

真PG是獨立合成 fixture：`127.0.0.1:55436/caliburn_jd_relational_test`、PG18.6。public十三JD表＋Alembic，另 `jd_runtime_test`四Saver、`jd_memory_core_test`兩Store＋兩publication、host測試schema八表。精確連線／明示初始化及命令沿[App README](../../experiments/jd-relational-app/README.md)，不連正式DB或新建另一組「試一下」資料庫。

```powershell
# 已確認fixture就緒後才明示開啟真DB測試；不可連不上就當skip通過。
$env:JD_RELATIONAL_TEST_DB='1'
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -q -p no:cacheprovider tests/test_consultant_memory_postgres.py tests/test_ai_host_restart_postgres.py
Remove-Item Env:JD_RELATIONAL_TEST_DB
```

原 `test_memory_repair_postgres.py`只驗核心子圖；`test_consultant_memory_postgres.py`有App C測試，`test_ai_host_restart_postgres.py`現已接C資源與FH05，才構成新C跨程序驗證。Windows宿主測試在新Hidden helper跑；真正DPAPI／Win32需要該使用者token時依既有權限流程，不能改ACL或關安全檢查換PASS。

一般啟動不得 `setup()`／重建volume／清資料，後端reload保持關閉。只停止身分核實的自有helper，不按port任意kill。交接當下沒有本輪新產品服務需交付控制；舊服務是否存在接手須查證。

## 8. 下次收尾應交付什麼

H1–H3 的 **C接合可驗收單位已完成**：正常同輪讀取、取消／未知保存、兩個停止位置收尾與真新程序查回，獨審、精確commit/tag、單一結果稿及路由都已收。接著 H4、H5 按依賴完成成品，未解問題仍用既有 OI ID。

這份交接不替下一位默認費用授權。**下一位不必重問是否繼續已同意需求；從 §5 的 H4 開始，先交採用映射。**不得再把「新App接合未完」描述成「原顧問未做完」，也不要重跑已完成的 H2／H3 反例當新工作。

前次交接的文件窄核不等於程式獨審。H2–H3施工的審查與修正紀錄見結果稿，提交後另一次獨立複核見審查結果，兩者不互相冒用；沒有啟用日常模型或正式切換。
