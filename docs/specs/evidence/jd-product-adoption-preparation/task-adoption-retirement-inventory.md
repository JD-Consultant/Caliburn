# A1/A2 舊正式 JD writers／契約／入口退役盤點

2026-09-10；只讀盤點，未退役、未採用production。Topic：JD-R002／R5，正式採用設計 A1/A2 前置。Current stage：隔離核心G7、Task5唯一code施工；production仍現行code／0060 authority，0073／0074 Proposed。唯一問題：既定一份當前JD正式切換時，哪些已可達的舊JD路線必須退出，哪些共用來源／對話／基礎責任不能隨整檔刪除？

依據：`docs/specs/2026-09-10-jd-production-adoption-design.md` §3.1、§5 A1/A2/A5；`AGENTS.md`、`docs/contract-strategy.md`、ADR0060與0057、current-decisions／decision-process。0057檔頭本身仍Proposed；RAG隔離亦由現行AGENTS／0060明示，本盤點不改其狀態。未研究框架／Memory新政策、未讀Task5變動、key/env、未跑test／模型／DB／安裝或git mutation。

## Baseline 與適用範圍

實讀checkout為 `S:/caliburn/.worktrees/analysis-only-agent`，branch `codex/analysis-only-agent`，HEAD `8eec072d51e97735b22c5f0df598b67101fe570b`。主checkout `S:/caliburn` HEAD實核 `8979494dfe73634708e35a6c4b369e6af0fd8719`，root指出branch `refactor/current-only-architecture`。兩HEAD不當成同版本。

有限比較 `apps/api`、`apps/web`、`packages/job-analysis-contract` 的170個受版控檔案（排除env／lock檔）已保存逐檔兩側SHA於 [baseline hashes](task-adoption-retirement-baseline-hashes.json)。166 byte相同；下列4檔hash不同，但逐字以CRLF正規化LF後完全相同：`apps/web/src/app/page.tsx`、`packages/job-analysis-contract/pyproject.toml`、`scripts/check-codegen.mjs`、`scripts/strip-index-sig.mjs`（後二以同package為根）。故以下可達鏈在兩checkout內容一致；這不取代A1完整lock/採用版本manifest，也不把工作樹檔案自動等同HEAD blob。沒有搜尋或盤點三個指定產品樹之外的runtime。

以下路徑均相對上述checkout；「退出」指將來G6之後正式接線時不可仍可達，**不是現在刪除授權**。「拆分／映射」指責任必須由採用runtime/新DTO接住，並不要求舊實作或舊owner延續。

## 1. 唯一可達 composition 與 HTTP 表面

入口鏈：`apps/api/app/main.py:lifespan` 建 `PostgresConsultantRuntime`／`ConsultantTurnProcessor` → `app_factory.py:configure` → `api/router.py:api_router` → `api/routes/consultant.py:router`。完整prefix **`/api/v1/job-analysis/consultant-documents`**。`run_live.py`沿 `app.main:app`；不是另一份writer。`api/deps.py:get_consultant_runtime/get_consultant_turn_processor` 注入同一app.state。

下表路由位置均在 `apps/api/app/api/routes/consultant.py`。

