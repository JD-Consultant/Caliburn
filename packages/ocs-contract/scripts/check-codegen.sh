#!/usr/bin/env bash
# Fails if src/ocs_contract/models.py is out of sync with the schema
# (schema changed but codegen not re-run + committed). Uses `git diff` so
# line-ending (CRLF/LF) normalization is handled by git; codegen uses
# --disable-timestamp so output is deterministic.
set -euo pipefail
cd "$(dirname "$0")/.."

uv run datamodel-codegen \
  --input schema/ocs-document.schema.json --input-file-type jsonschema \
  --output src/ocs_contract/models.py \
  --output-model-type pydantic_v2.BaseModel \
  --use-standard-collections --use-union-operator --use-schema-description \
  --target-python-version 3.11 --disable-timestamp

if ! git diff --quiet -- src/ocs_contract/models.py; then
  echo "ERROR: src/ocs_contract/models.py is out of sync with schema/ocs-document.schema.json."
  echo "       Run 'npm run codegen' (in packages/ocs-contract) and commit the result."
  git --no-pager diff --stat -- src/ocs_contract/models.py
  git checkout -- src/ocs_contract/models.py   # restore — non-destructive check
  exit 1
fi
echo "OK: generated models in sync with schema."

# --- TypeScript (Contract #3): regen types/ocs-document.ts + diff ---
npm run --silent codegen:ts

if ! git diff --quiet -- types/ocs-document.ts; then
  echo "ERROR: types/ocs-document.ts is out of sync with schema/ocs-document.schema.json."
  echo "       Run 'npm run codegen:ts' (in packages/ocs-contract) and commit the result."
  git --no-pager diff --stat -- types/ocs-document.ts
  git checkout -- types/ocs-document.ts   # restore — non-destructive check
  exit 1
fi
echo "OK: generated TS in sync with schema."
