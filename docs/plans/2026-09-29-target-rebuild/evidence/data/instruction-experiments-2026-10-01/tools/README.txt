Local (git-ignored) tools used for the 2026-10-01 quality, capacity and cutover work.
 eval-backend.ps1   start|stop|restart|migrate an isolated evaluation backend (schema eval_b, port 8103)
 run-eval-q.ps1     run simulated interviews sequentially: -Version q1 -Plan course_admin:1,warehouse:1 [-ExtraArgs ...]
 analyze_eval.py    summary per version (shape, gaps, citations, redundancy); show_run.py prints one transcript+JD
 analyze_long.py    quantitative summary of one long run (+ DB: attempts, cost, memory, checkpoints)
 timeline.py        which turn first wrote tasks; EVAL_SCHEMA=eval_b
 retro_citations.py recompute the citation audit over saved runs
 cutover-env.ps1 / cutover-verify.ps1  clean-worktree acceptance steps for the cutover candidate
 arch_metrics.py / web_metrics.py      static cohesion/coupling metrics (docs/.../t15-code-organization-review.md)
Scripts hard-code S:\caliburn paths; the OpenAI key is only read through apps/api/.env and never printed.
 check_links.py     relative markdown link / #anchor checker (pre-existing broken links in docs/current-decisions.md are historical)
 instructions_c1.py candidate A instructions (three guide-derived edits); copy over apps/api/src/caliburn/agents/job_consultant/instructions.py to apply (see T14 evidence for the pre-registered rule)
 simulate_interview_late.py  harness variant with persona keys late_correction and min_turns; to be copied to apps/api/scripts/simulate_interview.py after Q1 ends
 restart-e2e.ps1   restart the scripted e2e backend (schema e2e_journey, port 8101)
