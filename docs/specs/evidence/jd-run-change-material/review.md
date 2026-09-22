# 固定 AI 改動材料：獨立審查

日期：2026-09-13。結論：**本次有界讀取接點無 P1／P2 finding。**本稿作者未參與此輪 `history.py`／新增測試的實作，只讀審查後執行無 DB 的受影響反例。

## 範圍與責任

- [實作](../../../../experiments/jd-relational-app/src/jd_relational/storage/history.py)：新增 `RunChangeMaterial`／`read_run_change`，以及共用 `_revision_producer` 的抽取。
- [54 個新純測試](../../../../experiments/jd-relational-app/tests/test_run_change_material.py)、原歷史讀取反例及[本輪結果稿](../../2026-09-13-jd-run-change-material-slice.md)。
- 依[CV-01](../../2026-09-12-jd-change-visibility-design.md)及[HR-02](../../2026-09-12-jd-ai-turn-undo-design.md)核對歸屬、固定比較範圍與上層責任；另讀現行 `AiRuntime.inspect_run`、`SavedOperation.from_row` 及 schema 約束。

原生回合與實際 writer 是否閉合、是否取得該回合完整操作集合，仍由 App／runtime 核對。本函式只驗本次已捕捉的 committed ID 集合，不要求它讀 Saver 或額外證明模型回合完成；返回值也沒有 terminal／撤回資格旗標。

## 核對結果

| 風險 | 實際檢查與結論 |
|---|---|
| 混入人工、別文件或別回合 | 查詢同時固定 document、run、origin=ai 與指定 operation IDs，沿既有 committed producer JOIN。逐列再核來源與歸屬；缺漏集合明示錯誤，沒有當空修改或忽略後繼續。 |
| 範圍在讀取中擴張 | `operation_ids` 必須為不重複、最多 96 個 UUID 的 tuple；無效輸入在連線前拒絕。查詢使用原集合，不重新掃最新 run 或 current head；呼叫後新增同輪操作不會擴入原結果。 |
| UUID／時間順序誤當修改順序 | 按 result revision number 排序，並同時核每筆 producer 的 base/result、父版本號及相鄰操作的精確 parent 身分。人工／別輪介入或鏈不連續時返回 `discontinuous`，不提供包含組外修改的首尾淨差異。 |
| 缺 producer、重複或破損 metadata | 缺選定 ID 不形成部分成功材料；重複 operation／revision／number、錯格式／profile、原回執解碼或 parent／producer 不一致都停止。抽取 `_revision_producer` 後，原完整 revision 檢查仍執行相同不變量。 |
| 首尾內容未驗或使用較晚現在稿 | 連續範圍才以原 `_revision` 讀兩份完整端點，執行原 snapshot codec／document／digest／producer 校驗，再核 endpoint 身分及號碼。不讀 current head；中間 snapshot 未全量載入是本次明示界線，metadata 並非全文已驗的宣稱。 |
| 曾改後改回被說成沒有操作 | `receipts` 保留兩筆真事件，首尾可交既有比較器得到空淨差異；`none` 僅表示指定集合為空，而且仍檢查文件存在。 |
| 讀取失敗造成寫入或秘密外露 | 沿一個原生 READ ONLY REPEATABLE READ transaction；所有語句為 SELECT，連線／driver 例外映為固定安全碼，無 writer、重播、callback I/O 或額外 engine。 |

此審查未发现需要新資料表、通用事件回放、另存 run 端點或重造比較器的缺口。公開 DTO、HTTP 與 Web 仍未接入，不能把內部材料通過稱為 CV-01 已交付；目前結果稿有明示這項限制，未見實質誤導的完成宣稱。

## 實際驗證

在原 frozen Python 環境執行：

```text
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -q -p no:cacheprovider tests/test_run_change_material.py tests/test_storage_history.py::test_invalid_arguments_rejected_without_connecting tests/test_storage_history.py::test_read_errors_hide_driver_payload_and_chain
67 passed in 1.00s
```

其中 54 項為新純反例、13 項為原歷史參數／安全錯誤回歸。本稿未修改反例或放寬斷言；未連 DB、呼叫 provider、啟動服務或操作瀏覽器。真 PostgreSQL isolation／driver／JOIN 驗證由另一工作單位與主代理交付，本稿沒有代稱通過。完整模型回合、畫面可見性、撤回及首次 Fetch 故障也不在這次 PASS 的範圍。
