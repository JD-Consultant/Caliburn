# 技術接線與版本來源

技術的用途與部署邊界由[系統規格](../../apps/backend/architecture.md#程序與技術)維護。版本以實際 lockfile 為準；本頁只定位來源，不手抄另一份版本清單。

| 範圍 | 配置與責任 |
|---|---|
| Python／FastAPI／OpenAI／LangGraph／資料存取 | [後端 pyproject](../../apps/backend/pyproject.toml)、[uv.lock](../../apps/backend/uv.lock)；Host 管資源，模組管能力。 |
| React／TypeScript／MUI／Query／Web 工具 | [前端 package](../../apps/frontend/package.json)、根 [pnpm-lock.yaml](../../pnpm-lock.yaml)。 |
| 公版本機模型 | 後端 `local-models` extra 與[公版模型實作](../../apps/backend/src/caliburn/modules/occupation_reference/infrastructure/models/local.py)；權重事先備妥，執行時不自動下載。 |
| 容器與資料服務 | 根 [Compose](../../compose.yaml)及 [Dockerfile](../../Dockerfile)；單 app、PostgreSQL、Qdrant。 |
| 文件工具 | 根 [package.json](../../package.json)與[圖庫命令](../diagrams/README.md#編輯與重繪)。 |

內部採明確型別及依實際需要的 Protocol；不為每個模組造 provider、repository 或 factory 家族。外部套件與框架能力不等於本產品已具備恢復、交易或品質保證，仍須以[適用驗證](verification-plan.md)核對。
