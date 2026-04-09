"""Module 5: Case viewer walkthrough over Modules 1-4 outputs.

Module 5 is the presentation layer. It collects pipeline artifacts and builds a
visual step-through of the detective process.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.case_viewer import (
    _summarize_new_facts,
    parse_evidence_to_room_state,
    get_solution_from_evidence,
    get_solution_from_metadata,
    load_evidence_and_rules_for_view,
    show_case_view_multi,
)


def _load_json(path: str | Path) -> dict[str, Any]:
    with open(Path(path), encoding="utf-8") as f:
        return json.load(f)


def _augment_with_hypothesis(evidence: dict[str, bool], hyp: dict[str, Any]) -> dict[str, bool]:
    out = dict(evidence)
    culprit = hyp.get("culprit")
    weapon = hyp.get("weapon")
    room = hyp.get("room")
    time = hyp.get("time")
    if culprit and room and time:
        out[f"At_{culprit}_{room}_{time}"] = True
    if weapon and room:
        out[f"Weapon_{weapon}_{room}"] = True
    if room:
        for k in list(out.keys()):
            if k.startswith("BodyDraggedFrom_"):
                out.pop(k, None)
        out[f"BodyDraggedFrom_{room}"] = True
    return out


def _build_verbal_timeline(
    *,
    solution: dict[str, Any],
    evidence: dict[str, bool],
    kb_fol_data: dict[str, Any],
    observations: list[dict[str, Any]] | None = None,
    inferred_facts_data: dict[str, Any] | None = None,
    rule_descriptions: dict[str, str] | None = None,
) -> list[str]:
    """Create a short narrative timeline using propositional + FOL evidence."""
    culprit = solution.get("culprit") or "Unknown"
    weapon = solution.get("weapon") or "Unknown weapon"
    room = solution.get("room") or "Unknown room"
    time = solution.get("time") or "unknown time"

    timeline: list[str] = ["Case walkthrough summary:"]
    narrative_bits: list[str] = [
        f"The current theory places {culprit} in {room} at {time} with {weapon}."
    ]

    if evidence.get(f"MurderLocation_{room}") is True:
        narrative_bits.append(f"Bloodstain evidence points to {room} as the murder location")
    if evidence.get(f"BodyDraggedFrom_{room}") is True:
        narrative_bits.append(f"the body appears to have been dragged from {room}")
    if time != "unknown time" and evidence.get(f"MurderTime_{time}") is True:
        narrative_bits.append(f"time-focused rules support {time} as the likely murder time")
    if time != "unknown time" and evidence.get(f"DragTraceFresh_{room}_{time}") is True:
        narrative_bits.append(f"fresh drag-trace evidence in {room} aligns with {time}")
    if len(narrative_bits) > 1:
        timeline.append(". ".join(narrative_bits[1:]).capitalize() + ".")

    inferred_count = 0
    for fol in kb_fol_data.get("fol_propositions", []):
        if fol.get("inferred") is True and fol.get("value") is True and not fol.get("negated"):
            inferred_count += 1
    timeline.append(
        f"Module 3 contributed {inferred_count} inferred FOL facts used in this walkthrough."
    )

    if observations:
        obs_pairs = [
            f"{obs.get('action', '?')} -> {obs.get('result', '?')}" for obs in observations[:4]
        ]
        timeline.append(
            "Module 2 query highlights include "
            + "; ".join(obs_pairs)
            + "."
        )

    if inferred_facts_data is not None:
        inf = inferred_facts_data.get("inferred_facts", [])
        if inf:
            rule_summaries: list[str] = []
            for step in inf[:4]:
                fact = step.get("fact", {})
                pred = fact.get("predicate", "?")
                args = ", ".join(str(a) for a in fact.get("args", []))
                rid = step.get("rule_id", "?")
                rdesc = (rule_descriptions or {}).get(str(rid), "rule applied")
                rule_summaries.append(f"{rid} ({rdesc}) inferred {pred}({args})")
            timeline.append("Notable rule applications: " + "; ".join(rule_summaries) + ".")

    warnings: list[str] = []
    if time != "unknown time" and evidence.get(f"Alibi_{culprit}_{time}") is True:
        warnings.append(f"{culprit} has an alibi at {time}")
    if time != "unknown time" and evidence.get(f"NOT_Culprit_{culprit}_{time}") is True:
        warnings.append(f"NOT_Culprit evidence exists for {culprit} at {time}")
    if warnings:
        timeline.append("Potential contradictions: " + "; ".join(warnings) + ".")

    if timeline and timeline[0] == "Case walkthrough summary:" and len(narrative_bits) >= 1:
        timeline.insert(1, narrative_bits[0])
    return timeline


def _build_grid_visual_payload(
    *,
    evidence: dict[str, bool],
    rooms: list[str],
    time_points: list[str],
    focus_time: str | None,
) -> dict[str, Any]:
    state = parse_evidence_to_room_state(
        evidence,
        rooms,
        time_points,
        murder_time=focus_time,
    )
    grid_cells: list[list[dict[str, Any] | None]] = [[None, None, None] for _ in range(3)]
    for idx, room in enumerate(rooms[:9]):
        r = idx // 3
        c = idx % 3
        room_state = state.get(room, {}).get(focus_time or "", {})
        grid_cells[r][c] = {
            "room": room,
            "people": room_state.get("people", []),
            "weapons": room_state.get("weapons", []),
            "door_locked": room_state.get("door_locked"),
            "body_found": room_state.get("body_found"),
            "dragged_from": room_state.get("dragged_from"),
        }
    return {
        "focus_time": focus_time,
        "grid_cells": grid_cells,
    }


def _grid_payload_to_ascii(grid_payload: dict[str, Any]) -> str:
    lines: list[str] = []
    focus_time = grid_payload.get("focus_time") or "unknown"
    lines.append(f"3x3 room grid at time: {focus_time}")
    lines.append("=" * 40)
    for row in grid_payload.get("grid_cells", []):
        row_cells: list[str] = []
        for cell in row:
            if not cell:
                row_cells.append("[empty]")
                continue
            room = cell.get("room", "?")
            people = ",".join(cell.get("people", [])[:2]) or "-"
            weapons = ",".join(cell.get("weapons", [])[:2]) or "-"
            flags: list[str] = []
            if cell.get("body_found"):
                flags.append("Body")
            if cell.get("dragged_from"):
                flags.append("Dragged")
            if cell.get("door_locked") is True:
                flags.append("Locked")
            flag_text = "|".join(flags) if flags else "-"
            row_cells.append(f"[{room} P:{people} W:{weapons} F:{flag_text}]")
        lines.append(" ".join(row_cells))
    return "\n".join(lines)


def build_steps(
    *,
    rules_path: str | Path,
    evidence_path: str | Path,
    module2_observations_path: str | Path,
    kb_fol_path: str | Path,
    inferred_facts_path: str | Path | None,
    hypotheses_ranked_path: str | Path,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Build viewer steps from module artifacts."""
    evidence1, rooms, time_points, metadata = load_evidence_and_rules_for_view(
        evidence_path, rules_path
    )
    rules_data = _load_json(rules_path)
    rule_descriptions = {
        str(r.get("id", "")): str(r.get("description", "")).strip()
        for r in rules_data.get("rules", [])
    }

    final_kb = dict(evidence1)
    obs_data = _load_json(module2_observations_path)
    for obs in obs_data.get("observations", []):
        action = obs.get("action", "")
        value = obs.get("result")
        if value is True:
            final_kb[action] = True
        elif value is False and (action.startswith("KeyFound_") or action.startswith("At_")):
            final_kb[f"NOT_{action}"] = True

    kb_fol_data = _load_json(kb_fol_path)
    inferred_facts_data = _load_json(inferred_facts_path) if inferred_facts_path is not None else {}
    evidence3 = dict(final_kb)
    for fol in kb_fol_data.get("fol_propositions", []):
        if fol.get("value") is True and not fol.get("negated"):
            prop = fol.get("propositional")
            if prop:
                evidence3[prop] = True

    ranked_data = _load_json(hypotheses_ranked_path)
    best_hyp = (ranked_data.get("hypotheses_ranked") or [{}])[0]

    solution1 = get_solution_from_metadata(metadata)
    solution2 = get_solution_from_evidence(final_kb)
    if solution2.get("culprit") is None:
        solution2 = solution1
    solution3 = get_solution_from_evidence(evidence3)
    if solution3.get("culprit") is None:
        solution3 = solution1
    solution4 = {
        "culprit": best_hyp.get("culprit"),
        "weapon": best_hyp.get("weapon"),
        "room": best_hyp.get("room"),
        "time": best_hyp.get("time"),
    }
    evidence4 = _augment_with_hypothesis(evidence3, solution4)
    verbal_timeline = _build_verbal_timeline(
        solution=solution4,
        evidence=evidence4,
        kb_fol_data=kb_fol_data,
        observations=obs_data.get("observations", []),
        inferred_facts_data=inferred_facts_data,
        rule_descriptions=rule_descriptions,
    )

    steps = [
        {
            "module_id": 1,
            "title": "Module 1 — Case init & evidence",
            "solution": solution1,
            "evidence": evidence1,
            "extra_lines": ["Module 1 created the initial evidence base (propositional KB)."],
        },
        {
            "module_id": 2,
            "title": "Module 2 — After query planning & observations",
            "solution": solution2,
            "evidence": final_kb,
            "extra_lines": ["Module 2 added witness-query observations.", *_summarize_new_facts(evidence1, final_kb)],
        },
        {
            "module_id": 3,
            "title": "Module 3 — After FOL inference",
            "solution": solution3,
            "evidence": evidence3,
            "extra_lines": [
                "Module 3 expanded the case with first-order inferences.",
                f"Total FOL propositions: {len(kb_fol_data.get('fol_propositions', []))}",
            ],
        },
        {
            "module_id": 4,
            "title": "Module 4 — After hypothesis ranking",
            "solution": solution4,
            "evidence": evidence4,
            "extra_lines": [
                "Module 4 ranked candidate hypotheses using the evidence.",
                f"Best hypothesis score: {best_hyp.get('score', '—')}",
            ],
        },
        {
            "module_id": 5,
            "title": "Module 5 — Visual walkthrough",
            "solution": solution4,
            "evidence": evidence4,
            "extra_lines": [
                "Module 5 combines module outputs into a concise visual walkthrough.",
                *verbal_timeline,
            ],
        },
    ]
    return steps, rooms, time_points


