# Integration tests for module_1: they run the full pipeline (read case_init + rules,
# build KB, ground rules, infer) on real data files in this directory and check that
# the module behaves correctly as a whole.
#
# Run from project root: python -m unittest integration_tests.module_1.test_integration_module_1 -v

import unittest
from pathlib import Path

from src import module_1

_THIS_DIR = Path(__file__).resolve().parent
CASE_INIT_PATH = _THIS_DIR / "case_init_contradiction.json"
RULES_PATH = _THIS_DIR / "rules.json"


class TestRun(unittest.TestCase):
    """Tests for module_1.run (entry point: read_case_init + read_rules + future inference/output)."""

    def test_accepts_paths_and_does_not_raise(self):
        """run(case_init_path, rules_path) should not raise when given valid integration test paths."""
        # We are testing that run completes without error when given valid Path objects to the integration test files.
        module_1.run(CASE_INIT_PATH, RULES_PATH)

    def test_accepts_string_paths(self):
        """run should accept str paths as well as Path objects."""
        # We are testing that run accepts string paths in addition to pathlib Path objects.
        module_1.run(str(CASE_INIT_PATH), str(RULES_PATH))


if __name__ == "__main__":
    unittest.main()
