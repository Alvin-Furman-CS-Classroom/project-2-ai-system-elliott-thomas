"""Unit tests for module_4: hypothesis generation + scoring."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src import module_4


class TestModule4(unittest.TestCase):
    def _write_kb_fol(self, path: Path) -> None:
        kb_payload = {
            "fol_propositions": [
                {
                    "predicate": "LikelyCulprit",
                    "args": ["MrsWhite"],
                    "value": True,
                    "propositional": "LikelyCulprit_MrsWhite",
                },
                {
                    "predicate": "LikelyWeapon",
                    "args": ["Dagger"],
                    "value": True,
                    "propositional": "LikelyWeapon_Dagger",
                },
                {
                    "predicate": "LikelyRoom",
                    "args": ["Study"],
                    "value": True,
                    "propositional": "LikelyRoom_Study",
                },
                {
                    "predicate": "Weapon",
                    "args": ["Dagger", "Study"],
                    "value": True,
                    "propositional": "Weapon_Dagger_Study",
                },
                {
                    "predicate": "VictimFound",
                    "args": ["Study"],
                    "value": True,
                    "propositional": "VictimFound_Study",
                },
                {
                    "predicate": "At",
                    "args": ["MrsWhite", "Study", "9pm"],
                    "value": True,
                    "propositional": "At_MrsWhite_Study_9pm",
                },
                {
                    "predicate": "At",
                    "args": ["MrsWhite", "Study", "8pm"],
                    "value": True,
                    "negated": True,
                    "propositional": "NOT_At_MrsWhite_Study_8pm",
                },
                # Include a time candidate so module_4 can enumerate.
                {
                    "predicate": "At",
                    "args": ["MrGreen", "Kitchen", "8pm"],
                    "value": True,
                    "propositional": "At_MrGreen_Kitchen_8pm",
                },
            ],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(kb_payload), encoding="utf-8")

    def _write_inferred(self, path: Path) -> None:
        inferred_payload = {
            "inferred_facts": [
                {
                    "fact": {"predicate": "At", "args": ["MrsWhite", "Study", "TIME"]},
                    "rule_id": "R002",
                    "variable_bindings": {"PERSON": "MrsWhite", "ROOM": "Study"},
                    "premise_facts": [],
                }
            ]
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(inferred_payload), encoding="utf-8")

    def test_run_writes_outputs_and_ranks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            kb_path = tmp_path / "kb_fol.json"
            inf_path = tmp_path / "inferred_facts.json"
            out_dir = tmp_path / "out"

            self._write_kb_fol(kb_path)
            self._write_inferred(inf_path)

            payload = module_4.run(
                kb_fol_path=kb_path,
                inferred_facts_path=inf_path,
                output_dir=out_dir,
                top_k=3,
            )

            ranked_path = out_dir / "hypotheses_ranked.json"
            log_path = out_dir / "optimization_log.txt"
            self.assertTrue(ranked_path.exists())
            self.assertTrue(log_path.exists())

            ranked_data = json.loads(ranked_path.read_text(encoding="utf-8"))
            self.assertIn("hypotheses_ranked", ranked_data)
            self.assertIn("summary", ranked_data)

            hypotheses = ranked_data["hypotheses_ranked"]
            self.assertTrue(len(hypotheses) >= 1)

            # Ensure sorted descending by score.
            scores = [float(h["score"]) for h in hypotheses]
            self.assertEqual(scores, sorted(scores, reverse=True))

            # Best hypothesis should match the true positive At at 9pm.
            best = hypotheses[0]
            self.assertEqual(best["culprit"], "MrsWhite")
            self.assertEqual(best["weapon"], "Dagger")
            self.assertEqual(best["room"], "Study")
            self.assertEqual(best["time"], "9pm")


if __name__ == "__main__":
    unittest.main()