| 路由／symbol | 真正呼叫鏈 | 未來處置／理由 |
|---|---|---|
| POST `/{document_id}/reviews/{changeset_id}`；`review_document_changes` L380 | Web `reviewDocumentChanges` → mutation admission → `workspace_review_context` → `WorkspaceReviewCommand` → `decide_workspace_changes` | **退出舊四決策HTTP路線**：accept_changes／edit_and_accept_changes／reject_changes／defer_changes。不能只移除UI；原端點不可再改checkpoint approved或workspace。 |
| PUT `/{document_id}/approved-document`；`edit_approved_document` L544 | Web `editApprovedDocument` → `_approved_document_from_edit` L109 → `apply_direct_edit` | **退出舊整份Approved DTO writer**與server-minted direct-edit evidence拼接；由已採JD保存契約承接。舊body不得仍被接受後寫第二份稿。 |
| GET `/{document_id}/export`；`export_approved_document` L588 | Web `exportConsultantDocument(force)` → reopen snapshot → `_readiness` → `assemble_approved_export_document` → `render_xlsx` | **退出**含 `?force=true`；刪readiness確認按鈕不足，HTTP也必須不可再下載舊approved稿。 |
| GET `/{document_id}/snapshot`；`get_consultant_snapshot` L307 | `reopen_document` → `_snapshot_view` → DTO | **拆分／重映射**。此單一snapshot含approved/review/readiness，也含員工逐字來源、顧問訊息與run狀態；不可整個讀取責任一起消失。 |
| GET `/{document_id}/events`；`stream_consultant_snapshot_events` L322 | 每秒reopen／revision，native SSE snapshot_changed／document_deleted | 舊snapshot/refetch與deleted語意退出或重映射；恢復／狀態責任須接新契約，非JD writer，不能誤算新的保存authority。 |
| POST `/{document_id}/answers`；`submit_employee_answer` L235；POST `/{document_id}/runs/{run_id}/retry` L276 | `_accept_answer` → `admit_employee_answer` → `processor.claim/process_claimed`；retry重用source/run | **整體runtime映射**。雖不是直接approved writer，會進模型workspace writer；不能保留這條舊agent做第二顧問。原話／run回復責任須承接，不沿用舊Store來源owner。 |
| POST `/{document_id}/calibrations/{calibration_id}`；`decide_understanding_calibration` L438 | direct_correction轉 `_accept_answer`；confirm/later runtime command | 混合來源／理解決策，非JD接受。不可把此路由當review alias刪；A2按已採runtime界面明確取代，保留原話責任。 |
| POST `/{document_id}/clarifications/{clarification_id}`；`answer_required_clarification` L507 | `answer_required_clarification` runtime command及source receipt | 同上：來源／澄清，非approved writer；需映射，不憑名字批量刪。 |
| GET／POST空suffix、GET `/{document_id}` | `list/create/get_consultant_document` → catalog | 文件身分／列表／建立責任保留於新catalog契約；舊UUID5 header-key路線不混入新create-key原子性。 |
| DELETE `/{document_id}`；`delete_consultant_document` L219 | runtime `delete_document` → tombstone／清Saver與Store namespaces | **退出破壞式文件入口**，映為既定封存／恢復；不是改名後仍呼叫delete。不得在此盤點執行刪資料。 |

`api/problems.py:EXPORT_CONFIRMATION_REQUIRED`及Web問題訊息表中的export-confirmation-required隨舊export退出。`INVALID_REQUEST`、not-found／conflict等問題基礎責任與 `app_factory.py` CORS／validation／healthz、`api/deps.py` 都是共用檔，A2逐項映射，不整檔當JD廢碼刪。

## 2. 內部 writer／派生／持久化鏈

