# Run 格式與固定 checkpoint 接點獨立窄審

查閱日期：2026-09-13。基準 `36cc1cb9`；審查者 `jd_ref_signer_preflight`，非本輪受審變更作者。本次只讀 `ai_records.py`、`ai_checkpoints.py`／`runtime_checkpoints.py` 本輪差異及對應 records／checkpoints／inspection 測試，**未審自己的 `ai_history.py`**，未修改任何 src。

**結論：本次範圍未發現可重現 P1／P2。**

| 核對點 | 直接證據與判斷 |
|---|---|
| V1 不被升級 | `ai_records.py:55–70` 使用兩個具名模型及原生 discriminator；V1 沒有 `start_revision_id`，額外欄位被拒。`request_digest_for_record` 對 V1 保持舊 canonical payload；`ai_checkpoints.py:388` 結案只複製原模型並改 status。測試以 literal V1 原保存紀錄驗 root／child／START／mixed prior 的觀察與結案，沒有透過新 builder 偽造 V1。 |
| V2 固定起始 JD 版本 | `ai_records.py:91–109` 的 V2 digest 納入 `format_version=2`、dataset、document、原始 text、`start_revision_id`；run ID 留作外層請求身分。`new_run_record` 的 revision 是 required keyword，驗 canonical UUID。固定 digest golden 及修改 revision／把同 digest 降為 V1 的反例皆通過；原 CRLF、空白與字元不正規化。 |
| 嚴格格式標籤 | `ai_records.py:34–52` 在原生 Literal／tagged union 前增加精確 `type(format_version) is int` 的有限檢查，配合 strict／extra forbid。dict、JSON 與直接具名模型測試均拒 bool、float、字串版本及不明版本；未以 Pydantic strict 設定推定 Literal 本身足夠。 |
| 固定觀察不轉 latest | `ai_checkpoints.py:250–285` 的 `observe_at` 要求 exact root config 三個位置欄位、相同 document、root namespace 及非空 ID；提供 config 時略過 latest 分支。之後核回傳 root config，child 也由该 root 指向的位置固定讀取並核 namespace／原 record。舊 V1 root 之後即使已有新 V2 START，FixedOnly 測試仍只讀舊 root，無法以新 run ID 取得它。 |
| Manual gate 共用格式判定 | `runtime_checkpoints.py:143–155` 改用同一 parser，沒有另一份 V2 判定；V1／V2 running 都保持 busy，明確結案後才解除此條件。錯誤版本 tag 仍回 invalid_checkpoint。這個 gate 不承擔 JD revision 或完整 AI 材料權威核對。 |
| 檢視模式不因格式變更執行 | inspection 測試只補新 builder 所需 revision；沿原生同 layout 讀取完整 pending child，sync／async model、tools、after_model 入口皆由原 execution-disabled guard 拒絕。沒有加入可呼叫 provider 的測試分支。 |

## 實際驗證

App 目錄以 `uv run --frozen --offline pytest -q -p no:cacheprovider tests/test_ai_records.py tests/test_ai_checkpoints.py tests/test_consultant_inspection.py -k 'test_ai_records or legacy_root or saved_start_preserves or observe_at or v2_saved or manual_gate or test_consultant_inspection'` 執行：**81 PASS、52 deselected，2.33s**。本次窄審測試首次即通過；合成 native graph／InMemorySaver，零 provider／DB／宿主服務操作。

## 限制

這份結論只涵蓋新紀錄格式、原 V1 讀回及固定位置解碼；不宣稱已驗真 PG 故障、Windows 重啟、HTTP、瀏覽器或自然模型。本輪仍由 AiRuntime 的實際 owner 准入驗證 `start_revision_id` 是否等於當下 JD；格式模型只能證明其形狀與 request digest 一致。`observe_at` 是唯讀材料接點，不授予 writer 或 worker 停止證據，也不自行判定某個舊 checkpoint 是否屬目前有效祖先鏈。
