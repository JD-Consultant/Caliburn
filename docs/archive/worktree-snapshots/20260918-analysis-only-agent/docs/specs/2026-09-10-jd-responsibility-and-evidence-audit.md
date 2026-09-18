# AI 職務說明書顧問：全流程責任與證據稽核

2026-09-10；JD-R002/C03，連動 JD-R001／C01／C02。**G2 定點補證／G4 缺口稽核；不是新產品取捨、已修正的 schema 或 production 施工授權。**

**後續執行狀態（同日）：**Owner 同意補正，TF／ER 已落入同一候選 schema 與工具語意，DB02–04／ER03 固定有限實作方案，詳 §10 及[驗證紀錄](evidence/jd-contract-closure/README.md)。§1–9 保留補正前的稽核、候選分類及當時驗證，不能當作新版本仍未修正或所有整合已通過；production authority 不變。

Owner 要求研究涵蓋整個 AI 專業職務說明書顧問，不限於 Owner 舉出的參數、錯誤、引用與資料庫例子。本稿是責任與證據覆蓋索引；語意仍由[主設計](2026-09-09-jd-editor-app-integration-design.md)、[工具契約](2026-09-10-jd-app-tool-contract.md)、[schema 附件](2026-09-10-jd-editor-contract-schema.md)及既有內容指南各自維護，不在此建立第二份契約。狀態及唯一下一步依 [register](../current-decisions.md)。

## 1. 從產品效果檢查整個設計

目標是員工透過持續訪談，讓 AI 理解自己的真實工作，再形成完整、有依據、可更正的個人 JD。品質包括：事實忠實、工作完整、責任邊界、必要條件與例外、案例和常態的區別、未知的保留、閱讀品質，以及持續編輯與保存的可靠性。使用者不必懂專業寫作，也不必代替工程團隊發現漏研究的技術問題。

「最佳方式」以這些效果和實測比較判斷。採用最新仍適用的成熟官方能力、核對版本及棄用狀態；較早且仍有效的契約可沿用，不因新名詞、更多 Agent 或更多工具而自行換架構。既有 Memory／訪談研究保持其成果與已知限制，有實際接點缺口才定點補證，不重開整套 Memory。

每個會影響正確性、模型負擔、保存、安全恢復或員工體驗的設計，必須能回答：

1. 要達成哪個效果、避免哪個已知失敗？
2. 由 LLM、App、原生框架、資料庫或使用者中的誰負責？App 已知、能推導、原生會產生的資料，為何還需要模型填？
3. 官方直接證據是什麼？查閱日、適用版本、穩定／預覽／棄用狀態是什麼？採用套件的授權是否仍符合免費開源？
4. 哪些是跨來源共同原則、哪些是 Caliburn 的需求映射？未公開的內部實作保持 Unknown。
5. 正常、失敗、取消與重開時如何驗證？目前只讀文件、只驗 schema、已驗原生，還是已驗整合與自然模型？

這是對重要設計決策的工程紀律，不要求替每個變數名稱尋找大廠先例。官方沒有通用 JD 資料表、固定三工具或唯一通知長度；本案仍須從需求推導並驗證，不可把自己的映射命名成大廠共識。技術資料能回答的問題由研究者主動處理；只有確實改變已同意效果的取捨才回到產品討論。

## 2. 全流程責任與覆蓋狀態

下表的「已研究」不等於「已接通」。既有固定證據直接沿用；缺口和未驗狀態不因本文成立而關閉。

