"""Unit tests for module_3: First-Order Logic evidence store and inference."""
# Written with the help of Cursor Agent
# Tests FOL approach per AIgent Proposal: predicates, args, relational representation

import json
import tempfile
import unittest
from pathlib import Path

from src import module_3

# Paths to integration test data (run tests from project root)
EVIDENCE_PATH = Path("integration_tests/module_1/output_test_files/evidence_found.json")
RULES_PATH = Path("integration_tests/module_1/rules.json")


# --- load_evidence_and_rules ---


class TestLoadEvidenceAndRules(unittest.TestCase):
    """Tests for module_3.load_evidence_and_rules (load evidence from module_2 + rules.json)."""

    def test_returns_dict_with_expected_keys(self) -> None:
        """Return value should have evidence, witness_queries_added, metadata, rules, game_constraints, rules_metadata."""
        if not EVIDENCE_PATH.exists():
            self.skipTest(f"Evidence file not found: {EVIDENCE_PATH}")
        result = module_3.load_evidence_and_rules(EVIDENCE_PATH, RULES_PATH)
        self.assertIn("evidence", result)
        self.assertIn("witness_queries_added", result)
        self.assertIn("metadata", result)
        self.assertIn("rules", result)
        self.assertIn("game_constraints", result)
        self.assertIn("rules_metadata", result)

    def test_evidence_is_dict_of_propositions(self) -> None:
        """evidence should be a dict mapping proposition names to booleans."""
        if not EVIDENCE_PATH.exists():
            self.skipTest(f"Evidence file not found: {EVIDENCE_PATH}")
        result = module_3.load_evidence_and_rules(EVIDENCE_PATH, RULES_PATH)
        self.assertIsInstance(result["evidence"], dict)
        for key, val in result["evidence"].items():
            self.assertIsInstance(key, str)
            self.assertIn(val, (True, False))

    def test_rules_and_game_constraints_structure(self) -> None:
        """rules should be a list of dicts; game_constraints should have suspects, rooms, weapons, time_points."""
        if not EVIDENCE_PATH.exists():
            self.skipTest(f"Evidence file not found: {EVIDENCE_PATH}")
        result = module_3.load_evidence_and_rules(EVIDENCE_PATH, RULES_PATH)
        self.assertIsInstance(result["rules"], list)
        for rule in result["rules"]:
            self.assertIn("id", rule)
            self.assertIn("if", rule)
            self.assertIn("then", rule)
        gc = result["game_constraints"]
        self.assertIn("suspects", gc)
        self.assertIn("rooms", gc)
        self.assertIn("weapons", gc)
        self.assertIn("time_points", gc)

    def test_nonexistent_evidence_path_raises(self) -> None:
        """load_evidence_and_rules should raise FileNotFoundError when evidence file does not exist."""
        with self.assertRaises(FileNotFoundError):
            module_3.load_evidence_and_rules("nonexistent_evidence.json", RULES_PATH)

    def test_nonexistent_rules_path_raises(self) -> None:
        """load_evidence_and_rules should raise FileNotFoundError when rules file does not exist."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"evidence": {}, "metadata": {}}, f)
            evidence_path = f.name
        try:
            with self.assertRaises(FileNotFoundError):
                module_3.load_evidence_and_rules(evidence_path, "nonexistent_rules.json")
        finally:
            Path(evidence_path).unlink(missing_ok=True)


# --- create_fol_propositions ---


class TestCreateFolPropositions(unittest.TestCase):
    """Tests for module_3.create_fol_propositions (convert propositional KB to FOL structure).

    Per AIgent Proposal: FOL uses predicates and args for relational representation
    (e.g. At(person, place, time), NOT_Culprit(person, time)).
    """

    def test_returns_list_of_fol_dicts(self) -> None:
        """create_fol_propositions should return a list of dicts with predicate, args, value, propositional."""
        evidence = {"At_ColonelMustard_Study_9pm": True}
        result = module_3.create_fol_propositions(evidence)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        fol = result[0]
        self.assertIn("predicate", fol)
        self.assertIn("args", fol)
        self.assertIn("value", fol)
        self.assertIn("propositional", fol)

    def test_parses_at_person_room_time_to_fol(self) -> None:
        """At_Person_Room_Time should become predicate At with args [person, room, time]."""
        evidence = {"At_ColonelMustard_Study_9pm": True}
        result = module_3.create_fol_propositions(evidence)
        self.assertEqual(result[0]["predicate"], "At")
        self.assertEqual(result[0]["args"], ["ColonelMustard", "Study", "9pm"])
        self.assertIs(result[0]["value"], True)
        self.assertFalse(result[0].get("negated", False))

    def test_parses_not_culprit_to_fol_with_negated(self) -> None:
        """NOT_Culprit_Person_Time should become predicate Culprit with negated=True."""
        evidence = {"NOT_Culprit_MissScarlet_9pm": True}
        result = module_3.create_fol_propositions(evidence)
        self.assertEqual(result[0]["predicate"], "Culprit")
        self.assertEqual(result[0]["args"], ["MissScarlet", "9pm"])
        self.assertIs(result[0]["negated"], True)

    def test_parses_weapon_weapon_room_to_fol(self) -> None:
        """Weapon_Weapon_Room should become predicate Weapon with args [weapon, room]."""
        evidence = {"Weapon_Candlestick_Study": True}
        result = module_3.create_fol_propositions(evidence)
        self.assertEqual(result[0]["predicate"], "Weapon")
        self.assertEqual(result[0]["args"], ["Candlestick", "Study"])

    def test_parses_alibi_person_time_to_fol(self) -> None:
        """Alibi_Person_Time should become predicate Alibi with args [person, time]."""
        evidence = {"Alibi_ProfessorPlum_9pm": True}
        result = module_3.create_fol_propositions(evidence)
        self.assertEqual(result[0]["predicate"], "Alibi")
        self.assertEqual(result[0]["args"], ["ProfessorPlum", "9pm"])

    def test_parses_fingerprints_room_person_to_fol(self) -> None:
        """Fingerprints_Room_Person should become predicate Fingerprints with args [room, person]."""
        evidence = {"Fingerprints_Study_ColonelMustard": True}
        result = module_3.create_fol_propositions(evidence)
        self.assertEqual(result[0]["predicate"], "Fingerprints")
        self.assertEqual(result[0]["args"], ["Study", "ColonelMustard"])

    def test_empty_evidence_returns_empty_list(self) -> None:
        """Empty evidence should return an empty list."""
        result = module_3.create_fol_propositions({})
        self.assertEqual(result, [])

    def test_writes_to_output_path_when_provided(self) -> None:
        """When output_path is provided, FOL propositions should be written as JSON."""
        evidence = {"VictimFound_Study": True}
        output_path = Path("integration_tests/module_1/output_test_files/test_kb_fol_output.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        module_3.create_fol_propositions(evidence, output_path=output_path)
        self.assertTrue(output_path.exists())
        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("fol_propositions", data)
        self.assertEqual(len(data["fol_propositions"]), 1)
        self.assertEqual(data["fol_propositions"][0]["predicate"], "VictimFound")
        self.assertEqual(data["fol_propositions"][0]["args"], ["Study"])

    def test_preserves_propositional_name_for_traceability(self) -> None:
        """Each FOL proposition should include the original propositional name."""
        evidence = {"MurderLocation_Study": True}
        result = module_3.create_fol_propositions(evidence)
        self.assertEqual(result[0]["propositional"], "MurderLocation_Study")


# --- Integration: FOL approach per AIgent Proposal ---


class TestFolIntegration(unittest.TestCase):
    """Integration tests: load evidence + rules, create FOL propositions.

    AIgent Proposal: Module 3 elevates propositional facts to relational
    knowledge using predicates (At, Alibi, etc.) with structured args.
    """

    def test_full_pipeline_produces_fol_propositions(self) -> None:
        """load_evidence_and_rules + create_fol_propositions should produce valid FOL structure."""
        if not EVIDENCE_PATH.exists():
            self.skipTest(f"Evidence file not found: {EVIDENCE_PATH}")
        data = module_3.load_evidence_and_rules(EVIDENCE_PATH, RULES_PATH)
        fol_list = module_3.create_fol_propositions(data["evidence"])
        self.assertGreater(len(fol_list), 0)
        for fol in fol_list:
            self.assertIsInstance(fol["predicate"], str)
            self.assertIsInstance(fol["args"], list)
            self.assertIn("value", fol)
            self.assertIn("propositional", fol)

    def test_fol_propositions_cover_predicate_types_from_rules(self) -> None:
        """FOL output should include predicate types used in rules (At, Alibi, Weapon, etc.)."""
        if not EVIDENCE_PATH.exists():
            self.skipTest(f"Evidence file not found: {EVIDENCE_PATH}")
        data = module_3.load_evidence_and_rules(EVIDENCE_PATH, RULES_PATH)
        fol_list = module_3.create_fol_propositions(data["evidence"])
        predicates = {fol["predicate"] for fol in fol_list}
        # Per rules.json: At, Weapon, Alibi, Fingerprints, VictimFound, Culprit, etc.
        self.assertIn("At", predicates)
        self.assertGreater(len(predicates), 1)

    def test_negated_predicates_preserved(self) -> None:
        """NOT_ prefixed propositions should appear with negated=True in FOL output."""
        evidence = {
            "At_Alice_Kitchen_8pm": True,
            "NOT_Culprit_Alice_8pm": True,
        }
        fol_list = module_3.create_fol_propositions(evidence)
        negated = [f for f in fol_list if f.get("negated")]
        self.assertEqual(len(negated), 1)
        self.assertEqual(negated[0]["predicate"], "Culprit")


# --- infer_fol ---


class TestInferFol(unittest.TestCase):
    """Tests for FOL inference: unification + forward chaining per AIgent Proposal."""

    def test_returns_extended_fol_and_inferred_facts(self) -> None:
        """infer_fol should return (fol_list, inferred_facts) with proof steps."""
        fol = [
            {"predicate": "At", "args": ["Alice", "Kitchen", "8pm"], "value": True},
            {"predicate": "Weapon", "args": ["Candlestick", "Kitchen"], "value": True},
            {"predicate": "DoorLocked", "args": ["Kitchen", "8pm"], "value": True},
        ]
        rules = [
            {
                "id": "R001",
                "if": ["At_PERSON_ROOM_TIME", "Weapon_WEAPON_ROOM", "DoorLocked_ROOM_TIME"],
                "then": "ForcedEntry_ROOM_TIME",
            },
        ]
        extended, inferred = module_3.infer_fol(fol, rules)
        self.assertIn("ForcedEntry", [p["predicate"] for p in extended])
        self.assertEqual(len(inferred), 1)
        self.assertEqual(inferred[0]["rule_id"], "R001")
        self.assertIn("variable_bindings", inferred[0])
        self.assertIn("premise_facts", inferred[0])
        self.assertEqual(inferred[0]["fact"]["predicate"], "ForcedEntry")
        self.assertEqual(inferred[0]["fact"]["args"], ["Kitchen", "8pm"])

    def test_variable_bindings_merge_across_premises(self) -> None:
        """Unification should merge substitutions consistently across premises."""
        fol = [
            {"predicate": "At", "args": ["ColonelMustard", "Study", "9pm"], "value": True},
            {"predicate": "Weapon", "args": ["Candlestick", "Study"], "value": True},
            {"predicate": "MurderLocation", "args": ["Study"], "value": True},
        ]
        rules = [
            {
                "id": "R009",
                "if": ["MurderLocation_ROOM", "At_PERSON_ROOM_TIME", "Weapon_WEAPON_ROOM"],
                "then": "UsedWeapon_PERSON_WEAPON",
            },
        ]
        _, inferred = module_3.infer_fol(fol, rules)
        self.assertEqual(len(inferred), 1)
        bindings = inferred[0]["variable_bindings"]
        self.assertEqual(bindings["PERSON"], "ColonelMustard")
        self.assertEqual(bindings["WEAPON"], "Candlestick")
        self.assertEqual(bindings["ROOM"], "Study")

    def test_skips_contradiction_rules(self) -> None:
        """CONTRADICTION conclusion rules should not add to inferred_facts."""
        fol = [
            {"predicate": "At", "args": ["Alice", "Room1", "9pm"], "value": True},
            {"predicate": "At", "args": ["Alice", "Room2", "9pm"], "value": True},
        ]
        rules = [
            {
                "id": "R011",
                "if": ["At_PERSON_ROOM1_TIME", "At_PERSON_ROOM2_TIME", "NOT_ROOM1_EQ_ROOM2"],
                "then": "CONTRADICTION",
            },
        ]
        _, inferred = module_3.infer_fol(fol, rules)
        self.assertEqual(len(inferred), 0)

    def test_empty_fol_returns_empty_inferred(self) -> None:
        """Empty FOL propositions should yield no inferred facts."""
        _, inferred = module_3.infer_fol([], [])
        self.assertEqual(inferred, [])


# --- write_inferred_facts ---


class TestWriteInferredFacts(unittest.TestCase):
    """Tests for write_inferred_facts output."""

    def test_writes_json_with_inferred_facts_key(self) -> None:
        """write_inferred_facts should write JSON with inferred_facts array."""
        output_path = Path("integration_tests/module_1/output_test_files/test_inferred_output.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        inferred = [
            {"fact": {"predicate": "ForcedEntry", "args": ["Study", "9pm"]}, "rule_id": "R001", "variable_bindings": {}},
        ]
        module_3.write_inferred_facts(inferred, output_path)
        self.assertTrue(output_path.exists())
        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("inferred_facts", data)
        self.assertEqual(len(data["inferred_facts"]), 1)
        self.assertEqual(data["inferred_facts"][0]["fact"]["predicate"], "ForcedEntry")


# --- run ---


class TestRun(unittest.TestCase):
    """Tests for module_3.run full pipeline."""

    def test_run_produces_inferred_facts(self) -> None:
        """run() should produce inferred_facts when given output paths."""
        if not EVIDENCE_PATH.exists():
            self.skipTest(f"Evidence file not found: {EVIDENCE_PATH}")
        kb_path = Path("integration_tests/module_1/output_test_files/test_run_kb_fol.json")
        inf_path = Path("integration_tests/module_1/output_test_files/test_run_inferred.json")
        result = module_3.run(EVIDENCE_PATH, RULES_PATH, kb_fol_path=kb_path, inferred_facts_path=inf_path)
        self.assertIn("fol_propositions", result)
        self.assertIn("inferred_facts", result)
        self.assertGreater(len(result["fol_propositions"]), 0)
        if inf_path.exists():
            with open(inf_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("inferred_facts", data)


if __name__ == "__main__":
    unittest.main()
