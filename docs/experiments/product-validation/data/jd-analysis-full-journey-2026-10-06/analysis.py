"""Reuse the prior batch's ledger and snapshot checks without model/database calls."""

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    script = HERE.parent / "full-interview-rag-2026-10-06/analyze.py"
    spec = importlib.util.spec_from_file_location("prior_analysis", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.HERE = HERE
    module.main()


if __name__ == "__main__":
    main()
