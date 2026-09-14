# JD 編輯核心 Task 1 實作與獨立審查結果

2026-09-10；JD-R002/C03。Task 1完成：Spec PASS／Code quality APPROVED；R1移動定位與R2受影響內容均CLOSED，checkout換行補核PASS。68 native、27 Python、codegen／check／build及公開ports已驗；既有顧問93項離線baseline通過。最終staged bytes核對102個授權entries（94個已記SHA，另8個官方archive沿革）及5份契約／fixture產物全相等；104個套件中2個只有metadata授權聲明。作者／生成物空白檢查通過，官方授權原始空白完整保留。以下保留執行與初審／修正沿革，當時pending措辭不覆蓋本段及最後複核結論。只完成隔離契約／原生核心，DB、DOM、取消、自然模型與成品未驗；0付費模型，production authority未變。

# Task 1 — implementation handoff / pending independent review

2026-09-10；checkout `S:/caliburn/.worktrees/analysis-only-agent`，branch `codex/analysis-only-agent`。

## 實作範圍

- 建立 `experiments/jd-editor/` isolated npm workspace、exact lock、Node profile／React plugins、七個 resolved commands、validate-value、read-selection、固定 stdin/stdout bridge，以及同文件人工 copy helper。
- C 由 active v2 SSOT 機械複製／生成全部 Python DTO、TS DTO；同時補保留生成器省略的純 `$ref` public aliases。check-codegen 在臨時目錄生成後逐 byte 比對。
- 正式有限 validation：原 schema grammar／props／JSON shape，保存 ID 唯一、同版 Task→K/S種類／端點、numeric／HTML span一致性。各入口先clone，原輸入不變；transform失敗不回candidate，原生normalization後再驗全文。
- profile使用官方basic/list/table、semantic containers只有普通element；NodeId `reuseId:true,initialValueIds:'always'`；不加normalizer／codec／diff／來源引擎。clean operations以真onChange捕捉、JSON原樣往返，Task8完整move與取消bold操作可對fresh baseline精確replay。
- read-selection先驗canonical不被normalization改變；native range同一p/h1/h2/h3/lic，native fragment與NodeApi只取已解析target block，不保留不完整祖先當完整Task。
- A僅新增local editable C與既有固定jsonschema依賴。`uv.lock`只多本地package與metadata／reference，既有所有套件version未變。
- 無production程式／root lock／DB／模型／API key變更，0付費，未commit/tag（由controller在review後處理）。

## RED → GREEN 與實際發現

1. 最初npm offline cache miss、Vitest sandbox spawn EPERM是環境失敗，不算RED。使用已核准escalation後固定四個test suite因正式profile/validate/transform/read-selection缺檔而失敗；Python2項因未生成models/schema失敗。此後才寫native模組。
2. npm10.9 optional-peer解析兩次`edgesOut`；固定Vite8.1.3（沿root lock）仍重現，採`.npmrc legacy-peer-deps=true`，之後實際`npm ls --all`無缺少／不符依賴。全部npm install/ci用ignore-scripts。
3. 固定datamodel-code-generator0.71.0產生`list["JsonValue" | None]`導致import TypeError。採官方`--no-use-union-operator`後重生，26 Python測試過；沒手改生成物。
4. TS generator對allOf/not生成宽properties constraint，所以驗原schema後有限mapper收斂。公開ports typecheck另抓到JdEditResult／JdManualSaveResult純ref別名省略，codegen機械讀同SSOT補aliases，重生／byte check／typecheck過。
5. native copy測試缺模組RED後完成helper。後續測試曾對合法省略knowledge_ids呼叫map，修測試保留undefined；未改產品判定。
6. 真r2巢狀Task選取RED：fragment帶局部Task祖先，schema拒絕missing required groups。有限native NodeApi提取相同target fragment block後過，沒有修正文或自建matcher。
7. npm --prefix在主checkout cwd一度把本地root package當dependency加入isolated package；立刻移除并改用J cwd安裝。最終lock root沒有production引用、F02全部48個runtime package版本相等。曾在checkout root產生空license盤點檔已刪除，其他既有dirty未動。

## Fresh verification

- `npm run codegen -w @caliburn/jd-editor-contract`：exit0。
- `npm run check-codegen -w @caliburn/jd-editor-contract`：exit0、3生成物bytes一致。
- `npm run build -w @caliburn/jd-editor-native`：exit0。
- `npm run test -w @caliburn/jd-editor-native`：**8 files／43 tests passed**（最後07:38:59，Vitest4.1.11）。涵蓋指定四檔與span、copy、真bridge、完整operation replay、來源fixture及JSON反例。
- TS所有22公開ports import typecheck：exit0。
- `uv run --project contract pytest -q contract/tests/test_schema_contract.py`：**26 passed**（最後07:36），包括完整r2 Pydantic roundtrip、write status conditional以原schema判定。
- `npm ls --all`：無missing/invalid。
- 既有A lock version全保留；未驗DOM/SQL/provider。

