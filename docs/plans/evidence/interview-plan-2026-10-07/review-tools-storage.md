# INTPLAN 工具與保存層獨立審查：2026-10-07

T4 implementer 對 T1／T2 作獨立只讀審查，未發現需阻擋目前施工的 finding。此結論限定於下列原碼與反例範圍，不代表 provider 接受、真模型語意正確、整體採用或訪談品質通過；未改動被審查程式。

責任來源為 [設計 §5–6](../../../specs/2026-10-06-consultant-interview-planning-and-focus-design.md)、[施工計畫 T1／T2](../../2026-10-07-interview-plan-implementation-and-comparison.md)，並核 `code-organization.md`／`coding-standard.md`／`development-standard.md` 的 owner、短交易及生成責任。這份紀錄只保存審查證據，不維護另一份產品 authority。

## 原碼範圍與判斷

| 範圍 | 實際核對 |
| --- | --- |
| `adapters/body_edits.py`、`body_matching.py`；原 Memory 相容接線 | App-only `allow_blank_body` 只放寬原非空前後置檢查。原語法、逐行匹配、ambiguity／scan 容量、全 hunk 成功才建結果與 LF／CRLF 保留沿同一核心。沒有新 editor 或把 Memory 私有業務 preparation 引入 plan。 |
| `transport/model_tools/interview_plans.py` L125–182；canonical tools schemas／generated DTO | 模型只提供 `{}`／`{diff}`；scope、operation、position 與 writer 由 App 綁定。L142 對 `None` 無文字效果保留 nullable 原值，其他比較逐字不 strip。完整 actual diff／unchanged JSON 在 prepare 核序列化容量，execute 不重新匹配、不套新版容量，L182 直接回 owner 原 `result_text`。完整 prepared command 有 strict roundtrip 與 JSON 型別等值核對，不以 `True == 1` 修復保存參數。 |
| `features/interview_plans/models.py`、`service.py` L88–153 | apply 先找原 operation，再逐項核 execution、expected revision、intent digest、完整 next body 與原 result。原結果恢復不寫 current；新 operation 核 current CAS，保存完整 nullable body／result 後才推進 revision。unchanged 仍保存結果與新 revision。read_base 指固定 start，read_current 指現 head，沒有把重入 baseline 換成較新正文。 |
| `workflows/interview_plans.py` L46–96 | file lock → writer lock 保留既有顺序。active-only 新效果核原 writer；paused／cancelled／failed 不產生新效果。completed 分支先由 executions owner 核原 writer，只有 exact retained operation 可恢復，沒有原 operation 就拒絕，不能倒退 current 或產生新操作。 |
| `workflows/interview_plans.py` L29–43；interviews queries／persistence 新 metadata；executions service／persistence batch metadata | workflow 用同檔案 matched formal employee input／reply 與 completed consultant metadata 交集做資格；employee input sequence 受固定 frontier 限制。plan owner 不讀 foreign ORM，也沒有掃外部 owner 正文；它只取得 typed `(execution_id, employee_input_sequence)`。 |
| `features/interview_plans/persistence.py` L135–165 | 資格讀取只 join plan 自有 candidate／operation 與參數化 typed values，按 employee input sequence 最新一筆選 body。最新 winner 為 `None`／`""` 仍保留，不以 truthiness 回退前輪。沒有額外 adopted 正文或完成旗標。 |
| `workflows/consultant_completion.py`；`service.validate_final` L155–179 | 正常完成同交易核最終 plan exact scope／head，既有候選不能以 None 略過。`recover_completed` 只核原 completed writer、context position、exchange reply 與同 execution plan head，不再採用 JD／改後續 Turn 的 head。舊能力無 candidate 才允許 None。 |
| `migrations/versions/0026_interview_plans.py`；ORM table definitions；migration env registration | 兩表與 ORM 的欄位、nullable、unique、shape／predecessor checks 相符。operation→execution、expected revision、candidate base/current 的 composite FK 均綁同 file／execution，索引涵蓋 expected FK 查詢。不可變 trigger 在 job file 仍存在時拒絕 update/delete；整檔删除可走既有 cascade，另一檔案保持。down migration 明確拒絕破壞保留位置。 |
| `scripts/generate_contracts.py` 與 canonical schemas | 新跨 family local ref 只在 staging relocation，原 canonical／packaged schema 保留；remote、越界及 basename collision 明確拒絕。Python／TS consumers 沿生成，沒有手改 generated DTO 或增加第二份欄位定義。 |

## 核過的行為反例

審查逐一讀取以下測試內容，包含成功後的保存結果與拒絕／回滾核對；未把 mock 呼叫當成真 PG 證據。

- `test_interview_plan_body_edits.py`／原 Memory body tests：空建立、全刪成空、EOF 無文字效果、空白與 CRLF、容量、Memory 原非空政策。
- `test_interview_plan_tools.py`：nullable no-op、模糊定位回實際差異、非法後段／零／多處匹配拒絕、prepare 輸出容量、較小新上限仍回原成功結果、缺 prepared nullable 欄位／foreign execution／非整數版本拒絕。
- `test_interview_plan_storage.py`：unchanged 新 revision，原結果重播不倒退 head，completed 只重播原 operation，提交後確認遺失，cross scope／stale writer／pause／terminal fencing，nullable 最新採用 winner，cancelled／failed 隔離，固定 baseline，最終位置錯誤與任意例外完整回滾，完成／取消 Barrier 競爭，原 completed outcome 在後輪前進後仍可恢复。
- 同 PG 檔案的 migration 反例實際用 SQL 核 `CheckViolation`、跨 scope `ForeignKeyViolation`、whole-file delete 後兩表零 row 與另一檔案不變；資格反例分別建立只有 completed／只有正式 exchange，以及不同 file／Memory kind／不在 selected IDs 的執行，核不能採用。
- `test_contract_generation.py` 與 plan contract tests：local cross family、來源逐字不變、remote／越界／碰撞拒絕；required nullable／scalar wire 由生成 `model_dump(mode='json')` 核對。

審查前本切片另實際執行 HTTP/status／兩份 Turn contract 的真 PG 合併 **41 passed**；全 Web **301 passed** 與 Chromium **4 passed** 證據沿 [T4 原件](t4-ui.md)。T1／T2 各自較廣 unit／contracts／PG 命令及主代理後續全套門檻沿其原證據，這份只讀審查沒有宣稱重新執行全部 owner tests。

## 回報與界線

已回報主代理無阻擋 finding，並指出施工計畫 T4 interface 當時仍寫 `fetch(stale0)`，需與已裁決 `query(options)` 的效果等價替換同步。審查沒有改工具／保存／agent 檔案，也沒有 provider 呼叫或資料處置。對使用者的重要未知是否保留、是否正確返回取證、是否成為有據正式 JD，仍由 T5 的匿名語意對照檢查，不能由本審查補足。
