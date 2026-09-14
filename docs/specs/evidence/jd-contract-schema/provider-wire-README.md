# JD 三工具：固定 SDK wire 序列化觀測

2026-09-10；JD-R002/C03。Owner／主線要求核對官方接法後完成的**零網路、本地序列化**，不是 provider API 接受或模型品質實驗。之後僅保存已執行原碼與輸出，沒有重跑或修改判準。

## 操作與材料

- 執行 cwd：`S:/caliburn/.worktrees/analysis-only-agent/experiments/analysis-agent`；Python 使用該目錄 `.venv/Scripts/python.exe`。原程式透過 PowerShell here-string 傳 stdin，第二次 argv `-B -`；封存 Python 檔按實際執行文字保存為 LF，hash 是封存檔的 bytes。
- `provider-wire-serialize.py`：實際成功取得本地 SDK request 的第二次程式。沿現有 `analysis_agent.provider.build_model`／`runtime.build_agent`，不改檔案或模型設定；`httpx.MockTransport` 收到 SDK request 後立即回固定 400，沒有外部網路、DB、真模型或工具執行。
- `provider-wire-output.txt`：工具回傳的實際 stdout／stderr 合併內容；保留套件的 socket/proxy 提示及刻意的 `OpenAIInvalidRequestError`。該錯誤来自本地固定 400，不是實際 OpenAI 拒絕 schema。
- `provider-wire-first-attempt.py`／`provider-wire-first-output.txt`：首次少了 `src` import 路由，於 import `analysis_agent` 停止；未取得 SDK request。第二次加 `sys.path.insert(0,'src')` 及 `-B`，沒有因此改動 schema 或 provider 接線主張。兩次完整原碼均保留。
- `provider-wire-hashes.json`：封存腳本／輸出、實際套件 METADATA、固定 source、封存時 schema 的 SHA256。沒有安裝新套件、vendor patch 或通用 schema compiler。

## 實際結果與責任

固定版本：`langchain 1.4.0`、`langchain-core 1.6.2`、`langchain-openai 1.6.0`、`openai 3.8.0`；由執行中的 `importlib.metadata.version` 輸出，不引用最新網頁版代替。

1. 普通 `BaseTool(args_schema=dict)` 經官方 converter，三工具 `$defs` 皆被移除；read／edit／change 的 `$ref` 計數分別由 `4/61/4` 變成 `0/0/0`。這是已見的轉換結果。source 顯示循環 ref 會只留非-ref sibling，pure recursive ref 可能成 `{}`；不能把直綁 converter 說成遞迴 schema 原樣傳遞。
2. 固定 JD `wrap_model_call` 只將三個 **factory instance identity** 命中的工具，在 model request view 替換成原格式 Responses function dict，含同一 SSOT 抽出的 ModelInput＋所引用 defs 與 `strict:false`。原 ToolNode 註冊的 BaseTool 仍在原 `create_agent` tools 內；本次沒有執行 ToolNode，實際工具執行／factory close-reconcile 還需施工測試。
3. SDK 最終 request 中，三個 `parameters_equal` 皆 `true`，`$defs` 皆在、三者 strict 都是 false；對照的非 JD 工具仍省略 strict，`parallel_tool_calls:false`／`store:false` 保留。沒有把全模型 `model_settings.strict` 改成 false。
4. `BaseTool` 的 dict args_schema 不自動驗輸入（source 直接 return tool_input）；執行前必須經 App 完整 JSON Schema validator、scope／refs／source／base 檢查。non-strict 的代價是 provider 不保證參數符合完整 schema，錯誤走既有有界修正／停止；不能進 Node／SQL 後才驗。

## 官方接點與未證範圍

相對隔離 venv `Lib/site-packages/`：`langchain_core/utils/function_calling.py` 的 `_convert_json_schema_to_openai_function`（115起）、`convert_to_openai_tool`（515起）；`langchain_core/utils/json_schema.py` 的循環處理（117起）；`langchain_core/tools/base.py` 的 dict schema／parse 接點（689、815附近）；`langchain/agents/factory.py` 標準 `bind_tools` 分支（1431附近）；`langchain_openai/chat_models/base.py` `bind_tools`（2389起）與 Responses payload（4479起）。其 bytes hash 與 metadata 另列。

這支持初版採「既有 OpenAI Responses runtime＋固定三工具 raw schema binding＋明確 per-tool strict:false＋App 完整驗證」的具體方案，**不是官方普遍推薦 non-strict，也不宣稱可直接用于 Anthropic strict**。Responses 省略 strict 的服務端預設不能由本地 source 判定為 non-strict；相關現行官方規則由主線證據 §2.13 承接。

尚未驗：真 provider 是否接受此非 strict schema、自然模型是否依規則生成、實際 ToolNode／typed mapper 執行、schema-generated DTO 的細節；本次固定 MockTransport 不回答這些問題。沒有 HTTP payload 檔案留存；原程式只在記憶體比對完整 parameters 並输出上述布林值，不能宣稱封存了完整 raw HTTP request。

重現時以相同 cwd、依 manifest 核固定 schema／source，將本封存 script 交該 venv Python執行即可；不能把稍後改版 schema 的新結果回填成這次觀測。未因封存再次執行。
