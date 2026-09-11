# Task5 manual recovery transport：有限獨立設計 review

2026-09-10；reviewer為獨立AI。受審候選 `task-5-manual-recovery-transport-design.md` SHA256已實核 **aa6456ab4d96e38bc510b44a061ba4bf0f7a552a5d0f7c201a3a8980a6fbf4f3**。只讀此稿、既採lifecycle／journey／contract-strategy與接受點 `8eec072d51e97735b22c5f0df598b67101fe570b` 的指定 `git show` 原碼；未讀Task5施工source、未跑runtime／PG／OS／模型測試，無implementation verdict。

**Spec verdict：CHANGES REQUIRED。Quality verdict：CHANGES REQUIRED。兩項有限缺口，均在新transport／UI接合內；不重開工具、框架、Windows／PG停止proof或Owner產品選擇。**

## MRD-R01 — exact cache＋no_pending 沒有明確的同意圖提交出口

**Severity P2；OPEN。** 位置：候選L39、L80、L83，§4；§6 MT10/11未涵蓋此可達路徑。

接受Task4 `W/src/jd/JdWorkspace.tsx` 的「依原記錄再次確認」明示呼叫 `session.save(true)`；`useJdSession.ts:save`使用保存的完整原payload／key，並非新key。`A/src/analysis_agent/jd_routes.py:manual_save`先以operation＋digest查receipt，否則再做admission／完整payload保存。因此原POST根本未到server而cache已寫入，並不等同無法處理的資料遺失；員工仍持有exact submission。

新稿取消load自動POST是正確的；GET absence不能被當known-none也正確。但L80將「有未明cache＋無descriptor/receipt」（明列admission前HTTP失敗）停在診斷／未知，L83只明確保留not_admitted／「可重新送出」候選而未定義後者如何成立。若按這個有限union實作，未知候選只能反覆GET或POST manual-recovery→no_pending；兩者都不送payload，discard仍禁止，原可用的明示full manual-save出口可能消失。這是規格不完整，不能靠實作者猜「可重新送出」包含何者。

有限修正：明定**持有exact cache的no_pending／未確認情境保留另一個明示『再次送出同一份』動作**，調用原full manual-save，保持原key/base/value/digest，不清候選、不稱原先零寫入、不使用key-only recovery來publish。它可能是原意圖首次送達，必須誠實區分「查詢／清理恢復」與「提交原候選」；server以同文件owner admission、原receipt/digest及pending身分裁決遲到原POST／新競速。存在有效active或其他未閉合owner時仍不能繞gate；GET no_pending本身不是admission授權。無cache的no_pending則確實不能重建，原限制保留。

補一個有限MT案例：cache已寫、原POST在到server前中斷→重開只GET且no_pending→無自動POST→員工明示原完整提交→成功或真typed拒絕；另驗原POST遲到，同key只一份效果。不得要求先取得not_admitted marker才顯示這個出口，因該反例原server根本未回覆。

## MRD-R02 — available/no_pending 缺server gate投影及terminal待清的動作能力

**Severity P2；OPEN。** 位置：候選L37–39、L53、L67、L78及MT06 L102。

稿內正確要求「有terminal但clear失敗／其他owner outstanding時仍保gate」，卻只有unknown分支攜帶can_recover。available只回result，no_pending只回key，§4亦只對unknown定義恢復按鈕。terminal結果已確認後，Web看不到server是否仍有匹配descriptor待清、是否能再做一次清理，或兄弟native仍未退出。接受點的DocumentOutput只有id/title/created_at/archived/metadata_version；RunOutput是AI run狀態，不代表manual／純read owner。`JdSession.locked`目前靠local manualUnknown與run，不存在可假定已提供的全文件owner gate投影。

server擋寫能避免實際第二writer，**但不能補齊UI應唯讀／仍可恢復的可觀測契約**：Web可能在available後錯解鎖，或保守永鎖且不再提供clear重試。MT06僅寫「不得假定全文件可寫」仍無資料可使該断言成立。

有限修正：在此App-only DTO（或明確指定的同次既有server投影）提供**每個status均可取得的完整文件寫入gate snapshot**，及「此原key是否可明示再作清理／對帳」能力。可採最小共用布林／有限理由，不必新增operation store或通用engine；欄位命名交原作者，但語意、來源與refresh規則須明列。原result可讀與完整owner可新admit必須分開；available且descriptor待清時仍能顯示一次明示清理入口，其他owner outstanding不得偽装成此key可清。gate未知則回錯誤/保留blocked，不能由Web從result推導。POST仍重新admit，snapshot不保證競速後可寫。

