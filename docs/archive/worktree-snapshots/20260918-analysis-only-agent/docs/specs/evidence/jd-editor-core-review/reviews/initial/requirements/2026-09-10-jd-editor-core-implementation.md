# JD 編輯核心隔離接線 Implementation Plan

**2026-09-10 Task4完整稿效能補核：**真App反證定位同一SSOT重複遞迴驗證。[有限候選2](../specs/2026-09-10-jd-schema-validation-performance.md)經獨立Spec／quality PASS後採用，僅在原`JdSavedElement`已完整檢查children的context引用既有type條件，standalone wrappers／wire欄位／格式不變。Task4須官方重新生成、重建API快取，跑受影響contract/native/API/Web及完整r2 HTTP／表格／子清單保存與重開；候選單段計時不替代實际驗收。本項不引入新validator／schema／framework或改Task5責任，首候選生成失敗保留。

**2026-09-10 成品計畫執行授權：**Owner已要求實作[完整成品總計畫](2026-09-10-jd-product-delivery.md)。本六切片是其中P1/P2的核心依據，現在由Task 1開始隔離接線。文件入口／未保存保護等增補按完整旅程設計在相應切片前閉合；正式採用、自然模型、日常維護及真人試用不以六切片通過代稱完成。0付費及production authority gate不變。

**2026-09-10 語意契約補齊：**Owner已同意完整格式及原生JSONB＋同PG保存方向；[語意契約v2](../specs/evidence/2026-09-10-jd-semantic-contract-closure.md)固定Task平行成果／要求組、完整K／S item及同版單向引用，模型refs與保存IDs分開，首建先內容後重讀／連結。以下active切片已改用v2；有限驗證與獨立review已完成，恢復原Task 1，不重問已同意格式／資料庫。真人交付及production切換仍在原gate之外。

v1 schema、F02與原201項契約結果保留歷史效力；新profile不能直接消費v1 fixture。Task 1須用新完整樣稿fixture及關係反例重做原生／生成契約驗收。這不是舊產品資料migration，研究probe不得成為runtime import。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在既有 CT49–51 隔離顧問旁完成一個可實際操作的工作畫面：訪談與唯一可編 JD 同頁，人工與 AI 接續已保存最新版，實際差異可查、取消可對帳、關閉重開不丟已保存內容。

**Architecture:** 接合目標為隔離 `analysis_agent` 的現有 canonical conversation／Memory runtime；JD 以固定 Plate 官方插件運算 clean value，由同一 PostgreSQL 的 JD 短交易唯一保存 immutable revisions／head／operation receipts。沿現有 Next／React／FastAPI 接點建立隔離 Web，明確接 8091 的文件與 run 身分；不從 production import worktree，也不把隔離 Memory 搬入 production。

**Tech Stack:** Python 3.12.13、隔離 `uv.lock`；LangChain 1.4.0／DeepAgents 0.7.13；Node 22.23.2（Task4起隔離導入；原Task1–3 baseline為22.12.0）、Plate 53.3.11、react／react-dom套件19.2.4、Next／eslint-config-next 16.3.3；PostgreSQL；JSON Schema draft 2020-12 SSOT＋生成 Python／TypeScript DTO。Next App Router內建React／RSC另記實際版本，不視為native單測的同一runtime。

**Spec:** [主設計 §4.1／§9.1](../specs/2026-09-09-jd-editor-app-integration-design.md)、[Proposed ADR 0073](../adr/0073-plate-jd-app-working-document-and-revision-authority.md)、[正式 profile](../specs/2026-09-10-jd-plate-document-profile.md)、[三工具契約](../specs/2026-09-10-jd-app-tool-contract.md)、[正式設計 schema](../specs/contracts/jd-editor-v2.schema.json)。先讀 [register](../current-decisions.md)／[process](../decision-process.md)，上述文件與本計畫一同交接。

## Global Constraints

- 2026-09-10 全面責任稽核補充：對每個影響效果／正確性的設計主動核對 LLM／App／原生／DB owner、現行官方依據／版本／免費授權、參數負擔與具體驗收，不限 Owner 舉例。已知／可推導資料交 App；技術決策由實作者研究處理，不要求 Owner 選資料表／錯誤欄位。[本批補正](../specs/2026-09-10-jd-responsibility-and-evidence-audit.md)已將 TF／ER 參數與結果落入同一 SSOT，並固定模型說明、DB02–04 單向約束、ER03 有限策略；[離線結果](../specs/evidence/jd-contract-closure/README.md)只證設計 shape／SDK 傳遞。下列各切片仍須實際實作驗證；跨輪 context 沿 Task 3.3a，Memory locator 不列必做。不重選 Plate／工作稿或重建 Memory。

- Topic `JD-R002/C03`；本文件沿Owner完整成品授權進入隔離G7，Task 1–5已完成並獨立review通過；Task5保存點44441672後接Task6。各切片依實際結果標記，不以語意v2有限設計驗證代稱接線通過。
- Owner 已同意 Plate 免費核心＋持續工作稿、同畫面實際差異、前景 AI run 期間暫停手改（含純訪談）、同 PG 唯一 JD 保存；不再提供個別 pending accept／reject 或 accepted projection。
- 本版不做真人交付／核對功能、HTML／DOCX＋問答交付包。來源回查、AI 顧問本身的內容核對、工程驗收與交接仍在範圍。
- 施工僅限既有隔離 checkout。正式 production 切換須先完成独立、有限的 Memory authority 正式化 gate，再安排單一切換單位；本計畫不替它定案，也不讓它阻塞隔離核心。
- 0 付費模型請求。自動驗收一律固定回應／既有離線 provider transport；不得因啟動瀏覽器驗收而讀真 API key 或意外呼叫 provider。真正自然選工具、專業 JD 品質、延遲／費用另列有預算的驗收，不以本計畫綠燈代稱通過。
- 沿 `createSlateEditor`／`createPlateEditor`、官方 basic/list/table plugins、NodeId、normalization、history 與 `computeDiff`；不自建通用 diff、rebase、排序、回退、codec、表格／清單或來源引擎。
- 固定 `reuseId:true, initialValueIds:'always'`，保留原生 ID 生成；載入保存稿先驗唯一 ID。所有新 Element 的模型輸入不得帶 ID，正式 value 不含 suggestion／diff／session metadata。
- clean value、原生 operations、比較 projection 分開；原生 operations 原樣 JSON 安全保存，`computeDiff` 只在記憶體中算，不回灌或保存成正文。反例、首輪失敗及既有封存不改判、不覆寫。
- 外部 Node 只收固定 entrypoint 的 stdin JSON／回 stdout JSON；不讀 DB／Memory／原文、無主機路徑或程式碼參數，stderr 只放有界診斷。模型／Node 運算不持有 SQL transaction。
- 遵循 [contract strategy](../contract-strategy.md)：SSOT 生成 DTO，mapper 承接 transport 與內部型別；不手寫第二份 wire schema。所有新增依賴免費 OSS、exact lock，npm 安裝停用 scripts；不改 root production lock。
- 每切片先寫指定失敗測試，確認失敗原因，完成最小接線，再跑指定檢查及獨立 review。未通過不往下包裝成功；無新反證不擴充微型研究。

## 施工位置與開始條件

以下路徑以**執行 checkout 根目錄**為準。預期 checkout 為 `S:/caliburn/.worktrees/analysis-only-agent`、branch `codex/analysis-only-agent`；本文撰寫時參考 HEAD `622e548d9d37ce4f8adb2ac0f0e61ce0d7aad3d9`。執行時依 using-git-worktrees 技能核對實際 branch、dirty 與使用中的程序，不 reset 既有 `experiments/analysis-agent/README.md` 修改。設計附件及 schema 尚在主 checkout 時，先將**經 review 的同一內容**帶入執行 checkout 的相同 `docs/` 路徑並記 hash；不能 import 主 checkout／`.research-tmp` 來維持 runtime。

| 路徑代號 | 精確位置／責任 |
|---|---|
| `A/` | `experiments/analysis-agent/`；既有 Python 顧問、Saver／Store、來源與 API 8091 |
| `J/` | 新 `experiments/jd-editor/`；獨立 npm workspace／lock，只含 `contract`、`native`、`web`，不加入 production monorepo workspace |
| `S` | `docs/specs/contracts/jd-editor-v2.schema.json`；唯一可手改的 JD wire SSOT |
| `C/` | `J/contract/`；機械生成的 schema 副本、TypeScript／Pydantic DTO 及 codegen；生成副本不是另一權威 |
| `N/` | `J/native/`；固定原生 profile、有限 command adapter、Node bridge、共享 React plugin 設定 |
| `W/` | `J/web/`；Next 本地 3001，唯一 JD 工作畫面與唯讀歷史展開 |

六個切片按 `1 → 2 → 3 → 4 → 5 → 6` 驗收。Task 3 的工具可由固定呼叫驗，Task 4 的畫面可由 Task 3 已存在的服務及固定 provider 驗；Task 5 才驗完整取消／reconcile 與 writer gate。前項通過後可局部並行寫後項測試，不以未完成接點假裝端到端已通。

