"""One authorized directory and no replay of a funded experiment."""

from pathlib import Path


def claim_run(run_dir: Path, funded_dir: Path) -> None:
    if run_dir.resolve() != funded_dir.resolve():
        raise ValueError("Only the funded directory may execute paid requests")
    with (run_dir / "started.json").open("x", encoding="utf-8") as marker:
        marker.write('{"status":"started"}\n')
