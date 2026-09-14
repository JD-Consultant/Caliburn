# F01 封存重現

[主報告與效力](../2026-09-09-jd-native-content-profile-probe.md)。本目錄是原始研究腳本／結果副本，勿在此覆寫原證據。README.md 保留執行前範圍及當時來源 hash，不改成事後全綠說明。

在可寫暫存根還原以下三個相鄰目錄：

```text
jd-editor-profile-probe/  ← 本目錄副本
jd-editor-native-probe/   ← ../jd-native-probe 的 package.json／package-lock.json，依 lock 安裝
jd-editor-ui-probe/       ← ../jd-ui-probe/fixture.mjs（只需這份固定資料）
```

在 native 目錄執行 `npm ci --ignore-scripts --no-audit --no-fund` 後，從暫存根執行：

```text
node jd-editor-profile-probe/profile-probe.mjs
```

本輪沿用既有安裝，没有再次執行 npm install。node_modules／cache 不封存。Node v22.12.0，依賴與授權沿[前次原生證據](../2026-09-09-jd-native-editor-probe.md)及[套件盤點](../jd-ui-probe/results/license-inventory.json)。F01 不呼叫 diff、AI、DB 或瀏覽器。

**預期第二輪為六组、五通過、一個保留的 raw-JSON 反例，exit 1。**F01-A traces 的 normalizationObservations 另記可讀文字不變、只移除已知空無格式 leaf、canonical JSON 重開全等；不是把原斷言改為 PASS。首輪有另一個 harness aliasing 失敗，來源保留為 results/first-run-profile-probe.mjs；若需重跑首輪，須在獨立副本把它放回 profile-probe.mjs，不能直接從 results 執行而改變 import 相對路徑。

results/saved-profile.json 是第二輪 canonical value 的實際保存材料；結果／traces 使用新的時間檔名。重新執行會生成另一組結果，不應覆盖原始紀錄。
