"""Integration tests for module_3: FOL reasoning on real case data.

Run from project root:
    python -m unittest integration_tests.module_3.test_integration_module_3 -v

This integration test shows the case viewer at the end (Module 1 → 2 → 3 steps).

This integration test writes its output to:
    integration_tests/module_3/output_test_files/

Output files (consolidated in one directory):
    - kb_fol.json (FOL KB including inferred facts)
    - inferred_facts.json (proof-carrying inferred facts)

It builds on the module_2 integration test by running:
    module_1.run_random_case() -> module_2.run_search() -> module_3.run()
on a randomly generated case.
"""

import json
import unittest
from pathlib import Path

from src import module_1, module_2, module_3
from src.case_viewer import (
    get_solution_from_evidence,
    load_evidence_and_rules_for_view,
    show_case_view_multi,
    _summarize_new_facts,
)


_THIS_DIR = Path(__file__).resolve().parent
_MODULE_1_DIR = _THIS_DIR.parent / "module_1"

# Directory for upstream pipeline outputs (modules 1–2); kept separate so that
# module_3's own outputs stay focused and readable.
_PIPELINE_DIR = _THIS_DIR / "pipeline_tmp"
_PIPELINE_DIR.mkdir(parents=True, exist_ok=True)

# Directory for module_3 outputs only.
_OUTPUT_DIR = _THIS_DIR / "output_test_files"
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RULES_PATH = _MODULE_1_DIR / "rules.json"
EVIDENCE_PATH = _PIPELINE_DIR / "evidence_found.json"
CASE_INIT_PATH = _PIPELINE_DIR / "case_init_generated.json"
KB_FOL_PATH = _OUTPUT_DIR / "kb_fol.json"
INFERRED_FACTS_PATH = _OUTPUT_DIR / "inferred_facts.json"


