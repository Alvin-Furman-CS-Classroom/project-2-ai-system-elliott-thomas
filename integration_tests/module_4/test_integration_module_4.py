"""Integration tests for module_4: hypothesis generation + ranking.

Runs the Modules 1→2→3 pipeline on a randomly generated case, then calls
Module 4 using Module 3 outputs.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from src import module_1, module_2, module_3, module_4
from src.case_viewer import (
    get_solution_from_evidence,
    get_solution_from_metadata,
    load_evidence_and_rules_for_view,
    show_case_view_multi,
    _summarize_new_facts,
)


_THIS_DIR = Path(__file__).resolve().parent
_MODULE_1_DIR = _THIS_DIR.parent / "module_1"

_PIPELINE_DIR = _THIS_DIR / "pipeline_tmp"
_PIPELINE_DIR.mkdir(parents=True, exist_ok=True)

_OUTPUT_DIR = _THIS_DIR / "output_test_files"
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RULES_PATH = _MODULE_1_DIR / "rules.json"
EVIDENCE_PATH = _PIPELINE_DIR / "evidence_found.json"
KB_FOL_PATH = _OUTPUT_DIR / "kb_fol.json"
INFERRED_FACTS_PATH = _OUTPUT_DIR / "inferred_facts.json"

HYPOTHESES_RANKED_PATH = _OUTPUT_DIR / "hypotheses_ranked.json"
OPTIMIZATION_LOG_PATH = _OUTPUT_DIR / "optimization_log.txt"


class TestModule4Integration(unittest.TestCase):
    def test_full_pipeline_module1_then_2_then_3_then_4(self) -> None:
        case = module_1.run_random_case(
            rules_path=RULES_PATH,
            output_dir=_PIPELINE_DIR,
            seed=202,
            kb_ratio=0.4,
        )
        self.assertTrue(EVIDENCE_PATH.exists(), "module_1 should create evidence_found.json")

        evidence1, rooms, time_points, metadata = load_evidence_and_rules_for_view(
            EVIDENCE_PATH, RULES_PATH
        )

        witness_knowledge = case["witness_knowledge"]
        self.assertGreater(len(witness_knowledge), 0, "Expected witness knowledge")

        module_2.run_search(
            evidence_path=EVIDENCE_PATH,
            witness_knowledge=witness_knowledge,
            query_budget=100,
            output_dir=_PIPELINE_DIR,
            beam_width=3,
            rules_path=RULES_PATH,
        )

        module_3.run(
            evidence_path=EVIDENCE_PATH,
            rules_path=RULES_PATH,
            kb_fol_path=KB_FOL_PATH,
            inferred_facts_path=INFERRED_FACTS_PATH,
            show_case_view=False,
        )

        self.assertTrue(KB_FOL_PATH.exists(), "kb_fol.json should be created by module_3")
        self.assertTrue(INFERRED_FACTS_PATH.exists(), "inferred_facts.json should be created by module_3")

        module_4.run(
            kb_fol_path=KB_FOL_PATH,
            inferred_facts_path=INFERRED_FACTS_PATH,
            output_dir=_OUTPUT_DIR,
            top_k=3,
            random_seed=123,
        )

        self.assertTrue(HYPOTHESES_RANKED_PATH.exists(), "hypotheses_ranked.json should be written by module_4")
        self.assertTrue(OPTIMIZATION_LOG_PATH.exists(), "optimization_log.txt should be written by module_4")

        with open(HYPOTHESES_RANKED_PATH, encoding="utf-8") as f:
            ranked = json.load(f)

        self.assertIn("hypotheses_ranked", ranked)
        self.assertIn("summary", ranked)
        self.assertIn("ga_config", ranked)
        self.assertIn("fitness_progress", ranked)
        self.assertIn("search_stats", ranked)
        hypotheses = ranked["hypotheses_ranked"]
        self.assertIsInstance(hypotheses, list)
        self.assertGreater(len(hypotheses), 0, "Expected at least one hypothesis")
        self.assertLessEqual(len(hypotheses), 3, "Should respect top_k")

        # Build a viewer pipeline: Module 1 -> Module 2 -> Module 3 -> Module 4.
        # For step 2 (Module 2), reconstruct the cumulative KB used to feed Module 3.
        # Note: Module 3 evidence already includes forward-inferred facts in its FOL output;
        # for the viewer we inject those back into a propositional dict.
        final_kb = dict(evidence1)
        module_2_obs_path = _PIPELINE_DIR / "observations.json"
        if module_2_obs_path.exists():
            with open(module_2_obs_path, encoding="utf-8") as f:
                obs_data = json.load(f)
            for obs in obs_data.get("observations", []):
                action = obs.get("action", "")
                value = obs.get("result")
                if value is True:
                    final_kb[action] = True
                elif value is False and (action.startswith("KeyFound_") or action.startswith("At_")):
                    final_kb[f"NOT_{action}"] = True

        with open(KB_FOL_PATH, encoding="utf-8") as f:
            kb_fol_data = json.load(f)
        evidence3 = dict(final_kb)
        for fol in kb_fol_data.get("fol_propositions", []):
            if fol.get("value") is True and not fol.get("negated"):
                prop = fol.get("propositional")
                if prop:
                    evidence3[prop] = True

        # Solution extraction for steps.
        solution1 = get_solution_from_metadata(metadata)
        solution2 = get_solution_from_evidence(final_kb)
        if solution2.get("culprit") is None:
            solution2 = solution1
        solution3 = get_solution_from_evidence(evidence3)
        if solution3.get("culprit") is None:
            solution3 = solution1

        solution4 = get_solution_from_evidence(evidence3)
        best_hyp = hypotheses[0] if hypotheses else {}
        if best_hyp:
            solution4 = {
                "culprit": best_hyp.get("culprit"),
                "weapon": best_hyp.get("weapon"),
                "room": best_hyp.get("room"),
                "time": best_hyp.get("time"),
            }

        # For visualization: inject the best hypothesis placement so the room map can show it.
        evidence4 = dict(evidence3)
        if solution4.get("culprit") and solution4.get("room") and solution4.get("time"):
            evidence4[f"At_{solution4['culprit']}_{solution4['room']}_{solution4['time']}"] = True
        if solution4.get("weapon") and solution4.get("room"):
            evidence4[f"Weapon_{solution4['weapon']}_{solution4['room']}"] = True
        if solution4.get("room"):
            evidence4[f"VictimFound_{solution4['room']}"] = True

        steps = [
            {
                "module_id": 1,
                "title": "Module 1 — Case init & evidence",
                "solution": solution1,
                "evidence": evidence1,
                "extra_lines": ["Module 1 created the initial evidence (propositional KB)."],
            },
            {
                "module_id": 2,
                "title": "Module 2 — After query planning & observations",
                "solution": solution2,
                "evidence": final_kb,
                "extra_lines": [
                    *_summarize_new_facts(evidence1, final_kb),
                ],
            },
            {
                "module_id": 3,
                "title": "Module 3 — After FOL inference",
                "solution": solution3,
                "evidence": evidence3,
                "extra_lines": [
                    f"Total FOL propositions: {len(kb_fol_data.get('fol_propositions', []))}",
                ],
            },
            {
                "module_id": 4,
                "title": "Module 4 — After hypothesis ranking",
                "solution": solution4,
                "evidence": evidence4,
                "extra_lines": [
                    f"Best hypothesis score: {best_hyp.get('score', '—')}",
                ],
            },
        ]

        show_case_view_multi(steps, rooms, time_points)


if __name__ == "__main__":
    unittest.main()

