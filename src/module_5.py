"""Module 5: Case viewer walkthrough over Modules 1-4 outputs.

Module 5 is the presentation layer. It collects pipeline artifacts and builds a
visual step-through of the detective process.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.case_viewer import (
    parse_evidence_to_room_state,
    get_solution_from_evidence,
    get_solution_from_metadata,
    load_evidence_and_rules_for_view,
    show_case_view_multi,
)

MODULE2_OBS_SAMPLE_LIMIT = 12
GRID_DIMENSION = 3
ASCII_ROW_PERSON_LIMIT = 2
ASCII_ROW_WEAPON_LIMIT = 2


def _load_json(path: str | Path) -> dict[str, Any]:
    """Load JSON from disk with clear error messages for missing or invalid files."""
    target = Path(path)
    try:
        with open(target, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Required JSON input not found: {target}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in file: {target}") from exc


def _coerce_obs_result(value: Any) -> bool | None:
    """Normalize observation result values to bool when possible."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        txt = value.strip().lower()
        if txt in {"true", "t", "1", "yes", "y"}:
            return True
        if txt in {"false", "f", "0", "no", "n"}:
            return False
    return None


def _true_prop_keys(evidence: dict[str, bool]) -> set[str]:
    """Return only proposition keys currently marked as true in the evidence map."""
    return {k for k, v in evidence.items() if v is True}


def _module2_evidence_delta(
    evidence_pre_m2: dict[str, bool], evidence_post_m2: dict[str, bool]
) -> tuple[set[str], set[str], int]:
    """Compare pre/post Module 2 evidence and report which true facts were added."""
    pre = _true_prop_keys(evidence_pre_m2)
    post = _true_prop_keys(evidence_post_m2)
    added = post - pre
    return pre, added, len(added)


def _module2_learned_fact_keys(observations: list[dict[str, Any]] | None) -> set[str]:
    """Extract proposition keys learned from Module 2 observation results."""
    learned: set[str] = set()
    for obs in observations or []:
        action = str(obs.get("action", "")).strip()
        if not action:
            continue
        value = _coerce_obs_result(obs.get("result"))
        if value is True:
            learned.add(action)
        elif value is False and (action.startswith("KeyFound_") or action.startswith("At_")):
            learned.add(f"NOT_{action}")
    return learned


def _summarize_module2_observations(observations: list[dict[str, Any]] | None) -> list[str]:
    """Build short display lines describing learned facts from Module 2 observations."""
    learned = sorted(_module2_learned_fact_keys(observations))
    if not learned:
        return []
    sample = learned[:MODULE2_OBS_SAMPLE_LIMIT]
    more = len(learned) - len(sample)
    return [
        f"New facts learned from Module 2 observations: {len(learned)}",
        "Learned facts (sample): " + ", ".join(sample) + (f" ... (+{more} more)" if more > 0 else ""),
    ]


def _origin_blurb(
    prop_key: str,
    *,
    pre_m2: set[str],
    m2_added: set[str],
    m3_only: set[str],
) -> str:
    """Return a short source label for where a proposition likely came from."""
    if prop_key in pre_m2:
        return "already established in the initial case (Module 1)"
    if prop_key in m2_added:
        return "learned during Module 2 witness queries"
    if prop_key in m3_only:
        return "derived later by first-order inference (Module 3)"
    return "supported by the combined pipeline state"


def _reason_with_origin(
    *,
    evidence: dict[str, bool],
    prop_key: str,
    sentence: str,
    pre_m2: set[str],
    m2_added: set[str],
    m3_only: set[str],
) -> str | None:
    """Create one reason sentence for a proposition, including where the fact came from."""
    if evidence.get(prop_key) is not True:
        return None
    return (
        f"{sentence} "
        f"({_origin_blurb(prop_key, pre_m2=pre_m2, m2_added=m2_added, m3_only=m3_only)})"
    )


def _append_reasoned_timeline_line(
    timeline: list[str],
    *,
    subject_text: str,
    reason_parts: list[str],
    fallback_reason: str,
) -> None:
    """Append a timeline sentence using specific reasons or a fallback explanation."""
    reason = "; ".join(reason_parts) if reason_parts else fallback_reason
    timeline.append(f"{subject_text}, because {reason}.")