v2在原切片的必要接點：Task 1完成全候選grammar／關係及原生映射；Task 2以format 2保存定義與links、歷史同版解析及失敗零發布；Task 3從完整revision發配正反向refs、映射set及unset、實測先建→read→link與unknown不重複新增；Task 4讓兩組可清空但不誤拆、K／S與引用／共享影響可讀，人工copy／貼上走同一完整性邊界。Task 5在兩次首建之間取消／重開時保留已保存中間稿，Task 6整體核對。每項都有[語意契約§2–6](../specs/evidence/2026-09-10-jd-semantic-contract-closure.md#2-最小完整文件結構)對照，不新增平行施工路線。

每個 task 的通過條件包含：該切片固定測試、North Star／decision drift 核對、獨立 review 無阻擋 finding、更新其 README。本計畫開始執行須 register 明列允許的隔離施工範圍；不得憑本檔直接取代仍 Proposed 的 production ADR。

## 共用介面及生成規則

`C/types/jd-editor-v2.ts`、`C/src/jd_editor_contract/models.py` 與 `C/generated/jd-editor-v2.schema.json` 全由 `S` 生成，禁止手改。C 僅是隔離消費所需的機械生成產物，不成為第二個 current 契約；後續 production 切換須將經核准的 JD defs 納回原 `packages/job-analysis-contract` SSOT／codegen 路線，退出隔離 package 的 runtime 引用。採現有工具鏈的固定版本：`json-schema-to-typescript@15.0.4`、`datamodel-code-generator==0.71.0`；Python `jsonschema==4.26.0` 驗完整 draft 2020-12，生成 DTO 不取代跨欄位／grammar 檢查。JS 使用 `ajv@8.20.0` 的 2020 接點，禁止 coercion、defaults 或刪除額外欄位。上述版本取自現有 lock，不把新安裝視為已完成。

| 邊界 | SSOT 公開 defs／具體 port |
|---|---|
| 模型可見 | `JdReadModelInput`／`JdEditModelInput`／`JdChangeReadModelInput`；只有 `jd_read`／`jd_edit`／`jd_change_read` 三個 JD 工具 |
| Python runtime | `JdReadRuntimeRequest`／`JdEditRuntimeRequest`／`JdChangeReadRuntimeRequest` → 對應 `JdReadResult`／`JdEditResult`／`JdChangeReadResult` |
| 手編保存 | Browser `JdManualSaveClientInput` → Python adapter 組装 `JdManualSaveRequest` → `JdManualSaveResult`；document／digest／profile 由 server 映射，不冒充模型 tool call |
| Node transform | `JdPlateTransformRequest` → `JdPlateTransformResult`；`JdResolvedEditCommand` 只供 App→Node，不提供給模型 |
| Node 完整 value 驗證 | `JdPlateValidateValueRequest` → `JdPlateValidateValueResult`；人工稿走此入口，不造 edit／no-op command |
| Node 選取唯讀驗證 | `JdPlateReadSelectionRequest` → `JdPlateReadSelectionResult`；固定 read-selection entry，驗 same-block range／取得 native fragment，不改正式 value |
| 文件／變動 | `JdDocumentValue`／`JdActualChanges`／`JdWriteResult`；`profile={format_version:2,engine_profile:'jd-plate-clean-v2'}` |

上表是 HTTP／tool／Node **adapter** 的 wire signature；`JdService` 不直接 import generated DTO。固定責任為 `jd_contract.py` 驗 envelope／映射，`jd_types.py` 定純 Python 內部 typed scope／query／intent／view／outcome，`jd_service.py` 組合運算及交易，`jd_engine.py` 接固定 subprocess，`jd_store.py` 唯一擁有 JD SQL。內部方法為 `read(scope:JdScope,query:JdReadQuery)->JdReadView`、`edit(intent:JdEditIntent)->JdWriteOutcome`、`change_read(scope:JdScope,query:JdChangeQuery)->JdChangeView`、`manual_save(intent:JdManualIntent)->JdWriteOutcome`。query 表示 current／既存 revision／target／selection 的有限讀法；intent 持有已解析 scope、operation／digest／base、七種有限命令或完整人工 value；view／outcome 持有實際 revision／保存結果，最後才由 mapper 產生上表 DTO。不另造 JSON Schema、序列化協定或泛用 command bus。

`JdToolSession` 於 Task 3 定義，僅保存已發配引用、tool binding 與恢復所需身分，不保存另一份 current JD。瀏覽器讀取也經相同內部 read/change 方法，由 HTTP adapter 注入 catalog scope；不偽造 AI run 或 tool call。內部 port 不要求讀者必有 AI run。

隔離 package 名稱固定 `@caliburn/jd-editor-contract`、`@caliburn/jd-editor-native`、`@caliburn/jd-editor-web`。C scripts 提供 `codegen`／`check-codegen`；N 的 `build=tsc -p tsconfig.json`、`test=vitest run`；W 的 `dev=next dev --hostname 127.0.0.1 --port 3001`、`build=next build`、`test=vitest run`、`typecheck=tsc --noEmit`、`lint=eslint`。測試工具沿現有 lock 的 TypeScript5.9.3／Vitest4.1.11（Task1已補官方安全修正）／jsdom28.1.0／Testing Library React16.3.2／user-event14.6.4。Task4可補Playwright1.61.0作隔離browser測試依賴，非product runtime；不得從root複製舊Vitest4.1.9。

## Task 1：同一 schema 與官方原生文件可執行

**完成：**[實作／初審／修正／複核證據](../specs/evidence/2026-09-10-jd-editor-task1-results.md)，68 native／27 Python、codegen/check/build通過，R1/R2 CLOSED。保存点`88eda480`／`jd-editor-core-task1-20260910`。原生與契約限定範圍完成，不代稱後續DB、DOM或模型驗收。

**Files**

- Create：`J/package.json`、`J/package-lock.json`、`J/README.md`。
- Create：`C/package.json`、`C/pyproject.toml`、`C/uv.lock`、`C/scripts/codegen.mjs`、`C/scripts/check-codegen.mjs`、`C/types/jd-editor-v2.ts`、`C/src/jd_editor_contract/__init__.py`、`C/src/jd_editor_contract/models.py`、`C/generated/jd-editor-v2.schema.json`。
- Create：`N/package.json`、`N/tsconfig.json`、`N/src/profile.ts`、`N/src/react-profile.tsx`、`N/src/validate.ts`、`N/src/transform.ts`、`N/src/read-selection.ts`、`N/src/bridge.ts`。
- Create tests：`N/tests/profile.test.ts`、`N/tests/transform.test.ts`、`N/tests/read-selection.test.ts`、`N/tests/contract.test.ts`、`C/tests/test_schema_contract.py`；`J/fixtures/r2-canonical.json`、`J/fixtures/expected-task8-move.json`、`J/fixtures/empty-mark.json`。
- Modify：`A/pyproject.toml`／`A/uv.lock` 僅新增本地 `C` DTO 依賴與已鎖 validator；既有模型／Memory 套件版本不變。

**Interfaces**：`createJdEditor(value:JdDocumentValue)`、`validateJdValue(request:JdPlateValidateValueRequest):JdPlateValidateValueResult`、`transform(request:JdPlateTransformRequest):JdPlateTransformResult`、`readJdSelection(request:JdPlateReadSelectionRequest):JdPlateReadSelectionResult`；只實現 profile 的有限 grammar／ID／props 驗證及七個 command 對原生 API 的接線。`react-profile.tsx` 對應 `/react` 官方插件，不能重註冊 plain list/table。bridge 只有 App 固定選擇的 argv `transform`／`validate-value`／`read-selection` 三入口，各收上表 schema；不是模型可指定 argv。

v2增加同一candidate的有限ID→item索引及Task端點檢查，AI與人工validate-value共用。模型`knowledge_refs`／`skill_refs`在Python映為Node的`knowledge_ids`／`skill_ids`，unset欄名同樣映射；不能共用兩種不同語意的properties DTO。Task1不負責發配opaque refs或操作DB。研究probe只作案例與證據，正式validator在`N/`接線，禁止import probe實作。

- [x] **1.1 建測試與 fixture。** 使用`docs/specs/evidence/jd-semantic-native-probe/fixture.json`及其`fixture-mapping.json`／`fixture-statistics.json`：完整r2文字／marks及來源節點保留，8個Task各有两組，5 K／5 S完整item，兩張K／S表格外框明示退役後剩1張基本資料表。新增links是合成測試配置，不當已核實職務事實。來源handle改用測試會實際發配者，在`J/fixtures/source-map.json`留對照。單Task8 move的完整expected用`task8-move-full-expected.json`（固定oracle），不得混用先copy再move的F03-C after；原生綜合實測見F03封存結果。v1／F02不改、不直接拿來當v2。先加入下表assertions，再執行`npm run test -w @caliburn/jd-editor-native -- tests/profile.test.ts tests/transform.test.ts tests/read-selection.test.ts tests/contract.test.ts`，預期缺正式模組／功能而失敗。

| 固定測試 | 必須斷言的完整結果 |
|---|---|
| `profile_roundtrip_full_r2_v2` | canonical→JSON→fresh editor全值相等；1張基本資料表、Task4子清單、Task8月檢限制、8組成果／8組要求、5 K／5 S、當前所有ID／source refs／links保留。v1→fixture的38個外框ID退役另看固定mapping，不以純文字相等替代重開全值相等 |
| `reject_invalid_clean_value` | 重複 ID、保存稿缺 ID、未知 leaf `score`、suggestion／diff metadata、非法 Task nesting、node null／undefined 全拒絕；原輸入不改。空 `p`、無 Duty Task、空 leaf 的合法 mark 接受 |
| `all_seven_commands_are_native` | 每個 union 分支至少一個固定 before／command／expected after；同時測完整 `Task8` move、Duty unwrap 保留標題與子工作、刪除只刪明示 subtree、插入所有新 Element ID 與現存互異 |
| `selection_is_resolved_by_app` | 重複繁中文字串只改 App 發配的固定 selection；無 selection 不做 first-match；錯 target 或跨 block range 拒絕 |
| `batch_failure_discards_candidate` | 第 1 command 改目的段、第 2 target 不存在；failure 不帶 candidate value；呼叫者 baseline 全值不變 |
| `native_operations_remain_json_safe` | 取消 bold 捕真 `set_node`，`newProperties` 不含該 key；普通 JSON 往返後對 fresh baseline apply 得 exact after；不產 codec |
| `validate_value_is_not_a_fake_edit` | 完整人工 value 走 validate-value，同 profile 原生 normalization 後驗全文／ID／props；記真正 normalized value／operations，不加入假 command。非法 value failure，不回部分稿 |
| `read_selection_is_read_only_and_exact` | 固定 canonical value＋Plate 真 range，原生驗同一支持文字 block 並 `editor.api.fragment` 取得 exact fragment／target_id；無正式內容／操作發布。跨 block、越界、錯型別，或載入 normalization 使 canonical value 改變均拒絕；不模糊搜尋、不修正文後返回近似選取 |
| `single_intent_properties` | set／unset 同欄位在 App／Node 入口拒絕，正式value不變；模型attributes拒絕，saved attributes仍可載入。numeric span set同步既有對應HTMLkey、unset不讓舊fallback復活、保留另一維；同批第二command依當時cell而非舊base運算。依模型附件三例驗完整合法table，不能只驗props字典 |
| `semantic_groups_and_relations_v2` | 每Task恰一成果／要求組，未知empty p合法；同版K／S端點、種類、唯一ID／links與人工全值同驗；原生move/copy保留應保留內容、複本內引用映射不改組外；刪仍被引用item／祖先或單unwrapTask拒絕，明示同批解除／改接或展開兩組再Task才可發布；v1不當v2載入 |

- [x] **1.2 建 schema 生成命令。** `C/scripts/codegen.mjs` 從 checkout 的 `S` 讀取，機械複製及生成兩端 DTO；Python 以 `--output-model-type pydantic_v2.BaseModel --target-python-version 3.12 --strict-types int --disable-timestamp`，TS 以 `--unreachableDefinitions` 保留所有公開 defs。`check-codegen` 在臨時輸出目錄生成後逐檔比 bytes，不改已保存生成物以求過測。assert 全部上表公開名稱可 import，`JdWriteResult` 條件仍以原 schema 判定。
- [x] **1.3 固定免費依賴。** `platejs@53.3.11`、`@platejs/basic-nodes@53.0.0`、`@platejs/list-classic@53.0.0`、`@platejs/table@53.0.9`、`@platejs/diff@53.0.0`、React／DOM `19.2.4`；其餘 engine transitive 以 F02 lock 為基準核對。只在 `J/` 以 `npm install --ignore-scripts` 產生獨立 lock；同時保存 exact metadata／LICENSE 清單。`diff` 的原衍生碼及雙授權界線照 F02 盤點，不把全部泛稱 MIT。
- [x] **1.4 接原生運算。** 由同步 onChange 捕捉真 operations；按序將 command 接到官方 insert／delete／set／move／unwrap／range transforms。只做已定 profile 的 grammar／ID／欄位檢查；normalization 造成的真改動也在結果內。任何 command throw 丟棄整個 disposable editor，不稱框架已 rollback。bridge 編譯為固定 `N/dist/bridge.js`，stdout 只有一份 validated result，非法輸入／異常只回 schema error。
- [x] **1.4a 接固定選取讀取。** `read-selection` 收 SSOT `JdPlateReadSelectionRequest={profile,value,range}`；canonical 載入若被 normalizer 改變立即拒絕，不回修過的 value。原生查同一支持 block、驗 range 並呼叫 `editor.api.fragment`；success 用 SSOT `{ok:true,target_id,range,fragment}`，failure 沿既有 engine error result，沒有 value／operations 寫入結果。這是有限唯讀 native 接線，不能塞進 validate-value overload 或偽装成 edit/no-op。
- [x] **1.5 驗收。** 在 `J/` 執行 `npm run codegen -w @caliburn/jd-editor-contract`、`npm run check-codegen -w @caliburn/jd-editor-contract`、`npm run build -w @caliburn/jd-editor-native` 與上述固定測試；Python 在 `C/` 執行 `uv run pytest -q tests/test_schema_contract.py`（同表 fixtures，於本切片建立）。生成器、Ajv、Pydantic 與原 schema 接受／拒絕有差異時，以原 schema 為準，修 mapper／validator，不手改生成物。
- [x] **1.6 收尾。** 記錄實際版本、source/hash、首個失败及未驗 DOM。review 通過後只提交本 task 檔案，commit `feat(jd): add isolated canonical contract and native editor`。

**停止線：** 原生插件會丟失合法必要內容而有限官方接法無法修正、需要自訂 content normalizer／通用 importer／diff 補丁，或 schema 必須縮減已同意的完整 JD 才能過測；停在具體反例，不加新探針。

## Task 2：同 PG 唯一工作稿、revision 與回執

**完成：**[實作／PG故障／初審及R1複核](../specs/evidence/2026-09-10-jd-editor-task2-results.md)，130項原完整驗收及修正後14focused通過；Spec PASS／quality APPROVED。保存点`23bf0161`／`jd-editor-core-task2-20260910`，20個本task檔案。Task3真來源binding、Task4/5 DOM／admission／取消仍未驗。

**Files**

- Create：`A/src/analysis_agent/jd_contract.py`、`jd_types.py`、`jd_engine.py`、`jd_store.py`、`jd_service.py`。
- Create tests：`A/tests/test_jd_engine.py`、`test_jd_store.py`、`test_jd_postgres.py`、`jd_process_worker.py`。
- Modify：`A/src/analysis_agent/api.py` 的 `open_service`／lifespan、`A/src/analysis_agent/service.py` 的文件建立 composition、`A/src/analysis_agent/catalog.py` 的 `create_document` session 接點；`A/README.md`。

**Interfaces**：adapter 消費 Task 1 DTO／bridge，經 `jd_contract.py` mapper 接上述內部 ports。`JdStore` 只擁有主設計 §5.4 的 `jd_head`／`jd_revision`／`jd_operation`；`JdService` 產內部 view／outcome，mapper 才回 wire 結果。API composition 沿用 catalog 同一 engine，不能另開第二 DB URL。來源驗證 Task 3 注入，Task 2 只使用固定 synthetic owner。

- [x] **2.1 建交易失敗測試。** `test_jd_postgres.py` 僅在已明確設定的 loopback `Q019_TEST_DATABASE_URL` 執行；每測建立唯一測試 document，不重建／清空共享資料庫。沿既有 opt-in PG fixture，沒有 DSN 記 SKIP，不能以 SKIP 宣稱保存驗收通過。

| 固定測試 | 精確判準 |
|---|---|
| `create_has_canonical_initial_head` | catalog 文件與初始空 `p` 的 head 可讀，同文件 revision 複合外鍵；不能觀察到無基底 head |
| `commit_replay_and_conflict` | 插入一段後，同 operation／digest 回完全同一 receipt、只有一內容版；同鍵不同文字回 `operation_conflict`，原 receipt／head 不變 |
| `no_change_and_terminal_failure` | 相同 value 回 no_change，revision 數不增；stale／target_missing／engine_failed 終局回執重開後原樣返回，Node 不再執行 |
| `two_connections_one_winner` | 真兩連線 barrier 同 base，不同 operation 競爭；一個 committed、一個 stale；revision/head/receipt 精確一致，非僅順序呼叫 |
| `rollback_and_unknown_are_distinct` | revision insert 後、head update 後、receipt insert 前逐点注入 transaction exception：均 rollback；commit 確認前失聯只有 outcome_unknown，不能先稱未保存 |
| `fresh_process_receipt_first` | 子程序提交後在回覆前退出；另一程序同 operation 查回已提交結果、不再插入；普通 JSON snapshot／operations 與原值全等 |
| `scope_and_missing_document` | 文件 B 不能用 A 的 revision／operation；不存在 catalog 文件的 JD 讀寫拒絕，不只是 UI 隱藏；不把只有孤立 JD row 當有效文件 |
| `single_direction_revision_constraints` | 即時 FK 下 revision→receipt→head 可提交，producer反查唯一；兩個 no_change 可指同一base，第二個committed producer不可指同版。初版中途失敗無半成品；origin／parent／same-document／receipt與欄位錯配在指定層拒絕 |
| `net_zero_and_full_value_equality` | 使用PG JSONB = 驗完整value；陣列順序／重複項、marks、props、refs變更不能被containment吃掉。no_change不更新head、不造版、native_operations=null且affected IDs=[]，不發布暫時淨零操作 |
| `closed_vs_unconfirmed_failure` | bound＋unconfirmed failure為unchanged但只能reconcile；成功保存terminal failure後原樣重播，不因額度改next_action。read_failed走typed stop；busy未配operation；conflict不覆寫原row |
| `manual_snapshot_has_no_invented_operations` | 人工committed保留不同before/after完整快照；native_operations=null、affected IDs=[]表示未提供可靠定位，不當no_change。candidate normalization紀錄不冒充baseline→manual差異；人工事件仍計入跨輪通知 |

- [x] **2.2 執行紅燈。** 在 `A/` 執行 `uv run pytest -q tests/test_jd_engine.py tests/test_jd_store.py tests/test_jd_postgres.py`，確認未實作的接點失敗；PG 不可用則完成離線部分並明列唯一尚缺的 PG 驗收，不改用 SQLite 充數。
- [x] **2.3 接固定 subprocess client。** `jd_engine.py` 以無 shell 的固定 argv 啟动 Node；validate request／response，timeout／取消 terminate 並 reap，stdout 截斷或超界回有界錯誤。依[ER03唯一策略](../specs/evidence/2026-09-10-jd-error-recovery-contract-closure.md)每個明示執行一次attempt、不自動重播，Node起始控制預算30秒、terminate／kill回收各5秒；計時不重設，OS spawn不可中斷限制須明列。限額以完整 r2 及有明示規模的 stress 批次實際 wall time／bytes 記錄與驗證；schema 未定命令數上限，不把實驗批次規模當產品最大值，不任意截短 JD。逾時但尚未證明程序停止不能解writer gate；Node 不知道 DSN、canonical 原文或付費模型設定。
- [x] **2.4 實作唯一 SQL transaction。** 欄位／nullable／PK／FK／部分UNIQUE／CHECK／mapper核值固定依[DB契約補正](../specs/evidence/2026-09-10-jd-storage-contract-closure.md)，不另存revision.producing_operation。catalog 的 `create_document(title,*,session=None)` 增有限既有 session 接點；新文件由 composition 在同一短交易建立 catalog／空稿 revision／head，舊無參數呼叫仍沿原行為，不更動原文／Memory。改稿依 receipt-first → 交易外候選 → lock head row → 再查同 operation／digest → 核 base／head → 同交易 revision→receipt→head→commit。`no_change` 與已知失敗只寫 immutable receipt，不造內容版；已終局不得覆寫。request digest 含 document／base／commands（含明示來源）／profile，不含時間／隨機候選 ID。SQL各明示階段一次attempt、總控制預算30秒，沿現有connect5／statement10／lock5秒收斂剩餘時間；不把statement timeout當transaction總上限。確認rollback才可記失敗receipt，unknown只對帳，故障映射與UI恢復依ER03。測試前核實實際PG16版本／logged tables／fsync／synchronous_commit，不推定設定已正確。
- [x] **2.5 接完整人工 value 保存。** `JdManualSaveClientInput` 僅含 `{request_key,base_revision_ref,value}`；browser App 以 `crypto.randomUUID()` 配 key，Python 以 route document／此 key 綁 submission，計算 exact payload digest 並注入 profile／origin，映成 `JdManualSaveRequest`。不加預約 ID endpoint／新 identity store。人工與 AI 共用 scope、base、profile、來源、receipt 與交易邊界。以 `JdPlateValidateValueRequest` 走 `validate-value`；結果 normalization operations 是從送入的人工 candidate 起算，不能冒稱 authoritative baseline→人工稿的逐鍵操作。人工 actual_changes 保留 exact before／after、origin=manual、`native_operations:null`，不補造 events、不靜默修改舊 revision。

人工full-value沒有可靠baseline定位時，`affected_element_ids=[]`只表示未提供定位，不能解讀為沒有變更；不轉用candidate normalization的ID清單。committed／不同revision及完整前後快照仍證明有改，通知必計入事件。這沿既有空array／null契約與完整快照fallback，已經有限review核對；不為人工保存新增diff引擎。

- [x] **2.5a 提供既有歷史的唯讀接點。** 依[跨輪通知設計§6](../specs/2026-09-10-jd-model-view-change-notice-design.md#6-三工具是否需要改-wire)，同store提供revision→唯一creating committed receipt、同文件ancestor區間counts及最新四事件的有限typed read ports。initial無producer、no_change不進建立事件鏈；核scope／直接parent，不以created_at猜lineage。不新增表／已讀服務或公開工具，Task 3再映成既有change_refs語意。驗manual→manual改回仍有兩事件、混ai/manual與非祖先拒絕。
- [x] **2.6 驗收及提交。** 重跑 2.2；檢查每個測試實際輸出 head／revision／receipt 的完整內容及 fresh-process 結果，`A/README.md` 記 fresh setup／文件 scope 與不存在文件拒絕。本Task不驗封存或完整生命週期；更名／封存／恢復沿下方Task 4／5增補及P5。永久刪除已由成品計畫PARKED，不列Memory正式採用前提，也不清空共用DB；各測試使用唯一文件身分。review 後 commit `feat(jd): persist isolated working revisions and receipts`。

**停止線：** 需改 Memory／Saver／Store 的 ownership、operation 已提交卻要新配 ID 重做、或只能靠雙寫舊 approved document 才工作，停止該接線；不是本計畫自行正式化 Memory。

## Task 3：同一既有顧問的三工具、已發配 refs 與來源

**取消接點有限增補：**依[已審查 lifecycle 設計](../specs/2026-09-10-jd-native-process-lifecycle-design.md)，本 Task 只將同文件 stop Event 實際傳至 JD wrapper／service／engine，並在 Node 前保存 exact operation binding；unconfirmed／reconcile_operation 保留 pending 且停止下一 intent／模型迴圈。可窄改 `jd_service.py`、`jd_engine.py` 的 keyword-only cancel forwarding。完整 Popen owner、Windows Job／mutex、manual descriptor 與 cleanup／重開證據留 Task 5；不注入空 owner 後宣稱已追蹤程序。

**初審修正範圍：**[T3-R01–04](../specs/evidence/jd-editor-task3/review.md)屬原 Task3 的實際供給／發配要求。R04 可窄改 `A/src/analysis_agent/sources.py`，提供當次原 `ConversationReader` 成功讀取的觀察接點，供既有 JD source acquisition 核對真正返回內容／scope；不改 canonical source window、Memory policy／保存 owner、不新增可寫來源服務。其餘修正沿既有 session／最終公開 middleware／通知 helper，僅跑具體反例與受影響回歸。

**3.3a前置設計已閉合：**依[跨輪通知設計](../specs/2026-09-10-jd-model-view-change-notice-design.md)及[獨立review](../specs/evidence/2026-09-10-jd-model-view-design-review.md)實作：先納§6.2兩處SSOT description並重生／驗最終request；shape不變。最近成功返回請求的有限manifest與AI response同model checkpoint，root／child共用；每次compaction投影後重加有界App資料通知。事件基準不冒充內容已讀，16KiB／4明細／2KiB預覽是本案起始值，沿原token／tool預算。MV01–17／19在本Task實驗，MV18取消傳遞留Task 5；本段不宣稱已通過接線。

**Files**

- Create：`A/src/analysis_agent/jd_tools.py`、`jd_references.py`。
- Create tests：`A/tests/test_jd_tools.py`、`test_jd_references.py`、`test_jd_sources.py`、`test_jd_provider_binding.py`。
- Create：`A/src/analysis_agent/jd_context.py`有限通知helper、`A/tests/test_jd_model_view.py`、`test_jd_model_view_recovery.py`；不得另造同步／已讀服務。三工具description由同一SSOT供给。
- Modify：`A/src/analysis_agent/api.py` 的 `MessageInput.jd_selection`／既有 run route；`service.py` 的 `_context`／run selection admission；`conversation.py` 的 `ConversationState`／`TurnState` 有限 run selection context 及 `build_conversation` 工具保留名稱／factory identity 核對；`A/README.md`。

**Interfaces**：`JdToolSession` 持有 factory-built `tools` 三件、`read_tools` 兩件及 checkpointed binding；呼叫 Task 2 的 `JdService`。工具可見 schema 只取三個 `*ModelInput`；runtime context 包含 saved input／run／AI message／tool call，不能加到模型參數。

**固定 provider binding：**第一版只接 §4.1 已選 CT49–51 OpenAI Responses runtime。由同一 SSOT 抽取各 ModelInput 與其引用 defs（保留內容，不自行編譯成跨廠 subset）；factory 的三個 `BaseTool(args_schema=dict)` 保留在 ToolNode。`JdToolSession` 的官方 `wrap_model_call` 以 `request.override(tools=...)` **只替換命中原 factory instance identity 的三個 JD model-view 項目**，送原格式 `{type:'function',name,description,parameters,strict:false}`；name 沿同一工具，description 固定取 SSOT 對應 ModelInput.description，parameters 為完整抽出 schema；不得另手寫一份模型說明。其他工具原 instance 保留，不設全模型 `strict=False`，不更改 Memory／provider／parallel_tool_calls。`convert_to_openai_tool` 官方 raw function 直通可保留 `$defs`，避免 BaseTool converter 的 dereference／循環剪枝。沒有新 Agent、工具執行層或通用 compiler。

此為完整參數形狀下的明確 compatibility 選擇，**不是官方推薦所有工具 non-strict**。OpenAI strict 的 subset 與 Anthropic strict 的遞迴限制不同，不能將 App full schema 直接稱為兩家 strict 通用；省略 strict 也不能假定是 non-strict。代價是 provider 不保證參數符合 schema；`jd_contract.py` 必須在任何 operation／Node／SQL 寫入前驗完整 ModelInput，再驗 refs／scope／source／base。dict args_schema 的 BaseTool 本身不驗輸入，不能漏掉這一步。固定 serialize 已證實最終 SDK request 的三份 parameters 全等、JD strict=false／非 JD 仍省略；尚未證真 provider 接受／自然模型品質，見 [原碼與實際輸出](../specs/evidence/jd-contract-schema/provider-wire-README.md)。

- [x] **3.1 建紅燈與固定呼叫。** 先實際呼叫 `jd_read({})`，在返回 `targets` 選 fixture 的 Task8 正文 element，取其 `target_ref`；另呼叫 `ConversationReader` 取得實際 saved input 的 source handle。組 `JdEditModelInput.commands` 同批兩命令：`replace_block_content` 用該target及 `content=[{text:'僅對約定服務執行每月檢查；異常依既有故障處理程序交接。'}]`；`set_properties` 對同target明示 `source_refs` 為需保留的原有相關refs加新handle。沒有頂層來源集合，App僅收本批明示附著聯集。不能硬寫字串跳過 read。執行 `uv run pytest -q tests/test_jd_tools.py tests/test_jd_references.py tests/test_jd_sources.py`，先見缺接點失敗。

- [x] **3.2 驗並接 references。** `jd_read({})` 取得 current_base；明示 revision 讀即使碰巧為 head 仍 read_only。refs 綁實際 saved revision／read 種類／target；selection 只取同一支持文字 block 的實際選取。有限 read pagination 返回同 revision continuation，change_read 的 continuation 則綁原確切比較，不能用新 head 偷換後頁。continuation 本身無寫入權；**current 續頁可對該同一 base 新讀到的內容發出 current_base targets**，仍須提交時 head／base 檢查；history 續頁只讀，不升格或換 head。固定測試逐頁收齊原完整內容，current 後頁 target 可按同 base 規則寫、history 後頁 target 不可寫。用既有 checkpointed tool result／binding 驗「已發配」，不建泛用 token／模糊搜尋服務。
- [x] **3.2a 接首次 selection 發配。** 本切片先在既有 `POST /documents/{document}/runs` 的 `MessageInput` 加 optional `jd_selection`，shape 只引用 SSOT `JdSelectionCaptureClientInput={base_revision_ref,range:SlateRange}`，保留其他原欄位語意。API admission 先驗該 base 仍是 current head；`jd_engine.py` mapper 用 Task 1 的固定 `read-selection` 及 `JdPlateReadSelectionRequest/Result`，原生核同一支持文字 block／range 並取得 fragment，再按 admission 邊界重檢 head，不能由 Python 自製 range matcher 或用假 edit 取文。把 document／本次 run／已保存 input／base／block／range／fragment 的有限 selection context checkpoint 在當次 App runtime，經 SSOT 的 `JdReadRuntimeRequest.jd_selection` adapter 映到內部 read port；不是把選取內容拼进員工原話，沒有第二份 Memory／token store。`jd_read({})` 根據此 context 發 selection_ref 給模型，後续範圍過期依既有 base 規則拒絕；純聊天不帶 selection、沿既有流程，不能沿用上一 run 的選取。Task 3 先以 Task 1 已有的固定 Plate editor 原生選取產生 range，經實際 API input／admission／jd_read 取得 ref，絕不預造 selection_ref；真 browser capture 端到端列 Task 4，不當 Task 3 的退出前提。
- [x] **3.3 驗並接來源。** 向現有 `sources.py` 的 `ConversationReader`／既有 Memory read owner 解析；同 run 已保存 current input 可用，歷史 extraction window 仍須 completed／safely closed。跨文件、缺 checkpoint、未讀／捏造 handle、把 ToolMessage 當員工原話均拒絕。原始來源內容不複製到 JD 表，source refs 有效不代表人工新文字被 reverified。
- [x] **3.3a 補齊跨輪人工變更 context。** 依[主設計 §3.1](../specs/2026-09-09-jd-editor-app-integration-design.md#31-不每輪改稿的顧問接點)與[官方定點研究 §3](../specs/2026-09-10-jd-context-change-and-source-research.md#3-本案如何沿官方接點接線)已核對的既有 `wrap_model_call`／`request.override` model-view 接點，寫清楚比較基準、模型先前實際取得版本／範圍、當輪通知的呈現預算、重開／基準未知行為，再作有限審查並接線；不重做廣泛廠商比較，也不採 experimental Codex API 作新依賴。固定 provider request 驗「員工已保存更動」在下一輪模型回應前可見，能沿三工具取得確切前後內容，不只驗 `jd_read` 可以讀最新版。覆蓋跨輪多次手改、先改再改回、AI 改後再手改、下一輪只訪談、另一文件隔離、通知較長內容有明示續讀、保存失敗不冒稱新版，以及關頁重開或 context 縮減後不把未提供內容誤標為已讀；純訪談可不改 JD。通知組裝失敗不能静默略過或假報未改；canonical 員工問句與 Memory extraction 不包含 App 注入的偽造問答。沿既有文件 revisions 與 runtime，不另造 Memory／同步引擎；若需要改公開 wire shape，先更新同一 SSOT 並重驗生成，不在 prompt 偷塞未定義的工具參數。此新增驗收尚未執行，原 schema／provider 離線證據不覆蓋它。
- [x] **3.4 注入工具及 durable binding。** 在現有 `_context` 的 `tools` 中加入唯一 JD factory instances；保持 `MemorySession`／background／provider／compaction／budget 原設定。JD middleware 在 Node 前保存 input→AI message→tool call→operation／digest／base／command binding，重開同 binding；同名替代工具或 middleware 注入同名工具 fail closed。不接受模型自填 path／offset／document／profile／operation。
- [x] **3.4a Schema-first 的實際 model transport 驗收。** `test_jd_provider_binding.py` 沿真正 `build_agent`／`ChatOpenAI`／SDK，固定 `httpx.MockTransport` 捕最終 request：三個 JD parameters 與 SSOT＋refs 閉包全等、description 與同一 SSOT 完全相同、root type object、遞迴 refs／必要 constraints 未被剪掉、strict false；非 JD schema／strict 及模型設定維持原樣。用固定 ToolMessage 路徑再驗原 ToolNode 只執行原 factory instance；不合法雙 ref／未知 prop／非法 recursive content 先被 App 完整 validator 拒絕，engine invocation 為 0。執行 `uv run pytest -q tests/test_jd_provider_binding.py tests/test_jd_tools.py`；真 provider 是否接受此 schema 仍列獨立、有預算的接線驗收，不因 MockTransport 400／固定成功回應而冒稱已通過。
- [x] **3.5 驗收精確負例。** current read→改月檢通過且故障內容完整；同文件 history target 寫入拒絕；混兩版 refs 整批拒絕；猜真 ID 但無已發配 read拒絕；selection 重複文字只改指定處；no-change change_ref 可查空差異；兩版 comparison 不冒稱某一次 AI 修改；source 返回逐字原話。用固定模型回應驗工具注入與 ToolMessage 正確，外部請求數為 0。
- [x] **3.6 提交。** 重跑 3.1 並更新 README 的 tools／sources／binding seam；review 後 commit `feat(jd): wire advisor tools to issued document references`。

**停止線：** close／resume 還未完成前，不宣稱本切片具取消安全；不為通過引用測試複製 Memory、把可解析字串當已讀證明，或使用 production 舊 VFS writers。

## Task 4：同頁手編、完整實際差異與 session history

**完成並接受：**[結果及fix1 closure](../specs/evidence/2026-09-10-jd-editor-task4-results.md)，初輪工程及必要真browser、fix1受影響窄檢查通過，T4-R01–04全CLOSED／Spec PASS／quality APPROVED。原clipboard誤判與首敗保留，有限paragraph/marks保真另有實證；OS真人IME NOT RUN。Task5完整生命周期、Task6與自然品質仍後續。

**成品旅程增補（2026-09-10，獨立設計review通過）：**本Task同時實作[員工旅程§6–10](../specs/2026-09-10-jd-employee-journey-design.md#6-最小-apiwire-增補與回覆遺失)的create／list／reopen及共同metadata接點。§9為精確增補清單，J01–J12為對應驗收；完整更名／封存管理UI在P5完成。普通未提交dirty採頁面buffer與navigation guard；只有送出請求有持久recovery cache，不宣稱普通dirty在crash後可恢復。

**Files**

- Create：`W/package.json`、`W/next.config.ts`、`W/tsconfig.json`、`W/vitest.config.ts`、`W/eslint.config.mjs`、`W/.env.example`。
- Create：`W/src/app/layout.tsx`、`W/src/app/page.tsx`、`W/src/app/workspace/[document_id]/page.tsx`、`W/src/app/globals.css`。
- Create：`W/src/jd/JdWorkspace.tsx`、`JdEditor.tsx`、`JdChanges.tsx`、`JdNode.tsx`、`JdLeaf.tsx`、`useJdSession.ts`、`submissionCache.ts`、`api.ts`；`W/src/generated/analysis-api.ts`。
- Create：`W/src/documents/DocumentList.tsx`、`DocumentActions.tsx`、`W/src/jd/navigationGuard.ts`、`requestRecoveryCache.ts`及對應測試；修改A的catalog／service／API與API測試，以同一active schema補有限metadata／request lookup defs，不手寫Web鏡像。
- Create：`A/src/analysis_agent/jd_routes.py`、`A/scripts/export_web_contract.py`；tests `A/tests/test_jd_api.py`、`W/src/jd/JdWorkspace.test.tsx`、`JdChanges.test.tsx`、`useJdSession.test.tsx`、`submissionCache.test.ts`。
- Modify：`A/src/analysis_agent/api.py` 的 router／CORS／same_origin（消費 Task 3 已接的 MessageInput／run selection）、`J/README.md`、`A/README.md`。

**Interfaces**：Web 消費 generated DTO；catalog／messages／runs 消費8091 API同源機械生成型別，新create identity／metadata conditional command／run-by-request defs納入active SSOT，再由API Pydantic models引用生成型別，不import 8001 `jobAnalysisApi.ts`。`N/react-profile`＋同一 `JdNode`／`JdLeaf` 用於 current、exact before／after、diff；只有 current 可編輯。

- [x] **4.0 導入已核官方修補runtime。** 依[Web核對§4](../specs/2026-09-10-jd-web-execution-preflight.md#4-node-22-支援與安全修補補核2026-09-10)及[限定review](../specs/evidence/2026-09-10-jd-web-preflight-review.md)採Node22.23.2官方Windows portable distribution，核架構、官方簽署SHASUMS與SHA256，保留Node及附帶元件授權。放專案隔離runtime目錄並排除binary入git；以有限啟動環境／明確executable使用，不替換全機Node/PATH或Task3進行中的程序，不新增版本管理framework。重建API/JdEngine（它在建構時解析node），記self.node、worker process.execPath／version、npm scripts及process.versions，不能只看terminal版本。先在原鎖重驗contract生成bytes/check、native commands／selection／copy／history/build、Python→Node真子程序及錯誤/UTF-8；若涉及保存沿現有專用PG recovery集合。舊Task1–3證據保留原runtime；另記本次新版結果，不能改判歷史。後續W依4.6驗compiledReact／DOM。
- [x] **4.1 建同頁與 API 紅燈。** 初版 `/` 只列 catalog 文件／建立文件，選一份到 `/workspace/{document_id}` 的聊天＋JD。測試「選文件 A→讀 A messages/run/head→保存 A→切 B 不帶 A refs」，以及 dirty 保存失敗不發 run；不以兩個 tabs 表示目前稿／更正稿。
- [x] **4.2 建最小隔離 Next 設定。** 依[Web施工前官方核對](../specs/2026-09-10-jd-web-execution-preflight.md)改用Next／eslint-config-next 16.3.3；react／react-dom宣告與resolved套件保留19.2.4並與native鎖一致，Vitest／mocker沿4.1.11。這是已知官方修補的有限cross-minor升級，不改production鎖。另記Next compiled React／RSC及browser實際React runtime，不override、不強迫版本等於19.2.4；相容性以真DOM證明。`transpilePackages` 明列 `@caliburn/jd-editor-native`／`@caliburn/jd-editor-contract`，不用新 bundler。Web dev 固定 `next dev --hostname 127.0.0.1 --port 3001`，API origin `http://127.0.0.1:8091`。API 同時調整既有 same_origin guard 與 `CORSMiddleware`，只允許 `http://127.0.0.1:3001`、`http://localhost:3001`，`allow_credentials=False`，methods `GET,POST,PATCH`，headers `Content-Type`。保留 TrustedHost localhost／127.0.0.1；未知 Origin 回 403，合法 preflight 通過。production 3000／8001 配置不改。
- [x] **4.3 接完整路由。** 使用現有 `/documents`、`/documents/{document}/messages`、`/runs`、`/runs/{run_id}`、`/stop`／`/resume`，新增下表固定 JD routes；消費 Task 3 已接的 optional `MessageInput.jd_selection:JdSelectionCaptureClientInput`。每次以 route document 核 scope；server mapper 接內部 ports，Web 不偽造 AI run／tool ID。`export_web_contract.py` 只讀 `api.py` 的 `DocumentInput/DocumentOutput/MessageInput/MessageOutput/RunOutput/MemoryStatusOutput`與旅程§6新增且引用同一生成defs的metadata／request-lookup models，以 Pydantic `TypeAdapter` 聯集的 `json_schema()` 輸出生成資料，再沿 C 既有 `json-schema-to-typescript` 生成 `W/src/generated/analysis-api.ts`；不啟動 `open_service`、不手抄型別，不新增 OpenAPI generator。C 的 check-codegen 一併比對此檔。

| HTTP 入口 | Body → response／責任 |
|---|---|
| `POST /documents` | title＋App request_key；首次catalog／key／digest／初始revision／head同交易，同鍵same payload查回同文件不增版；更名／封存後重送仍同ID |
| `GET /documents`、`GET /documents/{document}`、`PATCH /documents/{document}` | UI列表可按archived篩選；metadata帶version；rename／set_archived以expected version條件更新，不造JD revision。内部scheduler完整列表不篩掉archived |
| `GET /documents/{document}/runs/by-request` | 唯讀key查詢，排在run-ID route前；found與canonical input_received分開。重開先查，不自動POST或resume |
| 既有 `POST /documents/{document}/runs` | 原 `MessageInput`＋optional `jd_selection:JdSelectionCaptureClientInput` → 原 `RunOutput`；digest涵蓋text、abandon_pending、selection全部admission有效輸入；沒有新模型工具 |
| `GET /documents/{document}/jd` | 無 body → `JdReadResult`；current read |
| `POST /documents/{document}/jd/read` | `JdReadModelInput` → `JdReadResult`；明示 revision／target／selection／continuation 讀取，仍由 browser adapter 核 scope，不是 AI call |
| `POST /documents/{document}/jd/changes/read` | `JdChangeReadModelInput` → `JdChangeReadResult`；immutable change 或兩版比較 |
| `POST /documents/{document}/jd/manual-save` | `JdManualSaveClientInput` → `JdManualSaveResult`；Python 配 authoritative envelope；同 key／exact payload 重送先取原回執，不新增查詢工具或預約 endpoint |

- [x] **4.3a 保存送出中的非權威記錄。** `submissionCache.ts` 使用原生 localStorage 的新 namespace `caliburn:jd-plate-clean-v2:submission:{document_id}`；發送前保存 `{document_id,request_key,base_revision_ref,value}` 的 exact payload，重開先以同 key／原 payload 對帳。只有 `committed`／`no_change` 且 receipt confirmed 可直接清除；confirmed failure 仍保留 exact 人工候選及同頁恢復提示，不自動覆新 head，直到已轉成另一份持久的新提交記錄或員工明示捨棄才清。不能只把候選讀進記憶體展示就刪 cache，否則再次關頁會失文。cache failure 則不發送並保留 dirty，不能假裝請求已有可恢復身分。這只是送出中／尚待處理失敗請求的非權威記錄，與普通未保存 dirty buffer 分開；不讀旧 `caliburn:consultant-document-draft:`、不以 cache 覆蓋已保存新版、不作离線合併。unknown／回執未確認保留記錄，receipt 才是成功證據。

同鍵已終局的重送屬 receipt 查詢，不重入 writer；即使此刻另一前景 run 持有 gate，也應返回原結果。只有尚無終局結果的新寫入才檢查 busy／base；同鍵不同 payload 仍拒絕，不能用 busy 掩蓋原結果或更新原回執。

- [x] **4.3b 由真選取送出聊天。** 員工在同頁 Plate 選正文後送出原問句；若有 dirty，先保存並確認 authoritative base，再由當時 Plate 真 `editor.selection` capture `range`，與該 `base_revision_ref` 一起送既有 run route。保存／重載後選取不存在、送出前選取已變或 API 判 base 過期／跨支持 block 時拒絕本次選取，不自行回搜相同文字；UI 保留聊天室輸入讓員工重新選。伺服器按 Task 3.2a 檢查／保存 App selection context，canonical HumanMessage 保留原始問句，不混入位置 JSON。沒有選取就不加此 optional 欄位，也不新增平行編輯稿。

- [x] **4.4 接人工 editor 與有限 renderer。** 標題、段落、官方清單／表格、格式與 JD 容器都保留支持的操作；JdNode 顯示 section_kind／sources／允許表格屬性，JdLeaf 顯示全部支持 marks。合法內容貼上沿官方 parser／transform，驗 profile，不以攤平表格或刪 metadata 求過測。失敗保留原 buffer，明示未保存；正式保存稿不存 session/localStorage 備份為第二 authority。

成果／要求空組、K／S同版全文／引用與incoming清單、人工有限link控制及共享影響按旅程§8呈現。改共享項目列兩版引用者聯集及各自名稱；歷史解析使用該版定義，不能使用current替代。對無operations的任意快照比較顯示確切前後與高亮限制，不補造operation。
- [x] **4.5 接實際差異與 history。** 新版到達僅在乾淨同 baseline 套已保存的原生 operations；`withNewBatch`／`withoutNormalizing` 後 `setSplittingOnce(true)` 分開後續人工輸入。無 operations 或版本不合時先保護 dirty buffer，確認無 dirty 才重建 editor 並明示 session history 重設。`setValue`／`withoutSaving` 不用來假裝保留可用舊 history。undo／redo 是新人工內容，可再保存；重開 session stack 不延續。

| 固定驗收 | 精確通過條件 |
|---|---|
| DOM 全稿 | active v2完整r2的1張基本資料表、子清單、8個Task及各自成果／要求組、5個K／5個S及其引用／共享影響、所有適用條件皆可讀且可編；before／after／diff同構renderer；同ID刪增兩個比較節點正文皆存在。舊v1三表不再作本列驗收 |
| metadata／空格式 | 所有 profile 允許欄位與 marks 的前後資訊可在當畫面讀到；空 leaf mark 有文字說明，不能僅憑 computeDiff 空結果稱無變更；舊非法 score fixture 只作反例展示／負例，不納 clean profile |
| 人工保存 | 繁中輸入、IME composition、換段、nested list Enter、表格一組官方增刪列、複製新 ID；保存→關頁→重開 exact value、ID、refs 相等。POST 發出即關頁／回覆遺失後，以 localStorage 原 key／payload 重送只得原 receipt，不能重複新增；committed/no_change confirmed 清記錄；stale/save_failed confirmed 保留候選，第二次關閉重開仍 exact 可恢復、不覆 current，轉持久新提交或員工明示捨棄後才清 |
| history | 固定 AI batch→相鄰人工改字，undo 一次只退人工，再一次退 AI；redo 順序恢復且 ID 不變；保存 undo 結果保留歷史 revision，不刪 AI 曾改過的紀錄 |
| 真 selection 入口 | Browser 在同一 `p/h1/h2/h3/lic` 中選取第二次出現的相同繁中文字→必要 dirty 保存成功→capture→既有 POST runs→jd_read({}) 取得 selection_ref→replace_selection；只改該範圍且 HumanMessage 原問句全等。錯 head、跨 block、保存後已變選取均拒絕並保留 chat input；不預造 ref、不自動猜 match，純聊天無 selection 仍通過 |
| API origin | 上述 2 origins 的 GET／POST／PATCH／preflight 通過；外部 origin、3000 origin、錯 document refs 負例拒絕；Network 無 8001 請求 |

- [x] **4.6 驗收與提交。** `A/`：`uv run pytest -q tests/test_jd_api.py`。`J/`：`npm run test -w @caliburn/jd-editor-web`、`npm run typecheck -w @caliburn/jd-editor-web`、`npm run lint -w @caliburn/jd-editor-web`、`npm run build -w @caliburn/jd-editor-web`及native regression。核新增套件resolved／授權／audit，記Node、Next compiled React／RSC、browser React runtime／version／channel／headed狀態。依[Web核對§2–3](../specs/2026-09-10-jd-web-execution-preflight.md#2-真-browser-的可行路徑與不能冒稱的範圍)走真browser selection／clipboard／composition，留畫面／AX／actual request／saved value；CDP只用已核可呼叫的imeSetComposition→insertText，沒有imeCommitComposition。CDP引擎證據與Windows真人IME分列，未操作OS候選則記OS IME NOT RUN，不能勾整列通過或由jsdom代替。review 後 commit `feat(jd): add isolated same-page editor and visible changes`。

**停止線：** 需要第二份可編稿、忽略 unsupported 資料或自建 history／diff 才能呈現；保留失敗與 buffer，不扩引擎。只有 headless／jsdom 綠燈時 DOM／IME 仍未通過。

## Task 5：人工→AI admission、取消與已提交結果對帳

**2026-09-11 已接受：**[最終結果及獨立 closure](../specs/evidence/2026-09-10-jd-editor-task5-results.md)通過，R01–R06 CLOSED。原六項有限證據與真人 IME／自然品質限制保留。完成本地保存點後接 Task6；production gate 不變。

**2026-09-10 transport設計閉合：**採[有限人工恢復設計](../specs/2026-09-10-jd-manual-recovery-transport-design.md)，MRD-R01/02 CLOSED／Spec與quality PASS。5.1/5.4/5.5納MT01–14：同原key GET/POST、全部status的server write_blocked/can_recover、exact cache/no_pending另次明示原完整提交、晚到結果及clear失敗。Files增加A/scripts/export_web_contract.py、W/src/jd/api.ts及其generated analysis-api.ts，actual Pydantic單一來源，不改三工具／主JD SSOT。Task4原驗收保留，未知load改純GET由Task5承接。

**原生 lifecycle 有限設計採用：**按[設計§6–8](../specs/2026-09-10-jd-native-process-lifecycle-design.md)及[獨立審查 closure](../specs/evidence/2026-09-10-jd-native-lifecycle-review.md)採 B。API 在任何實際工作前使用私有 Windows Job／mutex，先終止並核對 exact 舊 Job，再加入新 Job；有限 Popen owner 保留 handle／pipe／I/O 清理責任。publish 前重核 cleanup／cancel；重開的 known-none 需舊 API／Node 停止及 PG head-lock 後 receipt 證據。最多一筆 root-only manual identity binding 不存候選、不造 input，終局確認才清除。驗 NL01–13 及 review 所列 root-only descriptor 正反例，使用真 bootstrap／獨立 test installation key；不得由 test harness 代替產品停止證據。Task 3 forwarding 通過不代稱本 Task 安全。

**成品旅程增補：**同時執行[員工旅程§7／9／J05–J08](../specs/2026-09-10-jd-employee-journey-design.md#7-封存與恢復的-admission)。archive／rename與新run／manual-write共用同文件admission；原terminal receipt及request查詢優先，封存不遮蔽結果。browser abort／關頁不當stop。背景B1／B2／C對已接收來源沿原政策，含未首次排程／部分批次／受控恢復；內部`service.list_documents()`含archived，封存不額外啟動或等待背景歸零。

**跨輪通知取消增補：**依[通知設計MV18](../specs/2026-09-10-jd-model-view-change-notice-design.md#8-精確-task-3-增補與驗收)驗兩條close分支均把已確認manifest從child傳root；尚未實際有response的準備紀錄不升格，補ToolMessage不代表下一次模型已取得。沿既有close／reconcile，不加第二取消協調器。

**Files**

- Create：`A/src/analysis_agent/jd_reconcile.py`；`A/tests/test_jd_admission.py`、`test_jd_close_reconcile.py`、`test_jd_postgres_recovery.py`。
- Create：`A/src/analysis_agent/windows_lifecycle.py`、`A/tests/test_windows_lifecycle.py` 及有限 child 故障 harness；Modify API bootstrap、`jd_engine.py`／`jd_service.py`／`jd_store.py`、`conversation.py` root-only manual binding、`jd_routes.py`；`A/pyproject.toml`／`uv.lock` 加 Windows-only `pywin32==312` 並核 CPython3.12 wheel／各部分授權。無假 input、無模型呼叫、无外部 supervisor。
- Modify：`A/src/analysis_agent/service.py` 的 submit／stop／join／close，`conversation.py` 的 close_turn／send_input，`jd_tools.py`、`jd_routes.py`；`W/src/jd/useJdSession.ts`／`JdWorkspace.tsx` 及其測試；`A/README.md`。

**Interfaces**：`JdToolSession.reconcile(state,message,call,config)` 只處理 factory-bound、checkpointed、已發配 JD operation；使用 Task 2 同 operation receipt。`close_turn(...,jd_session=None)` 新增此**限定** port，保留既有 memory_session 接點與 unknown write fail-closed。

- [x] **5.1 建固定 race／故障測試。** 使用事件 barrier 而非 sleep 猜時序；writer 尚在運行時 close 不得對帳解鎖。執行 `uv run pytest -q tests/test_jd_admission.py tests/test_jd_close_reconcile.py tests/test_jd_postgres_recovery.py`，先確認未接分支失敗。

| 時序 | 保存／畫面／對話精確期望 |
|---|---|
| dirty→送出對話 | 先拿人工成功回執／revision，才保存輸入並 admit run；人工失敗／未知不啟動 AI、不丟 dirty |
| 前景純訪談 | 整輪同文件人工保存 API 回 busy，仍能 read/diff；無 jd_edit binding 的完成／取消不等 receipt；背景 Memory 不寫 JD、不延長 gate |
| AI writer＋延遲手編 POST | 同一 admission 邊界拒人工；另一文件仍隔離；不能只靠 Web disabled |
| commit 後、ToolMessage 前中斷 | stop→確認 worker 已停止→同 operation 查 terminal receipt→只補缺的原 tool_call_id 結果→close turn→解鎖；head 不倒退、不再插入 |
| 已有 ToolMessage 又 close | 不追加第二個匹配結果，canonical 原文與既有 messages 不改寫 |
| receipt 查詢暫不可用 | run uncertain，writer gate 保持；不補造失敗結果／新操作，也不要求模型重寫 |
| 尚未啟動／已知 rollback | 依可證明的 known-none／unchanged 結果閉合；document_effect 與 receipt_durability 各據實，無 JD operation 不虛構 reference |
| forged tool identity | 同名 jd_edit／jd_read 的替代 instance 不享 reconcile／read-only 例外；未知 unpaired write 仍 fail closed |

- [x] **5.2 接 admission。** 沿 `AnalysisService` 的單文件同步與既有 input-before-model；人工保存與 run admit 在同一 App gate 互斥。restart 先讀未閉合 run／bindings 決定是否允許寫入，不因 process lock 清空就解鎖。既有 max_workers／Memory B/C 調度與 token/model budget 不改。
- [x] **5.3 接 close／resume。** worker join 後才 receipt 查詢；只回填缺失 ToolMessage，以原 call ID、真結果及 factory identity 配對。JD read result 遺失可按已綁定 read-only 規則丟棄，不表示資料不存在；jd_edit 不能套 read 規則。既有 `input=None` 不是任意重放授權；不擴寫通用 resumable_tools 白名單。
- [x] **5.4 驗新程序恢复。** 以 `jd_process_worker.py` 固定故障模式提交／中斷／另程序查同 receipt；assert native engine invocation count 不增加、原問答／Memory namespace 未變、原 operation／digest 保留。可證明未提交時才受控同鍵恢復；已 terminal failure 不能被改成成功。
- [x] **5.5 驗收與提交。** 跑 5.1 及 Task 4 session／submission cache tests；`A/` 跑 `uv run pytest -q tests/test_api.py tests/test_conversation_lifecycle.py tests/test_postgres_conversation_lifecycle.py tests/test_publication.py tests/test_postgres_publication.py`。README 明列忙碌、可閱讀、取消、未知與恢復時點。review 後 commit `feat(jd): reconcile foreground edits before restoring manual access`。

**停止線：** 要用泛用重播、補造 ToolMessage、未知先解鎖或 Memory ownership 改寫才能恢復；保留 uncertain 與清楚診斷，不能靜默採用新政策。

## Task 6：一份專業方法、固定端到端與核心交接

**Files**

- Create：`A/src/analysis_agent/skills/write-customized-jd/SKILL.md`、`references/complete-work-guide.md`、`references/writing-and-correction.md`。
- Modify：`A/src/analysis_agent/api.py` 的主顧問能力宣告、`skills.py` 的能力邊界文句；不改 Memory B／C 文字、策略、模型與預算。
- Create tests：`A/tests/test_jd_skill_contract.py`、`test_jd_end_to_end.py`、`jd_offline_service.py`；`J/fixtures/core-scenario.json`、`J/ACCEPTANCE.md`。
- Modify：`A/README.md`／`J/README.md`；實際完成時新增 `docs/specs/evidence/2026-09-10-jd-editor-core-integration.md`，逐項記 PASS／FAIL／未驗及證據。

**Interfaces**：既有 `SkillAssets`／`SkillsMiddleware` 的 `/skills/write-customized-jd/SKILL.md` 按需讀；同一 main Agent 三工具，不新增 Agent。`jd_offline_service.py:create_app` 注入既有離線 model transport 到同一 service/router composition，禁止自行縮水成測試專用 JD API。

**Task5→6 啟動接點：**下列離線 factory 亦須經 Task5 已驗的真 Windows bootstrap，在任何 DB／native／client 工作前建立 owner；測試只替換 provider 及專用安裝 key／DB，不可繞過 bootstrap 或由 harness 代填停止證據。Task5 若需調整啟動命令，須同步本段、6.4、README 與驗收命令；不能把舊 bare uvicorn 例子當繞過接點的授權。

- [ ] **6.1 寫方法 fixture 與紅燈。** 依主稿專業方法段落，把 [完整工作分析](../specs/2026-09-09-complete-work-analysis-guide.md)、[客製深度／訪談校準](../specs/2026-09-09-customized-jd-depth-and-interview-calibration.md)、[JD 寫作時機](../specs/2026-09-09-jd-field-and-writing-guide.md) 精煉為一份按需 Skill＋兩份有限引用；不重抄 wire schema、不當每輪必讀。`test_jd_skill_contract.py` 驗 discovery／read、路徑有界、無寫檔能力，既有訪談／Memory 方法仍可讀。
- [ ] **6.2 調整最小能力宣告。** 移除主 A「目前只做訪談分析，不製作或編輯 JD」的矛盾句，改為需要寫稿／實質修正時按需讀方法、讀最新版、用 JD 工具並依真保存結果回答。Skills 說明保留「方法資產本身不授予寫入」；不加每輪強制工具、stop judge、自評滿分或額外預算。
- [ ] **6.3 建固定端到端情境。** `core-scenario.json` 的 employee utterances、synthetic tool calls、expected 完整 JD 都固定；保留合成標記，不對既有 r2 反覆調到全綠。最少走下列順序：

1. 空文件訪談：先保存員工原话；資料不足的固定回應只追問、不造 JD revision。
2. 固定已知工作足夠後，current read→首次插入有意義 JD；三工具的真結果回到同 Agent loop，畫面顯示已保存內容與真差異。
3. 員工指出月檢僅限約定服務；AI 讀 current，在原 Task 內修正完整條件，另一處故障處理與 Task4 細節全值保留，來源回查精確。
4. 同頁人工改一段／保存→再送訪談，在模型回應前必須可見人工變更通知、明確比較範圍及可查實際前後內容，續編取得人工新版；另驗連續數次保存與純訪談不改稿。manual origin 不等於工作事實已核准，也不暗中修 Memory。重開／缺前版脈絡不能假報未改，保存失敗候選不能冒稱 current。
5. 一次 commit 後回覆遺失→取消／重開對帳，文件只增加一版、ToolMessage 不重複；另一次純訪談取消不等 JD receipt。
6. 關 Web／API 後重新啟動，current 全值、immutable before／after、歷次來源與 operation 結果相等；history 只讀可展開，沒有第二可編稿。

- [ ] **6.4 跑零付費整合。** `A/`：`uv run pytest -q tests/test_jd_skill_contract.py tests/test_jd_end_to_end.py`。本地頁面只用 `uv run --no-sync uvicorn jd_offline_service:create_app --factory --app-dir tests --host 127.0.0.1 --port 8091 --workers 1 --no-proxy-headers`，配明確測試 DB 與離線 provider；`J/` 用 `npm run dev -w @caliburn/jd-editor-web`。`ACCEPTANCE.md` 記 exact route／操作／before-after／結果，核 Network 沒有外部 provider 或 8001。
- [ ] **6.5 完成必要回歸。** `A/` 跑 `uv run pytest -q`（PG opt-in 組須實際通過並單列）；`J/` 跑 `npm run check-codegen -w @caliburn/jd-editor-contract`、`npm run test --workspaces --if-present`、`npm run build --workspaces --if-present`、Web typecheck／lint；checkout 跑 `git diff --check`。檢查 `apps/api`／`apps/web`／`packages/job-analysis-contract` 及 root lock 無本次變更，不把舊 production 測試綠燈當隔離接合證據。
- [ ] **6.6 獨立 review 與交接。** Reviewer 對 schema／實際 API／native profile／保存／source／close／同頁效果逐項比對。證據報告分成「固定離線核心效果」「真 DOM／IME」「PG／新程序」「未驗自然模型品質」；列 first failures，不刪反例。review 後 commit `feat(jd): complete isolated advisor editing acceptance`；全部 task 審查完成後建本地 tag `jd-editor-core-isolated-20260910`，不 merge／push。

**停止線：** 為通過固定資料而改專業事實、讓 provider 自動連線、擴大 Memory 策略、把真人交付重啟或把離線結果宣稱所有職位專業品質已通過。本版固定情境完成即交接，不追加無界新職位研究。

## 完成定義與 production 下一道邊界

核心隔離完成須六切片各自通過：一份 clean document SSOT、官方 editor 實際操作、同 PG 唯一 revisions／receipt、人編／AI 接續、原畫面真差異、已發配 references／canonical source、取消／未知結果閉合、新程序重開、免費固定端到端；未保存 buffer、DOM／IME 與自然模型品質的限制逐項可見。

正式切換仍是後續獨立單位：先把 CT49–51 已研究 Memory 的 exact version、被取代 owner、namespace/setup/delete/recovery、Python／dependency／composition root 以有限 authority gate 正式化，再安排一次切換。不能只改 `NEXT_PUBLIC_API_URL`，不能從 `apps/api` import `.worktrees`，也不能把 8091 的顧問 Memory 和 8001 舊 JD VFS 混接。

供該後續單位使用的**只讀路由清單**：`apps/web/src/features/consultant/ApprovedDocumentEditor.tsx`、`DocumentReviewPanel.tsx`、`DocumentChangeEditor.tsx` 及 `shared/api/jobAnalysisApi.ts` 的舊 approved／review writers 要依 successor 退出；API `app/consultant/workspace_state.py`／`workspace_review.py`／`workspace_authority.py`／`document_authority.py` 與 `api/routes/consultant.py` 的 review／approved-document routes 同樣不能雙寫。`app/adapters/langgraph/postgres.py`／`workspace_backend.py` 同含來源或非 JD 責任，不可整檔刪除。`packages/job-analysis-contract` 的舊 generated DTO 必須從其 SSOT 改，不手改生成檔。**以上都不是本計畫的修改清單。**

本地 dev CORS 的官方接點為 [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/)，local package 接點為 [Next transpilePackages](https://nextjs.org/docs/app/api-reference/config/next-config-js/transpilePackages)，均由主線於 2026-09-10 核對；3001／8091 與 allowlist 是本案隔離配置，不稱官方統一端口。原生已驗範圍及限制依 [F02](../specs/evidence/2026-09-10-jd-official-profile-probe.md)、[history](../specs/evidence/2026-09-09-jd-native-history-and-sync-probe.md)、[P01](../specs/evidence/2026-09-09-jd-native-save-probe.md) 原證據；本計畫不增加它們的證明效力。
