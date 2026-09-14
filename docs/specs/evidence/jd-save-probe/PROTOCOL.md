# P01 fixed probe IPC (authoritative for this experiment)

This is a research fixture protocol, not the final product contract.

Input: `{ "value": PlateValue, "commands": [Command] }`.

Command uses **`type`**, never `kind` and no alias:

- `{ "type": "append_text", "target_id": string, "text": string }`
- `{ "type": "insert_paragraph_after", "target_id": string, "text": string }`

An empty commands array is the no-change case. The full r2 fixture has a `purpose` target.

Success: `{ "ok": true, "value": PlateValue, "operations": Operation[], "changed": boolean }`.

Failure: `{ "ok": false, "error": { "code": string, "command_index": number | null, "message": string }, "durable_effect": "none" }`.
`command_index` is zero-based. Failure does not return a partially mutated value. Node has no durable side effects; `none` says nothing about a Python transaction that has already committed separately.

stdout contains exactly one JSON object. The fixed Node entrypoint receives no paths, database configuration, executable source, or shell commands.
