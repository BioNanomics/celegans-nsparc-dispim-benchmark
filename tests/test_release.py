import contextlib
import io
import re
import unittest
from pathlib import Path

import celegans_benchmark
from celegans_benchmark.cli import main

ROOT = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    def test_version_matches_pyproject(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        declared = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE).group(1)
        self.assertEqual(celegans_benchmark.__version__, declared)

    def test_version_is_semver(self):
        self.assertRegex(celegans_benchmark.__version__, r"^\d+\.\d+\.\d+$")

    def test_version_flag_prints_version_and_exits_zero(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as ctx:
            main(["--version"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn(celegans_benchmark.__version__, out.getvalue())

    def test_version_flag_works_without_subcommand(self):
        # --version must not demand a subcommand or data directory
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as ctx:
            main(["--version"])
        self.assertEqual(ctx.exception.code, 0)

    def test_changelog_has_entry_for_current_version(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"## [{celegans_benchmark.__version__}]", changelog)


if __name__ == "__main__":
    unittest.main()
