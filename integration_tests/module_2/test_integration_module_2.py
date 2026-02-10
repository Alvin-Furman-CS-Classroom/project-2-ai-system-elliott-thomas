"""Integration tests for module_2: run selection + evidence writing on real case_init data.

Run from project root:
    python -m unittest integration_tests.module_2.test_integration_module_2 -v

This integration test writes its output to:
    integration_tests/module_2/output_test_files/evidence_found_module_2.json
so you can manually inspect the results after running it.
"""

import json
import unittest
from pathlib import Path

from src import module_1, module_2


_THIS_DIR = Path(__file__).resolve().parent
_OUTPUT_DIR = _THIS_DIR / "output_test_files"
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Where this test will write its evidence file.
EVIDENCE_OUTPUT_PATH = _OUTPUT_DIR / "evidence_found_module_2.json"

# Reuse the existing integration test case_init.json from module_1.
CASE_INIT_PATH = _THIS_DIR.parent / "module_1" / "case_inits" / "case_init.json"


class TestModule2Integration(unittest.TestCase):
    """End-to-end tests for module_2 using real case_init data."""

    def test_selects_witness_facts_and_writes_to_evidence_file(self) -> None:
        """module_2 should select some witness facts and record them in evidence_found.json."""
        # Use module_1 to read the real case_init and build the initial KB + witness_knowledge.
        case = module_1.read_case_init(CASE_INIT_PATH)
        kb = module_1.build_kb(case["kb_evidence"])
        witness_knowledge = case["witness_knowledge"]

        self.assertGreater(len(witness_knowledge), 0, "Expected some witness knowledge in the test case.")

        # Select a small number of witness facts to ask about and add them to the KB.
        selected = module_2.select_and_add_witness_facts(
            kb,
            witness_knowledge,
            n=module_2.DEFAULT_NUM_FACTS_TO_SELECT,
        )

        # We should select at least one question, and at most the configured default number.
        self.assertGreater(len(selected), 0)
        self.assertLessEqual(len(selected), module_2.DEFAULT_NUM_FACTS_TO_SELECT)

        # All selected propositions must come from witness_knowledge.
        for proposition_name in selected:
            self.assertIn(proposition_name, witness_knowledge)

        # Any selected proposition that is True in witness_knowledge should now be in the KB.
        for proposition_name in selected:
            if witness_knowledge[proposition_name] is True:
                self.assertIn(proposition_name, kb)

        # Write the evidence file into integration_tests/module_2/output_test_files
        module_2.write_questions_to_evidence(
            evidence_path=EVIDENCE_OUTPUT_PATH,
            questions=selected,
            witness_knowledge=witness_knowledge,
        )

        # The file should exist and contain witness_queries_added with our selected questions.
        self.assertTrue(EVIDENCE_OUTPUT_PATH.exists())
        with open(EVIDENCE_OUTPUT_PATH, encoding="utf-8") as file_handle:
            data = json.load(file_handle)

        self.assertIn("witness_queries_added", data)
        recorded_questions = [entry["question"] for entry in data["witness_queries_added"]]
        for proposition_name in selected:
            self.assertIn(proposition_name, recorded_questions)


if __name__ == "__main__":
    unittest.main()

