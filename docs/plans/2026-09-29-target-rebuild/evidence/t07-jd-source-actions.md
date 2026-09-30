# T07 canonical 來源新增／移除／明確確認

- 日期：2026-09-30。
- 範圍：來源模型操作的窄驗證／修補；不是全 T07、provider 接受或自然模型品質 gate。
- 契約：[JD 工具 §2、§4.1–4.3、§5](../../../specs/2026-09-29-jd-model-tool-contract-review.md)、[共同工具規範](../../../specs/2026-09-27-agent-tool-contract-design-research.md)、[來源 owner](../../../implementation/jd-storage.md#33-直接來源按需讀取與候選模型寫入t07-增量)。

## 名稱與接線

正式八入口不含獨立 `modify_jd_sources`／`confirm_jd_sources`。來源動作已由 `revise_jd_profile`／`revise_jd_item` 的 `changes[]` 承接：`add_source`、`remove_source`、`confirm_reference_alignment`。本片不新增別名、不改 registry／A runner，也不新增 source owner、receipt、store 或 migration。

既有 `revise-jd-profile-arguments.schema.json`／`revise-jd-item-arguments.schema.json`、生成 DTO、wire parser 與 prepare／execute 接點已完整存在，本片保留不改、不重生成。

- Profile：`JdProfileWriteWorkflow(sessions).prepare(binding, *, command_id, changes, sources)` → `PreparedProfileWrite`；`execute(writer, prepared) -> str`。
- Item：`JdItemRevisionWorkflow(sessions).prepare(binding, *, command_id, intent)` → `PreparedItemRevision`；`execute(writer, prepared) -> str`。
- 現有 adapter：`JdWriteTools.prepare(name, arguments, command_id)` → prepared 或既有拒絕 wire；原 JSON checkpoint codec 保存／還原後交 `execute(prepared) -> str`。無新增 constructor 參數或方法。
- `jd_write_definitions()` 已由共同 `function_definition` 讀權威 packaged schema，無 binding 即可取得；沒有改用 `model_json_schema()`。

唯一 production 修補：兩個 workflow 在候選修訂確實變更、且本次只有來源明確確認時回 `aligned`；沒有變更回 `unchanged`，混合文字／來源增刪或其他修訂仍回 `updated`。重入依既有 operation 結果計算，不看目前 head 推測原結果。來源身分、資格、目標、review 與交易業務完全沿原 owner。

## Red–Green／真 PG 證據

`test_jd_source_tool_actions.py` 的 profile／item／detail／capability relation 四種參數案例先觀察到 `updated != aligned` 的行為 Red；修補後 5 案通過。另補已存在能力的 PG 與 wire 回歸，共 **8 個新增案例通過**：

- 模型參數經真 parser／adapter、prepared JSON codec、workflow／原來源 owner 寫入；四種精確目標可 add／remove／confirm，未選引用保留，不把父來源複製到子項。
- 改正文使原引用待核對，重加同來源不刷新；只確認指定 citation，其餘仍待核對。已相符再確認為 `unchanged`；後續改文後重送舊 prepared 返回原 `aligned` 而不倒轉 head／review。
- 同 citation remove＋confirm、錯誤明細 target 拒絕且不改候選。文字與第一組來源已寫、第二組來源寫後注入例外，整次回滾；同一 prepared 可重入成功。取消後遲到 execute 拒絕，正式 JD 與訪談不被候選污染。
- `test_jd_source_tool_memory.py` 經真正訪談完成與 Memory 發布建立兩層來源；讀 diff／重加新版不對齊。prepare 後晚到 Memory 刪除再同名建立，執行仍只綁 Turn 固定快照中的原物件／修訂。下一 Turn 選晚到版時，兩種舊引用均 `source_not_available`，不改指同名新物件。
- `test_jd_source_actions_wire.py` 驗兩個 canonical definition、schema 與 parser 一致；四種來源選擇可達。所有 object required 完整、禁止額外欄位、`$ref` 無旁接關鍵字；模型不能塞 revision／多餘 source／null 分支。

## 官方核對、驗證層級與限制

2026-09-30 取得 [OpenAI strict mode 官方正文](https://developers.openai.com/api/docs/guides/function-calling#strict-mode)：明設 strict、object 禁額外屬性、宣告欄位全 required，需省略的選項以明確合法分支／nullable 表達。這只約束 wire，不證明引用資格、交易成功或語意支持。本片沿既有 finite variants，沒有改 provider／runtime。

擴大回歸命令：`pytest tests/unit tests/contracts tests/integration/test_jd_source_tool_actions.py tests/integration/test_jd_source_tool_memory.py tests/integration/test_jd_source_edits.py tests/integration/test_jd_source_persistence.py tests/integration/test_jd_profile_tool_write.py tests/integration/test_jd_item_revision.py tests/integration/test_jd_changes.py -q --tb=short -p no:cacheprovider`。

結果 **838 passed，5 setup errors，28.33s**。5 個錯誤全屬既有 `tests/unit/test_openai_credentials.py` 的 `tmp_path` fixture（`test_reads_only_the_requested_key_without_applying_other_settings`，及 `test_missing_ambiguous_or_executable_values_are_rejected_without_echo` 的四種參數），在 Windows sandbox 對 `pytest-of-chenb` 暫存目錄的 ACL 拒絕；尚未執行測試正文。未改 credentials、讀秘密或為本片擴權排除該環境問題。所有本片／來源相關 PG、wire 與其餘 unit/contracts 通過；不稱整套全綠。

本片 5 個 Python 檔案的 Ruff check／format、2 個 production workflow 的 scoped mypy、`git diff --check` 通過。

沒有真模型／付費 API、.env、commit、外送私人內容。未重跑完整 PG suite、瀏覽器旅程或 provider schema 接受驗證；JDT-01 provider 與 JDT-09 自然模型效果仍保留原 gate。
