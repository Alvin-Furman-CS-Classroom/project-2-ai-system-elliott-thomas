"""Integration test for module_5: case viewer walkthrough over modules 1-4."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from src import module_1, module_2, module_3, module_4, module_5


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
VISUAL_DISPLAY_PATH = _OUTPUT_DIR / "module_5_visual_display.json"
TIMELINE_PATH = _OUTPUT_DIR / "module_5_timeline.txt"
ROOM_GRID_JSON_PATH = _OUTPUT_DIR / "module_5_room_grid.json"
ROOM_GRID_TXT_PATH = _OUTPUT_DIR / "module_5_room_grid.txt"
class TestModule5Integration(unittest.TestCase):
    def test_module5_builds_case_walkthrough(self) -> None:
        case = module_1.run_random_case(
            rules_path=RULES_PATH,
            output_dir=_PIPELINE_DIR,
            seed=202,
            kb_ratio=0.4,
        )
        self.assertTrue(EVIDENCE_PATH.exists(), "module_1 should create evidence_found.json")

        module_2.run_search(
            evidence_path=EVIDENCE_PATH,
            witness_knowledge=case["witness_knowledge"],
            query_budget=200,
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
            top_k=5,
        )
        self.assertTrue(HYPOTHESES_RANKED_PATH.exists(), "module_4 should write hypotheses_ranked.json")

        result = module_5.run(
            rules_path=RULES_PATH,
            evidence_path=EVIDENCE_PATH,
            module2_observations_path=_PIPELINE_DIR / "observations.json",
            kb_fol_path=KB_FOL_PATH,
            inferred_facts_path=INFERRED_FACTS_PATH,
            hypotheses_ranked_path=HYPOTHESES_RANKED_PATH,
            show_view=True,
            output_dir=_OUTPUT_DIR,
        )
        self.assertTrue(VISUAL_DISPLAY_PATH.exists(), "module_5 should write module_5_visual_display.json")
        self.assertTrue(TIMELINE_PATH.exists(), "module_5 should write module_5_timeline.txt")
        self.assertTrue(ROOM_GRID_JSON_PATH.exists(), "module_5 should write module_5_room_grid.json")
        self.assertTrue(ROOM_GRID_TXT_PATH.exists(), "module_5 should write module_5_room_grid.txt")
        self.assertIn("steps", result)
        self.assertIn("rooms", result)
        self.assertIn("time_points", result)
        self.assertIn("timeline_lines", result)
        self.assertIn("room_grid", result)
        steps = result["steps"]
        self.assertIsInstance(steps, list)
        self.assertEqual(len(steps), 5, "Expected Module 1..5 walkthrough steps")
        self.assertEqual(steps[-1].get("module_id"), 5)
        self.assertIn("Visual walkthrough", steps[-1].get("title", ""))


if __name__ == "__main__":
    unittest.main()

