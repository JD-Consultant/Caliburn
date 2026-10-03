"""Probe-only launcher for T16 section 12: the unchanged product backend with a lower B1/B2 pre-batch threshold.

The Owner's 128,000-token policy lives in caliburn.agents.memory_analysis.runner and is read at call
time, so setting the module attribute before the app starts changes only this process. A's own
128K and the shared 160K mid-work guard are other constants and stay as they are. Run from
apps/api with PYTHONPATH=apps/api: python low_b_threshold_backend.py --key-file .env --port 8105
"""

import caliburn.agents.memory_analysis.runner as role_runner
from scripts.run_backend import main

PROBE_THRESHOLD_TOKENS = 3_000

role_runner.HISTORY_THRESHOLD_TOKENS = PROBE_THRESHOLD_TOKENS
print(f"B1/B2 pre-batch compaction threshold for this process: {role_runner.HISTORY_THRESHOLD_TOKENS}", flush=True)
main()
