# AI 整輪修改：固定版本的比較材料

- 日期：2026-09-13；Topic：JD-R002；RS-3／4、CV-01 的資料讀取接點，**有界實作、純反例、真 PG 與獨立審查完成**；整體 CV-01 尚未交付。
- 產品依據：[已選的變更呈現](2026-09-12-jd-change-visibility-design.md)、[整輪 JD 撤回](2026-09-12-jd-ai-turn-undo-design.md)。本次不改已定產品語意、不新增 LLM 參數或資料表。
- 施工：[關聯式 App 計畫](../plans/2026-09-13-jd-relational-app-implementation.md)。ADR0075 Proposed／production ADR0060 不變；產品模型呼叫 0。

## 1. 要避免的錯誤

同一輪 AI 可能先補一項任務，再修正剛寫的內容。逐次操作的歷史已可查，但整輪預設應顯示開始前到本次已保存結果的淨差異。若中間夾有人工或別輪修改，不能把它們一起算成這輪 AI 的改動；若 AI 改後改回，也不能把保存紀錄說成不存在。

App 既有的原生回合檢查負責確認操作歸屬與完整性；本次資料讀取只接它已確認的 committed 操作集合。這兩項責任不互相替代，SQL 有幾筆回執不等於模型回合已完整結束。

## 2. 官方依據與本案選擇