## Fixture / source hashes

- SSOT v2：`c6cc0f996b7a24b37cdf784a9d46e88cbb1d59f4d68d327e4167f3dfa40fb715`。
- canonical v2：`f994045df13fd0095593a3333755df9e411dbc52ddeaeeba9aa276298d19a264`，和已review source全bytes相等。
- Task8-only expected：`08e698cf6c68afdd9fcf3befcd1efbd02c6e27bfddaa478629187d8222fbd953`。
- fixture-mapping保留38退役外框；source-map現階段測試issuer沿固定8個synthetic handle，Node不做source scope owner。Task3再接真source owner。

## 可審查的限制／concerns

1. 初交的`affected_element_ids`全集作法被獨立review R2判定不符binding，已於下方fix round1修正；不是可延期的產品選擇。原review FAIL紀錄保留，等待scoped重審。
2. copy helper是local same-document UI API（不是第八個wire command），應只在disposable editor使用，最終validate再保存；跨文件authority仍App。未接DOM/clipboard。
3. 初次audit2 moderate（Vitest／@vitest/mocker redirect mock path traversal）已修復。主線核官方GHSA-82fw-gwwq-j7x9後明確裁示tooling-only patch，已固定Vitest4.1.11；48個F02 runtime版本核對全相等，npm audit為0 vulnerabilities，npm ls無缺失；授權inventory／audit／README已更新。官方：https://github.com/vitest-dev/vitest/security/advisories/GHSA-82fw-gwwq-j7x9。
4. 修補後已保存104個實裝JS套件metadata；官方F02的8缺license套件沿相同固定版本官方fallback授權。新tooling的stackback與Windows rolldown binary只有package MIT declaration，inventory明列；未聲稱全有實裝license文字。
5. 本Task未驗正式DB保存／取消／reconcile／DOM／自然模型／完整成品；不重問已有format/DB方向。

## Files

`experiments/jd-editor/`：package/lock/npmrc、README、license inventory/licenses、npm audit、contract codegen/DTO/schema/Python lock/tests、native src/tests/README、fixtures。`experiments/analysis-agent/pyproject.toml`與`uv.lock`僅上述依賴。未編輯root docs/register。

請獨立review上述核心；未commit。所有43/26 pass不替代review或後續產品切片。

## 最終 review-ready snapshot（07:38:59）

依主線明示安全修補完成Vitest4.1.11固定升級，43 native tests全過；Python未改動且前次26 passed保持其原驗證時點。48 runtime依賴全未變、0 audit vulnerabilities、npm ls無缺失。未commit，已ready供controller獨立review。



## Fix round 1 — R1/R2 scoped re-review ready（2026-09-10 07:49:45）

原 `task-1-review.md` 判 Spec FAIL／CHANGES REQUIRED 受理，未以初交43 tests綠燈推翻review。這是有限adapter修正，不變更schema、profile、runtime依賴、產品政策。

### RED

新增 `native/tests/review-round1.test.ts`，初次有效run共23 cases：**11 failed／12 passed**（07:47:26）。包含review列明三個向後移動錯序、自指after、同父adjacent/no-op與無關siblings被列affected。最初檔案路徑前綴重複造成write失敗/no tests是harness錯誤，不算RED；其後成功建測試才取得上述有效RED。

### R1修正及官方依據

固定Slate0.126.2 `dist/index.es.js` 的moveNodes（4941起）傳真move_node；apply的move_node（2075起）會以`Path.transform(op.path,op)`求真正新path，跨層父path自動調整，同父新index則已是最終位置。故adapter僅在`PathApi.isSibling(path,to)`且來源在目的前，用`PathApi.previous(to)`把before/after或append_child的插入間隙轉為最終sibling index。跨父不預先位移，避免double-adjust。解析target_id與destination_id相同先拒絕，真正相鄰位置/同父prepend已在原位則不發假operation。仍只呼叫官方moveNodes，不手改children、不建排序器。

### R2修正及官方依據