| 面向／效果 | 主要責任 | 證據與設計位置 | 目前可說到哪裡／剩餘驗收 |
|---|---|---|---|
| 訪談、追問與專業內容 | LLM 判斷工作意義、缺口、條件、未知；員工提供／更正事實；App 保存原話 | [內容研究](2026-09-09-job-analysis-and-jd-content-research.md)、[工作分析](2026-09-09-complete-work-analysis-guide.md)、[深度與追問](2026-09-09-customized-jd-depth-and-interview-calibration.md) | 內容方向已有研究與樣稿；真職位持續訪談及未見案例的專業品質未因此通過 |
| 何時寫、改哪些工作 | LLM 在理解足夠或有實質更正時決定；App 不以每輪／每次 Memory 更新強迫改稿 | 主設計 §3.1／§3.4、既有顧問 Skill 接點 | 已同意節奏；須驗該寫有寫、不需改時可只訪談，不能用固定工具回應證明自然選擇 |
| 工具與参数 | LLM 選語意目標、有限操作、新內容與相关來源；App 注入 scope／版本／執行身分 | 工具契約 §2–5、下方 §3、官方 [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)／[Anthropic define tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools#best-practices-for-tool-definitions) | 原則有直接依據；本輪找到 TF01–04，正式模型說明及實際使用效果仍待補 |
| 定位與內容運算 | App 解析已發配 ref／有效基底；Plate 計算原生操作和新節點 ID | [正式 profile](2026-09-10-jd-plate-document-profile.md)、[F02](evidence/2026-09-10-jd-official-profile-probe.md) | 固定 headless／JSON 能力已有界通過；不是完整 App、DOM／繁中 IME 或模型誤定位通過 |
| 人改後 AI 知道變化 | App 將已保存現況與可查差異供給模型；LLM 理解變化，必要時追問 | [跨輪研究](2026-09-10-jd-context-change-and-source-research.md)、[OpenAI](evidence/2026-09-10-jd-context-openai.md)、[Anthropic](evidence/2026-09-10-jd-context-anthropic.md) | 模型可見 context 有官方機制；本案基準、預算、壓縮／重開恢復及實際 request 尚待固定／驗證；UI 通知不算模型已知 |
| 原話、Memory 與引用 | LLM 選擇內容相關依據；App 驗 scope／既發引用並回查唯一來源；Memory 是可修訂理解 | 工具契約 §8、跨輪研究 §4 | 目前沿 canonical 原話回查；裸 Memory path 不能當永久原始證據。Memory 版本 locator 僅在日後需要追查 AI 參考哪版理解時另定，不列本輪阻塞；本輪釐清的是 TF03 來源參數語意 |
| 工具結果、錯誤與恢復 | LLM 只修可修的語意／參數；App 處理執行、保存、對帳、取消與停止 | 主設計 §6／§7.1、下方 §4 | 原則已研究；ER01–03 尚未閉合。回覆說成功不能取代實際提交 |
| 保存、版本與隔離 | PostgreSQL 強制鍵、交易及鎖；App 持有 JD 唯一保存責任，讀寫同文件 | 主設計 §5、[資料關係稽核](evidence/2026-09-10-jd-storage-relations-audit.md) | 存整份 clean value 是本案選擇；DB01–04 須固定。真正兩連線競爭、回覆遺失及重開未由 schema 驗證代替 |
| 員工閱讀、手改與審閱 | 原生 editor 編輯；App 顯示真實差異、保存狀態及同畫面歷史；員工核對事實 | 主設計 §5.1／§5.5／§8.1、[審閱裁決](2026-09-09-jd-editing-and-review-working-design.md) | 持續工作稿已同意，不再做逐筆 pending 接受／拒絕；保存不等於看過或專業核准。正式人編／取消／重開須驗 |
| 契約與 provider 接線 | SSOT 生成 DTO；App 驗完整格式及跨欄位條件；既有 SDK 傳輸 | schema 附件 §6、[序列化證據](evidence/jd-contract-schema/provider-wire-README.md) | 本地 SDK request 形狀有證據；不是 provider 接受、ToolNode 執行或模型理解證據。描述仍為 probe placeholder |
| 品質、成本與回歸 | 工程固定測試＋經專業校準的內容評估；LLM 可輔助評分但不獨自核准自己 | [六切片計畫](../plans/2026-09-10-jd-editor-core-implementation.md)、下方 §6 | 固定文件能力與自然模型效果分開；付費測試另定資料及預算，不能用「滿分」宣稱品質已保證 |

免費開源選型與逐套件授權維持[既有能力研究](2026-09-09-jd-oss-editor-capabilities-and-gaps.md)及 F02 lock／LICENSE 證據。ChatGPT／Claude 商業畫面是概念參照，不是付費功能採用。版本更新時對實際採用套件追 release／migration，不把本次查閱日稱為永遠最新。

## 3. 模型需要填什麼，App 應接走什麼

OpenAI 官方直接建議讓程式提供已知參數、用清楚結構減少無效組合、清楚說明用途及回傳；Anthropic 同樣強調工具目的、参数及限制、相關操作的組織與有用結果。兩者共同支持「讓模型選語意、程式承擔確定操作」的方向，**沒有共同指定 Caliburn 的三工具或七命令**。OpenAI 的少於 20 工具是起始軟建議；不能據此證明三個最優。`read` 不必然接 `edit`，也不能只為減數量合成每次必改的工具。

| 現有工具 | 模型實際輸入 | App／原生負責、模型不填 |
|---|---|---|
| `jd_read` | 空物件讀目前稿，或一個已發配 revision／target／selection／continuation ref | 文件 scope、ref 解析與有效性、固定版本、內容／target／續頁發配 |
| `jd_edit` | 有限 commands、已發配目標、位置意圖、新內容、有限屬性更新及相關來源 | document／run／input／message／tool-call 綁定、operation／digest／base／profile／actor、新 ID、Slate path／offset、完整驗證、真實保存結果 |
| `jd_change_read` | 一個 change ref，或一對前後 revision ref，或 continuation | 同文件／同版本對檢查、immutable 前後內容、實際差異及顯示限制 |

App 不能替模型推斷「已讀來源就必然支持這段文字」；選擇與內容相關的來源仍是語意責任。相反地，識別码、版本、保存效果或能由同一意圖機械推得的重複表示，不應要求模型猜填。

本輪對候選 schema 的定點檢查使用既有 AJV 8.20.0，未寫入 runtime；候選 SHA256 為 `6B42BA220C0102590DC651692BE7497AE400BD713CB6F0D86FA1C5103F753F67`。以下是**候選缺口，尚未修改 schema**：

| ID | 發現／證據界線 | 契約閉合要求 |
|---|---|---|
| TF01／P2 | 同一屬性可以同時在 `set` 與 `unset`，如 `set:{background:"red"}` 加 `unset:["background"]`；AJV 接受，語意稿未規定結果 | 明確拒絕交集或使輸入無法表達衝突；不能由 native 呼叫先後暗中裁定 |
| TF02／減負候選 | 模型 new-element／properties 同時看得到 numeric `colSpan/rowSpan` 和 HTML string `attributes.colspan/rowspan`；不一致可過 schema，但 App 已被要求拒絕 | 核對保存格式與模型格式的差別，優先單一模型意圖、App／原生生成必要衍生表示；固定清除／預設值規則，不改壞官方保存 shape |
| TF03／語意待閉合 | 頂層 `source_refs` 與節點／properties 內嵌 refs 可重填同一集合；目前要求內嵌是頂層的子集 | 釐清操作依據與節點依據的不同責任；若只為聯集驗證由 App 推得，若文字替換需額外依據不能直接刪除。確定來源附著／移除語意後再縮欄位 |
| TF04／說明與接線待驗 | 既有 provider probe 的 description 是 `fixed offline serialization only`；證明傳輸 shape，沒有證明正式操作指引 | 固定模型實際看得到的用途、何時不改、目標／placement／來源規則與失敗後動作，再驗實際 request 和有限操作情境 |

四個 schema-valid 反例另涵蓋 paragraph 帶 span、span 不一致、內嵌來源超出頂層。後三者已明定 App 的額外檢查，不能因 schema 接受就宣稱 App 存在未設防的實作漏洞；它們是後續 producer／consumer 驗收項，尚無執行結果。

## 4. 錯誤、重試與停止的責任

Anthropic 的 tool result 用原 `tool_use_id` 配對並以錯誤標記及原因協助修正；OpenAI patch 的失敗讓模型重讀／調整，但原子性由 App 決定。AWS 官方要求有界重試、避免多層放大、辨別暫時性與冪等性；同意圖 token、異參數拒絕及副作用與 token 同交易，支持本案對帳方向。這些都不代表官方已提供相同 JD enum 或替本案設好重試數字。[Anthropic errors](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls#handling-errors-with-is_error)、[OpenAI patch errors](https://developers.openai.com/api/docs/guides/tools-apply-patch#handling-common-errors)、[AWS retry](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_mitigate_interaction_failure_limit_retries.html)、[AWS idempotency](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)。

| 情境 | LLM 的工作 | App／runtime 的工作 |
|---|---|---|
| 參數不合法 | 看具體原因，修正新 call | 副作用前拒絕、配對原 call 結果、限制模型修正額度 |
| 目標過時／不存在 | 重讀目前稿，重新規劃 | 確認舊操作未發布，解析新基底；不默認相似文字就是目標 |
| 不支持的內容／操作 | 改用支持方式，保留有效內容 | 誠實拒絕，不丟資料來使驗證通過 |
| 引擎失敗 | 只有原因確實可由參數修正才重寫 | 丟棄未發布候選，處理程序故障／停止，不能一律交模型修 |
| provider HTTP 暫時失敗 | 不負責修 JD | 沿既有 SDK transport 重試，不重跑整個 Agent／寫入工作流 |
| 保存確定失敗 | 不改文字來修資料庫 | 已確認未提交；終局回執前受控重試，終局結果不覆寫，保留可恢復輸入 |
| 保存結果未知／回覆遺失 | 不送替代新增 | 同 operation 對帳；找到回執返回原結果並只補缺失原 call 結果；用完額度仍未知不能猜失敗 |
| 同 operation 不同 payload | 不自行改 operation ID | 拒絕衝突，保留原回執及原操作處理責任 |
| 讀取失敗／忙碌 | 不把不可讀當內容不存在，不無限循環 | 有界唯讀重試／等待，明示恢復或停止入口 |

| ID | 本輪發現 | 關閉條件 |
|---|---|---|
| ER01／P2 | `JdWriteResult` 只對部分狀態限制 `next_action`；shape 仍容許 `save_failed + correct_arguments`、`stale_base + continue` 等違反語意的組合 | 同一 status×next_action 矩陣供 schema 可表達部分與 App producer／runtime 執行；`wait`／`reconcile_operation` 明定是 App 行動，不新增模型工具 |
| ER02／P2 | `JdReadFailure` 只有 invalid-input／unsupported／target-missing／busy，未交代 DB 暫不可讀的誠實出口 | 明定 typed read error 或外層 runtime error 的唯一責任、模型可見結果與恢復，不讓實作者猜 |
| ER03／接線前須固定 | SQL、Node 與 receipt 查詢只有有界原則，缺各層可重試條件、次數／時間、取消與用完後結果 | 列責任與有限策略；SQL 已回滾可重試和 commit unknown 對帳分開。SDK HTTP retry 與模型／工具額度都不能代替基礎設施上限 |

既有隔離 `conversation.py` 已明說不加外層 HTTP retry；沿用此邊界。OpenAI／Anthropic SDK 的 transport 預設重試不等於 JD 工具去重或安全重播：[OpenAI Python](https://github.com/openai/openai-python#retries)、[Anthropic Python](https://platform.claude.com/docs/en/cli-sdks-libraries/sdks/python#retries)。

## 5. 資料關係也要有依據，但不冒稱存在通用 JD ERD

官方 Slate 文件的 Editor／Element／Text 樹與自訂 props 支持保存結構化文件；它不替業務規定「一項任務只能需要一項技能」。本案把職責、任務及敘述保留在官方 clean tree，不能從畫面父子關係推論全域技能實體的一對多，也不因理論上可多對多就增加 master tables。[Slate nodes](https://docs.slatejs.org/concepts/02-nodes)、[既有內容關係研究](2026-09-09-jd-document-relationships-working-research.md)。

資料庫採用依據是本案的保存與隔離需求，加上 PostgreSQL 如何強制 PK／FK／UNIQUE／CHECK／交易的官方契約。完整來源、版本與 finding 見[資料關係稽核](evidence/2026-09-10-jd-storage-relations-audit.md)。本輪需處理：

| ID | 關係／缺口 | 工程要求 |
|---|---|---|
| DB01／已決待驗 | catalog 與 head 的 PK／FK 只能保證至多一個，不能保證建立後必定有可讀初版；既有 Task 2 已要求同交易建立 | 保留同一交易完成 catalog／initial revision／head，並驗半途失敗不留下不完整文件；是責任釐清及驗收，不是新設計阻塞 |
| DB02 | committed operation 產生新版本是一對一；多次 no-change operation 可以引用同一既有版本 | 區分「產生」與「引用」；不得對全部 result revision 加 UNIQUE |
| DB03 | revision 指向 producing operation，operation 又指向 result revision，若兩邊都立即 FK 會有建立順序循環 | 明定延後檢查或單向保存的方案，保留同文件與唯一產生關係；不得留給 migration 作者臨場猜 |
| DB04 | JSON Schema 不比較 base/result/actual_changes 的欄位值相等與所有跨列關係 | 同列結果一致性由合適 DB 條件／mapper 檢查，跨列由 FK／交易驗證；JSONB 有合法 JSON 不等於合法 JD |

主設計舊段落要求 catalog 的 active／整份文件刪除驗收，與 §4.1 隔離 catalog 無這些欄位／API 矛盾。本輪修正文義：本版檢查文件存在與 scope；整份 catalog 刪除生命週期在 production adoption 時對照，不新增角色或刪除能力。JD 內職責／任務刪除仍屬原有編輯範圍。

## 6. 用實際成果證明選擇

OpenAI 官方評估方法要求任務特定、貼近真實資料分布、隨變更持續驗證，並用人工判斷校準自動評分。這支持已有的短情境、持續訪談、未用於調整的職位案例與保留失敗證據；不能靠通用排行榜、單份漂亮樣稿或模型自評 100 分代替本產品驗收。[Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices#how-to-read-evals)。

本案驗收依既有計畫分層：

- **文件能力：**完整內容／ID／條件保留、繁中及重複文字定位、移動／拆分／貼上、真實差異、保存／重開、失敗與取消。固定呼叫可驗機械結果。
- **模型使用 App：**看得到必要工具說明與文件變動，選對操作，錯誤後能修正，保存未知不重複新增；檢查實際送出的模型請求，不只看 runtime 變數或 UI。
- **專業顧問效果：**是否理解工作、適當追問、資訊足够才寫；不把案例變常態、不補造未知、不因局部更正抹掉其他工作；工作→JD 與 JD→來源雙向核對。
- **持續品質與代價：**長訪談、壓縮／重開後續編、未見職位、誤改／漏改與資訊保留、錯誤恢復、延遲與費用。語意評分需校準，付費測試另列資料和預算。

上述是工程與內容驗收，不啟動已 PARKED 的真人顧問交付功能。採用評估方法也不等於採用某個雲端評估平台：本輪查到 [OpenAI Evals guide](https://developers.openai.com/api/docs/guides/evals)已公告 Evals platform 棄用，2026-10-31 轉唯讀、2026-11-30 預定關閉；不把該平台列成新的採用依賴。官方方法仍可用於既有本地評估與經核准的模型測試。

## 7. 本輪完成與唯一下一單位

本輪完成：既有設計的模型／App／框架／DB 分工核對、兩家工具與錯誤原則補證、PG16 適用約束稽核、整體品質覆蓋索引。TF01／ER01–02 是明確契約缺口；TF02–03 是須裁定的減負／語意候選，TF04／ER03 是接線前要固定的說明與策略；DB01 為既有決定待驗，DB02–04 為關係及約束补正，不能全部稱作已證實作漏洞。主設計的 busy「尚未同意」及 catalog active／delete 舊敘述同步修正；schema 附件釐清隔離接線與 production gate。沒有修改 schema、production／隔離 runtime、DB、Memory 或模型指引，沒有安裝或付費模型呼叫。

**下一個有限工作單位：補正這一批已定位的契約缺口，然後依原六切片接線。**TF01–03、ER01–02 涉及共用輸入／結果，須先統一工具語意、SSOT 和檢查責任，不能先生成已知有歧義的契約。TF04 正式說明在 Task 3 binding 前驗；DB01–04 與 ER03 各層策略在 Task 2／對應接線前固定；跨輪 context 的基準／預算／恢復依既有 Task 3.3a 處理。工程選擇由研究者據官方資料與需求完成，不再向 Owner 詢問技術欄位。

退出條件：每個 finding 有具體處置、唯一責任文件、相符 schema／App invariant 與有限驗收；獨立 review 無影響該切片的未決缺口。若剩餘疑問只能實作驗證，明列測試及停止條件，不追加泛化引擎。先前 S5 審查保留其當時的有限結論，本次新發現不能被「先前通過」掩蓋。Plate／持續工作稿／單畫面／本地單人／真人交付 PARKED 不重開，ADR 0073 仍 Proposed，production G6 不變。

## 8. 本輪來源範圍

本輪外部來源查閱日均為 **2026-09-10**。OpenAI／Anthropic 工具指南屬現行公開 API 指南；引用的段落未標 preview，但不是產品內部實作保證，亦未提供各段精確發布日。兩家 SDK 僅作重試層責任參照，未新增採用；實際安裝版以既有 lock／provider 證據為準。AWS 可靠性文章是一般工程原則，不是 Caliburn 契約。PostgreSQL 依 **16** 官方文件，詳 DB 附件；JSON Schema 依 **draft 2020-12**，其形狀约束與 App 語意檢查分工見[官方 object reference](https://json-schema.org/understanding-json-schema/reference/object)。

框架版本／授權沿正式 profile／F02：Plate 53.3.11 及逐套件 exact lock／MIT 核對，詳各責任附件，不從商業文件推定所有功能免費。Codex experimental 接點／Apache-2.0 公開源碼，以及 Claude 公開 SDK 與閉源模型請求範圍，沿跨輪研究的明列版本與證據界線。本文來源是研究參照，未將新服務或 SDK 加入 runtime。

## 9. 文件審查與驗證紀錄

本輪獨立只讀 review 找到一項 P2：把日後才可能需要的 Memory 版本 locator 寫成必補接點；已恢復其條件性，不列本輪阻塞。另將 DB01 明確標成既有決定的責任／驗收釐清。審查者重讀修正後確認該 P2 關閉，無剩餘影響本次稽核交付的 finding；這不代表 §3–5 的待補正契約已修復。

文件檢查：既有 36 份 JD 路由文件的 463 個本地連結、79 個錨點及封存 hash 核對無錯；新增本稿與 DB 附件的 26 個本地連結／空白檢查無錯。既有失敗／反例保持原狀，沒有重跑原生或模型實驗。`git diff --check` 通過；正式候選 schema SHA256 仍為 §3 原值，production `apps`／`packages`／root package 與 lock 無本輪變更。這些結果只證明文檔路由與證據未受破壞。

## 10. Owner 同意後的契約補正

本次唯一工作單位是已定位的契約補正；沒有擴展產品、替換 Memory、另造編輯器或啟動 production。官方原則、原碼及本案取捨分別保存在[模型參數](evidence/2026-09-10-jd-model-input-contract-closure.md)、[錯誤與恢復](evidence/2026-09-10-jd-error-recovery-contract-closure.md)、[資料保存](evidence/2026-09-10-jd-storage-contract-closure.md)三份定點附件；現行語意回寫主設計／工具／schema 附件及六切片，不由歷史稽核表覆蓋新規則。

| Finding | 已完成的處置 | 仍須施工驗收 |
|---|---|---|
| TF01 | SSOT 共用有限 set／unset 交集限制；模型與 resolved commands 同用 | App 預檢、Node 執行零副作用 |
| TF02 | 模型僅 numeric span；saved HTML 表示不刪。固定 native 同步／清除 fallback 規則 | 完整合法表格的原生 adapter、同批接續及重開 |
| TF03 | 移除頂層來源集合；附著位置輸入、App 收聯集。明定保留／清除／unwrap 歷史，不假造 consulted-source log | 既有來源 owner 的 scope／窗口及正文／引用前後結果 |
| TF04 | 正式說明由 SSOT 維護，現行 SDK 的實際本地 request 已驗完整傳遞 | 真 ToolNode 執行、真 provider 接受與自然模型使用效果 |
| ER01–02 | 兩層動作矩陣、未閉合優先對帳、failure refs 及 typed read_failed 已入 SSOT | producer 實際效果／真實回執／中斷結果 |
| ER03 | 每明示階段一次 attempt、零自動重播，控制預算、取消清理與可恢復 UI 責任已固定 | 真程序退出、SQL rollback／unknown、額度及恢復入口 |
| DB01 | 保留既有同交易建立初版要求 | 初版中途失敗原子性 |
| DB02–04 | 單向 FK、committed 部分唯一、producer 反查、終局約束、JSONB 完整相等與 mapper 核值已固定 | DDL／真正兩連線競爭／重開／持久性設定 |

有限驗證：86 defs、201 個 shape／矩陣／例子檢查均符預期；同一最終檢查在原 schema 有136項 mismatch。正式三工具的參數／說明經現行 SDK 的 MockTransport 全等，0 工具執行、0 外部 provider／付費請求。這不是201個真實員工情境，也不是原生或資料庫測試。初次紅燈、中間綠燈、完整 before／after 及最終輸出分別保存，詳[驗證入口](evidence/jd-contract-closure/README.md)。

兩路交叉只讀 review 分別核模型／saved profile／來源與 DB／錯誤恢復，未發現新阻擋；最後 refs-null 補正由主線 schema 正反例核驗。最後一次文義複核另指出主稿仍有泛化「先重試證明安全／runtime換新operation」舊句，已改為先有原writer停止及未提交的證據、再於另次顯式觸發沿原identity恢復；本版零自動重播不變。沒有把設計審查說成 runtime 測試。六切片已加入相應失敗情境與正式說明來源。**本批設計／共用契約缺口閉合，唯一下一施工單位回到原 Task 1。**Task 3.3a 的跨輪比較基準／呈現預算／恢復仍按既定接線前工作處理；不把條件性的 Memory 版本 locator 列必做，不自動啟動付費驗收。
