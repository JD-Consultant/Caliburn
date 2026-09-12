# JD 管理 App：需求重審與設計審查

- 日期：2026-09-12；Topic：JD-R002/C01–C03。
- 結論：**Needs revision；本批 G4 草稿未通過，不據此施工。**本次是文件與官方契約走查，未執行新 UI、DB 或自然模型測試。
- 最新修訂：**JR-R01–05 均 DESIGN CLOSED**；R02／03 見[保存契約窄複核](2026-09-12-jd-relational-save-contract-review.md)，R01／04／05 與新增首敗見[完整業務複核](2026-09-12-jd-business-operations-review.md)。以下初審定位與反例保留作歷史，狀態依本段更新。未完整草稿／撤回等產品問題及整體 G4 未通過；不能將文件閉合稱產品已驗。
- 審查方式：主代理核對工具、編輯器與產品流程；兩個唯讀子代理分別核對 JD 內容研究與保存契約；以下只收錄經主代理再次核實的結論。
- 範圍：[需求紀錄](../2026-09-12-jd-relational-editing-requirements.md)、[整體設計](../2026-09-12-jd-relational-editor-design.md)、[資料庫草稿](../2026-09-12-jd-relational-schema-and-write-contract.md)、[工具草稿](../2026-09-12-jd-relational-agent-tool-contract.md)。本稿記 finding 與討論狀態，不建立另一套正式 schema。

## 1. 本輪使用者澄清及效力

