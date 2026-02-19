# Integration tests for module_1: they run the full pipeline (read case_init + rules,
# build KB, ground rules, infer) on real data files in this directory and check that
# the module behaves correctly as a whole.
#
# Run from project root: python -m unittest integration_tests.module_1.test_integration_module_1 -v

import json
import tempfile
import unittest
from pathlib import Path

from src import module_1

_THIS_DIR = Path(__file__).resolve().parent
CASE_INIT_PATH = _THIS_DIR / "case_inits" / "case_init_uncertain.json"
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


class TestRunRandomCase(unittest.TestCase):
    """Tests for module_1.run_random_case (generate random case and run full pipeline)."""

    def test_generates_and_runs_random_case(self):
        """run_random_case should generate a random case and run the full Module 1 pipeline."""
        output_dir = _THIS_DIR / "output_test_files" / "random_case_test"
        output_dir.mkdir(parents=True, exist_ok=True)

        result = module_1.run_random_case(
            rules_path=RULES_PATH,
            output_dir=output_dir,
            seed=42,
            kb_ratio=0.4,
        )

        # Check return value
        self.assertIn("kb_evidence", result)
        self.assertIn("witness_knowledge", result)
        self.assertIn("metadata", result)
        self.assertIn("_solution_culprit", result["metadata"])

        # Check output files were created
        evidence_path = output_dir / "evidence_found.json"
        report_path = output_dir / "questionable_evidence_report.txt"
        self.assertTrue(evidence_path.exists(), "evidence_found.json should be created")
        self.assertTrue(report_path.exists(), "questionable_evidence_report.txt should be created")

        # Check evidence_found.json structure
        with open(evidence_path, encoding="utf-8") as f:
            evidence_data = json.load(f)
        self.assertIn("evidence", evidence_data)
        self.assertIn("metadata", evidence_data)
        self.assertIn("_solution_culprit", evidence_data["metadata"])

    def test_reproducible_with_same_seed(self):
        """Same seed should produce same random case."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir1 = Path(tmp_dir) / "run1"
            output_dir2 = Path(tmp_dir) / "run2"

            result1 = module_1.run_random_case(RULES_PATH, output_dir1, seed=999)
            result2 = module_1.run_random_case(RULES_PATH, output_dir2, seed=999)

            # Solutions should match
            self.assertEqual(
                result1["metadata"]["_solution_culprit"],
                result2["metadata"]["_solution_culprit"],
            )
            self.assertEqual(
                result1["metadata"]["_solution_weapon"],
                result2["metadata"]["_solution_weapon"],
            )
            self.assertEqual(
                result1["metadata"]["_solution_room"],
                result2["metadata"]["_solution_room"],
            )

    def test_different_seeds_produce_different_cases(self):
        """Different seeds should produce different cases."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir1 = Path(tmp_dir) / "run1"
            output_dir2 = Path(tmp_dir) / "run2"

            result1 = module_1.run_random_case(RULES_PATH, output_dir1, seed=100)
            result2 = module_1.run_random_case(RULES_PATH, output_dir2, seed=200)

            # Solutions should differ (very likely)
            solutions_differ = (
                result1["metadata"]["_solution_culprit"] != result2["metadata"]["_solution_culprit"]
                or result1["metadata"]["_solution_weapon"] != result2["metadata"]["_solution_weapon"]
                or result1["metadata"]["_solution_room"] != result2["metadata"]["_solution_room"]
            )
            self.assertTrue(solutions_differ, "Different seeds should produce different cases")

    def test_respects_kb_ratio_parameter(self):
        """run_random_case should respect kb_ratio parameter."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = module_1.run_random_case(RULES_PATH, Path(tmp_dir), seed=42, kb_ratio=0.3)
            total = len(result["kb_evidence"]) + len(result["witness_knowledge"])
            kb_ratio_actual = len(result["kb_evidence"]) / total if total > 0 else 0
            self.assertAlmostEqual(kb_ratio_actual, 0.3, delta=0.1)


if __name__ == "__main__":
    unittest.main()
