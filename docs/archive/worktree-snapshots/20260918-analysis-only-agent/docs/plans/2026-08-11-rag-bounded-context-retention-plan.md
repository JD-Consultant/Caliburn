# RAG Bounded Context Retention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Restore the future RAG bounded contexts, contracts, and source corpora to the monorepo while keeping them independently runnable and fully isolated from the current API/Web product.

**Architecture:** Restore pdf-to-json, ocs-indexer, and embedder plus ocs-contract and indexer-contract from the tree immediately before 60db19a. Keep the current API/Web composition root unchanged; put Qdrant and embedder behind an explicit Compose rag profile and filter default Turbo development to API/Web. Full PDF and OCS JSON corpora return as source material for future RAG, but no current route or database writer consumes them.

**Tech Stack:** Turborepo/npm workspaces, per-app uv projects and lockfiles, Python 3.11+ RAG apps, Pydantic, pdfplumber, Qdrant client, FastAPI/uvicorn embedder, Docker Compose profiles, BGE-M3 GPU container, pytest, Vitest, TypeScript, ESLint.

## Global Constraints

- Current API/Web remains the only production product path; do not import or call RAG apps from apps/api or apps/web.
- Restore apps/pdf-to-json, apps/ocs-indexer, apps/embedder, packages/ocs-contract, and packages/indexer-contract from the tree immediately before 60db19a; do not restore retired interview, vNext, job_authoring, old migrations, old Web editor, or SaaS runtime.
- Restore all 908 PDFs and all 908 OCS JSON documents; retain PDF parser test fixtures as they existed before 60db19a.
- npm run up and default npm run dev start only current API/Web plus PostgreSQL; RAG services require an explicit profile or RAG-specific command.
- Keep per-app uv.lock files and local path dependencies; do not convert the independent Python apps into one shared Python environment.
- Use restore-only changes where possible; preserve existing characterization tests and require a green result for each task before committing.
- One task produces one commit. Do not push unless the owner explicitly requests it.
- ADR 0057 is still Proposed; update it directly to record the corrected boundary. Do not edit any Accepted ADR.

---

## File Map

### Restored bounded contexts and contracts

