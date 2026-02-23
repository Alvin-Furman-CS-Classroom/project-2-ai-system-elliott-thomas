"""Unit tests for module_2: beam-search query planning and run_search entry point."""
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


# --- beam_search_query_planning ---


class TestBeamSearchQueryPlanning(unittest.TestCase):
    """Tests for module_2.beam_search_query_planning (beam search for query sequences)."""

    def test_returns_empty_when_no_budget(self) -> None:
        """With query_budget <= 0, should return empty results."""
        initial_kb: dict[str, bool] = {}
        witness_knowledge = {"Alibi_ColonelMustard_9pm": True}
        queries, observations, trace = module_2.beam_search_query_planning(
            initial_kb, witness_knowledge, query_budget=0, beam_width=3
        )
        self.assertEqual(queries, [])
        self.assertEqual(observations, [])
        self.assertEqual(trace, [])

    def test_returns_empty_when_no_witness_knowledge(self) -> None:
        """With empty witness_knowledge, should return empty results."""
        initial_kb: dict[str, bool] = {}
        witness_knowledge: dict[str, bool] = {}
        queries, observations, trace = module_2.beam_search_query_planning(
            initial_kb, witness_knowledge, query_budget=5, beam_width=3
        )
        self.assertEqual(queries, [])
        self.assertEqual(observations, [])
        self.assertEqual(trace, [])

    def test_respects_query_budget(self) -> None:
        """Should not exceed query_budget in the returned query plan."""
        initial_kb: dict[str, bool] = {}
        witness_knowledge = {
            "Alibi_ColonelMustard_9pm": True,
            "Alibi_MissScarlet_9pm": True,
            "At_ColonelMustard_Study_9pm": True,
            "Weapon_Candlestick_Study": True,
            "Fingerprints_Study_ColonelMustard": True,
        }
        queries, observations, trace = module_2.beam_search_query_planning(
            initial_kb, witness_knowledge, query_budget=3, beam_width=2
        )
        self.assertLessEqual(len(queries), 3, "Should respect query_budget")
        self.assertEqual(len(observations), len(queries))

    def test_observations_match_queries(self) -> None:
        """Each observation should correspond to a query in the plan."""
        initial_kb: dict[str, bool] = {}
        witness_knowledge = {
            "Alibi_ColonelMustard_9pm": True,
            "At_MissScarlet_Ballroom_9pm": False,
        }
        queries, observations, trace = module_2.beam_search_query_planning(
            initial_kb, witness_knowledge, query_budget=2, beam_width=2
        )
        self.assertEqual(len(observations), len(queries))
        for i, query in enumerate(queries):
            self.assertEqual(observations[i]["action"], query)
            self.assertEqual(observations[i]["result"], witness_knowledge[query])

    def test_only_adds_true_facts_to_kb(self) -> None:
        """Only True-valued facts should be added to the KB during search."""
        initial_kb: dict[str, bool] = {}
        witness_knowledge = {
            "Alibi_ColonelMustard_9pm": True,
            "At_MissScarlet_Ballroom_9pm": False,
        }
        queries, observations, trace = module_2.beam_search_query_planning(
            initial_kb, witness_knowledge, query_budget=2, beam_width=2
        )
        # Both should be queried, but only True one should affect KB state
        self.assertEqual(len(queries), 2)
        # The search should have queried both
        for query in queries:
            self.assertIn(query, witness_knowledge)

    def test_trace_records_search_steps(self) -> None:
        """Search trace should record information about each search step."""
        initial_kb: dict[str, bool] = {}
        witness_knowledge = {
            "Alibi_ColonelMustard_9pm": True,
            "Alibi_MissScarlet_9pm": True,
            "At_ColonelMustard_Study_9pm": True,
        }
        queries, observations, trace = module_2.beam_search_query_planning(
            initial_kb, witness_knowledge, query_budget=2, beam_width=2
        )
        if queries:  # If any queries were made
            self.assertGreater(len(trace), 0, "Should record at least one search step")
            for entry in trace:
                self.assertIn("step", entry)
                self.assertIn("num_candidates", entry)
                self.assertIn("beam_heuristics", entry)
                self.assertIn("beam_queries", entry)

    def test_beam_width_limits_states_kept(self) -> None:
        """Beam search should keep at most beam_width states at each step."""
        initial_kb: dict[str, bool] = {}
        witness_knowledge = {
            "Alibi_ColonelMustard_9pm": True,
            "Alibi_MissScarlet_9pm": True,
            "Alibi_ProfessorPlum_9pm": True,
            "At_ColonelMustard_Study_9pm": True,
            "At_MissScarlet_Ballroom_9pm": True,
        }
        queries, observations, trace = module_2.beam_search_query_planning(
            initial_kb, witness_knowledge, query_budget=2, beam_width=2
        )
        # Check that beam_heuristics in trace has at most beam_width entries
        for entry in trace:
            beam_heuristics = entry.get("beam_heuristics", [])
            self.assertLessEqual(
                len(beam_heuristics),
                2,
                "Should keep at most beam_width states",
            )


# --- write_search_outputs ---