| 精確檔案／symbol | caller／用途 | 未來退出或拆分界線 |
|---|---|---|
| `apps/api/app/consultant/run_service.py:ConsultantTurnProcessor`（workspace建置L174–214） | answers/retry processor建立StoreBackedWorkspace、catalog及backend，再交agent | 舊模型workspace產稿整條退出；受测runtime整體承接顧問，不包舊processor。該檔也管run、錯誤、source與callback，不能只刪workspace import後稱完成採用。 |
| `apps/api/app/consultant/agent.py` L220–267：`FilesystemMiddleware`、`WorkspaceToolWaveMiddleware` | `build_consultant_agent`取得既有filesystem tools | 舊通用write_file/edit_file workspace接點退出。模型不直接寫approved；但這是可達舊候選writer，必須納入退役而非只搜HTTP。 |
| `apps/api/app/consultant/workspace_backend.py:WorkspacePolicyBackend` L506（awrite L686、aedit L725、adelete L757） | agent filesystem →官方StoreBackend；mutation guard／path policy | 退出舊可寫workspace、對應mutation policy／wave protocol；不是實際OS檔案。 |
| 同檔 `build_consultant_workspace_backend` L1038／`ConsultantWorkspaceBackendBinding` L1020 | 五root CompositeBackend：default workspace、/skills、/sources、/approved、/review | 必須解除旧composite完整可達性。**共享檔**的 `EmployeeSourceProjectionBackend` L803、`_source_metadata` L996及skill接點承擔來源／只讀Skill，不可把它們當純JD檔無說明刪除；採用後依新來源reader/Skill映射。 |
| 同檔 `ApprovedProjectionBackend` L246／`WorkspaceReviewProjectionBackend` L253 | agent唯讀approved/review派生資料 | 舊approved/review投影退出，不能作新JD第二可讀真相。這些backend的download_files方法是framework projection介面，非HTTP XLSX/CSV下載端點。 |
| `apps/api/app/consultant/workspace_state.py:StoreBackedWorkspace` L133 | run初始化、snapshot、authority rebase；`ensure_initialized`、`commit_validation`、`apply_rebase`、manifest／files | 舊workspace正文及generation/resource digest/decision namespaces路線退出。不是新JD版本庫，不能沿用雙存正文。 |
| `apps/api/app/consultant/workspace_resources.py:WorkspaceCatalog` L151、`project_workspace_files` L542、`parse_workspace_files` L621；Workspace*Resource／Draft／EditableDocument | backend/state／validation把approved/source映射成資源及可寫草稿 | 舊schema/resource codecs退出；其evidence/source handle處理與新conversation來源映射分清，不複製為第二格式。 |
| `apps/api/app/consultant/workspace_validation.py:validate_workspace_payload` L611、`evidence_basis_digest` L709 | _snapshot／review/backend派生驗證與來源basis | 舊workspace語法／review有效性驗證退出；來源真實性責任必須由採用既有來源鏈承接，非刪驗證就採用。 |
| `apps/api/app/consultant/workspace_review.py:derive_semantic_changes` L360、`derive_workspace_review`、`WorkspaceReviewProjection/Group/Decision` | runtime snapshot及authority從workspace對approved派生差異 | 舊pending/review群組、依賴／stale／reject/defer記錄退出。未來可讀精確變更是新JD版本差異，不能重用這個待審流程冒充。 |
| `apps/api/app/consultant/workspace_authority.py:WorkspaceReviewCommand` L77、`WorkspaceAuthorityService.decide` L1144 | runtime `decide_workspace_changes` | accept/edit_accept：apply actions後 `workspace_authority_commit`；reject/defer改Store決策／rebase。整個review writer退出。 |
| 同檔 `prepare_direct_edit_rebase` L907、`finish_direct_edit_rebase` L938、`recover` L1094、`_finish_rebase` L1046、record/plan helpers | direct edit、reopen、review replay | **必列退出**：避免舊receipt/rebase恢復再寫approved或workspace。不是只刪decide public method。內含edit-accept source鑄造，舊政策不得延用至新JD手改來源。 |
| `apps/api/app/consultant/document_authority.py:apply_document_actions` L221、`edited_action_source_payload` L303 | workspace authority／review验证 | 舊Approved document patch／source差分算法退出；禁止當新JD兼容writer。 |
| `apps/api/app/adapters/langgraph/postgres.py:apply_direct_edit` L1049／`decide_workspace_changes` L1164 | HTTP兩writer →graph + workspace authority | 退出；包括 `_changed_employee_text` L930、旧OPKS evidence查核、source prepare/checkpoint/rebase這條舊寫入組合。 |
| 同檔 `reopen_document` L382、`workspace_review_context` L388、`_snapshot` L393、workspace namespaces／review decisions L199–214 | snapshot/events/model/review，讀時會初始化／驗證派生及recovery | 舊workspace重建/recovery接點退出。**共享檔不可整檔直接刪而漏接**：catalog、get/list/record source、source更正/quote、admit/retry、clarification/calibration、setup/connection cleanup均有非JD責任；A4整体runtime取代須逐責任映射。 |
| 同檔 `export_approved_document` L1370 | 僅已找到tests呼叫；HTTP export直接reopen，不呼此helper | 同步退役的內部approved read helper，非第二HTTP下載端點。 |
| `apps/api/app/consultant/graph.py:_apply_command` L76，branches `workspace_authority_commit` L183／`direct_edit` L199 | review/direct runtime `graph.ainvoke` | 這兩處實際寫 `approved_document` checkpoint，必須退出，不能留read-only UI卻仍接受內部command。其他source/run/calibration/result分支是共用責任。 |
| `apps/api/app/consultant/state.py:ApprovedDuty/Task/OpksItem/JobDocument` L165–312；`DocumentPatchAction/ChangeSet` L479/535 | domain／workspace／projection／export | 舊JD型別/invariant退出；`ConsultantThreadState.approved_document` L669與`ConsultantCommandContext.approved_document`舊可寫channel退出。**同檔來源EmployeeSource/Reference/QuoteAnchor、run/command receipts、理解/訪談等不可無映射整檔刪除**。 |
| `apps/api/app/consultant/views.py:DocumentReviewProjection` L63、`ConsultantSnapshot` L76、`document_review_projection_from_workspace` L138 | runtime→HTTP mapper | 移除旧approved/review/readiness shape；保留/映射顧問訊息與run/來源等責任。 |
| `apps/api/app/api/consultant_mapper.py:_document_changeset_view` L66、`_employee_workspace_diagnostic` L108、`_readiness` L129、`to_consultant_snapshot_view` L176 | route snapshot/export | 舊review/approved/export mapper退出；同函式employee_messages过滤EMPLOYEE_TURN、来源lineage、messages/run不可整份漏掉。 |