新增 `affected.ts` 在capture時觀測native `editor.apply`/`editor.tf.apply`相同接點；呼叫原始apply不改op。之前樹以NodeApi/PathApi取得實際節點與必要祖先；結構增刪／搬移只收真subtree，merge收來源與survivor，split收原節點與被分出children。原生NodeId insert/split會替換incoming payload（固定core `withSlate-CGuPv-qn.js` 2821／2856起），所以新ID從當次實際`editor.operations`已套用payload收集，包含normalization递迴operations。既有同步onChange仍捕捉原生operations，沒有第二份tree/replay/diff引擎。全文淨零只回空affected IDs而保留真操作。

### GREEN / final verification

- focused從23 cases／11 failed → 23 passed；補native split generated ID與cross-parent affected兩個完整案例後，**25 passed**（07:49:44）。
- `npm run build -w @caliburn/jd-editor-native` exit0。中間第一個build發現PathApi.previous回傳可能undefined的型別已修；沒有把該失敗冒稱build通過。
- `npm run test -w @caliburn/jd-editor-native`：**9 files／68 tests passed**（07:49:45，Vitest4.1.11）。
- 完整value與JSON operations fresh-editor replay核對：三sibling前／後移、adjacent no-op、自指拒絕、同父prepend/append、跨父before/after、root移出使destination parent位移、原完整Task8 oracle均過；caller baseline不變。
- affected：改字、mark取消、props、insert/delete/move、兩邊父容器、normalization、native split生成ID、淨零結果，均排除明知未變siblings。
- 沒改contract/codegen/Python，不重跑無關26 Python或生成器；既有證據效力保持原時點。0 paid／DB／production，未commit／spawn。

### 本輪精確變更檔

1. `experiments/jd-editor/native/src/affected.ts`（新增）
2. `experiments/jd-editor/native/src/profile.ts`
3. `experiments/jd-editor/native/src/transform.ts`
4. `experiments/jd-editor/native/src/validate.ts`
5. `experiments/jd-editor/native/tests/review-round1.test.ts`（新增）
6. `experiments/jd-editor/README.md`（取消全集宣稱，寫現行操作足跡）
7. 本 `task-1-report.md`

Fix round1已ready，請原reviewer scoped重審R1/R2；不以本報告自判Task1已accept。


## Controller checkout-byte follow-up

Before commit, git core.autocrlf=true plus absent JD attributes would transform schema/generated/fixture bytes. Root added narrow LF rules for source SSOT and JD package; upstream licenses are -text to preserve exact originals. Original license whitespace is retained and excluded only from authored whitespace lint. Three author-owned files had a single surplus blank EOF removed (README, contract pyproject, command-mapper); no behavior changed.

The first staged-byte verifier correctly found Windows datamodel-codegen emits CRLF Python while checkout rules require LF. Added regression test_generated_python_bytes_survive_lf_git_checkout: actual RED 1 failed (CR found); first harness also emitted inaccessible pytest cache warnings, not a product failure. Codegen now mechanically normalizes generated Python CRLF to LF after official generation; no DTO hand edits. npm codegen/check-codegen passed; full Python contract 27 passed in11.47s with cacheprovider disabled (cache only, no tests skipped). Native code unchanged since 68-pass/7-scenario review. Same raw-byte license/contract verifier remains required before commit. Checkout follow-up pending narrow independent review; no runtime/model/DB changes.


# Task 1 獨立審查

日期：2026-09-10。範圍：S:/caliburn/.worktrees/analysis-only-agent；BASE 622e548d9d37ce4f8adb2ac0f0e61ce0d7aad3d9，尚無 Task commit。依 current-decisions 頂部，這是 Owner 核准的隔離 Task 1；production authority 仍為 ADR 0060。

**Spec compliance：FAIL；Code quality：CHANGES REQUIRED。** 以下兩項修正前不可宣稱 Task 1 通過，也不宜進入 Task 2。沒有新增產品選擇或需要 Owner 重選架構的問題。

## Findings

### R1 — [P1] move_content 向後同層移動的目的位置錯一格

位置：`experiments/jd-editor/native/src/transform.ts:43-50`（destination 另見 25-30）。

destination 使用尚未移動前的 sibling path，直接傳入 `editor.tf.moveNodes({at:path,to})`。原生 moveNodes 並不把本案的 before/after 語意自動換成正確的移除後 sibling index。三個以上 sibling 時，向後搬動會成功發布錯誤順序；只有兩節點的既有測試剛好沒有揭露問題。此缺陷同樣影響任務／章節重新排序，不只是測試文字。

使用現有已編譯 transform 的 focused Node 反例（所有節點都是合法 `p`、各帶相同 ID/text；profile v2）：

| 基底 | 命令 | 應得 | 實得 |
|---|---|---|---|
| [a,b,c] | a before b | [a,b,c] | [b,a,c] |
| [a,b,c] | a before c | [b,a,c] | [b,c,a] |
| [a,b,c] | a after b | [b,a,c] | [b,c,a] |
| [a,b,c] | b after b | no-op 或明確拒絕自指 | [a,c,b] |

