"""Integration tests for module_2: run selection + evidence writing on real case_init data.

Run from project root:
    python -m unittest integration_tests.module_2.test_integration_module_2 -v

This integration test writes its output to:
    integration_tests/module_2/output_test_files/evidence_found_module_2.json
so you can manually inspect the results after running it.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src import module_1, module_2


_THIS_DIR = Path(__file__).resolve().parent
_MODULE_1_DIR = _THIS_DIR.parent / "module_1"
_OUTPUT_DIR = _THIS_DIR / "output_test_files"
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Where this test will write its evidence file.
EVIDENCE_OUTPUT_PATH = _OUTPUT_DIR / "evidence_found_module_2.json"

# Reuse the existing integration test case_init.json and rules from module_1.
CASE_INIT_PATH = _MODULE_1_DIR / "case_inits" / "case_init.json"
RULES_PATH = _MODULE_1_DIR / "rules.json"


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

    def test_full_pipeline_module1_then_module2_extends_evidence_file(self) -> None:
        """Run module_1.run() then module_2: evidence_found.json from module_1 can be extended by module_2."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            shutil.copy(CASE_INIT_PATH, tmp / "case_init.json")
            shutil.copy(RULES_PATH, tmp / "rules.json")

            # Module 1: run inference and write evidence_found.json to tmp/output_test_files/
            module_1.run(tmp / "case_init.json", tmp / "rules.json")
            evidence_path = tmp / "output_test_files" / "evidence_found.json"
            self.assertTrue(evidence_path.exists(), "module_1.run() should create evidence_found.json")

            with open(evidence_path, encoding="utf-8") as f:
                data_before = json.load(f)
            self.assertIn("evidence", data_before, "module_1 output should contain 'evidence'")

            # Module 2: build KB and witness_knowledge from same case, select facts, extend evidence file
            case = module_1.read_case_init(tmp / "case_init.json")
            kb = module_1.build_kb(case["kb_evidence"])
            witness_knowledge = case["witness_knowledge"]
            selected = module_2.select_and_add_witness_facts(
                kb, witness_knowledge, n=module_2.DEFAULT_NUM_FACTS_TO_SELECT
            )
            module_2.write_questions_to_evidence(evidence_path, selected, witness_knowledge)

            # File should still have module_1's keys and now have witness_queries_added from module_2
            with open(evidence_path, encoding="utf-8") as f:
                data_after = json.load(f)
            self.assertIn("evidence", data_after, "evidence key should be preserved")
            self.assertEqual(data_after["evidence"], data_before["evidence"])
            self.assertIn("witness_queries_added", data_after)
            recorded = [e["question"] for e in data_after["witness_queries_added"]]
            for prop in selected:
                self.assertIn(prop, recorded)


if __name__ == "__main__":
    unittest.main()

