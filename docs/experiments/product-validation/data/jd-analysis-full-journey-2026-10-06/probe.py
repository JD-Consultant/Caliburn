"""Reuse existing HTTP observers against this batch; do not change the agent loop."""

import asyncio
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent / "full-interview-rag-2026-10-06"


def main():
    action = sys.argv[1]
    script = "source_probe.py" if action == "sources" else "journey.py"
    if action == "sources":
        sys.argv = [sys.argv[0]]
    spec = importlib.util.spec_from_file_location("batch_observer", SHARED / script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.HERE = HERE
    module.BASE = "http://127.0.0.1:8107"
    asyncio.run(module.main())


if __name__ == "__main__":
    main()