四案實際均回 ok:true。對照案 c after a 正確得到 [a,c,b]。本機固定 `@platejs/slate/dist/index.js:2073-2095` 的非 children 分支直接轉交 Slate moveNodes，沒有額外修正目的語意。

修正：在有限 command adapter 以官方 path／pathRef 接點明確處理來源移出造成的目的 sibling index 變化，再使用原生 moveNodes；自指應先明確拒絕或合法 no-op，不能移到下一項後。不要自建排序引擎。新增三 sibling 的前後移動、相鄰 no-op、自指、同父 prepend/append_child 及跨父固定 before/after oracle；繼續核完整 ID、metadata 與 native operations replay。

### R2 — [P2] affected_element_ids 把未受影響的整份文件誤報為實際變動

位置：`experiments/jd-editor/native/src/validate.ts:17-35`；README 的限制說明在 `experiments/jd-editor/README.md:32`。

只要全文不相等，result 就收集 before/after 所有 Element IDs。focused 反例：基底 [p(a,"a"),p(b,"b"),p(c,"c")]，只 replace_block_content(a,"changed")；原生 operations 只有 path [0,0] 的 remove_node/insert_node，b、c 的內容、位置及所有屬性全未變，結果卻回 affected_element_ids=[a,b,c]。r2 的單段修改同理會把全部 190 Elements 報為受影響。

這通過 schema 的 array shape，卻不符合 binding 的結果語意：`docs/specs/2026-09-10-jd-app-tool-contract.md:106` 要求返回原生 actual operations／affected content；同檔 140 明訂「不捏造受影響範圍或補造操作」；`docs/specs/evidence/2026-09-10-jd-storage-contract-closure.md:112` 要求 affected IDs 只能來自實際結果／已支持判定。JdActualChanges 會承載此欄位，後續工具與跨輪人工變更通知不能合理把未變動項目當作改過。README 自行稱其保守全集不會修改既有契約；延後依靠 computeDiff 也不能補正目前輸出的錯誤語意，尤其契約已記錄 computeDiff 的格式漏報。

修正：從實際捕捉的 operations 與其當時 tree/path/ID，做有限受影響 ID 收集（文字操作定位包含該文字的 Element；結構操作包含實際移動／增刪節點與必要父容器），涵蓋 normalization；不得不分情況加全文件。完整 before/after 仍保持唯一完整回查材料，不把 ID 清單當完整比較的替代。如果只能支持局部判定，至少不能把已知未變內容列作 changed。補單段改字排除無關 sibling、marks/props、insert/delete/move、normalization 與淨零結果的固定驗收。

## 已檢視內容與界線

- 依交接精確 code diff 檢视全部 authored native modules、codegen、Python/TS contract tests、8 native test files、README、package 設定與 A dependency diff；未另跑 git diff，未修改 code/index 或 commit。
- 七 union branches 均呼叫官方原生 transforms；沒有手寫 document mutation engine。候選 editor 為 clone，failure 只回 error；完整末端 validator 共用於人工 validate-value 與 AI transform。
- v2 grammar 由原 schema 驗；有限 validator 另核 ID 唯一、Task→同版 K/S 種類／端點及雙 span 一致性。copy helper 以原生 insert 配新 ID 後映射複本內 K/S，保持組外引用；它是 disposable same-document helper，尚非 DOM clipboard。read-selection 驗同 block、bounds 與 canonical normalization，再從原生 fragment 取指定 block，沒有模糊搜尋。
- codegen 讀同 checkout active SSOT，Python 官方 recursive union workaround、TS pure-ref alias 補回均為機械生成；TS allOf/not 寬型別由原 schema validation 補足。定點看 generated resolved command、editable properties、transform result 與 Python result DTO，未逐行人工審查整份生成 DTO。
- 全部 158 個 task-1-files.json 檔案 hash 均與 snapshot 相符；generated schema 與 SSOT 同 SHA256 c6cc0f99…，canonical 與已核 fixture 同 SHA256 f994045d…；沒有把 artifact 整檔當 authored code重讀。生成／fixture/schema/hash 定點核對；license-inventory 結構與 source-map 已讀，未逐條重新法律判讀 104 份授權，未重做 npm audit。48 runtime 固定及 Vitest4.1.11/audit0 採本輪實作者已保存驗證報告，沒有再提出已修安全項目。
- 43 native／26 Python、codegen/check/build／22公開ports與93既有advisor baseline 是實作者／主線既有證據，本 reviewer 未重跑全套。此次獨立執行僅上述 move/affected focused 反例與 hash核對，結果可由現有 native/dist/transform.js 無修改重現。
- 無 DB、DOM、provider、取消或自然模型／真人品質通過聲稱；0 付費呼叫。以上兩項局部修正可在既有 Task 1 邊界完成，不需 production authority 變更。

