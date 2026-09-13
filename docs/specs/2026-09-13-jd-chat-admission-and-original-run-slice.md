# JD 聊天接點：已保存版次准入與原回合查回

日期：2026-09-13。Topic JD-R002；RS-4 局部隔離施工。基準 `36cc1cb9`；落點 `experiments/jd-relational-app`。ADR0075 仍 Proposed、production ADR0060 不變，產品模型呼叫零次。

## 完成效果

新訪談必須以員工已確認保存的 JD 版本開始；相同原請求再次送達時先查原結果，不能因 JD 已前進而重新執行。已完成 A、又完成 B 後，可以查回 A 的原生保存與原操作回執。AI 執行期間的查詢不借用 writer 權限，App 關閉仍要等實際讀取結束。

這一單位完成 coordinator／owner／native history 接點。**聊天 HTTP、生成的公開聊天契約、串流與 Web 尚未發布**，日常畫面仍不能自然訪談。原 run 查找遇到保存鏈缺口或超過 256 個祖先位置，明確保留 `original_run_lookup_required`；尚未實作查找續頁，不把這個上限當成「原請求不存在」。

## 研究與採用依據

- [原聊天契約前置](evidence/jd-relational-ai-restart/chat-contract-preflight.md)、[格式與公開契約前置](evidence/jd-relational-chat-control/schema-preflight.md)、[owner 接點](evidence/jd-relational-chat-control/owner-preflight.md)及[原生歷史探針](evidence/jd-relational-chat-control/history-preflight.md)分工承接。框架固定於已有 lock，沒有重新選型／升級。
- 本輪已讀使用者提供的 LLM 工具分享，並直接核 OpenAI／Anthropic 官方工具文件。[採用與差距核對](evidence/jd-relational-chat-control/shared-tool-research-review.md)記清作者建議與官方契約；不將 Memory 提案／待審流程搬入本案。LLM 說明、參數與消息配對依兩家；AWS 對應業務原操作、重試與一致性。
- 原生 LangGraph `parent_config` 是此實作的查找依據。探針證明同文字 prefix／metadata filter 仍可命中另一分支，不能單獨用作原結果證明。新 ID 的不存在判斷依目前完整、未刪除的 Human／消息集合；日後壓縮／修剪必須另處理原話與請求識別保存，不能直接沿用此假設。

## 接點及責任

| 範圍 | 本輪結果 |
|---|---|
| 新原請求 | `AiRuntime.start(doc, run, text, *, expected_revision_id: UUID)` 必填已確認版次。V2 record 保存 canonical `start_revision_id`，其 digest 包含格式、資料集、文件、版次與逐字原話。run ID 仍為外層原請求識別。 |
| 舊原格式 | 原生 Pydantic discriminated union 讀 V1／V2；V1 原 digest／格式照存，close 只改 status，不猜 start revision。新 start 不接受 V1 假裝通過新契約，舊請求走明確 `lookup`。 |
| 嚴格格式 | 共用 native before-model validator 僅補 `type(format_version) is int`，封住 Literal 接受 bool／float 的已證缺口；其餘由原生型別驗證處理。此處比前置外層 parser 建議更直接，連 V1／V2 直接建構也維持嚴格規範。 |
| 原子准入 | `ManualRuntime.admit_foreground` 在同文件 slot 內先核原結果，再核新工作的 idle／封存／head，保留 reservation 到真 Future 掛接。原回合重查優先；新回合 stale 不保存 Human、不呼叫模型。沒有把 SQL 交易持有到模型結束。 |
| 執行前核對 | 真 `_run` 再核 current 及 turn notice 的版次與 admitted base 一致；不一致在 native input 前停止。後續工具可令 JD 前進，仍依真正 `jd_read` 建立每次編輯基準，沒有鎖死整轮工具必须同一舊版。 |
| 原回合查回 | `AiRunHistory.find` 一次固定 current，較舊 run 沿 public Saver parent 查找；候選是有效祖先的 idle terminal，整段原消息必須與目前對話中該輪一致。START 不拿前輪 record 充當新輸入；AI／Tool ID 撞名也不能作未使用 ID。 |
| 固定原生解碼 | `AiRunCheckpoints.observe_at` 只讀指定 root 及其固定 child，沿同一 START／scope／digest／完整訊息解碼，不轉讀 latest。沒有另一張 run／event／lineage 表。 |
| 只讀與關閉 | `inspect_document` 登記實際 callback 的完成 Event；不拿 writer permit，不維持該讀取自身的長 slot lock。close 先停新准入，再排空已登記讀取；同執行緒重入不假裝已停。status 有當地 busy／closed 證據時不讀 Saver。 |
| 工具真結果 | 查舊 terminal 仍核原 binding 與 SQL receipt。AC-R01 修正後，本輪沒有 binding 卻宣稱寫入成功不能通過；合法未執行 error 與前輪已完成工具訊息保持有效。 |