1. 過去已確認的需求也能調整；須核對當時情境、現在效果及理由，不能列為「不可重議」而跳過需求討論。
2. 需要可管理與 CRUD 的 JD App；員工和 LLM 共用業務邏輯、規則與保存結果，入口可以不同。
3. **本輪已確認：App 統一排版，欄位可寫文字與換行。**因此目前沒有必須採 Plate 的需求證據。推薦以一般文字欄位及結構化清單承接管理；這是本案選擇，尚未換 UI 或移除套件。
4. 刪除含任務職責的 D01 初審時保留，後續 Owner 明確授權研究者裁決，現採[刪職責保留任務](../2026-09-12-jd-relational-editing-requirements.md#8-d01刪除職責時保留任務2026-09-12)。授權來源與裁決者分開記錄；不是把技術偏好冒充 Owner 親自選項。必要範圍已依後續授權裁決並閉合 JR-R05 文件反例，整體 G4 未通過。

已確認不等於過時，也不等於永不重議。先保留能說明使用者工作且沒有新反證的語意；真正改變產品效果的取捨才拿具體案例討論。表數、工具數、SQL isolation、框架 API 不交使用者裁決。

## 2. 內容研究的承接範圍

| 依據文件 | 本輪核對結果 |
|---|---|
| [完整工作分析](../2026-09-09-complete-work-analysis-guide.md)、[欄位與寫作指南](../2026-09-09-jd-field-and-writing-guide.md) | 結構化欄位仍須容納本人行動、責任、判斷、交接、條件與重要低頻工作；不能縮成標籤或強制分析欄位。 |
| [深度與訪談校準](../2026-09-09-customized-jd-depth-and-interview-calibration.md) | 能保存有依據但未完整的工作，不用必填要求迫使模型補造。 |
| [完整格式](../2026-09-10-jd-format-review.md) | 六章、成果與要求兩組並列、知識／技能共享定義仍有明確產品理由；任務標題與敘述不強制同義重複。 |
| [關係研究](../2026-09-09-jd-document-relationships-working-research.md) | 身分、位置、適用範圍需分清；其中未歸任務的成果／要求是舊情境下的候選，需本輪另確認。 |
| [前端工程師樣稿 r2](../2026-09-09-frontend-engineer-jd-sample.md) | 作內容與深度範例；它早於部分明確關係設計，不能把其閱讀版直接當最終欄位／SQL 格式或自然模型驗收。 |

這不是宣布六章永遠固定，也不是宣稱現在 schema 已完整承接全部內容情境。

## 3. 具體 findings

### JR-R01／P2／DESIGN CLOSED：AI 組合修改的成功界線前後矛盾

定位：整體設計 §3.2（第 70 行）說 AI 一次 `jd_edit` 是原子 batch；工具稿 §4（第 144–146 行）卻限定只有人工可 batch，AI 每個小工具各自提交。工具稿 §3.3（第 63–75 行）還將新增 duty／task／K/S 的 `initial_text` 固定先寫名稱，再用另一工具補敘述。

反例：更正「對外承諾須由主管核准」需要同步改任務要求及共通權限。人工可以一次保存，AI 第二個工具若失敗，可能留下互相矛盾的兩處正文。另一例是已有完整任務敘述，卻仍須先提交名称，才能補入已知的內容。允許未完整草稿不代表必須把已知的完整工作拆成多次保存。

要求：先以新增一項任務、移動任務、更正責任範圍等情境定義共同的業務效果和保存界線，再比較具名完整操作與有界組合。不要先凍結七工具，也不直接改成任意巨大 JSON。人與 AI 的入口可以不同，但相同業務效果不能有矛盾的規則。

依據：OpenAI 建議由程式承擔已知參數，整合固定連續呼叫的功能；Anthropic 建議以重要工作流程設計工具，避免直接包裝每個 API，並以實測比較。它們支持按工作設計工具，不支持「越細越好」或某個固定工具數。[O1] [A1]

### JR-R02／P2／DESIGN CLOSED：目前內容與版本缺少共同讀取快照

定位：資料庫稿 §9（第 321–325 行）、整體設計 §5.1（第 96 行）、工具稿 §3.1（第 43 行）。

反例：讀者先讀 r5 的職責 A／B；正常寫入新增 C 並把任務 T 移至 C、提交 r6；讀者再讀 r6 的任務。這份回覆會出現 T 指向沒有一起讀到的 C。寫入全成、FK 正確，也不能保證分次讀取的一致性。

要求：明定 current projection、head／refs 與來源狀態的同一讀取界線。可評估單一 SQL statement 或 READ ONLY REPEATABLE READ transaction；分頁亦須固定同一版本或明確要求重讀。用讀寫交錯反例驗證，不能只測寫入 rollback。[P1]

### JR-R03／P2／DESIGN CLOSED：整體 rollback 與持久失敗回執未接合

定位：資料庫稿 §6.2（第 275–282 行）、§7（第 299–306 行）；工具稿失敗範例（第 190–202 行）回 `receipt_durability=confirmed`。

反例：人工 batch 第一步移動成功，第二步驗證失敗。按新稿「任一步失敗整體 rollback」，內容能還原，該交易中的 receipt 也不會留下；但結果契約又承諾可查的 confirmed 失敗結果。stale 在候選套用前被拒絕的 receipt 分支亦未說明。

要求：區分 operation 綁定前拒絕、可回到 savepoint 的語意拒絕、整筆交易失敗，以及 commit 結果未知。只有實際提交失敗回執才回 confirmed。交易失敗後的結案須明確接續已驗的原 operation 對帳與 writer 停止證明，不因新表格式再造一套恢復系統。[P2]

既有 [lifecycle §6.5](../2026-09-10-jd-native-process-lifecycle-design.md)、[人工恢復契約](../2026-09-10-jd-manual-recovery-transport-design.md)已有相關恢復流程。因此本 finding 是新稿的接合矛盾，**不是整個專案沒有恢復設計**。

### JR-R04／P2／DESIGN CLOSED：選取替換與整欄替換的輸入語意不一致

定位：工具稿 §3.2（第 47–57 行）。`text` 範例定義為整欄新全文，`target_field_ref` 又接受 selection ref，說明則稱只提供替換文字。

反例：任務敘述「依約定按月檢查，異常交由專案經理協調」選取「按月」要求改為「每季」。若模型遵照全文參數說明，卻由 App 只替換選區，會重複整段；若模型只給「每季」卻按整欄解讀，會丟失其他工作內容。

要求：分清整欄與選區的文字語意、驗證與回傳效果；工具描述必須讓模型在同一輸入下只有一個合理解讀。可以用不同操作或明確型別，但不由本審查先定工具形狀。不要求模型算行號，也不能以不透明 ref 代替清楚的編輯契約。[O1] [A1]

### JR-R05／P2／DESIGN CLOSED：任務移動與刪職責的內容驗收未涵蓋共通條件

定位：[完整格式](../2026-09-10-jd-format-review.md)的適用條件放置規則允許真正共通條件集中在職責說明；新資料庫稿 §3.5、整體設計 §11 原只核對 parent／排序變動及 ID、從屬內容保留。後續 §7.2 D01 新增保留要求，具體流程尚未閉合。

反例：職責 A 說明「以下維護均限服務約定」，其任務省略重述。移至 B 後所有資料列都還在，但限制可能不再隨任務可見；也不能因此自動套用 B 的不同限制。D01 刪 A 並保留未分組任務時也有同一問題：歷史找得到 A，不能證明目前 JD 仍保留限制。

要求：補移動及刪職責前後的適用範圍呈現、必要文字保留與保存前置案例，沿既有內容研究決定資訊放置；仍有效的條件須在目前稿可讀，不能把「列沒遺失」或「歷史找得到」當「工作意思沒改」。任務自己的來源保留；被刪 duty 的 current links 不得懸空或自動改掛到任務，需以實際文字調整及來源核對處理。D01 只裁決任務生命週期，未閉合本 finding；尚不能推定需增加關係表或自建條件繼承引擎。

## 4. 要與使用者討論的產品問題

| 題目 | 背景與推薦 | 狀態 |
|---|---|---|
| 欄位內排版 | App 固定呈現；文字與換行足夠，不必配置富文字框架 | **本輪已確認** |
| 尚未歸任務的成果／要求 | 舊關係稿第 76、100 行曾允許；新 schema 要求 task_id。推薦成果／要求屬任務，任務可不完整；若連工作尚未辨認則先留訪談／工作理解，不造假任務。這是新舊輸入情境取捨，不是 SQL 正誤 | **已提問，待回答** |
| 刪除含任務職責 | Owner 後續授權研究者按官方依據及本案需求裁決；採保留任務為未分組，必要範圍隨任務卡，理由見需求 §8／完整業務設計 | **政策已決；JR-R05 DESIGN CLOSED，實測未執行** |

後續依具體任務卡與操作情境逐項討論：新增、改內容、移動、刪除、共用 K/S 修改的影響，以及保存／撤回界線。既有選擇須附原背景；只重開真正影響目前需求的部分，不要求使用者重答整份歷史。

## 5. 官方依據與使用界線

本輪查閱日均為 2026-09-12。現行頁面能支持機制或方法，不等於公開了廠商產品的內部資料庫；未以未公開實作推論共識。

| ID | 官方資料、版本／狀態及授權界線 | 本輪用途與限制 |
|---|---|---|
| O1 | [OpenAI Function calling：Best practices](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)，現行 API 指引；服務文件，非採用 OSS 套件 | 工具清楚、已知參數交程式、合適的連續功能合併、工具數由評估決定。不是七工具或 JD schema 標準。 |
| A1 | [Anthropic Writing effective tools](https://www.anthropic.com/engineering/writing-tools-for-agents)，2025-09-11 工程方法，仍由官方提供；方法文章、非版本化 API 保證 | 工作流程導向與評估；較早發布不等於已棄用。與 O1 共同支持按實際任務調整粒度。 |
| A2 | [Claude Tool use overview](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)，現行文件；服務 API 非本地 OSS 依賴 | 模型決定何時呼叫，App 執行 client tool 並回結果；不是要求每輪都寫 JD。 |
| P1 | [PostgreSQL 16 Transaction isolation](https://www.postgresql.org/docs/16/transaction-iso.html)，專案適用且仍受支援的穩定主版本；PostgreSQL License | READ COMMITTED 每個 statement 的快照與 REPEATABLE READ 語意。此輪沒有升級資料庫。 |
| P2 | [PostgreSQL 16 Transactions](https://www.postgresql.org/docs/16/tutorial-transactions.html)，同上 | 全交易 rollback 與 savepoint 的差異；不自動替 App 保存失敗回執。 |
| P3 | [PostgreSQL 16 Constraints](https://www.postgresql.org/docs/16/ddl-constraints.html)，同上 | FK、多對多、刪除策略與完整性；本案 13 表、合併 K/S 表、snapshot 策略都是候選映射。 |
| M1 | [Microsoft 領域與應用分層](https://learn.microsoft.com/en-us/dotnet/architecture/microservices/microservice-ddd-cqrs-patterns/ddd-oriented-microservice)，官網既有架構指南，頁列 2022-04-13；方法參照、非新增依賴 | 業務規則不綁畫面入口；簡單 CRUD 可採較簡單實作。只參考責任分離，不引入微服務或完整 DDD 框架。 |
| E1 | [Plate Introduction](https://platejs.org/docs)、[Form](https://platejs.org/docs/form)，現行官方文件；既有 lock 版本授權見原證據 | Plate 是富文字 React 框架，也可放入表單；「需要關聯 DB」並不能證明 Plate 不適合。依本輪普通文字需求才提出不必採用的方向；沒有新增套件或將付費方案混入。 |

## 6. 未採納為 finding 的推論與交接

- 13 張表的數量本身不構成缺陷；同文件 FK、共享定義＋關係、唯讀歷史 snapshot 可以成立，但具體取捨尚未經本輪需求與反例驗證。
- 資料庫中保存 JSONB 仍是資料庫；原預覽的問題是管理操作與期待不符，不能說它其實只是文字檔，也不能說 JSON 無法表達關係或輸出 Excel。
- 普通文字是本輪明確選擇，故不再列為未授權減少富文字能力；但跨項新增／刪除／移動的撤回效果仍不能由文字輸入框的 undo 自動推定。
- 本輪未改 runtime、schema、生成契約、資料或 production authority；未執行產品付費模型。
- 下一步先確認產品情境，再在原責任文件逐項修正 findings、窄複核，才重新評估 G4／ADR0075；本稿不宣布新設計已完成。
