"""Unit tests for module_2: each public function tested independently."""
# Written with the help of Cursor Agent

import json
import tempfile
import unittest
from pathlib import Path

from src import module_2


# --- get_priority_score ---


class TestGetPriorityScore(unittest.TestCase):
    """Tests for module_2.get_priority_score (returns higher score for higher-priority prefixes)."""

    def test_known_prefix_has_positive_score(self) -> None:
        """Propositions with a known prefix should get a positive score."""
        score_alibi = module_2.get_priority_score("Alibi_ColonelMustard_9pm")
        score_weapon = module_2.get_priority_score("Weapon_Candlestick_Study")
        self.assertGreater(score_alibi, 0)
        self.assertGreater(score_weapon, 0)

    def test_unknown_prefix_has_zero_score(self) -> None:
        """Propositions with an unknown prefix should get score 0."""
        score = module_2.get_priority_score("RandomFact_123")
        self.assertEqual(score, 0)

    def test_higher_priority_prefix_gets_higher_score(self) -> None:
        """Earlier prefixes in the priority list should receive a higher score."""
        score_alibi = module_2.get_priority_score("Alibi_ColonelMustard_9pm")
        score_noise = module_2.get_priority_score("NoiseHeard_Study_9pm")
        self.assertGreater(
            score_alibi,
            score_noise,
            msg="Alibi_ should have higher priority than NoiseHeard_.",
        )


# --- select_and_add_witness_facts ---


class TestSelectAndAddWitnessFacts(unittest.TestCase):
    """Tests for module_2.select_and_add_witness_facts (choose top-n by priority and update KB)."""

    def test_returns_empty_list_when_no_witness_knowledge(self) -> None:
        """With empty witness_knowledge, the function should return an empty list."""
        kb: dict[str, bool] = {}
        witness_knowledge: dict[str, bool] = {}
        selected = module_2.select_and_add_witness_facts(kb, witness_knowledge, n=3)
        self.assertEqual(selected, [])
        self.assertEqual(kb, {})

    def test_returns_empty_list_when_n_is_non_positive(self) -> None:
        """When n <= 0, the function should not select any questions."""
        kb: dict[str, bool] = {}
        witness_knowledge = {"Alibi_ColonelMustard_9pm": True}
        selected = module_2.select_and_add_witness_facts(kb, witness_knowledge, n=0)
        self.assertEqual(selected, [])
        self.assertEqual(kb, {})

    def test_adds_only_true_values_to_kb(self) -> None:
        """Only propositions with value True in witness_knowledge should be added to the KB."""
        kb: dict[str, bool] = {}
        witness_knowledge = {
            "Alibi_ColonelMustard_9pm": True,
            "At_ColonelMustard_Study_9pm": False,
        }

        selected = module_2.select_and_add_witness_facts(kb, witness_knowledge, n=2)

        # Both propositions are candidates and should be in the selected list.
        self.assertIn("Alibi_ColonelMustard_9pm", selected)
        self.assertIn("At_ColonelMustard_Study_9pm", selected)

        # Only the True-valued proposition is added to the KB.
        self.assertIn("Alibi_ColonelMustard_9pm", kb)
        self.assertNotIn("At_ColonelMustard_Study_9pm", kb)

    def test_respects_priority_order_when_selecting(self) -> None:
        """Higher-priority proposition types should be selected before lower-priority ones."""
        kb: dict[str, bool] = {}
        witness_knowledge = {
            "Weapon_Candlestick_Study": True,
            "NoiseHeard_Study_9pm": True,
        }

        selected = module_2.select_and_add_witness_facts(kb, witness_knowledge, n=2)

        # Both should be selected, but Weapon_ should appear earlier than NoiseHeard_.
        self.assertEqual(set(selected), set(witness_knowledge.keys()))
        index_weapon = selected.index("Weapon_Candlestick_Study")
        index_noise = selected.index("NoiseHeard_Study_9pm")
        self.assertLess(
            index_weapon,
            index_noise,
            msg="Weapon_ should be higher priority than NoiseHeard_.",
        )


# --- write_questions_to_evidence ---


class TestWriteQuestionsToEvidence(unittest.TestCase):
    """Tests for module_2.write_questions_to_evidence (record witness queries into evidence_found.json)."""

    def test_creates_new_file_when_missing(self) -> None:
        """If evidence_found.json does not exist, the function should create it with witness_queries_added."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            evidence_path = Path(tmp_dir) / "evidence_found.json"
            questions = ["Alibi_ColonelMustard_9pm"]
            witness_knowledge = {"Alibi_ColonelMustard_9pm": True}

            module_2.write_questions_to_evidence(evidence_path, questions, witness_knowledge)

            self.assertTrue(evidence_path.exists())
            with open(evidence_path, encoding="utf-8") as file_handle:
                data = json.load(file_handle)

            self.assertIn("witness_queries_added", data)
            self.assertEqual(len(data["witness_queries_added"]), 1)
            entry = data["witness_queries_added"][0]
            self.assertEqual(entry["question"], "Alibi_ColonelMustard_9pm")
            self.assertIs(entry["value"], True)

    def test_preserves_existing_keys_when_updating_file(self) -> None:
        """Existing keys in evidence_found.json should be preserved when we add witness_queries_added."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            evidence_path = Path(tmp_dir) / "evidence_found.json"

            # Start with an existing evidence file.
            original_data = {"evidence": {"At_ColonelMustard_Study_9pm": True}}
            with open(evidence_path, "w", encoding="utf-8") as file_handle:
                json.dump(original_data, file_handle)

            questions = ["Alibi_ColonelMustard_9pm"]
            witness_knowledge = {"Alibi_ColonelMustard_9pm": False}

            module_2.write_questions_to_evidence(evidence_path, questions, witness_knowledge)

            with open(evidence_path, encoding="utf-8") as file_handle:
                data = json.load(file_handle)

            # Existing evidence key should still be present.
            self.assertIn("evidence", data)
            self.assertEqual(data["evidence"], original_data["evidence"])

            # New key with witness queries should be added.
            self.assertIn("witness_queries_added", data)
            self.assertEqual(len(data["witness_queries_added"]), 1)
            entry = data["witness_queries_added"][0]
            self.assertEqual(entry["question"], "Alibi_ColonelMustard_9pm")
            self.assertIs(entry["value"], False)


if __name__ == "__main__":
    unittest.main()

