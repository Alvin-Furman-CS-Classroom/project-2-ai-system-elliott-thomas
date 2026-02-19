# Integration tests for module_1: they run the full pipeline (generate random case + rules,
# build KB, ground rules, infer) and check that the module behaves correctly as a whole.
#
# Run from project root: python -m unittest integration_tests.module_1.test_integration_module_1 -v


import json
import unittest
from pathlib import Path

from src import module_1

_THIS_DIR = Path(__file__).resolve().parent
CASE_INIT_PATH = _THIS_DIR / "case_inits" / "case_init_uncertain.json"
RULES_PATH = _THIS_DIR / "rules.json"
_OUTPUT_DIR = _THIS_DIR / "output_test_files"
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# NEW CODE: Random case generation tests
class TestRunRandomCase(unittest.TestCase):
    """Tests for module_1.run_random_case (generate random case and run full pipeline)."""

    def test_generates_and_runs_random_case(self):
        """run_random_case should generate a random case and run the full Module 1 pipeline.
        
        Output files written to: integration_tests/module_1/output_test_files/random_case_test/
        """
        output_dir = _OUTPUT_DIR / "random_case_test"
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
        case_init_path = output_dir / "case_init_generated.json"
        self.assertTrue(evidence_path.exists(), "evidence_found.json should be created")
        self.assertTrue(report_path.exists(), "questionable_evidence_report.txt should be created")
        self.assertTrue(case_init_path.exists(), "case_init_generated.json should be created")

        # Check evidence_found.json structure
        with open(evidence_path, encoding="utf-8") as f:
            evidence_data = json.load(f)
        self.assertIn("evidence", evidence_data)
        self.assertIn("metadata", evidence_data)
        self.assertIn("_solution_culprit", evidence_data["metadata"])

        # Check case_init_generated.json structure (for review)
        with open(case_init_path, encoding="utf-8") as f:
            case_init_data = json.load(f)
        self.assertIn("initial_evidence", case_init_data)
        self.assertIn("metadata", case_init_data)
        self.assertIn("_solution_culprit", case_init_data["metadata"])
        # Verify it contains both kb_evidence and witness_knowledge facts
        initial_evidence = case_init_data["initial_evidence"]
        self.assertGreater(len(initial_evidence), 0)
        # All facts from result should be in initial_evidence
        all_facts = {**result["kb_evidence"], **result["witness_knowledge"]}
        for fact, value in all_facts.items():
            self.assertIn(fact, initial_evidence)
            self.assertEqual(initial_evidence[fact], value)

    def test_reproducible_with_same_seed(self):
        """Same seed should produce same random case.
        
        Output files written to: integration_tests/module_1/output_test_files/reproducible_test/
        Includes case_init_generated.json for review.
        """
        output_dir1 = _OUTPUT_DIR / "reproducible_test" / "run1"
        output_dir2 = _OUTPUT_DIR / "reproducible_test" / "run2"
        output_dir1.mkdir(parents=True, exist_ok=True)
        output_dir2.mkdir(parents=True, exist_ok=True)

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
        """Different seeds should produce different cases.
        
        Output files written to: integration_tests/module_1/output_test_files/different_seeds_test/
        Includes case_init_generated.json for review.
        """
        output_dir1 = _OUTPUT_DIR / "different_seeds_test" / "seed100"
        output_dir2 = _OUTPUT_DIR / "different_seeds_test" / "seed200"
        output_dir1.mkdir(parents=True, exist_ok=True)
        output_dir2.mkdir(parents=True, exist_ok=True)

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
        """run_random_case should respect kb_ratio parameter.
        
        Output files written to: integration_tests/module_1/output_test_files/kb_ratio_test/
        Includes case_init_generated.json for review.
        """
        output_dir = _OUTPUT_DIR / "kb_ratio_test"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        result = module_1.run_random_case(RULES_PATH, output_dir, seed=42, kb_ratio=0.3)
        total = len(result["kb_evidence"]) + len(result["witness_knowledge"])
        kb_ratio_actual = len(result["kb_evidence"]) / total if total > 0 else 0
        self.assertAlmostEqual(kb_ratio_actual, 0.3, delta=0.1)


if __name__ == "__main__":
    unittest.main()