`workspace_authority_commit`與`direct_edit`以外，`ConsultantCommandContext`仍列accept_changes等Literal，但 `_apply_command`沒有相應dispatch branch；它們是殘留型別表面，不能假列成額外可達writer。前景模型的verified semantic commit不是直接approved writer。此處「雙存風險」是**將來採用後若保留兩套**；未宣稱現行approved和workspace已違反其當時權威，後者是待審工作稿、前者才核准authority。

## 3. Web入口與隱藏下載查漏

| 檔案／symbol | caller／處置 |
|---|---|
| `apps/web/src/app/page.tsx:Home` →redirect `/workspace`；`app/workspace/page.tsx:WorkspacePage`；`app/workspace/[document_id]/page.tsx:DocumentWorkspacePage` | 路徑殼可沿用；透過feature index導入library/workspace，不另留舊詳情頁。 |
| `apps/web/src/features/consultant/ConsultantWorkspace.tsx:ConsultantWorkspace` L42 | 組Conversation／Insight／DocumentReviewPanel／ApprovedDocumentEditor；exportMutation L79、普通/force按鈕L146/175及exportFilename退出。保留殼的連線/錯誤與導航責任須映新session，不能直接指新API URL便算採用。 |
| `DocumentReviewPanel.tsx:DocumentReviewPanel` L336、內部review mutation L104 | 四決策、selection、dependency/stale/blocked UI退出；`DocumentChangeEditor.tsx` 的edit-before-accept/preview同退。 |
| `ApprovedDocumentEditor.tsx:ApprovedDocumentEditor` L209、`draftStorageKey`／load/save draft、mutation L248 | 舊Approved form與localStorage draft codec退出，不能用舊cache回填新schema；不要求此盤點刪使用者cache。新候選恢復依既定新契約。 |
| `consultantWorkspaceModel.ts:documentPathLabel` L42、`workspaceSections` L129、reviewSelectionForAction/Decision L176/209、buildReviewDecision L192、toApprovedDocumentWrite L241、pruneApprovedDocumentRelations L272、reconcileDocumentDraft L301 | 舊review/approved helpers退出；**共用**buildConversationEntries L83、disclosure、run label與SSE判斷另映射。 |
| `ConsultantDocumentLibrary.tsx` create/list/delete | delete mutation L45／不可回復確認L157須退出／映封存；文件列表與詳情導航L165保留新metadata責任。 |
| `ConsultantConversation.tsx`／`ConsultantInsightPanel.tsx` | 對話、retry、calibration/clarification、理解展示；非JD review類元件，不能跟兩個editor一起無映射整刪。受測runtime整體替換後按新投影接合。 |
| `apps/web/src/shared/api/jobAnalysisApi.ts:reviewDocumentChanges`、`editApprovedDocument`、`exportConsultantDocument` | 三條舊JD API client退出，連force參數一起；其餘catalog/answer/retry/calibration/clarification/snapshot/events與Problem通用處理分開映射。 |
| `apps/web/src/shared/query/jobAnalysisQueries.ts` | snapshot/cache revision/refetch、catalog query是shared，需按新契約替換；不是單純review檔。 |
| `apps/web/src/shared/lib/download.ts:downloadBlob/downloadJson` | downloadBlob唯一已找到產品caller是workspace XLSX；downloadJson在指定src範圍沒有外部caller，是未接線helper。沒有找到CSV writer／text/csv／.csv下載入口。不能把未使用helper記成可達JSON/CSV export。 |

