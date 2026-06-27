# ADR 0005 — per-app uv 專案;uv workspace 延後到 Phase 2

- **狀態**:Accepted（2026-06-27;Phase 1）

## 脈絡

Phase 1 原計畫用 **uv workspace**(共用一份 lockfile)管三個 Python app。實測 `uv lock` 失敗:跨服務 pin 衝突 —— api 要 `pytest==8.3.3`,pdf-to-json 要 `pytest>=7.4,<8`(也有 python-dotenv 等)。共用 lockfile 需要刻意 harmonize 各服務版本 = 改依賴,超出 Phase 1「只搬不改」。

## 決定

Phase 1 用 **per-app uv 專案**:每個 app 各自 `pyproject.toml` + `uv.lock`。
- `api` 是 **application 模式**(無 `[build-system]`;import 名仍 `app`,靠 `pytest.ini` 的 `pythonpath=.`)。
- **uv workspace 延後到 Phase 2** —— 屆時抽 `packages/ocs-contract`(ADR 0004),workspace 的真正價值(用 path dep 共享契約套件)才出現,一併 harmonize 版本。

## 後果

- ✅ 現在簡單、各 app 獨立鎖定(獨立部署的服務本就該獨立鎖)。
- ⏳ Phase 2 抽契約時再建 workspace + 統一工具版本。
- 📌 各 app 測試指令:api `uv run pytest`、ocs-indexer `uv run --all-extras pytest`、pdf-to-json `uv run --extra dev pytest`(見 `../../CONTRIBUTING.md`)。