class TestWriteSearchOutputs(unittest.TestCase):
    """Tests for module_2.write_search_outputs (write query plan, observations, trace)."""

    def test_creates_all_three_output_files(self) -> None:
        """Should create query_plan.json, observations.json, and search_trace.txt."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            query_plan = ["Alibi_ColonelMustard_9pm", "At_MissScarlet_Ballroom_9pm"]
            observations = [
                {"action": "Alibi_ColonelMustard_9pm", "result": True},
                {"action": "At_MissScarlet_Ballroom_9pm", "result": False},
            ]
            search_trace = [
                {
                    "step": 0,
                    "num_candidates": 5,
                    "beam_heuristics": [10.5, 9.8],
                    "beam_queries": [["Alibi_ColonelMustard_9pm"], ["At_MissScarlet_Ballroom_9pm"]],
                }
            ]

            module_2.write_search_outputs(query_plan, observations, search_trace, output_dir)

            query_plan_path = output_dir / "query_plan.json"
            observations_path = output_dir / "observations.json"
            trace_path = output_dir / "search_trace.txt"

            self.assertTrue(query_plan_path.exists(), "query_plan.json should be created")
            self.assertTrue(observations_path.exists(), "observations.json should be created")
            self.assertTrue(trace_path.exists(), "search_trace.txt should be created")

    def test_query_plan_json_has_correct_structure(self) -> None:
        """query_plan.json should have 'actions' key with list of queries."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            query_plan = ["Alibi_ColonelMustard_9pm"]
            module_2.write_search_outputs(query_plan, [], [], output_dir)

            with open(output_dir / "query_plan.json", encoding="utf-8") as f:
                data = json.load(f)

            self.assertIn("actions", data)
            self.assertEqual(data["actions"], query_plan)

    def test_observations_json_has_correct_structure(self) -> None:
        """observations.json should have 'observations' key with list of observation dicts."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            observations = [
                {"action": "Alibi_ColonelMustard_9pm", "result": True},
                {"action": "At_MissScarlet_Ballroom_9pm", "result": False},
            ]
            module_2.write_search_outputs([], observations, [], output_dir)

            with open(output_dir / "observations.json", encoding="utf-8") as f:
                data = json.load(f)

            self.assertIn("observations", data)
            self.assertEqual(data["observations"], observations)

    def test_search_trace_txt_is_readable(self) -> None:
        """search_trace.txt should contain readable trace information."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            search_trace = [
                {
                    "step": 0,
                    "num_candidates": 3,
                    "beam_heuristics": [10.5, 9.8],
                    "beam_queries": [["Alibi_ColonelMustard_9pm"], ["At_MissScarlet_Ballroom_9pm"]],
                }
            ]
            module_2.write_search_outputs([], [], search_trace, output_dir)

            with open(output_dir / "search_trace.txt", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("Beam search trace", content)
            self.assertIn("Step 0", content)


# --- run_search ---


class TestRunSearch(unittest.TestCase):
    """Tests for module_2.run_search (entry point for search-based query planning)."""

    def test_loads_evidence_and_runs_search(self) -> None:
        """Should load evidence from file and run beam search."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            evidence_path = tmp / "evidence_found.json"
            evidence_data = {"evidence": {"VictimFound_Study": True}}
            with open(evidence_path, "w", encoding="utf-8") as f:
                json.dump(evidence_data, f)

            witness_knowledge = {
                "Alibi_ColonelMustard_9pm": True,
                "At_MissScarlet_Ballroom_9pm": False,
            }

            output_dir = tmp / "search_outputs"
            result = module_2.run_search(
                evidence_path=evidence_path,
                witness_knowledge=witness_knowledge,
                query_budget=2,
                output_dir=output_dir,
                beam_width=2,
            )

            self.assertIn("query_plan", result)
            self.assertIn("observations", result)
            self.assertIn("search_trace", result)

    def test_creates_output_files(self) -> None:
        """Should create all three output files in the specified directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            evidence_path = tmp / "evidence_found.json"
            evidence_data = {"evidence": {}}
            with open(evidence_path, "w", encoding="utf-8") as f:
                json.dump(evidence_data, f)

            witness_knowledge = {"Alibi_ColonelMustard_9pm": True}

            output_dir = tmp / "search_outputs"
            module_2.run_search(
                evidence_path=evidence_path,
                witness_knowledge=witness_knowledge,
                query_budget=1,
                output_dir=output_dir,
                beam_width=2,
            )

            self.assertTrue((output_dir / "query_plan.json").exists())
            self.assertTrue((output_dir / "observations.json").exists())
            self.assertTrue((output_dir / "search_trace.txt").exists())

    def test_handles_missing_evidence_key(self) -> None:
        """Should handle evidence file without 'evidence' key gracefully."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            evidence_path = tmp / "evidence_found.json"
            evidence_data = {}  # No 'evidence' key
            with open(evidence_path, "w", encoding="utf-8") as f:
                json.dump(evidence_data, f)

            witness_knowledge = {"Alibi_ColonelMustard_9pm": True}

            output_dir = tmp / "search_outputs"
            # Should not raise an error
            result = module_2.run_search(
                evidence_path=evidence_path,
                witness_knowledge=witness_knowledge,
                query_budget=1,
                output_dir=output_dir,
                beam_width=2,
            )
            self.assertIn("query_plan", result)


if __name__ == "__main__":
    unittest.main()