## Fix round 1 scoped 重審（2026-09-10）

**最新判定：Spec compliance PASS；Code quality APPROVED（Task 1 範圍）。R1 CLOSED；R2 CLOSED。** 此結論取代上方初審的待修判定；原始反例與FAIL沿革保留。未發現本輪修正引入的相鄰阻擋回歸。

### R1 CLOSED

已讀 `task-1-fix1.diff` 六檔完整 snapshot 及實作者補充。`transform.ts:43-57` 現在明確拒絕相同來源／目的 ID，僅對來源在前的同父 insertion gap 以官方 PathApi 調整到 final sibling index；位置相等則合法 no-op，跨父仍交原生處理。定點讀固定 Slate0.126.2 `dist/index.es.js:2075` 的 move_node apply，確認原生會移除來源後以 Path.transform 算真正目的 parent/path，修正沒有再對跨父重複位移。

獨立重跑初審 a before b、a before c、a after b、c after a、自指 b after b，全部符合預期；另驗 root a 搬進其後 section s 的 append_child，目的 parent 位移正確。新固定 tests 另涵蓋兩方向、adjacent/no-op、同父 prepend/append、跨父 before/after 與完整 operation replay。R1 已解決。

### R2 CLOSED

`validate.ts:22-25` 已移除全集掃描；`affected.ts:4-75` 只觀測真實 native apply，從當時節點／必要祖先及結構操作 subtree 收集，NodeId 生成 ID 從實際 applied operations payload 取得。沒有改写 operation，也沒有維持第二份 tree、generic diff 或自建排序；既有同步 onChange 原生 operation capture 保留。完整淨零仍回空 IDs。

獨立重跑只改 a 的原反例，現在 affected IDs 精確為 [a]，排除 b/c；另驗跨層搬入 section，回傳集合僅 [a,s]，不含 section 的未動 sibling。新 tests 覆蓋 properties／mark、insert/remove/move、來源與目的容器、normalization、split 新 ID、淨零及 replay。這是有實際 operations 支持的受影響索引，允許包含必要父容器，不再聲稱全文件皆受影響；完整 before/after 仍為回查材料，符合原 binding 判準。人工保存相對上一版的變動映射屬 Task 2，不能把本次 validate-value 的 normalization 足跡誤當完整人工 edit history；本輪沒有冒稱解決該後續責任。

### 此次驗證／保留界線

- 六個 fix snapshot 檔案 hash 全部相符（6/6，0 mismatch）。此次獨立執行七個 focused scenarios 全過，未跑完整 suite。
- 實作者保存的有效 RED 23 cases/11 failed → focused 25 passed → native 全部 68 passed/build exit0 已讀；不將其冒稱 reviewer 獨立重跑。無 schema/dependency/Python 變更，前輪其餘審查與既有26 Python／codegen證據維持原時點。
- 此輪僅審 R1/R2 及直接相鄰風險；上方 artifacts／授權／未驗 DB、DOM、provider、取消、自然模型與真人品質界線全部保留。未改 code/index，未commit/spawn，0付費。

## Controller checkout-byte follow-up 審查（2026-09-10）

**PASS；Task 1 Spec compliance PASS／Code quality APPROVED 維持。** 已限定檢視 `task-1-checkout-fix.diff` 與 report 的 checkout-byte follow-up：SSOT 與 isolated JD package 固定 LF，使 codegen 的逐 byte 比對跨 Windows checkout 一致；較後的 `experiments/jd-editor/licenses/** -text` 明確關閉授權原檔的 Git 換行轉換，保留來源 bytes。codegen 在官方 Python generator 成功後僅機械地將 CRLF 換為 LF，不改 DTO 欄位／schema 語意、不手改生成物，並同樣適用 check-codegen 的暫存輸出。新增 raw-byte regression 直接檢出這次真正遇到的問題；controller 報告的 RED 1 failed → codegen/check GREEN／Python27 passed 已讀，未冒稱本人重新執行。三個 authored 檔單一 EOF 空白刪除不影響先前 native 審查。沒有新增 finding；最終 staged 104 license entries 與5 artifacts 的 raw-byte核对由 controller 在 commit 前執行，本次未代稱該後續核對已完成。原有未驗範圍與 R1/R2 CLOSED 結論保留；未改 code/index／未commit／未重跑套件。