def _augment_with_hypothesis(evidence: dict[str, bool], hyp: dict[str, Any]) -> dict[str, bool]:
    """Return a copy of evidence enriched with the current best hypothesis facts."""
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
    evidence_pre_m2: dict[str, bool],
    evidence_post_m2: dict[str, bool],
    evidence_post_m3: dict[str, bool],
    observations: list[dict[str, Any]] | None = None,
    inferred_facts_data: dict[str, Any] | None = None,
    rule_descriptions: dict[str, str] | None = None,
) -> list[str]:
    """Build a human-readable reasoning timeline for the final ranked solution."""
    culprit = solution.get("culprit") or "Unknown"
    weapon = solution.get("weapon") or "Unknown weapon"
    room = solution.get("room") or "Unknown room"
    time = solution.get("time") or "unknown time"

    timeline: list[str] = ["Case walkthrough summary:"]

    pre_m2, m2_added, m2_added_n = _module2_evidence_delta(evidence_pre_m2, evidence_post_m2)
    m2_from_obs = _module2_learned_fact_keys(observations)
    if m2_added_n == 0 and m2_from_obs:
        # Some pipelines persist post-Module-2 evidence to the same path used here.
        # Fallback to observation-derived learned facts to avoid false zero counts.
        m2_added = set(m2_from_obs)
        m2_added_n = len(m2_added)
    post_m2_keys = _true_prop_keys(evidence_post_m2)
    post_m3_keys = _true_prop_keys(evidence_post_m3)
    m3_only = post_m3_keys - post_m2_keys

    timeline.append(
        f"Before Module 2, the initial case file (Module 1 output) contained {len(pre_m2)} true propositions."
    )
    timeline.append(
        f"Module 2 witness queries added {m2_added_n} new true propositions "
        f"(bringing the working set to {len(post_m2_keys)} before first-order inference)."
    )
    if m3_only:
        timeline.append(
            f"Module 3 first-order inference then introduced {len(m3_only)} additional true propositions "
            f"beyond what Module 2 had established."
        )
    if observations:
        timeline.append(
            f"The Module 2 observation log contains {len(observations)} query actions that produced the additions above."
        )

    inferred_steps = (inferred_facts_data or {}).get("inferred_facts", [])

    def _first_rule_for(predicate: str, args: tuple[str, ...]) -> str | None:
        """Find the first inference-rule record that produced a target fact shape."""
        for step in inferred_steps:
            fact = step.get("fact", {})
            if fact.get("predicate") != predicate:
                continue
            fact_args = tuple(str(a) for a in fact.get("args", []))
            if fact_args == args:
                rid = str(step.get("rule_id", "?"))
                rdesc = (rule_descriptions or {}).get(rid, "rule applied")
                return f"{rid}: {rdesc}"
        return None

    rule_room = _first_rule_for("MurderLocation", (room,))
    room_reason_parts: list[str] = []
    ml_key = f"MurderLocation_{room}"
    ml_reason = _reason_with_origin(
        evidence=evidence,
        prop_key=ml_key,
        sentence=f"bloodstain and scene clues converge on {room} as the likely attack location",
        pre_m2=pre_m2,
        m2_added=m2_added,
        m3_only=m3_only,
    )
    if ml_reason:
        room_reason_parts.append(ml_reason)
    bdf_key = f"BodyDraggedFrom_{room}"
    bdf_reason = _reason_with_origin(
        evidence=evidence,
        prop_key=bdf_key,
        sentence=f"bloody drag marks indicate the body was moved from {room} toward the discovery site",
        pre_m2=pre_m2,
        m2_added=m2_added,
        m3_only=m3_only,
    )
    if bdf_reason:
        room_reason_parts.append(bdf_reason)
    if rule_room:
        room_reason_parts.append(f"this is reinforced by inference rule {rule_room}")
    _append_reasoned_timeline_line(
        timeline,
        subject_text=f"The murder location is identified as {room}",
        reason_parts=room_reason_parts,
        fallback_reason="current strongest hypothesis support",
    )

    rule_time = _first_rule_for("MurderTime", (time,))
    time_reason_parts: list[str] = []
    mt_key = f"MurderTime_{time}"
    mt_reason = (
        _reason_with_origin(
            evidence=evidence,
            prop_key=mt_key,
            sentence=f"time-linked clues narrow the event window to about {time}",
            pre_m2=pre_m2,
            m2_added=m2_added,
            m3_only=m3_only,
        )
        if time != "unknown time"
        else None
    )
    if mt_reason:
        time_reason_parts.append(mt_reason)
    dtf_key = f"DragTraceFresh_{room}_{time}"
    dtf_reason = (
        _reason_with_origin(
            evidence=evidence,
            prop_key=dtf_key,
            sentence=f"fresh drag traces in {room} suggest the movement happened around {time}",
            pre_m2=pre_m2,
            m2_added=m2_added,
            m3_only=m3_only,
        )
        if time != "unknown time"
        else None
    )
    if dtf_reason:
        time_reason_parts.append(dtf_reason)
    if rule_time:
        time_reason_parts.append(f"the timing is strengthened by inference rule {rule_time}")
    _append_reasoned_timeline_line(
        timeline,
        subject_text=f"The estimated murder time is {time}",
        reason_parts=time_reason_parts,
        fallback_reason="the top-ranked time hypothesis",
    )

    rule_culprit = _first_rule_for("Culprit", (culprit, time))
    culprit_reason_parts: list[str] = []
    cp_key = f"Culprit_{culprit}_{time}"
    cp_reason = (
        _reason_with_origin(
            evidence=evidence,
            prop_key=cp_key,
            sentence=f"culprit-focused deductions point to {culprit} during the {time} window",
            pre_m2=pre_m2,
            m2_added=m2_added,
            m3_only=m3_only,
        )
        if time != "unknown time"
        else None
    )
    if cp_reason:
        culprit_reason_parts.append(cp_reason)
    at_key = f"At_{culprit}_{room}_{time}"
    at_reason = (
        _reason_with_origin(
            evidence=evidence,
            prop_key=at_key,
            sentence=f"backward tracing places {culprit} at {room} when the critical events occurred",
            pre_m2=pre_m2,
            m2_added=m2_added,
            m3_only=m3_only,
        )
        if time != "unknown time"
        else None
    )
    if at_reason:
        culprit_reason_parts.append(at_reason)
    if rule_culprit:
        culprit_reason_parts.append(f"this alignment is supported by inference rule {rule_culprit}")
    _append_reasoned_timeline_line(
        timeline,
        subject_text=f"The likely culprit is {culprit}",
        reason_parts=culprit_reason_parts,
        fallback_reason="the top-ranked culprit hypothesis",
    )

    weapon_reason_parts: list[str] = []
    wpn_key = f"Weapon_{weapon}_{room}"
    wpn_reason = _reason_with_origin(
        evidence=evidence,
        prop_key=wpn_key,
        sentence=f"the {weapon} is tied to {room}, matching the reconstructed scene",
        pre_m2=pre_m2,
        m2_added=m2_added,
        m3_only=m3_only,
    )
    if wpn_reason:
        weapon_reason_parts.append(wpn_reason)
    if rule_room:
        weapon_reason_parts.append(
            f"once the scene is traced back to {room}, {weapon} becomes the most consistent instrument"
        )
    _append_reasoned_timeline_line(
        timeline,
        subject_text=f"The likely weapon is {weapon}",
        reason_parts=weapon_reason_parts,
        fallback_reason="the top-ranked weapon hypothesis",
    )

    return timeline