def run(
    *,
    rules_path: str | Path,
    evidence_path: str | Path,
    module2_observations_path: str | Path,
    kb_fol_path: str | Path,
    inferred_facts_path: str | Path | None = None,
    hypotheses_ranked_path: str | Path,
    show_view: bool = True,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Build and optionally render the Module 5 walkthrough.

    If output_dir is provided, writes `module_5_visual_display.json` containing
    the full display payload (steps, rooms, time points) so the visual output is
    reproducible in non-GUI environments.
    """
    steps, rooms, time_points = build_steps(
        rules_path=rules_path,
        evidence_path=evidence_path,
        module2_observations_path=module2_observations_path,
        kb_fol_path=kb_fol_path,
        inferred_facts_path=inferred_facts_path,
        hypotheses_ranked_path=hypotheses_ranked_path,
    )
    focus_time = (steps[-1].get("solution") or {}).get("time")
    grid_payload = _build_grid_visual_payload(
        evidence=steps[-1].get("evidence", {}),
        rooms=rooms,
        time_points=time_points,
        focus_time=focus_time,
    )
    timeline_lines = list(steps[-1].get("extra_lines") or [])
    payload = {
        "steps": steps,
        "rooms": rooms,
        "time_points": time_points,
        "timeline_lines": timeline_lines,
        "room_grid": grid_payload,
    }
    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        with open(out / "module_5_visual_display.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        with open(out / "module_5_timeline.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(timeline_lines) + "\n")
        with open(out / "module_5_room_grid.json", "w", encoding="utf-8") as f:
            json.dump(grid_payload, f, indent=2)
        with open(out / "module_5_room_grid.txt", "w", encoding="utf-8") as f:
            f.write(_grid_payload_to_ascii(grid_payload) + "\n")
    if show_view:
        show_case_view_multi(steps, rooms, time_points)
    return payload

