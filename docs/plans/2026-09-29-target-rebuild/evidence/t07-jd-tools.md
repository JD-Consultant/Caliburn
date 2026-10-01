# T07：JD 按需工具與來源的施工證據

## 1. 第一切片：導覽與同範圍物件定位（2026-09-30）

承接 `79b773ee`；T03／T04／T05 前置已具備，T06 共用恢復接縫仍依原任務續做。此切片完成精簡 map 與精確下鑽的定位基礎，不宣稱完整 `read_jd` 或八入口已交付。

責任來源：[A context](../../../specs/2026-09-26-consultant-context-and-state-design.md) §3.2–3.3、[JD 工具契約](../../../specs/2026-09-29-jd-model-tool-contract-review.md)、[JD 欄位指南](../../../guides/2026-09-09-jd-field-and-writing-guide.md)、[共同工具規範](../../../specs/2026-09-27-agent-tool-contract-design-research.md)及程式／契約規範。欄位的唯一 wire 來源是 `apps/api/contracts/tools/jd-map.schema.json`；接線說明由 [JD 保存接線 §3.2](../../../implementation/jd-storage.md#32-模型導覽與既有物件定位)維護，不在此複製 schema。

### 實際效果與取捨

- 使用既有候選一次捕捉的 profile／work 修訂，投影完整 map；不保存另一份 map、不重新用模型摘要、不另設短 ID registry。
- 既有物件 identity 產生 `read_ref`，只在本次 App 提供的可見 revision 內解析；同名異物件不混淆，改名仍為原物件，刪後同名新建不能承接舊定位。
- 導覽保留未歸屬任務、成果／要求數量、全部可用集合及合法未填妥名稱。明定 preview 才取文字前綴加省略號，其餘無靜默裁切／假摘要。120 字元是可調初值，沒有宣稱已驗最佳品質。
- 查 [Azure CQRS 官方模式](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs)，借查詢投影與修改分責、共用既有儲存的基礎形式；未引入 broker、event sourcing 或獨立讀取 DB。參考資料與實際選擇不混稱廠商保證。

### 驗證

1. Typed 骨架的行為 Red：導覽與 resolver 尚未實作，**10 failed**；實作後同檔 **10 passed**。不是把缺 import／工具未裝當成行為失敗。
2. 加 schema／真 PG 後，專項 **14 passed in 1.87s**：10 unit、1 contract、3 PG。PG 覆蓋候選導航與正式隔離、刪職責後任務完整保留、跨檔案定位拒絕，以及已取消 execution 不再提供候選基底。
3. 受影響回歸：`pytest tests/unit tests/contracts tests/integration/test_jd_candidate_navigation.py tests/integration/test_jd_candidates.py -q -p no:cacheprovider --tb=short`，**731 passed in 15.70s**。使用明確 loopback PostgreSQL `127.0.0.1:55439/caliburn_t01_test`；不是本增量完整後端、瀏覽器或真模型驗收。
4. Ruff check／format **236 files**、mypy **160 source files** 通過。生成、前端型別、文件及獨立審查結果於本節接續記錄。

測試先遇到 unit／integration 同 basename 的 pytest collection 衝突；更名為 `test_jd_candidate_navigation.py` 後再跑，沒有修改產品規則或刪掉斷言。首次契約生成因 sandbox 子程序存取臨時檔的 `PermissionError` 失敗；核對既有生成器後，獲准以同一命令執行完成，沒有改生成器、手改 DTO 或下載套件。

當次未讀 `.env`、無付費外送、無 migration／依賴變動、無 production 切換。原有較廣測試證據可重用，不宣稱前次全套涵蓋此次改動。

主代理最後以既有生成器 `--check` 完成全部契約比對；前端 `tsc --noEmit` 通過。獨立 reviewer 未發現本切片可重現的實質缺陷，專項 **14 passed（3 項真 PG）**、分層 **15 passed**，另驗 200 筆集合完整性、119／120／121 字元界線、null 名稱、改名／重建及投影不污染來源。Reviewer 的整套生成因暫存權限未完成，僅同工具逐項比對本次 Python／TS／封裝 schema；不拿它替代主代理已完成的全生成比對。數量不與主回歸相加，仍未宣稱完整工具／模型品質驗收。

## 2. 未完範圍與下一步

依 Owner 的先跑通優先序，沿既有 owner 接上 JD 精確／區域／全稿讀取、來源與編輯 handler，再接 A 的完整保存閉環；不先做額外觀測平台或完整效能調校。不得用假的空來源陣列把未完成來源能力包裝為正式工具。

- 本節原待辦已由 §3 完成來源保存／核對、current_input、完整 read 及兩個寫入 handler；仍欠兩類 diff 與其餘 handler，不將增量當全部 T07 完成。
- T06 尚欠已保存但結果未明的原 attempt 核對後受控恢復，範圍見[原任務 §18](t06-agent-execution.md#18-下一個可執行切片)。不是用導航切片掩蓋恢復缺口。
- T08／T09 才提供 A 正式 Turn、控制及候選預覽；T12／T15 的廣故障矩陣／效能、T16／T17 的真 provider／長訪談留各 gate。不為本次純 mapper 重跑整套 UI 或付費品質評測。
- `read_ref` 不是寫入許可或讀過全文的憑證；map 正文預覽也不等於已閱讀完整修改目標。後續 handler 使用原契約與既有候選資格，不自行推導授權。

## 3. 第二切片：來源、按需讀取與有據候選寫入（2026-09-30）

承接 `d002095f`。依五小時 Demo 優先序，交付 `read_jd`、`revise_jd_profile`、`create_jd_task` 及來源 owner；其餘入口仍未假註冊。實際接線唯一說明見 [JD 保存 §3.3](../../../implementation/jd-storage.md#33-直接來源按需讀取與候選模型寫入t07-增量)。

### 原因、反例與改進

- 只回空來源會讓模型把未接線誤認為沒有依據；因此先保存真正直接引用，再開讀取與寫入。current_input 同身分在 Turn 完成時正式化，不用模型填來源 UUID／scope／版本。
- `store=false` 下只保存 output_text 無法接續工具；A 沿既有原生 items／checkpoint。工具 prepared command 的 nested tuple 在官方 serializer 恢復後可能成 list；因此用現有 Pydantic JSON 嚴格還原，不加入自訂 serializer／pickle 或另一份業務資料庫。
- 獨立審核發現空白 Memory title 的 `InvalidMemoryChangeError` 沒有映射，會使可修正參數錯誤中止 Turn。先加入真正失敗反例，再回標準 `invalid_arguments`；不吞基礎設施錯誤。
- 真 PG 故障注入在已写來源後拋錯，確認內容、來源與候選位置全部回退；同 prepared operation 可再進入並承接原結果，未重複業務效果。

### 驗證層級

- 全 unit＋contracts：**763 passed in 8.70s**。命令：`pytest tests/unit tests/contracts -q --tb=short -p no:cacheprovider`。
- A 組裝／原子完成＋工具組合：**30 passed in 7.47s**；`test_consultant_runner.py`／`test_consultant_completion.py`／`test_consultant_tools.py`。Runner 用 OpenAI SDK 的合成 HTTP transport，DB 和官方 checkpointer 使用真 PostgreSQL；不是已通真模型。
- 個別增量：來源／profile／task 核心此前 **26 passed**；新增故障與 JSON 接續 **5 passed**；read 投影 **15 passed（含 2 PG）**；工具組合 **17 passed**。這些與上列有重疊，不相加稱總數。
- Runner＋settings mypy 通過；生成器已生成 schema／Python／TS（Windows 暫存 ACL 以已批准的相同命令處理）。各分工的 Ruff／型別通過，最終合併檢查另記。

未付費外送。官方 OpenAI key 尚未提供至授權位置，真模型 preflight／品質保持未驗。Demo 與整個 Goal 未完成；此證據不表示八入口、UI、來源 diff 或 T08 全部控制／恢復已完成。

## 4. 第三切片：其餘項目的建立、修訂與刪除

`create_jd_item`、`revise_jd_item`、`delete_jd_item` 已接 A registry 與原生 Step 的 prepared／execute 邊界。沿原 owner 完成五類非任務建立、同項目的欄位／成果要求／K/S 關係／來源修訂，以及有明確影響規則的刪除；未新增保存系統。各分工先驗既有 domain 和契約，主線再驗真實模型工具 codec，非只各自單元測試。

- create workflow＋wire：分工交付後以正式生成 DTO 回歸；5 類 item／原結果／來源與 scope 等測例由 `test_jd_item_creation.py` 留存。
- revise owner／wire／schema：13 passed；有來源原子性、跨任務 detail 拒絕、逐項修訂与原操作重入。
- delete：真 PG 一例驗刪組保留任務、K/S 在用拒絕、同 prepared 重入不前進及正式稿隔離。
- 整合 Red：`JdWriteTools` 尚无三個 handler 注入；接線後 `test_jd_model_item_roundtrip.py` 真 PG 驗 create → JSON 保存還原 → 重入 → revise → 重入 → delete → 重入，候選／正式隔離成立。曾因測例使用錯誤 action／HTTP 欄名失敗，改成契約實際 `set_field`／`areas`，未放寬 schema。
- `test_consultant_tools.py`＋上述 roundtrip＋profile tool＋runner 合計 **20 passed in 2.67s**；tool handler／codec strict mypy 與 Ruff 通過。
- 全 unit／contracts 第一次 **779 passed、1 failed**：舊拒絕測例未補新 constructor 依賴；補齊測試組裝後該例通過。完整新回歸於後續增量記錄，不把第一次當全過。

仍未宣稱移動、兩類 diff、真 provider schema／自然品質或全部 T07 已完成。

### 接續增量：移動及完整模型 codec

`move_jd_item` 已接同一 registry／JSON codec，具體效果見 [移動切片](t07-jd-item-movement.md)。主代理串驗 create → revise → move → delete，每步先 JSON 保存還原、再同命令重入；正式稿仍隔離。受影響 workflow／wire／schema／拒絕／role routing **63 passed in 19.50s**（含真 PostgreSQL）；全部 unit／contracts **791 passed in 11.24s**。handler／codec／bootstrap strict mypy 通過，正式生成器重新同步 Python／TS／包內 schema，未手改生成物。兩類 diff 正在接入，T07 尚未勾完成；真 provider 協定已由 T06 通過，但不代表所有 JD schema 與自然模型品質均已驗。

## 5. 任務完成對照（2026-09-30 恢復後）

沿[任務表 T07 的 Red 與完成條件](../tasks.md#t07-a-的-jd來源差異按需工具)及[JDT-01～06](../../../specs/2026-09-29-jd-model-tool-contract-review.md#7-剩餘工程-gate全部待實作驗證)逐條對照既有測試；缺口只補測試，不新增機制。路徑相對 `apps/api/tests`。

| T07 Red | 代表測例 |
|---|---|
| 同名新建被當舊來源 | `unit/test_jd_navigation.py::test_ref_follows_same_identity_after_rename_but_not_deleted_replacement`、`integration/test_jd_source_tool_memory.py::test_alignment_uses_pinned_revision_and_rejects_later_same_title_replacement`、`integration/test_jd_reads.py::test_memory_citations_keep_fixed_identity_after_rename_removal_and_late_publication` |
| 人工改待核對 JD 後丟舊基準 | `integration/test_jd_changes.py::test_source_diff_is_pinned_same_identity_with_related_changes_and_no_alignment`、`integration/test_turn_jd_changes.py::test_changes_keep_original_endpoints_after_undo_and_later_manual_edit` |
| 只讀 diff 解除待核對 | `unit/test_consultant_tools.py::test_diff_is_a_read_observation_not_a_write_or_alignment`、`integration/test_jd_source_http.py::test_fixed_chain_survives_upstream_rename_and_diff_does_not_align_reference` |
| 確認後再改文字仍視為已核對 | `unit/test_jd_source_rules.py::test_text_changes_remain_pending_after_revert_until_explicit_alignment`、`integration/test_jd_source_edits.py::test_candidate_source_edit_replay_content_change_and_explicit_alignment` |
| current_input 取消仍被引用 | `integration/test_jd_source_http.py::test_only_completed_jd_evidence_can_be_read_and_no_pending_input_is_exposed`、`integration/test_turn_jd_changes.py::test_uncompleted_turn_does_not_expose_candidate_as_formal_change`、`integration/test_jd_candidates.py::test_abandonment_can_join_execution_cancellation_from_pause` |
| 全稿重貼全部關係鏈 | 沒有「整份重寫」入口（產品「不做」）；讀取端 `unit/test_jd_full_text.py::test_full_preserves_all_content_grouping_and_relationship_order`、`test_dangling_relationship_is_not_silently_omitted` |

| Gate | 對照 |
|---|---|
| JDT-01 契約與 wire | **本次新增** `contracts/test_tool_schema_strictness.py`（32 案）：A／B1／B2 全部 28 個工具都是 root object、每個 object 封閉且所有欄位 required、`$ref` 只指本地且無 sibling 與遞迴、不含 `oneOf`／`allOf`／`not`、`strict: true`，並以七種違規的反向案證明檢查會報錯；各工具自己的契約測例（`test_jd_read_tool`、`test_jd_changes_wire`、`test_jd_item_creation_wire`、`test_jd_item_revision_schema`、`test_jd_source_actions_wire`）保留。**官方 API 是否逐 schema 接受仍是 T16 的 wire gate**；實務上 A 的 14 個工具已隨四輪真模型 Turn 送出且被接受（[T08 §4–5](t08-consultant-turn.md#4-有界真產品-demo-批次執行前2026-09-30-1032-台北)），但不等於逐項驗證 |
| JDT-02 欄位與 CRUD | `integration/test_jd_item_creation.py`、`test_jd_item_revision.py`、`test_jd_item_movement.py`、`test_jd_profile_tool_write.py`、`test_jd_task_tool_write.py`、`test_jd_model_item_roundtrip.py`；同名 K／S 與相同明細文字不混淆：`unit/test_jd_navigation.py::test_same_names_and_same_detail_text_do_not_merge_identity` |
| JDT-03 定位與內容基準 | `unit/test_jd_navigation.py`（7 案，含越界／無效 ref 不退回名稱）、`integration/test_jd_candidate_navigation.py`、`integration/test_jd_item_revision.py::test_detail_reference_cannot_escape_its_outer_task` |
| JDT-04 來源粒度與確認 | `unit/test_jd_source_rules.py`（6 案）、`integration/test_jd_source_persistence.py`、`test_jd_source_edits.py`、`test_jd_source_tool_actions.py`、`test_jd_source_tool_memory.py` |
| JDT-05 刪除、移動與單次完整效果 | 刪職責保留任務、在用 K／S 拒刪：`integration/test_jd_item_deletion.py::test_area_delete_preserves_tasks_replays_original_and_rejects_used_capability`；**本次新增**同檔 `test_task_collaborator_and_condition_delete_keep_shared_knowledge_and_replay_once`，補齊模型工具路徑對任務（連明細與知識連結一併清除、共用知識保留）、協作對象、共通條件的刪除，重送同一命令不再多刪；移動與後段失敗全拒：`integration/test_jd_item_movement.py`（6 案）、`integration/test_jd_item_revision.py::test_late_domain_rejection_rolls_back_text_and_rejects_conflicting_effects` |
| JDT-06 兩類差異與容量 | `integration/test_jd_changes.py`、`integration/test_turn_jd_changes.py`（5 案，含「只有來源變更不報無變更」）、`unit/test_jd_source_markdown.py`、`unit/test_turn_jd_markdown.py`；完整 read 不靜默裁切：`contracts/test_jd_read_tool.py::test_empty_collections_full_markdown_capacity_and_storage_failure` |
| scope／kind 非法明確拒絕 | `contracts/test_jd_read_tool.py::test_illegal_selection_never_reaches_database`、`contracts/test_jd_changes_wire.py::test_cross_variant_null_unknown_and_version_arguments_never_fall_back_to_all`、`contracts/test_jd_item_creation_wire.py::test_wire_rejects_other_kinds_missing_fields_cross_variant_fields_and_app_identity` |
| 來源屬正確 field／item／detail／relation | `unit/test_jd_read_projection.py::test_task_sources_belong_to_item_detail_or_relation_never_inherited`、`test_profile_sources_are_per_field_and_only_pending_status_is_visible` |
| V17／V18／V20 | V17：`test_jd_changes.py`、`test_jd_source_edits.py`；V18：`test_jd_reads.py`、`test_jd_source_tool_memory.py`；V20（JD 導覽與局部下鑽）：`test_jd_navigation.py`、`test_jd_read_projection.py`、`test_jd_full_text.py`。Memory 側的 V20 屬 T05 |

**結論：**T07 的離線層、真 PG 與 SDK 序列化層成立，勾選。**未驗證且明確歸屬**：JDT-01 的逐 schema 官方 API 接受、JDT-03 中「map 預覽不足不准寫」「已有充分觀察不重讀」這類**模型行為**（工具只提供 `read_ref`，不強制讀過；歸 T14／T16 的情境與工具使用量測）、JDT-07 的恢復與正式效果在 A 的完整 Turn（T08／T12）、JDT-09 的同資料模型比較（T14／T16／T17）。

**驗證：**完整後端 `pytest tests` **1847 passed、2 skipped in 600.46s**（命令與環境見 [T08 §8](t08-consultant-turn.md#8-任務完成對照2026-09-30-恢復後)；跳過的是需字型設定的 PDF 渲染，歸 T13）。本節新增的 `test_tool_schema_strictness.py`（**32 passed in 1.02s**）與 `test_jd_item_deletion.py`（**2 passed in 1.60s**）在該回歸啟動後才加入，另行執行；Ruff／format／mypy 通過。