def _build_case_story(
    *,
    solution: dict[str, Any],
    evidence: dict[str, bool],
    evidence_pre_m2: dict[str, bool],
    evidence_post_m2: dict[str, bool],
    observations: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Generate a short story-style recap of the case from current evidence."""
    culprit = str(solution.get("culprit") or "an unknown suspect")
    weapon = str(solution.get("weapon") or "an unknown weapon")
    room = str(solution.get("room") or "an unknown room")
    time = str(solution.get("time") or "an unknown time")

    pre_m2, _, m2_added_n = _module2_evidence_delta(evidence_pre_m2, evidence_post_m2)
    m2_from_obs = _module2_learned_fact_keys(observations)
    # If pre/post snapshots overlap, set-diff can report zero.
    # Prefer observation-derived learned facts when available.
    if m2_from_obs:
        m2_added_n = len(m2_from_obs)

    seed_text = f"{culprit}|{weapon}|{room}|{time}"
    variant = sum(ord(ch) for ch in seed_text) % 3

    openers = [
        f"Near {time}, tension centered around the {room}.",
        f"As the clock approached {time}, the investigation narrowed to the {room}.",
        f"By about {time}, the {room} became the focus of the case.",
    ]
    scene_lines = [
        f"Bloodstain patterns suggest the attack began in {room}, not where the body was eventually found.",
        f"The blood evidence points back to {room} as the most plausible origin of the violence.",
        f"Tracing the scene backward places the initial assault in {room}.",
    ]
    drag_lines = [
        f"Bloody drag marks imply the body was moved after the attack, which supports {room} as the source room.",
        f"Drag evidence indicates post-incident movement from {room} toward the final discovery location.",
        f"The drag trail reads like a relocation path, starting from {room}.",
    ]
    culprit_lines = [
        f"Placing people by room and time puts {culprit} at the center of events around {time}.",
        f"When witness and placement clues are aligned at {time}, {culprit} is the strongest fit.",
        f"Backtracking presence at the key moment points to {culprit} as the likely actor.",
    ]
    weapon_lines = [
        f"Because {weapon} is tied to {room}, it best matches the reconstructed sequence.",
        f"With the scene anchored in {room}, {weapon} becomes the most coherent weapon choice.",
        f"The link between {weapon} and {room} makes it the most consistent instrument in this scenario.",
    ]

    post_m2_count = len(_true_prop_keys(evidence_post_m2))
    story = [
        f"Before Module 2, the detective had only the Module 1 case file: {len(pre_m2)} true facts.",
        f"Module 2 witness queries added {m2_added_n} new true facts (running total {post_m2_count} before Module 3 inference).",
        openers[variant],
        scene_lines[variant],
        culprit_lines[variant],
        weapon_lines[variant],
    ]
    if evidence.get(f"BodyDraggedFrom_{room}") is True:
        story.insert(4, drag_lines[variant])

    return story


def _build_grid_visual_payload(
    *,
    evidence: dict[str, bool],
    rooms: list[str],
    time_points: list[str],
    focus_time: str | None,
) -> dict[str, Any]:
    """Convert evidence into a fixed 3x3 room-grid payload for the final display."""
    state = parse_evidence_to_room_state(
        evidence,
        rooms,
        time_points,
        murder_time=focus_time,
    )
    grid_cells: list[list[dict[str, Any] | None]] = [
        [None for _ in range(GRID_DIMENSION)] for _ in range(GRID_DIMENSION)
    ]
    for idx, room in enumerate(rooms[: GRID_DIMENSION * GRID_DIMENSION]):
        r = idx // GRID_DIMENSION
        c = idx % GRID_DIMENSION
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
    """Render the room-grid payload as a plain-text table for non-GUI outputs."""
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
            people = ",".join(cell.get("people", [])[:ASCII_ROW_PERSON_LIMIT]) or "-"
            weapons = ",".join(cell.get("weapons", [])[:ASCII_ROW_WEAPON_LIMIT]) or "-"
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
    """Assemble the five walkthrough snapshots consumed by the case viewer UI."""
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
        value = _coerce_obs_result(obs.get("result"))
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
    story_lines = _build_case_story(
        solution=solution4,
        evidence=evidence4,
        evidence_pre_m2=evidence1,
        evidence_post_m2=final_kb,
        observations=obs_data.get("observations", []),
    )
    verbal_timeline = _build_verbal_timeline(
        solution=solution4,
        evidence=evidence4,
        evidence_pre_m2=evidence1,
        evidence_post_m2=final_kb,
        evidence_post_m3=evidence3,
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
            "extra_lines": [
                "Module 2 added witness-query observations.",
                *_summarize_module2_observations(obs_data.get("observations", [])),
            ],
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
                "Case story:",
                *story_lines,
                "Reasoning timeline:",
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
    """Run Module 5 end-to-end: build steps, derive visuals, optionally render/write outputs.

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

