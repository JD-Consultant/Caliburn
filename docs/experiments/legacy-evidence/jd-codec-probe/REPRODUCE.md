# 封存後重現補充

本目錄保留首次材料，請在新的隔離目錄重現，勿覆寫原始輸出。

建立同層 `jd-editor-codec-probe` 與 `jd-editor-review-probe`：前者複製本目錄的 package.json、package-lock.json 與 codec-probe.mjs；後者複製[原 R01 package](../jd-review-probe/package.json)與[lock](../jd-review-probe/package-lock.json)。各自依固定 lock 執行 `npm ci --ignore-scripts --no-audit --no-fund`，再於 codec 目錄執行 `node codec-probe.mjs`。使用 Node 22.12.0；新增依賴的最低要求是 Node 18。

Plate 從同層 review-probe 解析，SuperJSON 從 codec-probe 解析；不需要舊 R4 的已損 JSON，不需 DB、原文或模型。[README](README.md)列完整判準與範圍。不同次數的原生 ID／時間可不同，應核對完整值與效果斷言，不比較隨機 ID 字面值。

[source／archive 清單](results/artifact-hashes.json)是主線封存核對；[原材料清單](artifact-hashes.json)來自凍結的首次 probe。capture-materials.mjs 是來源封存輔助，四項行為重現不需執行它。原始 R01、R01-F 與此次普通 JSON 控制失敗均保留。