MT06補兩個前端可判別assert：①available+matching descriptor clear失敗→結果顯示、寫入disabled、另次合法明示clear可重試；②available或no_pending+其他owner未閉合→server gate blocked，舊key不能清別人。清理成功且全owner已閉合後，下一真投影允許解除相應鎖。MT12覆蓋共用欄位的actual Pydantic→generated TS，不讓Web自行手寫猜值。

## 已核成立的設計部分

- document＋canonical UUID→既有operation，查A不fallback B；digest來可信descriptor，key-only POST不偽造candidate、不變更三模型工具。
- GET無cleanup／checkpoint mutation／Node／模型；讀取故障不同於no_pending；no-store。GET僅觀察、POST重新比對和admit，有race拒絕仍合理。
- 原terminal先於archive回覆；unknown恢復需可信停止證據和既定PG barrier，不能以receipt absence／HTTP abort／Future.done替代。原terminal優先、失敗可讀不算成功。
- recovery attempt單一、lock外有界等待、返回重核generation／identity，晚A不可清B。無新durabletoken、無第二receipt庫。
- actual API Pydantic DTO經既有TypeAdapter/codegen輸出Web、domain不import transport，適合此App-only seam；主JD SSOT與工具shape不改。
- MT01–05、07–09、10–12已有必要正常／失敗框架；上述兩项補齊可達出口及gate觀測即可，不要求另造廣泛測試矩陣。

## Closure

此稿方向可沿用，修MRD-R01／02後回同reviewer只核兩項closure。將來採用按§7同步journey原「不新增route」例外及lifecycle／plan／Proposed ADR0074／register；本review不自行採用或改權威。沒有runtime測試通過聲稱；Task5其他既授權工程可繼續。

## MRD 修訂窄 closure — 2026-09-10

**最新 Spec verdict：PASS。最新 quality verdict：PASS（有限transport設計）。MRD-R01／MRD-R02 均 CLOSED，沒有remaining finding。** 原稿與上方CHANGES REQUIRED／首輪理由保留為歷史，不覆寫。

實核新版設計SHA256 `34004e1e6eac29d6efca4ef5cbda165ad6fd8f44a4e543e3cc675ebd6fbcad6a`；受審精確diff `task-5-manual-recovery-transport-mrd-fix.diff` SHA256 `f9124bb7887eda80f31dfb982c0319585e2699042839c8c3ac512f8381a1ff20`。本輪只讀此兩項修訂及其相依文句，未重審原Windows／PG或runtime，沒有讀Task5施工source／重新跑Task4。

- **MRD-R01 CLOSED：** §4明定exact cache＋no_pending可另次明示完整原key/base/value提交，可能是首次到達，不要求不存在的not_admitted證明，也不從absence推導零效果。新server gate未知／blocked時仍禁用，manualUnknown不再單獨封死此特定出口；普通新候選保存保護保留。原full manual-save核receipt/digest及同文件admission，key-only recovery始終不publish。MT13覆蓋原POST未到／重開唯讀／明示同意圖提交／遲到同key競速與blocked反例，符合原有限修正。
- **MRD-R02 CLOSED：** 全status必填write_blocked及can_recover，來源明定同一完整owner/admission一致snapshot；不從receipt或run猜gate。available可同時blocked且可再清matching descriptor；只有其他owner時本key無清理權。terminal結果與清理效果分開，POST重新占用恢復權、不可重入；資訊不可靠回API錯誤。MT06分開待clear失敗、別人outstanding、本key清完但仍blocked及全閉合後刷新；MT12驗actual DTO生成的必填欄位，MT14驗晚回覆／刷新失敗不能解鎖。

相依核對：兩GET順序與讀取序列、mutation令舊snapshot失效、保存／恢復後刷新及失敗fail-closed已明定；archive仍只阻新意圖，matching recovery仍可走；can_recover與write_blocked並不互斥，no_pending的false清理能力不阻明示full submission。§7同步清單亦已區分「key-only不重播」與「有exact cache的另次完整提交」，不再留下前後語意矛盾。

效力：可交root採用並同步journey／lifecycle／plan／brief／Proposed ADR／register。這是設計closure，不是MT01–14、native停止、PG對帳或UI實作已通過；production G6及其餘原定gate不變，無需新增Owner技術確認。