- apps/pdf-to-json/**: PDF parser, OCS transformer, CLI, tests, full PDF corpus, and parser fixtures.
- apps/ocs-indexer/**: OCS ingestion, matching/query API, Qdrant adapter, tests, and full OCS JSON corpus.
- apps/embedder/**: BGE-M3 HTTP service Docker image and runtime.
- packages/ocs-contract/**: OCS JSON schema, generated Pydantic model, generated TypeScript type, and codegen scripts.
- packages/indexer-contract/**: indexer query wire models and uv project.

### Current boundary and workspace files

- package.json: keep current default dev/up filtered to API/Web; add explicit RAG commands.
- package-lock.json: regenerate for the restored npm workspace package.
- docker-compose.yml: keep PostgreSQL unprofiled; add Qdrant/embedder under rag profile and their named volumes.
- apps/api/tests/test_job_analysis_dependencies.py: extend the current-only guard to reject imports of restored RAG runtime packages.
- docs/adr/0057-current-only-runtime-and-data-boundary.md: correct the Proposed decision from “remove RAG apps” to “retain but isolate RAG bounded contexts”.
- docs/adr/README.md, AGENTS.md, ARCHITECTURE.md, CONTRIBUTING.md, docs/README.md, docs/runbook.md, apps/api/README.md: document isolated RAG operation.
- docs/design/rag-pipeline.md: add the cross-app PDF → OCS → indexer → embedder/Qdrant flow and explicit non-integration boundary.

---

### Task 1: Restore OCS Contract and PDF-to-JSON Bounded Context

**Files:**

- Restore from 60db19a^: packages/ocs-contract/**
- Restore from 60db19a^: apps/pdf-to-json/**
- Includes all files under apps/pdf-to-json/data/pdfs/ (908 PDFs) and apps/pdf-to-json/tests/fixtures/.

**Interfaces:**

- Produces the ocs-contract path package consumed by pdf-to-json and later ocs-indexer.
- Produces the jd-convert CLI and parser/transformer test surface consumed by the RAG corpus workflow.
- Does not depend on apps/api, apps/web, PostgreSQL, Qdrant, or the current job-analysis-contract.

- [ ] **Step 1: Restore only the approved historical paths**

~~~powershell
git restore --source=60db19a^ -- packages/ocs-contract apps/pdf-to-json
~~~

Confirm that the restore does not include apps/api, apps/web, old migrations, or retired interview paths:

~~~powershell
git status --short
git diff --name-only -- apps/api apps/web
~~~

Expected: only the two approved path groups are restored; no API/Web path appears in the diff.

- [ ] **Step 2: Verify contract and parser file inventory**

~~~powershell
git ls-files packages/ocs-contract apps/pdf-to-json | Measure-Object
Get-ChildItem -LiteralPath apps\pdf-to-json\data\pdfs -File | Measure-Object
Get-ChildItem -LiteralPath apps\pdf-to-json\tests\fixtures -Recurse -File | Measure-Object
~~~

Expected: the contract tree is present, the PDF corpus contains 908 PDFs, and the parser fixtures are present.

- [ ] **Step 3: Run the PDF parser characterization suite**

~~~powershell
Set-Location apps\pdf-to-json
uv sync --frozen
uv run --extra dev pytest -q
~~~

Expected: restored parser and transformer tests pass without PostgreSQL, Qdrant, or a GPU.

- [ ] **Step 4: Commit the bounded-context restore**

~~~powershell
git add packages/ocs-contract apps/pdf-to-json
git commit -m "restore: retain OCS contract and PDF parser"
~~~

---

### Task 2: Restore Indexer, Indexer Contract, and OCS Corpus

**Files:**

- Restore from 60db19a^: packages/indexer-contract/**
- Restore from 60db19a^: apps/ocs-indexer/**
- Includes all files under apps/ocs-indexer/data/jd-json/ (908 OCS JSON documents).

**Interfaces:**

- Consumes ocs-contract and the OCS JSON corpus from Task 1.
- Produces the jd-ocs-indexer CLI/API and indexer-contract wire models for future consumers.
- Calls the embedder through the existing HTTP adapter and Qdrant through the existing client; it does not import app.* or the current API.

- [ ] **Step 1: Restore only the approved indexer paths**

~~~powershell
git restore --source=60db19a^ -- packages/indexer-contract apps/ocs-indexer
~~~

Confirm the current application remains untouched:

~~~powershell
git diff --name-only -- apps/api apps/web packages/job-analysis-contract
~~~

Expected: no current API/Web/contract paths are modified by this task.

- [ ] **Step 2: Verify the corpus and path dependency declarations**

~~~powershell
Get-ChildItem -LiteralPath apps\ocs-indexer\data\jd-json -File | Measure-Object
rg -n "ocs-contract|indexer-contract|tool\.uv\.sources|http_embedder|qdrant" apps/ocs-indexer/pyproject.toml apps/ocs-indexer/src
~~~

Expected: 908 JSON documents are present; both local contracts and the HTTP embedder/Qdrant adapters are declared.

- [ ] **Step 3: Run indexer tests without live RAG infrastructure**

~~~powershell
Set-Location apps\ocs-indexer
uv sync --frozen
uv run --all-extras pytest -q
~~~

Expected: unit, contract, ingestion, matching, and fake-point tests pass without GPU or a running Qdrant.

- [ ] **Step 4: Commit the indexer restore**

~~~powershell
git add packages/indexer-contract apps/ocs-indexer
git commit -m "restore: retain OCS indexer bounded context"
~~~

---

### Task 3: Restore Embedder and Isolate RAG Infrastructure

**Files:**

- Restore from 60db19a^: apps/embedder/**
- Modify: docker-compose.yml
- Modify: package.json
- Regenerate: package-lock.json

**Interfaces:**

- Produces the apps/embedder Docker image and health/embedding HTTP surface consumed by ocs-indexer.
- Produces the explicit rag Compose profile; the unprofiled db service remains the only default infrastructure.
- Produces root commands that cannot cause Turbo dev to start indexer accidentally when the RAG app becomes an npm workspace member.

- [ ] **Step 1: Restore the embedder service**

~~~powershell
git restore --source=60db19a^ -- apps/embedder
~~~

Verify that the restored Docker build remains isolated from apps/api:

~~~powershell
rg -n "FROM|FlagEmbedding|MODEL_ID|/health|embed" apps/embedder
~~~

- [ ] **Step 2: Add the optional Compose profile**

Modify docker-compose.yml so qdrant and embedder have profiles: [rag], while db has no profile. Keep the historical Qdrant ports, embedder port, GPU declaration, healthchecks, and named volumes. Then verify both views:

~~~powershell
docker compose config
docker compose --profile rag config
~~~

Expected: the first configuration contains only db; the second contains db, qdrant, and embedder.

- [ ] **Step 3: Keep default development current-only**

Modify root package.json so current commands explicitly filter to @caliburn/api and @caliburn/web, and add explicit RAG commands equivalent to:

~~~json
{
  "up": "docker compose up -d db && turbo dev --filter=@caliburn/api --filter=@caliburn/web",
  "dev": "turbo dev --filter=@caliburn/api --filter=@caliburn/web",
  "rag:up": "docker compose --profile rag up -d",
  "rag:down": "docker compose --profile rag down",
  "rag:dev": "turbo dev --filter=@caliburn/ocs-indexer"
}
~~~

Keep test and build unfiltered so restored packages are included in verification. Do not add an API/Web dependency on any RAG package.

- [ ] **Step 4: Regenerate the npm lockfile and verify workspace discovery**

~~~powershell
npm install --package-lock-only
npm query "#workspace"
npm run build
~~~

Expected: @caliburn/ocs-contract is represented in the lockfile/workspace graph, while the Python-only indexer-contract remains managed by its own uv project.

- [ ] **Step 5: Commit infrastructure isolation**

~~~powershell
git add apps/embedder docker-compose.yml package.json package-lock.json
git commit -m "build: retain RAG infrastructure behind optional profile"
~~~

---

### Task 4: Correct Documentation and Enforce the Current Boundary

**Files:**

- Modify: docs/adr/0057-current-only-runtime-and-data-boundary.md
- Modify: docs/adr/README.md
- Modify: AGENTS.md
- Modify: ARCHITECTURE.md
- Modify: CONTRIBUTING.md
- Modify: docs/README.md
- Modify: docs/runbook.md
- Modify: apps/api/README.md
- Create: docs/design/rag-pipeline.md
- Modify: apps/api/tests/test_job_analysis_dependencies.py

**Interfaces:**

- Documentation says RAG members are retained future bounded contexts, not current API/Web runtime dependencies.
- ADR 0057 remains Proposed; its corrected Decision 5 records retention plus isolation.
- Boundary tests fail if current API composition surfaces import jd_ocs_indexer, jd_pdf_to_json, ocs_contract, indexer_contract, or embedder runtime modules.

- [ ] **Step 1: Update ADR 0057 and its index entry**

Change the Proposed ADR context, decision, and consequences so it states:

~~~text
Current API/Web remains current-only. RAG apps and contracts remain monorepo members as isolated future bounded contexts. Qdrant/embedder are optional RAG infrastructure. No current API/Web import, route, database write, or dual-write is added by this decision.
~~~

Keep ADR status Proposed; update the README summary but do not mark it Accepted without a separate owner-approval commit.

- [ ] **Step 2: Add the cross-app RAG design map**

Create docs/design/rag-pipeline.md with the PDF → OCS contract → JSON corpus → indexer → embedder/Qdrant flow, package ownership, local commands, data locations, and the explicit “not consumed by current API/Web” invariant. Link it from ARCHITECTURE.md, docs/README.md, and docs/runbook.md.

- [ ] **Step 3: Update orientation and contributor instructions**

Replace statements that say only apps/api, apps/web, and job-analysis-contract exist with the two-layer statement: current product surface is API/Web, while RAG apps/contracts are retained and independently operated. Document that npm run up excludes RAG and npm run rag:up is opt-in.

- [ ] **Step 4: Add the API-side negative boundary assertion**

Extend test_current_composition_does_not_import_removed_paths with the restored runtime roots:

~~~python
forbidden = (
    "jd_ocs_indexer",
    "jd_pdf_to_json",
    "embedder",
    "indexer_contract",
    "ocs_contract",
    "app.interview",
    "app.interview_vnext",
    "app.job_authoring",
)
~~~

Keep the scan limited to current API composition surfaces so the test does not prohibit RAG apps from importing their own contracts. Add this exact Web-side static check to the task gate:

~~~powershell
rg -n "ocs-contract|indexer-contract|jd_ocs_indexer|jd_pdf_to_json|embedder" apps/web/src apps/web/package.json
~~~

Expected: no output; current Web imports only @caliburn/job-analysis-contract for current data contracts.

- [ ] **Step 5: Run documentation and boundary checks**

~~~powershell
rg -n "remove.*(ocs-indexer|pdf-to-json|embedder)|only.*apps/api.*apps/web|Qdrant.*removed|RAG.*not.*repo" AGENTS.md ARCHITECTURE.md CONTRIBUTING.md docs apps
git diff --check
Set-Location apps\api
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'
uv run pytest tests/test_job_analysis_dependencies.py -q
~~~

Expected: no current documentation falsely claims that retained RAG members are deleted, and the API boundary suite remains green.

- [ ] **Step 6: Commit boundary and documentation correction**

~~~powershell
git add docs/adr/0057-current-only-runtime-and-data-boundary.md docs/adr/README.md AGENTS.md ARCHITECTURE.md CONTRIBUTING.md docs/README.md docs/runbook.md docs/design/rag-pipeline.md apps/api/README.md apps/api/tests/test_job_analysis_dependencies.py
git commit -m "docs: retain RAG contexts outside current runtime"
~~~

---

### Task 5: Full Monorepo Gates and RAG Retention Tag

**Files:**

- No new source files; verification only.
- Tag: current-rag-bounded-contexts-v1 after all gates pass.

- [ ] **Step 1: Verify workspace membership and retained paths**

~~~powershell
git ls-tree --name-only HEAD:apps
git ls-tree --name-only HEAD:packages
git status --short
~~~

Expected apps: api, web, pdf-to-json, ocs-indexer, embedder; expected packages: job-analysis-contract, ocs-contract, indexer-contract. The pre-existing untracked docs/current-job-analysis-analysis-flow.md remains untouched.

- [ ] **Step 2: Run all non-live tests and generated-contract checks**

~~~powershell
npx turbo test --force --env-mode=loose
npm run check-codegen -w @caliburn/job-analysis-contract
npm run check-codegen -w @caliburn/ocs-contract
Set-Location apps\web
npx tsc --noEmit
npm run lint
~~~

Expected: current API/Web gates retain their documented baseline; PDF, indexer, and contracts pass their own tests without GPU/Qdrant. Any known pre-existing PostgreSQL FK failure must remain explicitly reported rather than hidden.

- [ ] **Step 3: Verify default and opt-in runtime configuration**

~~~powershell
docker compose config --services
docker compose --profile rag config --services
rg -n '"up"|"dev"|"rag:up"|"rag:down"|"rag:dev"|--filter=@caliburn/(api|web|ocs-indexer)' package.json
~~~

Expected default service list: db; RAG profile list adds qdrant and embedder; package.json default up/dev commands contain only API/Web filters and RAG commands are explicit.

- [ ] **Step 4: Verify boundaries and hygiene**

~~~powershell
git diff --check
git status --short
git diff --name-only 27682eb..HEAD -- apps/api/app apps/web/src
~~~

Expected: no current production source was changed to wire RAG; only planned guard/docs/config changes are present; no generated cache or lockfile drift remains.

- [ ] **Step 5: Create the retention tag**

~~~powershell
git tag -a current-rag-bounded-contexts-v1 -m "Retain isolated RAG bounded contexts and corpora"
~~~

Verify the tag points at the final task commit:

~~~powershell
git rev-parse --short HEAD
git rev-parse --short current-rag-bounded-contexts-v1^{}
git status --short
~~~

Do not push the branch or tag until the owner explicitly requests it.

---

## Review Handoff

After Task 5, provide the commit list, restored path inventory, corpus counts/sizes, default/profile Compose service lists, test results, known baseline failures, and the exact tag SHA. Request a separate review of the deletion-boundary correction before any merge or push.
