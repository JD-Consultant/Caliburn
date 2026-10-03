# Task 3 fix round 1 — frozen review handoff

Base: 23bf0161d3d61dc8517ec1ecf4ee9ad5cb8e5a6d. Changes are relative to the original task-3-snapshot, not a new commit. No git mutation, subagents, paid requests, model key reads, production changes or schema/DTO changes.

## Review fixes

- R01: selection fragments issue navigation-only target capabilities. An off-page admitted selection also supplies only a range capability. Reading the complete target issues a distinct writable target. Both original reproductions now reject whole-block replacement; complete reread then replacement commits. Existing actual API + native Plate range replacement remains green.
- R02: the existing final JdExecutionIdentity middleware now verifies the actual public ModelRequest after all supplied wrappers. A request-local ContextVar carries exact expected JD schemas, App notice and view descriptors from preparation; it is not a durable state owner. Any same-name schema substitution, notice deletion/modification or changed visible-result/compaction coverage fails before the provider. Only the final checked handler response creates the manifest Command. The official middleware composer preserves other state Commands; lawful System additions and non-JD tools remain intact. All three negative cases assert zero SDK transport entries and no advanced manifest.
- R03: omission counts are derived from the final shared four-event detail set and each interval's counted events. Fixed turn-start and refreshed since-response totals/baselines remain unchanged. Four manual events followed by one AI event show three manual details plus AI and correctly report one omitted manual event.
- R04: ConversationReader adds a finite invocation-local successful-read observer. JD acquisition requires returned projection fields to match an actual successful canonical owner read during that invocation. An original outer factory identity and plausible fake result no longer suffice. No-read substitution and actual-read-then-altered-words both fail and issue no source. The existing MemorySession pinned replacement reader still reads, issues historical source and commits a linked JD edit. Source validity and acquisition remain separate; current saved input uses the original capture_input path.

## Verification evidence

- Initial RED: task-3-fix1-red.txt, 7 expected failures (two selection variants, three model mutations, event omission and fake reader).
- Initial minimal GREEN: task-3-fix1-green-initial.txt, 7 passed.
- Affected JD regression: task-3-fix1-regression.txt, 42 passed and one new test assertion failed, 167.95 seconds, one pre-existing Starlette warning. Failure was the legal Command positive test inspecting invalid_json_count on the root return; that existing field is child-only. The test now observes the actual child after_model state, with no implementation change for this test correction.
- Final focused: task-3-fix1-final.txt, 9 passed, 13.97 seconds. Includes the corrected child Command observation and both source fake variants.
- Existing owner regression: task-3-fix1-owner-regression.txt, 34 passed, 6.17 seconds (test_current_input_source.py and test_live_memory.py).
- Therefore 77 distinct affected cases have passed: all 43 cases in the JD matrix (42 in the matrix plus corrected positive in final focused) and 34 existing owner cases. Final focused is a subset, not nine additional distinct cases. No skipped cases. Original 177-item evidence is preserved and was not rerun.
- JD matrix files: test_jd_fix1.py, test_jd_sources.py, test_jd_provider_binding.py, test_jd_tools.py, test_jd_model_view.py, test_jd_model_view_recovery.py, test_jd_references.py. Actual graph, SDK MockTransport, dedicated local PostgreSQL q019_jd_app_20260910, native selection and separate official Saver processes are exercised. Local PG credentials were read only from docker-compose.yml into process environment, never printed.
- Root-scoped git diff --check -- experiments/analysis-agent passed. Original README first 11 lines were compared with the snapshot and preserved.

## Self-review / handoff

Checked installed official langchain/agents/factory.py wrapper composition: first wrapper surrounds later wrappers; inner ExtendedModelResponse Commands are accumulated before the public handler returns ModelResponse to outer wrappers. The existing final middleware is the last customization boundary before the existing model executor and ToolNode handler. No replacement chain or generic workflow engine was introduced. ContextVar tokens are reset in finally and owner observations hold copied bounded read projections only for the invocation.

Exact five changed paths are task-3-fix1-files.json. Only README, jd_tools.py, jd_context.py, sources.py and new test_jd_fix1.py differ from the initial review snapshot. Original native fixture remains experiments/jd-editor/fixtures/task3-selection.mjs and is unchanged in fix1. Root-owned .gitattributes and durable design evidence remain untouched. README and original report only receive appended fix1 notes.

FROZEN for root narrow review. No outstanding implementation concern; full lifecycle remains Task 5. Offline checks do not claim live provider acceptance, natural-model quality or browser/IME validation.
