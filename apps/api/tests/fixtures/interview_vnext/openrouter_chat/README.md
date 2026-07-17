# OpenRouter Chat fixture bodies(synthetic, test-only)

- 來源:OpenRouter 官方 OpenAPI(`https://openrouter.ai/openapi.json`)、Chat Completions
  overview、Models/Endpoints API 與 Router Metadata 文件;核對日期 **2026-07-17**。
- 全部 **人工最小化、synthetic**;無真實 API key、員工內容或 hidden reasoning 原文
  (`success-with-reasoning.json` 的 reasoning 是假字串,用來驗證 redaction)。
- 檔案保持 provider wire shape;status code、`x-request-id`/`x-generation-id` headers、
  用途等 metadata 放 sidecar `manifest.json`。
- 測試一律經 `httpx.MockTransport` + adapter 的真 JSON decoder 消費這些 body;
  §10 stable error_type 矩陣與部分 routing 污染案例以 table-driven / in-test 變異建構,
  避免近乎重複的檔案爆量。
- **待 R6 live probe 核對**:`openrouter_metadata.endpoints` 條目的巢狀(flat array vs
  `available`)在官方 docs 有兩種讀法;adapter 的 `_selected_endpoint` 同時容忍兩者,
  真實 shape 由 live capture bundle 定案後再收斂 fixtures。
