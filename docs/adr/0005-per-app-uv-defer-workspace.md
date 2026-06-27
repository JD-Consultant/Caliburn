# ADR 0005 — per-app uv 專案;uv workspace 延後到 Phase 2

- **狀態**:Accepted（2026-06-27;Phase 1）。**更新(Phase 2,2026-06-28):uv workspace 最終「不建」,改用 per-app path 依賴**(見下方更新)。

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

## 更新(Phase 2,2026-06-28):uv workspace 不建,改 path 依賴

Phase 2 抽 `packages/ocs-contract` 時,原本預期「此時建 uv workspace」。實際發現 workspace(單一直譯器 + 單一 lock)撐不住更深的異質性:**api 需 Python 3.13、ocs-indexer 綁 torch CUDA wheel(特定 py 版),單一直譯器無法同時滿足**(不只先前的 pytest pin 衝突)。

**最終決定:不建 uv workspace。** 改用 **per-app path 依賴**:
```toml
[tool.uv.sources]
ocs-contract = { path = "../../packages/ocs-contract", editable = true }
```
每個 app 仍各自鎖、各自直譯器,但共享契約套件(editable)。**完全避開 workspace 的單一直譯器/單一 lock 限制**,同樣達成「共享本地套件」的目的。→ 本 ADR 的「延後到 Phase 2 建 workspace」由此取代;workspace 在可見未來都不需要。
