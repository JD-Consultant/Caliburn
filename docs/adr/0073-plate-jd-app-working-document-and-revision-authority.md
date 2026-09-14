# 0073. Plate JD App、同一工作稿與文件修訂 authority

- **狀態**：Proposed；2026-09-12 已由 [ADR0075](0075-relational-jd-authority-and-structured-editor.md) 取代為目前 active candidate；從未改變 production authority
- **日期**：2026-09-10
- **最新 Owner 裁決**：同意核心接線推薦，真人交付／核對先不做；原 HTML／DOCX 問答交付包改 PARKED，不列本版施工及驗收。正式契約與核心整體 review 已完成，兩項 P2 關閉；本 ADR 仍 Proposed，尚未完成 production G6 或修改 production。
- **Topic**：JD-R002/C03，連動 C01／C02
- **2026-09-10 語意契約v2**：Owner同意完整JSONB＋同PG方向，Task成果／要求平行分組、K／S完整item及單向同版引用沿[語意契約](../specs/evidence/2026-09-10-jd-semantic-contract-closure.md)。模型用issued refs、App映ID及推導反向集合；首建先保存items再read/link，兩次各自原子。新profile明示format 2，v1封存不搬移；不增加工具或關係store，不改本ADR Proposed效力。
- **2026-09-10 契約補正**：Owner 同意依責任稽核補正後接線；同一 SSOT 收斂模型單一輸入意圖、錯誤／未閉合回執動作，並固定單向保存關係及有限執行策略，詳[補正紀錄](../specs/2026-09-10-jd-responsibility-and-evidence-audit.md)。這是本 Proposed 方案的工程閉合，不使 ADR 自動 Accepted，也不把離線契約證據當成 production／自然模型驗收。
- **產品依據**：Owner 已選 Plate 免費核心、持續工作稿與差異／更正；另明確排除「目前稿／更正後」兩頁。效力見 [register](../current-decisions.md)與[審閱裁決](../specs/2026-09-09-jd-editing-and-review-working-design.md#77-owner-裁決持續工作稿保留差異與更正)。
- **設計**：[App 接線](../specs/2026-09-09-jd-editor-app-integration-design.md)。Owner 已同意持久化與執行互斥方向；本 ADR 待正式契約及整體審查完成後正式化。

> 2026-09-12 Owner 試看預覽後要求 relational rows 與結構化 JD 管理編輯器。本文保留完整 Plate JSONB、版本／receipt 及隔離實證作沿革；後續設計、review 與施工以 ADR0075 路由，不能再以本文直接推進 adoption。

## Context

員工透過持續訪談讓既有顧問理解自己的工作，顧問在某項工作資料足夠、有實質補充或更正時撰寫 JD。員工主要閱讀、指出理解錯誤，也能直接編輯。人與 AI 應接續同一份有結構、完整敘述的 JD；修改必須可見、可查前後版本，不能只靠模型自述。

舊 ADR 保留 Store 中的 JD workspace、Saver 中的 approved document，以及 semantic groups、accept／reject 與 rebase。Owner 現已選擇持續工作稿，不再提供個別待審接受／取消。保留兩份當前 JD 並自動接受，只會沿用已不需要的狀態與效力。這次改動應明確退出舊 JD writers，保留 conversation／Memory 的既有研究成果。

Plate 原生操作、保存重開、history 接點與 Python→Node→PostgreSQL 已有有限正證，另有 diff／normalization／history 反例。[證據及限制](../specs/2026-09-09-jd-editor-app-integration-design.md#1-推薦組合與證據效力)。證據支持使用框架作底座，沒有證明正式人編、所有內容 profile 或顧問品質已完成。OpenAI／Anthropic 公開契約支持模型提出工具操作、App 執行並回真實結果；沒有公開相同的 Plate／資料表內部設計。

## Decision

1. **同一工作畫面只有一份可編輯 JD。** 聊天與 JD 並存，AI 保存後更新原稿；實際差異與唯讀歷史在原畫面展開。不建立「更正後」操作頁、第二份可編稿或個別待審接受／取消。保存及看過不等於專業核准。

2. **Plate 免費核心及逐套件核對的 OSS 擴充承接編輯。** 固定 document profile、native transforms、NodeId、normalization 與 renderer；專案只接必要 JD 容器、工具及保存，不自建通用 diff、定位、相依審核或 undo 引擎。正式 value 是可序列化的 clean 文件樹；比較刪文、選取、busy 與 session history 不進 authoritative value。不引入 pending codec。

3. **同一 PostgreSQL 中由 JD App 獨占文件寫入 authority。** 保存單位是完整 immutable `jd_revision`，`jd_head` 只指向該文件目前版；`jd_operation` 保存同操作真實結果。Agent checkpoint 只保留需要的引用，不另存可寫 JD value。版本快照是讀取真相，native operations 是變更證據與同基底畫面同步材料，不靠 operation 重播重建文件。conversation、工作理解、Memory 及 canonical 原文保持既有 owner，不納入 JD 資料表。

4. **AI 與人編走同一短交易邊界。** AI 用同一既有顧問的 `jd_read`／`jd_edit`／`jd_change_read`；人編保存帶原已保存基底與自己的新 value。App 驗证固定 profile、文件範圍、引用與來源，Node 使用 disposable editor 計算並驗 normalization；計算與模型呼叫在 SQL transaction 外。提交時锁定文件 head、重讀同 operation 結果並核對預期 revision；新版、head 與成功 receipt 在同一交易提交。no-change 不造內容版，過期不套用。不能以不同 payload 覆寫同鍵結果。

5. **App 配發定位與執行身分。** 模型選用已讀的 block／selection references，不生成 document ID、operation ID、Slate path／offset 或保存狀態。引用綁定已保存 revision，過期重讀；同批不混基底。Node 僅由固定程式、固定 argv 與 JSON stdin/stdout 呼叫，不開 DB／Memory、不執行模型程式碼或任意 shell。

6. **前景 AI run 與人工保存採同文件互斥，Owner 已同意此本案取捨。** 開始前暫停新輸入、完成 dirty buffer 保存，再取得 run admission；失敗保留輸入，未發配 operation 或 writer 已停且必要回執閉合後恢復編輯。run 期間 JD 可閱讀及查差異，暫停手改，包含純訪談回合；API 也檢查 admission，不能只鎖 UI。背景 Memory 不延長 JD 唯讀。不稱跨廠唯一共識，也不再詢問已同意時點。

7. **提交與通知分開判斷。** 保存結果區分已提交、確定未變與結果未知；receipt 是否持久確認另列。模型最後一句／通知失敗不撤回已保存稿。取消或程序恢復須先確認舊 writer 停止；只對已發配 JD operation 且結果尚未閉合的工具呼叫查同 operation，僅以原 tool_call_id 補回缺失 ToolMessage，再關閉／解鎖。既有結果不重複追加；無 JD operation 的訪談回合沿既有流程結束，不等 receipt。未知效果先對帳，不能生成新操作重做。現有隔離顧問的 close 路徑尚不識別 JD 寫入，必須新增該 port 接點與故障驗收，不能直接宣稱沿用即完成。

8. **人工輸入與恢復不靠隱藏合併。** AI 新版只在 browser 與其基底一致且無 dirty buffer 時原生套入；不同版本或失敗時保留未保存輸入、明示重新載入條件，不 refetch 覆蓋。原生 undo／redo 的當次編輯結果仍須保存成後續 revision；不刪歷史，也不承諾跨重開的 session undo。另一分頁的舊稿走 revision 檢查，不擴張為多人協作、CRDT／OT 或租約平台。

9. **來源與職務品質保持原本責任。** 保存來源只記對既有原文 owner 的引用，不複製成第二來源庫；引用有效不等於每個句子已核實，手改不自動重新背書或改寫 Memory。顧問沿既有完整 JD 方法、unknown／案例／更正規則與雙向核對。工具格式正確不等於「滿分」。真人交付／核對功能依 Owner 裁決先不做，不新增角色權限。

10. **讀取與比較固定版本；交付功能延後。** current read 只讀 clean head；指定歷史唯讀。一次實際改動與任意兩版比較分開標示；完整 immutable before／after 是比較的必要資料，native operations 只作額外提示。舊 approved-only export 不接到新工作稿，不把歷史刪文當 current。[交付附件](../specs/2026-09-10-jd-export-and-consultant-handoff.md)及其 HTML／DOCX＋原始問答交付包為 PARKED，不列本版施工、驗收或缺口。重新啟動時再依明示保存版設計，不恢復舊 iCAP／A／級別格式限制新內容。

11. **切換採 fresh data、單一 composition root。** 新 migration/setup 只建立需要的 JD 結構；不搬舊 JD、不雙寫、不做 compatibility wrapper。catalog 文件身分可沿用，隔離檢查覆蓋 revision、operation 與歷史 read；本 ADR 不授權此時清空任何 DB。正式切換的完整文件刪除／恢復需與既有來源／Memory 同步定義；隔離 catalog 尚無刪除 API，不在核心編輯器補造它。一次切換移除舊 JD runtime／route／schema／Web 分支，保留受現行邊界保护的 conversation／Memory 及隔離 RAG。

## Supersedes when Accepted

以下僅列 **JD 專屬效力**；Accepted 文件保持原文，由本 successor 及索引說明效力。

| 既有決策 | 由本 ADR 取代的部分 | 保留 |
|---|---|---|
| [0060](0060-langchain-langgraph-consultant-runtime-and-durable-authority.md) §authority／文件審核 | Saver 是核准 JD 唯一 owner；AI 只能產待審；人編／接受才改 approved | 顧問／框架責任、來源／Memory 邊界、單機及 no-RAG；本 ADR 不自行採用隔離 Memory 的 production 遷移 |
| [0061](0061-compact-consultant-wire-progressive-skills-and-tools.md)／[0063](0063-hybrid-candidate-edit-tool-and-structured-final-response.md) 未被後續取代的 JD 限制 | 舊 candidate／approved final publication、review dependency 與核准文件寫入政策 | model／App 分工、真實 tool feedback、typed transport 與有界執行原則 |
| [0064](0064-deep-agents-virtual-jd-workspace-and-deterministic-evidence-anchor.md) 的 JD VFS／resource／publication | `/candidate`、`/workspace`、`/approved`、`/pending`、JD file verbs／固定 JSON resources、semantic review 投影與群組結算 | 來源精確回查與範圍驗證原則；Memory／Skill 的 filesystem 元件不因此退役 |
| [0066](0066-persistent-ai-jd-working-draft-and-semantic-review.md)／[0067](0067-deep-agents-store-backed-jd-working-draft.md) 的 JD 生命周期 | Store workspace、manifest、approved-first／rebase、derived pending、accept／reject／defer、approved-only export；禁止專用 JD table 的舊選擇 | 同文件接續、按需讀取、有界失敗、來源隔離；Saver／Store 非 JD 事實不遷移 |
| [0069](0069-shared-current-jd-working-copy-and-semantic-approval.md) 決定 1–4、6–7、11–14 中相關部分 | current↔approved 雙 snapshot、direct-edit 核准、dependency closure、approved-only export、「不增 editor」與 AI 先審後入限制 | 唯一主編輯面、訪談可續、自然聊天更正、保留 browser input、同文件版本檢查 |
| [0070](0070-consultant-workspace-ui-and-explicit-pending-edit-approval.md) Proposed 的 JD 待審方案 | 本次不採 pending 人改／接受 UI 或舊固定欄位投影為新 JD profile | 可用 Web 元件只是既有能力；不重議本案既有非 JD 範圍 |

0065／0068 的 operational budgets 不在此調整。0071／0072 的 Memory／RAG 候選不由本 ADR 批准。若 production 組合必須改 Memory authority，先有其独立 successor，再在切換計畫明列相依；不能夾帶在 JD ADR。

## Consequences

正面：员工與 AI 共用乾淨成果，每次變更可從保存版確認；編輯交给 Plate，副作用結果交给唯一 JD 交易，沒有 pending 結算或 approved rebase。人工使用不必等整輪 Agent checkpoint 才有可保存 JD。

代價：需維護薄 JD 容器／native transform adapter、跨 Python／TypeScript 契約、文件交易／receipt 及同畫面差異。整段前景 run 暫停手改會降低同時操作彈性；真正 DOM／IME、paste、history、diff 限制與取消窗口須經整合驗收。保存資料表不是成熟框架自動提供的完整產品，但比混用兩個 JD owner 更符合目前需求。

## Rejected alternatives

- **同時保留 Store workspace 與新 revision 表作 mirror**：兩份可寫真相與同步代價，違反本次切換。
- **以 Saver checkpoint 直接代表每次 JD revision**：理論可行，但目前 root／child 接線、人工命令與回合中工具結果仍需額外協調；P01 已支持較直接的文件交易。若後續整合反證此路較薄，另以證據重開，不並建兩套。
- **Deep Agents 自建文件編輯／審核器**：harness 元件不替代成熟 editor，擴大自製範圍。
- **重新以 pending＋auto-accept 實現工作稿**：保留已被 Owner 排除的生命周期，且 auto-accept 容易誤表品質效力。
- **為同時手改與 AI 增加 CRDT／OT／重基底引擎**：目前單人場景可先用 admission＋版本檢查；若唯讀代價實際不可接受再討論。

## Acceptance gate

此文件仍是待正式化的 production 架構，不授權直接改 production。[主稿 §9.1](../specs/2026-09-09-jd-editor-app-integration-design.md#91-整體接線評審包)的人工暫停與保存取捨已同意，交付延後；核心正式契約及整體交叉審查已完成，可作 S5 核心設計／隔離施工交接。[F02](../specs/evidence/2026-09-10-jd-official-profile-probe.md)與 schema／SDK 證據仍不是正式 editor 或 Agent 整合。production Accepted／G6 及下述 Memory authority 採用尚未完成；必要能力若須新通用引擎則按停止線處理。施工計畫依已核准方向拆分，真人交付不列阻塞。

第一條垂直驗收為「人編保存→既有顧問工具讀取與修改→原畫面顯示真差異→同操作中斷對帳→關頁重開」。同時驗繁中、重複文字、條件／來源保留、過期與部分失敗零發布。免費固定操作驗收與實際付費模型品質驗收分列；本 ADR 不授權付費請求、DB 重建、merge 或 push。

具體邊界由[正式 schema 附件](../specs/2026-09-10-jd-editor-contract-schema.md)承接，[六切片計畫](../plans/2026-09-10-jd-editor-core-implementation.md)只接 CT49–51 隔離顧問。依[主稿 §4.1](../specs/2026-09-09-jd-editor-app-integration-design.md#41-接合目標與正式切換邊界)，production 仍有獨立且有限的 Memory authority 正式化依賴；不透過本 ADR 偷渡不同 Python／模型／Memory 版本。本機 schema 與 SDK serialization 驗收不能代稱真 provider 接受或自然模型品質，兩者按實際驗收範圍分列。

## Sources

- [官方工具及共同編輯證據](../specs/evidence/2026-09-09-jd-app-tool-and-review-contracts.md)：OpenAI、Anthropic、VS Code 的版本／成熟度與適用邊界，未公開實作保持 unknown。
- [Plate 免費套件與授權](../specs/evidence/2026-09-09-jd-oss-plate.md)、[固定保存 P01](../specs/evidence/2026-09-09-jd-native-save-probe.md)：限定原生與交易能力。
- [PostgreSQL 16 Transactions](https://www.postgresql.org/docs/16/tutorial-transactions.html)、[Read Committed](https://www.postgresql.org/docs/16/transaction-iso.html)：2026-09-10 查閱，穩定契約；不升級 repo DB。
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)：2026-09-10 查閱；框架 checkpoint 不是外部 JD side effect 已完成的證明。
- [現行本地 admission](../../apps/api/app/adapters/langgraph/postgres.py)、[隔離顧問取消／close](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/conversation.py)：2026-09-10 唯讀核對；兩者不可冒稱已接妥。
