"""Shared assertions for hypothesis_summary.json integration tests."""

from __future__ import annotations

from typing import Any


def assert_joint_best_guess_matches_top_hypothesis(testcase: Any, hyp_payload: dict) -> None:
    """Assert best_guess aligns with the top scored hypothesis entry.

    Expected shape:
      {
        "summary": {
          "best_guess": {"culprit": ..., "weapon": ..., "room": ..., "time": ...?},
          "hypotheses": [{"culprit": ..., "weapon": ..., "room": ..., "support": ...}, ...]
        },
        ...
      }
    """
    testcase.assertIsInstance(hyp_payload, dict)
    summary = hyp_payload.get("summary", {})
    testcase.assertIsInstance(summary, dict, "hypothesis_summary payload should include a summary object")

    best_guess = summary.get("best_guess", {})
    hypotheses = summary.get("hypotheses", [])

    testcase.assertIsInstance(best_guess, dict, "summary.best_guess should be a dict")
    testcase.assertIsInstance(hypotheses, list, "summary.hypotheses should be a list")
    testcase.assertGreater(len(hypotheses), 0, "summary.hypotheses should contain at least one entry")

    top = hypotheses[0]
    testcase.assertIsInstance(top, dict, "Top hypothesis entry should be a dict")

    for key in ("culprit", "weapon", "room"):
        testcase.assertIn(key, best_guess, f"best_guess should include '{key}'")
        testcase.assertIn(key, top, f"Top hypothesis should include '{key}'")
        testcase.assertEqual(
            best_guess.get(key),
            top.get(key),
            f"best_guess.{key} should match top hypothesis {key}",
        )
