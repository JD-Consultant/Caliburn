# Provider wire 觀測時 schema 的歷史材料

2026-09-10；只補歷史輸入保存，沒有重跑序列化／模型。

`provider-wire-hashes.json` 記錄的觀測時 schema SHA256 是 **c1e6c8342a81050302ef2fcc182f2e422d03f6c031e337a27229970fb5ca9951**，45980 bytes。原 manifest 保持不變；其 `docs/specs/contracts/jd-editor-v1.schema.json` 路徑是當時輸入來源，不表示該檔後來永遠不得修改。

後續設計新增 browser-only `JdSelectionCaptureClientInput` 與 `JdReadRuntimeRequest.jd_selection`，current schema 的整檔 hash 因此改變。三個 ModelInput 及其引用閉包未改，schema 作者已確認；不能以 current 整檔 hash 回填原觀測或假稱重新驗過 provider。

為保存可重現的歷史輸入，只逆向移除上述新增 definition／runtime property；**先在記憶體驗 SHA256 與原 manifest 完全相等，才寫入 [provider-wire-schema.json](provider-wire-schema.json)**。實際核對相等且 bytes=45980，沒有寫回 current schema。這是舊 bytes 的有 hash 驗證重建，不是 provider 接受測試，也未改原執行腳本／判準／輸出。

核對這次觀測的 schema 時，使用本歷史 `provider-wire-schema.json` 對原 manifest 的 schema hash；不要拿已更新的 current schema 得出原觀測失敗或據此更新原數值。若要重現原程式，於隔離副本提供這份相同路徑的歷史 schema；本次封存沒有再次執行原程式。
