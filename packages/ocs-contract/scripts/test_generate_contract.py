"""The checker must preserve a caller's working file, including on generator failure."""

import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import generate_contract


class CodegenCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / "src/ocs_contract/models.py"
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(b"existing working edit\r\n")
        self.before = (self.target.read_bytes(), self.target.stat().st_mtime_ns)

    def generate(self, content: str, *, fail: bool = False):
        def run(command, **kwargs):
            output = Path(command[command.index("--output") + 1])
            self.assertNotEqual(output, self.target)
            self.assertEqual(self.target.read_bytes(), self.before[0])
            self.assertEqual(Path(kwargs["cwd"]), self.root)
            output.write_text(content, encoding="utf-8")
            if fail:
                raise subprocess.CalledProcessError(1, command)
            return subprocess.CompletedProcess(command, 0)

        return patch.object(generate_contract.subprocess, "run", side_effect=run)

    def assert_preserved(self) -> None:
        self.assertEqual(
            self.before, (self.target.read_bytes(), self.target.stat().st_mtime_ns)
        )

    def test_matching_check_preserves_bytes_and_mtime(self) -> None:
        with self.generate("existing working edit\n"):
            self.assertTrue(generate_contract.generate_contract(self.root, check=True))
        self.assert_preserved()

    def test_mismatch_preserves_uncommitted_edit(self) -> None:
        with self.generate("different generated content\n"):
            self.assertFalse(generate_contract.generate_contract(self.root, check=True))
        self.assert_preserved()

    def test_generator_failure_preserves_uncommitted_edit(self) -> None:
        with (
            self.generate("partial failed output\n", fail=True),
            self.assertRaises(subprocess.CalledProcessError),
        ):
            generate_contract.generate_contract(self.root, check=True)
        self.assert_preserved()

    def test_missing_output_is_reported_without_creating_it(self) -> None:
        self.target.unlink()
        with patch.object(generate_contract.subprocess, "run") as run:
            run.side_effect = lambda command, **_: Path(
                command[command.index("--output") + 1]
            ).write_text("generated\n", encoding="utf-8")
            self.assertFalse(generate_contract.generate_contract(self.root, check=True))
        self.assertFalse(self.target.exists())

    def test_explicit_generation_writes_only_completed_output(self) -> None:
        with self.generate("complete generated output\n"):
            self.assertTrue(generate_contract.generate_contract(self.root, check=False))
        self.assertEqual(
            self.target.read_text(encoding="utf-8"), "complete generated output\n"
        )


if __name__ == "__main__":
    unittest.main()