後端export僅 `apps/api/app/export/approved.py:assemble_approved_export_document` → `export/models.py:ExportDocument`及相關ExportHeader/Duty/Task/Opks → `adapters/xlsx/renderer.py:render_xlsx` L229，兩package `__init__.py` re-export。此整套是舊approved XLSX形狀；正式切換不保留可達下載或另開CSV替代。已刪的 `app/api/routes/export.py`／`features/export` 在hard-cut保護清單，不應從歷史復活。沒有發現現行relational JD mirror／舊job_analysis_*寫入路線；現行checkpoint approved＋Store workspace/來源不應誤標為舊SQL JD表。

## 4. Shared contract：SSOT與生成出口

唯一正式SSOT：`packages/job-analysis-contract/schema/job-analysis-workspace.schema.json`（`$defs`）；Python `src/job_analysis_contract/models.py`＋`__init__.py`，TS `types/job-analysis-workspace.ts`。package exports/types只指生成TS。`package.json:codegen:py`用datamodel-codegen生成Pydantic v2（target Python3.11是codegen旗標，非runtime採用版本）；`codegen:ts`用json2ts `--unreachableDefinitions`加 `scripts/strip-index-sig.mjs`；`scripts/check-codegen.mjs`執行生成再檢git diff。**本輪只讀未執行。** A2正式JD defs併同此SSOT，不能手修models/TS或另藏第二schema。

| defs位置／精確符號 | caller／未來範圍 |
|---|---|
| L314–398：DocumentPathReadView、DocumentPatchActionView、DocumentChangeSetView、DocumentReviewView、WorkspaceDiagnosticView、WorkspaceReviewStatus | mapper／review UI；舊待審契約退出。BlockedInterviewBranchView牽涉訪談能否繼續，須明確映射，非純顯示刪除。 |
| L414–528：ApprovedEnablerView、ApprovedDutyView、ApprovedTaskView、ApprovedOpksItemView、ApprovedOpksItemWrite、ApprovedJobDocumentView、ApprovedJobDocumentWrite、DirectDocumentEditWrite | old approved editor／route／mapper；退出舊文法與whole-document PUT，依採用JD schema映射。 |
| L529–549：ExportReadinessIssueView、ExportReadinessView；L574 DocumentReviewDecisionWrite | export readiness／review commands退出。 |
| L550 ConsultantSnapshotView：approved_document、document_review、readiness | 拆除舊三欄；同snapshot的employee_messages/messages/run等不能整份丟。 |
| L242 EmployeeDecisionSummaryView／L265 SemanticProgressView；理解／sufficiency／calibration defs | 舊review進度相依須清理；這些不是新JD authority。按已採runtime投影映射，不為保留舊畫面造第二工作理解。 |
| ConsultantDocumentCreate/CatalogItem/Catalog、EmployeeAnswerWrite、ConsultantRunStatus/Accepted、DurableRunView、NextQuestionView、ConsultantMessageView、EmployeeMessageView、QuoteAnchorView、UnderstandingCalibrationDecisionWrite、RequiredClarificationAnswerWrite、ConsultantSnapshotEvent、ProblemFieldError/ProblemDetail | 涵蓋catalog／原話／回合／錯誤，**不是整package刪除清單**。A2逐責任轉正式受測契約；尤其source refs由已採conversation契約決定，不沿用舊QuoteAnchor輸入手編政策。 |

API内部仍用state/domain types，只有api mapper/route引用generated transport；新接線應保持此邊界。`ProblemDetail`內export-confirmation-required可隨下載退出，其餘problem identifier須依新路由核，不因舊JD退役清空通用問題回覆。

## 5. 現有保護測試與將來退出驗收

只定位未跑；不是聲稱當前suite已PASS。舊行為正證應在切換時轉為新行為或移入歷史，**不能直接刪整個共用test檔來消除fail**。