V2 是內部持久 run 格式演進，沒有修改模型工具輸入、JD snapshot、ModelView 或 tool/read binding 各自的版本。所有改動仍在相同 App 業務与十三表 JD 保存流程中。

## 實際驗證與首敗

| 證據層 | 執行結果與限制 |
|---|---|
| 主代理整合窄組 | `test_ai_chat_control`、`test_ai_runtime`、`test_ai_restart` **48 PASS／1.29 秒**；合成 SQL／模型 port、真 InMemorySaver 與 Future。新 stale 反例首跑是 1 FAIL／0.93 秒，舊 start 不接受 expected keyword；實作後拒 stale 且不存原話。 |
| 完整離線組 | [最終輸出](evidence/jd-relational-chat-control/full.final.stdout.txt)：**1961 PASS、201 SKIP、1 warning／29.29 秒**。SKIP 不算通過；warning 是 Starlette 對 AnyIO BlockingPortal 舊別名。沒有為追新升級 lock。 |
| Windows 權限首敗 | [首次完整輸出](evidence/jd-relational-chat-control/full.first.stdout.txt)在暫存 fixture 與清理階段 WinError 5，未產生可信完整統計。以另一個已確認不存在的 workspace 暫存目錄、正常本機權限重跑後全組完成；未刪除或改權限修補原目錄。 |
| 真 PostgreSQL＋SDK 固定回覆 | `test_ai_runtime_postgres` **4 PASS／3.48 秒**。AI→手改→AI 案新增 A 在 B 後的真正歷史／SQL 查回與原 A 重送，仍僅原六個 MockTransport 請求；另驗 COMMIT 回覆遺失、純訪談及中斷。不連 provider。 |
| 真 Windows 新程序＋PG | [最終輸出](evidence/jd-relational-chat-control/host.final.stdout.txt)：**4 PASS／52.87 秒**。更新 helper 以真正 head 送 V2，再驗正常唯讀重開、真未提交退出、已提交 ACK 遺失及原 START／child 保存邊界。恢復階段不呼叫模型／工具、不重跑原 execute、不跑 setup；必要 SQL 對帳仍照原責任執行。原準備過程 SDK 為固定 MockTransport。 |
| 原程序材料 | [四組原始檔案清單與 SHA-256](evidence/jd-relational-chat-control/host-run-records.json)指向本機合成報告、程序退出紀錄；未記真訪談或金鑰。stdout 入 repo 的副本只移除尾端空白，raw 在 `.research-tmp` 保留。 |
| 原生有限探針 | 歷史五組首次全通過，包含另一分支同 prefix、合法 missing parent、固定分頁與 metadata 限制；這是前置機制證據，不冒稱聊天分頁已施工。 |

各窄組與完整組互有重疊，不相加宣稱更多獨立案例。固定 SDK／真 DB／新程序不能代替自然訪談品質或真人試用。

## 獨立審查

- [Owner 審查](evidence/jd-relational-chat-control/owner-review.md)：116 項窄測試通過，無阻擋項。
- [格式及固定解碼審查](evidence/jd-relational-chat-control/records-review.md)：81 項窄測試通過，無阻擋項。
- [歷史定位審查](evidence/jd-relational-chat-control/history-review.md)：21 項窄測試通過，無阻擋項。
- [Coordinator 審查](evidence/jd-relational-chat-control/runtime-review.md)：AC-R01（P2）本輪無 binding 的假成功已重現、修正與窄複核；保留前輪合法成功，沒有回滾既有 SQL。

## 下一個工作單位

依[成品施工計畫](../plans/2026-09-13-jd-relational-app-implementation.md)，建立同一來源生成的 ChatStart／狀態／歷史／Problem，接 public service 與 HTTP，再接同頁聊天。查原請求／取消／恢復各自有明確作用；GET 不重播，顯示原話已存、run 狀態及 JD 原操作效果。聊天歷史以固定原生消息分頁，不從多份 checkpoint 疊加；超界原 run 查找須有可行後續出口。

Memory／source、選區、串流預覽、JD 整份還原／整轮撤回與完整 App／自然模型／真人驗收仍未完成。Excel 延後；不建立待審接受流程、不新增模型一般檔案工作區、不接回舊產品寫入路徑。