| 來源 | 查閱、版本、狀態、授權 | 本次採用與限制 |
|---|---|---|
| [PostgreSQL Transaction Isolation](https://www.postgresql.org/docs/18/transaction-iso.html) | 2026-09-13；實測目標 PostgreSQL 18.6，穩定版；PostgreSQL License。 | Repeatable Read 的後續查詢沿第一次非交易控制語句的快照，不會摻入較晚提交。唯讀交易不會有 serialization conflict。這是同一 SQL 交易的保證，不能外推為原生 Agent Saver 與 JD 跨儲存的共同交易。 |
| [SQLAlchemy PostgreSQL isolation／READ ONLY](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#setting-read-only-deferrable) | 2026-09-13；沿已固定 SQLAlchemy 2.0.52／psycopg 3.3.5，穩定 API；SQLAlchemy MIT，psycopg LGPL-3.0；無新依賴。 | 在第一個 SQL 前設定 connection isolation／readonly，使用原生 transaction context。文件提醒部分其他 driver 有不同 readonly 限制，不能只照範例推定本案 driver；由真 PG 測試核實。 |
| [CV-01 的 OpenAI／Codex、Anthropic／Claude 及 UI 官方證據](2026-09-12-jd-change-visibility-design.md#2-現行官方證據與分界) | 沿 2026-09-12 已核公開產品契約；此處未改 LLM 工具／context 或採用商業功能。 | 變更範圍要明確、結果可檢查；不同產品／模式有不同批准策略。它們沒有公開指定本案 SQL 查詢或 JD 差異算法。 |

本案選擇：以已固定的操作 ID 作本次查詢範圍，在單一短 READ ONLY REPEATABLE READ 交易批次讀取 metadata，確認連續後只取首尾完整版本。這不是「各大廠都用同一個函式」的宣稱，也不增加通用事件回放或差異引擎。實際內容比較仍使用已驗證的結構化 JD 比較器。

## 3. 有界責任與正常流程

1. 既有 `AiRuntime.inspect_run` 依原生回合與永久回執確認歸屬；執行中只能稱本次已確認範圍，完整結束仍沿既有 native terminal／effects 核對。
2. `HistoryReader.read_run_change` 接文件、run 與這次已確認的 committed IDs。最多 96 個、不重複；錯誤輸入在連 DB 前拒絕。這是內部呼叫，LLM 不填這些欄位。
3. 同一讀取交易查文件存在與指定回執的結果／父版本 metadata。按實際版本順序排列，不用 UUID 字典序、時間戳或聊天開始版次當內容順序。
4. 沒有指定修改時返回 `none`；連續時返回原操作及首 base／末 result；不連續時只返回原操作，不提供會混入別人修改的整輪端點。
5. 只有連續範圍讀取兩份完整歷史內容；逐次回執仍保留。讀取不觸碰目前 head、不開 writer，不另建第二份現在稿。

固定的集合不會因查詢中或查詢後同輪又保存而擴張。未來 HTTP 續頁也須固定此次範圍；不能每頁重新取目前最新集合。本次不提前新增公開 cursor 或簽章格式。

## 4. 失敗與避免誤報

- 找不到指定操作、錯文件／run 或錯傳非 committed 操作：固定錯誤，不能當成沒有修改。
- 回執、producer、父子版本、格式或端點 digest 不一致：明示保存資料不一致，不退回猜目前稿。
- 驅動／連線失敗：沿既有安全讀取錯誤，不外露正文／DB 診斷，不觸發編輯重播或新增保存。
- 讀取結果不包含「整輪已完成」「可以撤回」或目前稿標記授權。這些仍由上層依回合狀態及目前版次判定。

## 5. 驗證與交接

| 實際驗證 | 結果與證據 |
|---|---|
| 新純反例 | 首次方法尚未實作時 54 FAIL；落實後 54 PASS。[作者紀錄](evidence/jd-run-change-material/results.md)。 |
| 既有 history／run operations 純回歸 | 50 PASS，12 PG 當時未啟用；不冒稱真 DB 通過。 |
| 獨立撰寫、實際執行的 PostgreSQL 案例 | 首次 13 PASS。反 UUID／時間順序、三次改回、人工／其他 run 插入、指定集合後新增、同讀取交易中另連線提交、六種錯範圍與三種存檔損壞均有反例。[獨立 PG 結果](evidence/jd-run-change-material/postgres-results.md)。 |
| 主代理受影響回歸 | 差異投影／比較 70 PASS；history 25 PASS，含上列原未跑的 12 真 PG、13 純案例與作者回歸重疊。[實際紀錄](evidence/jd-run-change-material/root-regression.txt)。 |
| 獨立程式／責任審查 | [有界讀取審查](evidence/jd-run-change-material/review.md)未發現 P1／P2；另實跑新 54＋舊 13 純反例共 67 PASS，與上述數字重疊，不重複計數。 |

真 PG 當場核 `repeatable read`／`transaction_read_only=on`；固定集合不混入另一連線的新提交。1 與 8 筆操作讀取具有相同查詢數，每次最多兩份完整 snapshot，沒有 current head 查詢，該合成文件十三張表的筆數不變。96 筆上限只經純測，沒有宣稱 96 次真保存或壓力測試；中間版本只核 metadata／回執，不冒稱逐份重驗中間 JSON。

沒有契約／schema／依賴變更；未另跑無關 codegen 或全 App 回歸。前端僅曾暫時診斷 Fetch，已恢復原檔並完成乾淨建置，詳見下列故障稿。

尚未交付：公開整輪比較 DTO／HTTP、畫面目前欄位標記與直接可見刪除清單、完整 CV-01 瀏覽器情境及 HR-02 撤回。這個內部讀取接點不能宣稱上述畫面已完成。

下一單位把此材料接入原 `ChatService` 的唯讀 owner 範圍，重用既有完整差異投影，使用獨立整輪 envelope，不捏造 operation 身分。先有界驗證執行中增添修改時的固定續頁材料與既有 token 大小限制，再生成 DTO／HTTP 並接同頁呈現；不能先把 96 個 IDs 塞入 token，或每頁重算最新集合。這是工程接點，不另重開已同意的直接改稿／查看差異選擇。

同頁聊天的 Fetch 故障另見[有限診斷](evidence/jd-relational-chat-web/transport-diagnosis.md)：第三組取得 TypeError／13 ms／signal 未 abort 的證據，根因仍 OPEN；沒有證據不改 CORS、延長 timeout 或增加自動重送。
