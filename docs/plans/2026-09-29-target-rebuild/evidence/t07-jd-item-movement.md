# T07 獨立切片：JD 候選移動／同組排序

- 日期：2026-09-30；狀態：**owner、wire 及 canonical schema 已實作；focused 真 PG／wire 驗證通過。交接前主線已提供正式生成檔並通過直接 import 驗證；註冊及執行接線尚非本切片驗收，不勾 T07。**
- 授權：只寫新 movement workflow／wire／schema、專屬 tests／本證據；不改 registry、bootstrap、generated、UI、既有 JD persistence；不 commit／push／merge、不付費呼叫模型。
- 上位：[JD 八工具 §2／§4／§5／JDT-05](../../../specs/2026-09-29-jd-model-tool-contract-review.md)、[既有完整結構操作 §3.5](../../../specs/2026-09-12-jd-relational-agent-tool-contract.md#35-jd_move_item)、[SDD/TDD](../../../implementation/development-standard.md)、[程式撰寫](../../../implementation/coding-standard.md)。本頁是實作交接與證據，不是新產品 authority。

## 公開 API／主線接點

```python
workflow = JdItemMovementWorkflow(sessions)
intent = parse_item_movement(arguments)
prepared = await workflow.prepare(binding, command_id=operation_id, intent=intent)
# 先沿共用機制保存 prepared，恢復時承接同一份，不重跑 prepare。
result = await workflow.execute(writer, prepared)
```

- `binding` 沿既有 `PublishedMemoryRead`，`writer` 沿既有 `ExecutionWriter`；不新增模型可填的 scope／版本／operation key。
- `PreparedItemMovement` 是凍結 dataclass，可由 `TypeAdapter` JSON 往返；主線須把此型別接入既有 prepared-command checkpoint owner，不另建 registry／receipt。
- 工具名稱 `move_jd_item`；canonical schema：`apps/api/contracts/tools/move-jd-item-arguments.schema.json`。wire import 的 `caliburn.contracts.generated.tools.move_jd_item_arguments` 由主線跑既有 generator 產生，這個切片沒有寫 repo 的 generated；交接前已讀取該正式生成 module 完成測試。
- 一般結果短字串 `moved`；原地且沒有內容效果時 `unchanged`；轉未歸屬時 `moved · 原所屬職責已解除，任務現在未歸屬`。都只是候選效果。
- 業務定位錯誤沿 `JdReadTargetNotFoundError`；非法目的／內容範圍為 `InvalidItemMovementError`；既有 Domain／執行錯誤不吞掉。主線沿共用 model tool 錯誤翻譯產出明確 rejection，不把未知提交當失敗叫模型重送。

模型參數範例：

```json
{
  "read_ref": "task_App已提供",
  "destination": {"kind": "task_parent", "parent_read_ref": null},
  "position": {"kind": "last"},
  "content_changes": []
}
```

`destination.kind=current_container` 表示只改目前容器內同類排序；`task_parent` 才選新職責，null 明確表示未歸屬，兩者不混用。`position` 是 first／last，或 before／after 加 `neighbor_read_ref`；不是數字位置。Task 的能力引用順序仍由 `revise_jd_item` 負責，這裡只排序共用 K／S 定義。

只有真正換職責／未歸屬的 task 可附 `content_changes`：該任務 title／description、其既有成果／要求 text、來源／目的職責 scope_text，或新增該任務成果／要求。其他排序只收空集合。文字用 set_field／clear_field；新增明細用 add_detail。不允許改無關任務／職責、不允許跨組搬成果或要求、不自動清理／更新直接來源。文字變更是否使來源待核對由原來源繼承 owner 判定；新增明細不假裝繼承 task 來源。

## 接法及審查結論

1. prepare 只在 App 綁定的 active A Turn 候選解譯 `read_ref`、目的與鄰項；記錄預期候選 revision、原命令身分及必要 Domain 意圖。
2. execute 取得原 job-file／active writer／candidate guards。在同一 `sessions.begin()` 內呼叫既有 `MoveTask`／各類 `Reorder*`，再套用來源與目的職責摘要修正。沒有新 SQL／表／persistence。
3. 各內部命令 ID 由 App 原 operation ID 確定衍生；`apply_candidate_edit` 查回原 owner 回執，不把重入解讀成新的移動。後續候選已前進時，重放仍回原結果、不倒退目前候選。
4. 一個後段職責更新非法時，前面的移動、明細新增、來源繼承與操作紀錄一起回滾。全程沒有模型／網路等待佔住交易。

2026-09-30 查核 [SQLAlchemy 2.1 transaction 契約](https://docs.sqlalchemy.org/en/21/orm/session_transaction.html)：context manager 正常退出提交、例外回滾；本案沿既有短交易，不造 UnitOfWork。另查 [Pydantic TypeAdapter](https://pydantic.dev/docs/validation/latest/concepts/type_adapter/) 後以實測確認 prepared dataclass 的 JSON 往返。框架不自動保證原操作重入或產品隔離；這兩者仍由既有 owner 與真 PG 反例證明。

作者另行自審：範圍、同容器同 kind、任務身分與來源、無內容修改的 no-op、全成／全拒、read-only prepare 與 execute 的基準檢查均核對；未發現此切片阻擋項。沒有獨立 reviewer 工具，不將作者自審寫成獨立審查。

## 驗證

工作目錄 `apps/api`，Python `.venv-target/Scripts/python.exe`；PG 是明確 loopback 測試 DB `postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test`，fixture 每例新 schema，不用產品 DB。

- **Red**：先放 owner 的明確未實作占位，再跑四個真 PG 行為案例；四項因 `NotImplementedError` 失敗，不是 import／環境失敗。
- **Green／refactor**：`pytest tests/integration/test_jd_item_movement.py -q --tb=short -p no:cacheprovider` → **10 passed**。覆蓋 task 跨組／未歸屬、ID／明細／能力關係／來源保留、不動正式 head、原結果重放、checkpoint JSON 往返、異 scope target／neighbor／writer、無關 content target、跨 kind 明細排序拒絕、無效最終 task、後段 area 失敗的完整回滾，以及 area／detail／capability／collaborator／condition 的代表排序及 no-op。
- **Wire**：先用 repo 既有 generator 相同參數，只把 canonical schema 產到 `.research-tmp/move-jd-item-codegen/move_jd_item_arguments.py`，於測試程序載入該生成 module；`pytest tests/unit/test_jd_item_movement_wire.py` → **6 passed**。涵蓋 current container 與 parent null 區別、相對定位、有限文字／明細、拒絕模型 scope、非法多餘參數／缺 neighbor／清空明細。主線正式生成檔出現後，再直接跑 `pytest tests/unit/test_jd_item_movement_wire.py tests/unit/test_import_boundaries.py -q --tb=short -p no:cacheprovider` → **21 passed**（6 wire＋15 分層）。
- `mypy src/caliburn/workflows/jd_item_movement.py src/caliburn/transport/model_tools/jd_item_movement_wire.py` → **Success: 2 source files**；Ruff check／format 四個新增 Python 檔通過。`Draft202012Validator.check_schema` 確認 canonical JSON schema 有效，不代替 provider 接受性。

暫存 wire 驗證命令（不寫 repo generated；先用既有 `scripts/generate_contracts.py` 相同的 datamodel-code-generator 參數生成上列暫存檔）：

```powershell
./.venv-target/Scripts/python.exe -c "import importlib.util, sys; name='caliburn.contracts.generated.tools.move_jd_item_arguments'; spec=importlib.util.spec_from_file_location(name, 'S:/caliburn/.research-tmp/move-jd-item-codegen/move_jd_item_arguments.py'); module=importlib.util.module_from_spec(spec); sys.modules[name]=module; spec.loader.exec_module(module); import pytest; raise SystemExit(pytest.main(['tests/unit/test_jd_item_movement_wire.py', '-q', '--tb=short', '-p', 'no:cacheprovider']))"
```

## 未驗／後續歸屬

- 主線：維護正式 schema codegen（本次 Python 生成物已可直接使用）、包裝 tool definition、registry／prepared checkpoint 接線、錯誤轉譯，以及 A 整合後 focused 回歸。不把 wire 測試冒充已註冊工具。
- T12：較廣程序中斷／並行故障矩陣。這裡驗原 prepared 重入及 DB 原子，不宣稱 crash token／完整 Step runner 已驗。
- T16／T17：真 OpenAI 接受完整工具 schema、自然使用此工具及產品品質；本切片零 provider 呼叫。
- 不新增 undo、UI、來源對齊工具或任意 batch engine；本紀錄不代表整個 T07 完成。