| 保護檔案／具名重點 | 應承接的驗收 |
|---|---|
| `apps/api/tests/test_consultant_api.py`：test_employee_review_calibration_clarification_and_direct_edit_are_distinct L504；review_and_direct_edit_return_clear_busy_conflict L563；direct_edit_server_mints_opks_evidence L601；export_requires_explicit_force L629 | 舊review/PUT/export（含force）實際HTTP不再可達；不是只assert按鈕消失。來源／calibration／answer各自映新contract，原fixture不要使新API偽回舊snapshot。 |
| 同檔catalog/source-first/retry/SSE L318/432/471/337–411 | 共用catalog、來源保存、恢復與投影責任保留對應新測試。 |
| `test_consultant_workspace_authority.py` partial dependency/rebase/conflict；`test_consultant_durable_authority_postgres.py` L390 direct-edit rebase、L468 partial/replay、L733 receipt gap、L899 checkpoint-before-rebase、L951 edit-accept source crash、L1025 reject recovery | 確認舊workspace/review恢復無法在新process寫任何第二稿；保留已採用新JDreceipt/恢復工程證據，不照抄舊policy。 |
| 同PG檔L1130來源admission、L1164immutable/correction、L1333payload-bound idempotency、L1414setup、L1491delete；`test_consultant_workspace_recovery_postgres.py` L306source lineage、L496per-document admission | 共享資料／隔離／生命周期測試不能因review退役被整檔刪掉；delete改新封存保留資料之測法依已定設計。 |
| `test_consultant_task6_contract.py` L252/269 | 已明示checkpoint沒有舊queue，review只派生；新hard-cut要禁回舊workspace/approved契約與writers。 |
| `test_consultant_export_mapper.py`、`test_job_analysis_export_xlsx.py` | 目前舊XLSX映射/防公式注入/共享K/S等正證；下載退出後不再作新JD驗收需求，也不得默默留下舊export route來保住test。 |
| `test_consultant_api_mapper.py`、`test_consultant_foundation_boundaries.py`、`test_consultant_hard_cut.py`、`test_app_wiring.py`、`test_old_chain_removed.py` | mapper/source可見性與domain/transport邊界、唯一router/import禁止/RAG隔離保持；hard_cut L81 active0018期待依已定fresh0019調整，無遷移舊DB。 |
| `apps/web/src/shared/api/consultantApi.test.ts` L61/111；`features/consultant/ConsultantWorkspace.integration.test.tsx` L80/154/183/218/622/940 | 原review/direct/export client全部退出；dirty/recovery/晚回覆/連線狀態要由新工作面保證。 |
| `apps/web/src/features/consultant/consultantWorkspaceModel.test.ts`、`shared/query/jobAnalysisQueries.test.ts`、`src/architecture.test.ts` | shared邊界、cache新舊response隔離與模型helper切换不互相代替。 |
| `packages/job-analysis-contract/tests/test_schema.py`；`tests/test_consultant_contract.py`（review status L57、typed commands L99、edit map L123、manual fields L133、SSE L187） | schema生成無漂移、退役defs／入口不存在、新JD/source/run契約可機械驗證；不能直接手改TS以通過。 |

## 6. 提交root的精確delta／限制

1. **設計§1「舊pending/approved」是產品級簡稱，不能解讀為checkpoint pending queue。** 實際state只有approved_document；`PostgresConsultantRuntime._snapshot`從Store workspace＋approved＋source basis派生 `document_review`，Store另有decision/rebase metadata。task6_contract明確禁止舊queue。A1須包含本盤點workspace writers/backend/authority/recovery，A2取代範圍不可只列兩HTTP writers或不存在的pending table。這是補精確退出範圍，不重開產品選擇。
2. **主／隔離4項raw byte差異僅換行**，A1正式manifest須採明確checkout的bytes，不混兩套hash。沒有發現指定170檔中的內容漂移；lock差異未由本盤點驗，交root依賴清單處理。
3. **原話與手改在舊state/route/postgres/backend/mapper同檔**；舊direct edit曾鑄 `EmployeeSourceKind.DIRECT_EDIT`，新設計明說手改不能偽造訪談來源。不能把舊source工序當必須保留的authority；保留的是真原話回查／隔離責任，由新conversation reader接住。
4. 沒有current CSV HTTP入口；downloadJson無caller。只有單一XLSX route及force變體；framework backend download_files不是新增產品匯出。現有hard-cut禁止的老export/SQL JD tables不再當待刪檔，避免虛增清單。

Status：前置盤點完成，未生效的退役候選清單。Affected artifacts：僅本scratch與機械baseline hash JSON。Reopen trigger：production入口／writers／契約或baseline hash再變，或A2正式映射出現新的caller。Next gate：root併A1採用manifest／A2正式契約與successor取代範圍審查；G6仍需完整core／P3及採用manifest，之後才可正式施工。本盤點不批准刪檔、改ADR/register、資料遷移或正式採用。