class TestModule3Integration(unittest.TestCase):
    """End-to-end tests for module_3 FOL pipeline using module_1 + module_2."""

    def test_full_pipeline_produces_kb_and_inferred_facts(self) -> None:
        """Run modules 1–3; module_3 should write kb_fol.json and inferred_facts.json."""
        # 1) Generate a random case and initial evidence using module_1.
        case = module_1.run_random_case(
            rules_path=RULES_PATH,
            output_dir=_PIPELINE_DIR,
            kb_ratio=0.4,
        )

        # case_init_generated.json and evidence_found.json should exist after module_1.
        self.assertTrue(
            CASE_INIT_PATH.exists(),
            "module_1 should create case_init_generated.json in the pipeline directory",
        )
        self.assertTrue(EVIDENCE_PATH.exists(), "module_1 should create evidence_found.json")

        # Visualize the raw initial_evidence from case_init_generated.json (all initiated facts).
        with open(CASE_INIT_PATH, encoding="utf-8") as f:
            case_init_data = json.load(f)
        initial_evidence_full = case_init_data.get("initial_evidence", {})
        initial_evidence = {k: v for k, v in initial_evidence_full.items() if v is True}

        evidence1, rooms, time_points, _metadata = load_evidence_and_rules_for_view(
            EVIDENCE_PATH, RULES_PATH
        )
        self.assertGreater(len(evidence1), 0, "Module 1 should produce evidence")

        # 2) Run module_2 beam-search query planning, which may enrich the evidence file.
        witness_knowledge = case["witness_knowledge"]
        self.assertGreater(len(witness_knowledge), 0, "Expected some witness knowledge for integration test.")

        search_result = module_2.run_search(
            evidence_path=EVIDENCE_PATH,
            witness_knowledge=witness_knowledge,
            query_budget=10,
            output_dir=_PIPELINE_DIR,
            beam_width=3,
            rules_path=RULES_PATH,
        )

        # Build final_kb after Module 2 (evidence1 + observations, including NOT_ for False).
        final_kb = dict(evidence1)
        for obs in search_result["observations"]:
            action = obs.get("action", "")
            value = obs.get("result")
            if value is True:
                final_kb[action] = True
            elif value is False and (action.startswith("KeyFound_") or action.startswith("At_")):
                final_kb[f"NOT_{action}"] = True

        self.assertIn("query_plan", search_result)
        self.assertIn("observations", search_result)
        self.assertIn("search_trace", search_result)

        # 3) Run module_3 on the updated evidence + rules, writing its outputs to the module_3 directory.
        result = module_3.run(
            evidence_path=EVIDENCE_PATH,
            rules_path=RULES_PATH,
            kb_fol_path=KB_FOL_PATH,
            inferred_facts_path=INFERRED_FACTS_PATH,
        )

        # Check in-memory result structure.
        self.assertIn("fol_propositions", result)
        self.assertIn("inferred_facts", result)
        fol_list = result["fol_propositions"]
        inferred = result["inferred_facts"]
        self.assertIsInstance(fol_list, list)
        self.assertGreater(len(fol_list), 0)
        for fol in fol_list:
            self.assertIn("predicate", fol)
            self.assertIn("args", fol)
            self.assertIn("value", fol)
            self.assertIn("propositional", fol)

        self.assertIsInstance(inferred, list)

        # Check that kb_fol.json and inferred_facts.json were written to the module_3 output directory.
        self.assertTrue(KB_FOL_PATH.exists(), "kb_fol.json should be created by module_3.run()")
        self.assertTrue(
            INFERRED_FACTS_PATH.exists(),
            "inferred_facts.json should be created by module_3.run()",
        )

        with open(KB_FOL_PATH, encoding="utf-8") as f:
            kb_data = json.load(f)
        self.assertIn("fol_propositions", kb_data)
        self.assertIsInstance(kb_data["fol_propositions"], list)
        self.assertGreater(len(kb_data["fol_propositions"]), 0)

        with open(INFERRED_FACTS_PATH, encoding="utf-8") as f:
            inferred_data = json.load(f)
        self.assertIn("inferred_facts", inferred_data)
        self.assertIsInstance(inferred_data["inferred_facts"], list)

        # Show case viewer after the pipeline (Module 1 → 2 → 3).
        evidence3 = dict(final_kb)
        for fol in result.get("fol_propositions", []):
            if fol.get("value") is True and not fol.get("negated"):
                prop = fol.get("propositional")
                if prop:
                    evidence3[prop] = True
        # Solutions inferred/annotated at different points.
        # Important: do not use case/rules metadata for solution. Metadata is only for
        # human review; the displayed "identified culprit" must come from evidence only.
        solution0 = get_solution_from_evidence(initial_evidence)
        solution1 = get_solution_from_evidence(evidence1)
        solution2 = get_solution_from_evidence(final_kb)
        solution3 = get_solution_from_evidence(evidence3)
        qplan = search_result.get("query_plan", [])
        qplan_text = ", ".join(qplan) if qplan else "—"
        steps = [
            {
                "module_id": 0,
                "title": "Case init — Raw initial facts (case_init_generated.json)",
                "solution": solution0,
                "evidence": initial_evidence,
                "extra_lines": [
                    "Raw initial_evidence from case_init_generated.json (before Module 1 KB processing).",
                    f"Total initiated facts (True): {len(initial_evidence)}",
                ],
            },
            {
                "module_id": 1,
                "title": "Module 1 — Case init & evidence",
                "solution": solution1,
                "evidence": evidence1,
                "extra_lines": [
                    "Module 1 created a random case_init (body location in KB).",
                ],
            },
            {
                "module_id": 2,
                "title": "Module 2 — After query plan & observations",
                "solution": solution2,
                "evidence": final_kb,
                "extra_lines": [
                    f"Goal reached: {search_result['goal_reached']}",
                    f"Queries: {qplan_text}",
                    *_summarize_new_facts(evidence1, final_kb),
                ],
            },
            {
                "module_id": 3,
                "title": "Module 3 — After FOL inference",
                "solution": solution3,
                "evidence": evidence3,
                "extra_lines": [
                    f"Inferred facts: {len(result.get('inferred_facts', []))}",
                    f"Total FOL propositions: {len(result.get('fol_propositions', []))}",
                    *_summarize_new_facts(final_kb, evidence3),
                ],
            },
        ]
        show_case_view_multi(steps, rooms, time_points)


if __name__ == "__main__":
    unittest.main()

