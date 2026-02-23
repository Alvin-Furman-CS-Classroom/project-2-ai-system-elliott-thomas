"""Integration tests for module_2: beam-search query planning on real case data.

Run from project root:
    python -m unittest integration_tests.module_2.test_integration_module_2 -v

This integration test writes its output to:
    integration_tests/module_2/output_test_files/

Output files (consolidated in one directory):
    - evidence_found.json (from module_1.run_random_case)
    - query_plan.json (from module_2.run_search)
    - observations.json (from module_2.run_search)
    - search_trace.txt (from module_2.run_search)

You can manually inspect the results after running the tests.
"""

import json
import unittest
from pathlib import Path

from src import module_1, module_2


_THIS_DIR = Path(__file__).resolve().parent
_MODULE_1_DIR = _THIS_DIR.parent / "module_1"
_OUTPUT_DIR = _THIS_DIR / "output_test_files"
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Rules path; case data comes from module_1.run_random_case() (random case generation).
RULES_PATH = _MODULE_1_DIR / "rules.json"


class TestModule2Integration(unittest.TestCase):
    """End-to-end tests for module_2 beam-search pipeline using module_1 random case generation."""

    def test_run_search_selects_queries_from_witness_knowledge(self) -> None:
        """module_2.run_search() should produce a query plan from witness_knowledge and write outputs."""
        case = module_1.run_random_case(
            rules_path=RULES_PATH,
            output_dir=_OUTPUT_DIR,
            seed=42,
            kb_ratio=0.4,
        )
        evidence_path = _OUTPUT_DIR / "evidence_found.json"
        witness_knowledge = case["witness_knowledge"]
        self.assertGreater(len(witness_knowledge), 0, "Expected some witness knowledge in the test case.")

        result = module_2.run_search(
            evidence_path=evidence_path,
            witness_knowledge=witness_knowledge,
            query_budget=5,
            output_dir=_OUTPUT_DIR,
            beam_width=3,
        )

        self.assertIn("query_plan", result)
        self.assertIn("observations", result)
        self.assertIn("search_trace", result)
        self.assertIn("goal_reached", result)

        query_plan = result["query_plan"]
        self.assertLessEqual(len(query_plan), 5, "Should respect query_budget")
        for action in query_plan:
            self.assertIn(action, witness_knowledge, f"Query plan action {action} should be in witness_knowledge")

        observations = result["observations"]
        self.assertEqual(len(observations), len(query_plan))
        for i, obs in enumerate(observations):
            self.assertIn("action", obs)
            self.assertIn("result", obs)
            if i < len(query_plan):
                self.assertEqual(obs["action"], query_plan[i])

        self.assertTrue(evidence_path.exists())
        query_plan_path = _OUTPUT_DIR / "query_plan.json"
        self.assertTrue(query_plan_path.exists())
        observations_path = _OUTPUT_DIR / "observations.json"
        self.assertTrue(observations_path.exists())
        search_trace_path = _OUTPUT_DIR / "search_trace.txt"
        self.assertTrue(search_trace_path.exists())

    def test_full_pipeline_module1_then_module2_produces_search_outputs(self) -> None:
        """Run module_1.run_random_case() then module_2.run_search(); search outputs should be produced."""
        result = module_1.run_random_case(
            rules_path=RULES_PATH,
            output_dir=_OUTPUT_DIR,
            seed=99,
            kb_ratio=0.4,
        )
        evidence_path = _OUTPUT_DIR / "evidence_found.json"
        self.assertTrue(evidence_path.exists(), "module_1.run_random_case() should create evidence_found.json")

        with open(evidence_path, encoding="utf-8") as f:
            data_before = json.load(f)
        self.assertIn("evidence", data_before, "module_1 output should contain 'evidence'")

        witness_knowledge = result["witness_knowledge"]
        search_result = module_2.run_search(
            evidence_path=evidence_path,
            witness_knowledge=witness_knowledge,
            query_budget=5,
            output_dir=_OUTPUT_DIR,
            beam_width=3,
        )

        self.assertIn("query_plan", search_result)
        self.assertIn("observations", search_result)
        self.assertIn("search_trace", search_result)
        self.assertIn("goal_reached", search_result)

        self.assertTrue((_OUTPUT_DIR / "query_plan.json").exists())
        self.assertTrue((_OUTPUT_DIR / "observations.json").exists())
        self.assertTrue((_OUTPUT_DIR / "search_trace.txt").exists())

        with open(_OUTPUT_DIR / "query_plan.json", encoding="utf-8") as f:
            query_plan_data = json.load(f)
        self.assertIn("actions", query_plan_data)
        self.assertIsInstance(query_plan_data["actions"], list)

    def test_beam_search_query_planning_produces_outputs(self) -> None:
        """module_2.run_search() should produce query_plan.json, observations.json, and search_trace.txt."""
        case = module_1.run_random_case(
            rules_path=RULES_PATH,
            output_dir=_OUTPUT_DIR,
            seed=123,
            kb_ratio=0.4,
        )
        evidence_path = _OUTPUT_DIR / "evidence_found.json"
        self.assertTrue(evidence_path.exists(), "module_1.run_random_case() should create evidence_found.json")

        witness_knowledge = case["witness_knowledge"]
        self.assertGreater(len(witness_knowledge), 0, "Expected some witness knowledge")

        result = module_2.run_search(
            evidence_path=evidence_path,
            witness_knowledge=witness_knowledge,
            query_budget=5,
            output_dir=_OUTPUT_DIR,
            beam_width=3,
        )

        self.assertIn("query_plan", result)
        self.assertIn("observations", result)
        self.assertIn("search_trace", result)

        query_plan_path = _OUTPUT_DIR / "query_plan.json"
        self.assertTrue(query_plan_path.exists(), "query_plan.json should be created")
        with open(query_plan_path, encoding="utf-8") as f:
            query_plan_data = json.load(f)
        self.assertIn("actions", query_plan_data)
        self.assertIsInstance(query_plan_data["actions"], list)
        self.assertLessEqual(len(query_plan_data["actions"]), 5, "Should respect query_budget")

        observations_path = _OUTPUT_DIR / "observations.json"
        self.assertTrue(observations_path.exists(), "observations.json should be created")
        with open(observations_path, encoding="utf-8") as f:
            observations_data = json.load(f)
        self.assertIn("observations", observations_data)
        self.assertIsInstance(observations_data["observations"], list)
        self.assertEqual(
            len(observations_data["observations"]),
            len(query_plan_data["actions"]),
            "Observations should match query plan length",
        )

        search_trace_path = _OUTPUT_DIR / "search_trace.txt"
        self.assertTrue(search_trace_path.exists(), "search_trace.txt should be created")
        with open(search_trace_path, encoding="utf-8") as f:
            trace_content = f.read()
        self.assertIn("Beam search trace", trace_content)

        for action in query_plan_data["actions"]:
            self.assertIn(action, witness_knowledge, f"Query plan action {action} should be in witness_knowledge")

        for i, obs in enumerate(observations_data["observations"]):
            self.assertIn("action", obs)
            self.assertIn("result", obs)
            if i < len(query_plan_data["actions"]):
                self.assertEqual(obs["action"], query_plan_data["actions"][i])

    def test_beam_search_explores_multiple_paths(self) -> None:
        """Beam search should keep multiple candidate states (beam_width > 1)."""
        case = module_1.run_random_case(
            rules_path=RULES_PATH,
            output_dir=_OUTPUT_DIR,
            seed=456,
            kb_ratio=0.4,
        )
        evidence_path = _OUTPUT_DIR / "evidence_found.json"
        witness_knowledge = case["witness_knowledge"]

        result = module_2.run_search(
            evidence_path=evidence_path,
            witness_knowledge=witness_knowledge,
            query_budget=3,
            output_dir=_OUTPUT_DIR,
            beam_width=3,
        )

        search_trace = result["search_trace"]
        if search_trace:
            for entry in search_trace:
                if entry.get("num_candidates", 0) > 1:
                    beam_heuristics = entry.get("beam_heuristics", [])
                    self.assertGreaterEqual(
                        len(beam_heuristics),
                        1,
                        "Beam search should track heuristic values for kept states",
                    )


if __name__ == "__main__":
    unittest.main()
