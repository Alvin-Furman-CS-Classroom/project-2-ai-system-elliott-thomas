"""Module 2: Informed search for next best query (witness knowledge selection).

This module uses beam search to plan which witness facts to "ask" next and
produces a query plan, observations, and search trace for downstream modules.
"""
# Thomas Corbin and Elliott Chmil
# Written with the help of Cursor Agent

import json
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Order of proposition prefixes: earlier in the list = higher priority to query.
# Goal: Identify culprit, weapon, and room. Prioritize queries that directly help
# identify these three elements.
_QUERY_PRIORITY = (
    "Culprit_",  # Highest priority: directly identifies culprit
    "MurderLocation_",  # Second priority: identifies the room
    "Weapon_",  # Third priority: identifies weapon location
    "Alibi_",  # Helps eliminate suspects (NOT_Culprit)
    "At_",  # Location; used by Suspect, HadAccess, UsedWeapon rules
    "Fingerprints_",  # Can imply At_ via rules (e.g. R002)
    "VictimFound_",
    "BloodStains_",
    "NoiseHeard_",
    "DoorLocked_",
    "KeyFound_",
)

# Heuristic weights for beam search (avoid magic numbers).
_HEURISTIC_GOAL_PROGRESS = 100.0  # Score per goal element (culprit, weapon, room) already identified
_HEURISTIC_GOAL_BOOST = 3.0  # Extra multiplier for queries that would fill a missing goal element
_HEURISTIC_TIE_BREAKER_MAX = 0.1  # Max random jitter to break ties


def get_priority_score(proposition: str) -> int:
    """Return a priority score for a proposition; higher score = more valuable to query.

    Propositions whose prefix appears earlier in _QUERY_PRIORITY get a higher
    score. Propositions that don't match any prefix get 0.
    """
    for index, prefix in enumerate(_QUERY_PRIORITY):
        if proposition.startswith(prefix):
            # Earlier in list -> higher score (we use length - index so first = highest).
            return len(_QUERY_PRIORITY) - index
    return 0


# --- Search-based query planning (beam search with softer heuristics) ---


def _is_goal_state(kb: Dict[str, bool]) -> bool:
    """Check if the goal state is reached: culprit, weapon, and room are identified.

    Goal requires:
    1. At least one positive Culprit proposition (not negated)
    2. At least one MurderLocation proposition
    3. At least one Weapon proposition

    Args:
        kb: Current knowledge base (dict of proposition -> True).

    Returns:
        True if all three elements (culprit, weapon, room) are identified.
    """
    has_culprit = any(
        prop.startswith("Culprit_") and not prop.startswith("NOT_Culprit_")
        for prop in kb
    )
    has_murder_location = any(
        prop.startswith("MurderLocation_") for prop in kb
    )
    has_weapon = any(
        prop.startswith("Weapon_") for prop in kb
    )
    return has_culprit and has_murder_location and has_weapon


def _heuristic_value(
    kb: Dict[str, bool],
    witness_knowledge: Dict[str, bool],
) -> float:
    """Estimate the value of the current KB state.

    Prioritizes states that make progress toward identifying culprit, weapon, and room.
    The heuristic:
    1. Rewards states closer to goal (has culprit/weapon/room)
    2. Prioritizes remaining queries that help identify the three goal elements
    3. Adds small random jitter to break ties

    Args:
        kb: Current knowledge base (dict of proposition -> True).
        witness_knowledge: Dict of proposition -> bool (all available facts).

    Returns:
        Heuristic value (higher is better).
    """
    # Check progress toward goal
    has_culprit = any(
        prop.startswith("Culprit_") and not prop.startswith("NOT_Culprit_")
        for prop in kb
    )
    has_murder_location = any(
        prop.startswith("MurderLocation_") for prop in kb
    )
    has_weapon = any(
        prop.startswith("Weapon_") for prop in kb
    )

    # Base score: reward progress toward goal
    goal_progress = 0.0
    if has_culprit:
        goal_progress += _HEURISTIC_GOAL_PROGRESS
    if has_murder_location:
        goal_progress += _HEURISTIC_GOAL_PROGRESS
    if has_weapon:
        goal_progress += _HEURISTIC_GOAL_PROGRESS

    # Remaining queries that help identify goal elements get higher weight
    remaining = [
        prop
        for prop in witness_knowledge
        if prop not in kb
    ]

    # Boost priority for queries directly related to goal
    goal_related_score = 0.0
    for prop in remaining:
        base_score = get_priority_score(prop)
        # Extra boost for goal-related queries
        if prop.startswith("Culprit_") and not has_culprit:
            goal_related_score += base_score * _HEURISTIC_GOAL_BOOST
        elif prop.startswith("MurderLocation_") and not has_murder_location:
            goal_related_score += base_score * _HEURISTIC_GOAL_BOOST
        elif prop.startswith("Weapon_") and not has_weapon:
            goal_related_score += base_score * _HEURISTIC_GOAL_BOOST
        else:
            goal_related_score += base_score

    total_score = goal_progress + goal_related_score
    # Small random term to break ties and encourage exploration.
    return float(total_score) + random.random() * _HEURISTIC_TIE_BREAKER_MAX


def beam_search_query_planning(
    initial_kb: Dict[str, bool],
    witness_knowledge: Dict[str, bool],
    query_budget: int,
    beam_width: int = 3,
) -> Tuple[List[str], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Plan a sequence of queries using a simple beam search.

    Goal: Identify culprit, weapon, and room. The search stops early if the goal
    state is reached (all three elements identified).

    Each state is:
        - kb: current knowledge base (dict of proposition -> True)
        - queries: list of propositions we have chosen to "ask"
        - observations: list of {action, result} for each query

    The search keeps the top `beam_width` states at each depth, ranked by a
    heuristic that prioritizes progress toward identifying culprit, weapon, and room.
    This makes the module closer to the proposal's "informed search" while staying
    lightweight.

    Args:
        initial_kb: Starting knowledge base from module 1.
        witness_knowledge: Dict of proposition -> bool (all available facts to query).
        query_budget: Maximum number of queries to plan.
        beam_width: How many states to keep at each search step.

    Returns:
        (query_plan, observations, search_trace)
        - query_plan: list of proposition names queried in the best state.
        - observations: list of {action, result} entries for that plan.
        - search_trace: coarse trace of expanded states and heuristic values.
    """
    if query_budget <= 0 or not witness_knowledge:
        return [], [], []

    # Check if initial state already satisfies goal
    if _is_goal_state(initial_kb):
        search_trace: List[Dict[str, Any]] = [
            {
                "step": 0,
                "num_candidates": 0,
                "beam_heuristics": [],
                "beam_queries": [],
                "goal_reached": True,
            }
        ]
        return [], [], search_trace

    # Each element in the beam: (kb, queries, observations)
    beam: List[Tuple[Dict[str, bool], List[str], List[Dict[str, Any]]]] = [
        (dict(initial_kb), [], [])
    ]
    search_trace = []

    for step in range(query_budget):
        candidates: List[Tuple[float, Dict[str, bool], List[str], List[Dict[str, Any]]]] = []

        for kb, queries, observations in beam:
            # Check if this state already satisfies goal
            if _is_goal_state(kb):
                # Found goal state - return early
                search_trace.append(
                    {
                        "step": step,
                        "num_candidates": 0,
                        "beam_heuristics": [],
                        "beam_queries": [queries],
                        "goal_reached": True,
                    }
                )
                return queries, observations, search_trace

            # Available actions are propositions not yet in KB.
            available = [
                prop
                for prop in witness_knowledge
                if prop not in kb
            ]
            if not available:
                continue

            for prop in available:
                new_kb = dict(kb)
                value = witness_knowledge.get(prop)
                if value is True:
                    new_kb[prop] = True
                elif value is False:
                    # For some predicates, a False answer is itself useful knowledge
                    # represented as a positive NOT_ fact in the KB.
                    if prop.startswith("KeyFound_") or prop.startswith("At_"):
                        new_kb[f"NOT_{prop}"] = True
                new_queries = queries + [prop]
                new_observations = observations + [
                    {"action": prop, "result": value}
                ]
                h = _heuristic_value(new_kb, witness_knowledge)
                candidates.append((h, new_kb, new_queries, new_observations))

        if not candidates:
            break

        # Sort by heuristic descending (higher is better) and keep the top beam_width.
        candidates.sort(key=lambda item: item[0], reverse=True)
        top = candidates[:beam_width]

        # Check if any top candidate satisfies goal
        goal_reached = False
        for _, kb, _, _ in top:
            if _is_goal_state(kb):
                goal_reached = True
                break

        # Record a coarse trace for inspection.
        search_trace.append(
            {
                "step": step,
                "num_candidates": len(candidates),
                "beam_heuristics": [h for h, _, _, _ in top],
                "beam_queries": [q for _, _, q, _ in top],
                "goal_reached": goal_reached,
            }
        )

        # If goal reached, return the best goal state
        if goal_reached:
            for _, kb, queries, observations in top:
                if _is_goal_state(kb):
                    return queries, observations, search_trace

        beam = [(kb, qs, obs) for _, kb, qs, obs in top]

    if not beam:
        return [], [], search_trace

    # Take the best state from the final beam.
    best_kb, best_queries, best_observations = beam[0]
    return best_queries, best_observations, search_trace


def write_search_outputs(
    query_plan: List[str],
    observations: List[Dict[str, Any]],
    search_trace: List[Dict[str, Any]],
    output_dir: str | Path,
) -> None:
    """Write query plan, observations, and search trace to disk.

    This matches the proposal's suggested outputs at a lightweight level:
        - query_plan.json
        - observations.json
        - search_trace.txt
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(out_dir / "query_plan.json", "w", encoding="utf-8") as f:
        json.dump({"actions": query_plan}, f, indent=2)

    with open(out_dir / "observations.json", "w", encoding="utf-8") as f:
        json.dump({"observations": observations}, f, indent=2)

    with open(out_dir / "search_trace.txt", "w", encoding="utf-8") as f:
        f.write("Beam search trace (Module 2)\n")
        f.write("Goal: Identify culprit, weapon, and room\n")
        f.write("=" * 40 + "\n")
        for entry in search_trace:
            f.write(
                f"\nStep {entry['step']} "
                f"(candidates={entry['num_candidates']}):\n"
            )
            f.write(f"  heuristics: {entry['beam_heuristics']}\n")
            f.write(f"  queries: {entry['beam_queries']}\n")
            if entry.get("goal_reached"):
                f.write("  *** GOAL REACHED: Culprit, weapon, and room identified! ***\n")


def _summarize_hypotheses(
    kb: Dict[str, bool],
    game_constraints: dict,
) -> Dict[str, Any]:
    """Build a lightweight summary over culprit/weapon/room hypotheses.

    This does not try to be a full probability model; instead it:
    - Enumerates all (suspect, weapon, room) triples that are not trivially
      inconsistent with what we currently know.
    - Scores each triple by counting supporting facts in the KB
      (At_, Weapon_, VictimFound_, BloodStains_, Fingerprints_).
    - Aggregates scores into per-suspect / per-weapon / per-room tallies.
    """
    suspects: list[str] = list(game_constraints.get("suspects", []))
    weapons: list[str] = list(game_constraints.get("weapons", []))
    rooms: list[str] = list(game_constraints.get("rooms", []))

    if not suspects or not weapons or not rooms:
        return {}

    # Known elements inferred so far (if any).
    known_culprits: set[str] = set()
    for prop in kb:
        if prop.startswith("Culprit_") and not prop.startswith("NOT_Culprit_") and kb.get(prop) is True:
            parts = prop.split("_")
            if len(parts) >= 3:
                known_culprits.add(parts[1])

    known_murder_rooms: set[str] = set(
        r for r in rooms if kb.get(f"MurderLocation_{r}") is True
    )

    body_rooms: set[str] = set(
        r for r in rooms if kb.get(f"VictimFound_{r}") is True
    )

    # Candidate sets fall back to full domains when we don't know yet.
    culprit_candidates = list(known_culprits or suspects)
    room_candidates = list(known_murder_rooms or body_rooms or rooms)

    def _support_for(triple: tuple[str, str, str]) -> int:
        s, w, r = triple
        score = 0
        # Being at the room at any time is strong evidence.
        for prop in kb:
            if prop.startswith(f"At_{s}_{r}_") and kb.get(prop) is True:
                score += 2
        # Murder weapon suspected to be where it appears in Weapon_ facts.
        if kb.get(f"Weapon_{w}_{r}") is True:
            score += 2
        # Body and bloodstains in the room.
        if kb.get(f"VictimFound_{r}") is True:
            score += 1
        if kb.get(f"BloodStains_{r}") is True:
            score += 1
        # Fingerprints in the room for that suspect.
        if kb.get(f"Fingerprints_{r}_{s}") is True:
            score += 1
        return score

    hypotheses: list[dict] = []
    for s in culprit_candidates:
        for w in weapons:
            for r in room_candidates:
                support = _support_for((s, w, r))
                hypotheses.append(
                    {
                        "culprit": s,
                        "weapon": w,
                        "room": r,
                        "support": support,
                    }
                )

    # Sort by support descending and keep top few.
    hypotheses.sort(key=lambda h: h["support"], reverse=True)
    top_hypotheses = hypotheses[:10]

    culprit_scores: Dict[str, float] = {}
    weapon_scores: Dict[str, float] = {}
    room_scores: Dict[str, float] = {}
    for h in hypotheses:
        culprit_scores[h["culprit"]] = culprit_scores.get(h["culprit"], 0.0) + h["support"]
        weapon_scores[h["weapon"]] = weapon_scores.get(h["weapon"], 0.0) + h["support"]
        room_scores[h["room"]] = room_scores.get(h["room"], 0.0) + h["support"]

    def _best_key(scores: Dict[str, float]) -> str | None:
        if not scores:
            return None
        return max(scores.items(), key=lambda item: item[1])[0]

    best_guess = {
        "culprit": _best_key(culprit_scores),
        "weapon": _best_key(weapon_scores),
        "room": _best_key(room_scores),
    }

    return {
        "hypotheses": top_hypotheses,
        "culprit_scores": culprit_scores,
        "weapon_scores": weapon_scores,
        "room_scores": room_scores,
        "best_guess": best_guess,
    }


def _write_hypothesis_summary(
    output_dir: str | Path,
    summary: Dict[str, Any],
    query_plan: List[str],
    observations: List[Dict[str, Any]],
) -> None:
    """Persist hypothesis summary for downstream modules (e.g., Module 3)."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": summary,
        "query_plan": query_plan,
        "observations": observations,
    }
    with open(out_dir / "hypothesis_summary.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _default_rules_path() -> Path | None:
    """Best-effort default path to rules.json for this project."""
    # src/module_2.py -> repo root is parent of src/
    root = Path(__file__).resolve().parent.parent
    candidate = root / "integration_tests" / "module_1" / "rules.json"
    return candidate if candidate.exists() else None


def _write_updated_evidence_file(
    evidence_path: Path,
    base_data: dict,
    kb: Dict[str, bool],
    observations: List[Dict[str, Any]],
) -> None:
    """Update evidence_found.json in place with learned facts and queries.

    - evidence: adds all True facts in kb (excluding contradiction bookkeeping keys)
    - witness_queries_added: appends {question, value} entries from observations
    """
    evidence_out: dict[str, Any] = dict(base_data)
    evidence_out["evidence"] = {
        k: True
        for k, v in kb.items()
        if v is True and k not in ("CONTRADICTION", "_CONTRADICTION_GROUNDED_RULES")
    }

    existing = evidence_out.get("witness_queries_added", [])
    if not isinstance(existing, list):
        existing = []
    appended = [{"question": o.get("action"), "value": o.get("result")} for o in observations]
    evidence_out["witness_queries_added"] = existing + appended

    with open(evidence_path, "w", encoding="utf-8") as f:
        json.dump(evidence_out, f, indent=2)


def run_search(
    evidence_path: str | Path,
    witness_knowledge: Dict[str, bool],
    query_budget: int,
    output_dir: str | Path,
    beam_width: int = 3,
    rules_path: str | Path | None = None,
    show_case_view: bool = False,
) -> Dict[str, Any]:
    """Entry point: run beam-search-based query planning and write outputs.

    Goal: Identify culprit, weapon, and room. The search prioritizes queries that
    help identify these three elements and stops early when the goal is reached.

    Args:
        evidence_path: Path to evidence_found.json (from module_1 / module_2).
        witness_knowledge: Dict of proposition -> bool (facts we could still ask about).
        query_budget: Maximum number of queries to plan.
        output_dir: Directory where query_plan.json, observations.json, and
            search_trace.txt will be written.
        beam_width: How many states to keep at each search step.

    Returns:
        Dict with keys query_plan, observations, search_trace, goal_reached.
    """
    evidence_path = Path(evidence_path)
    try:
        with open(evidence_path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Evidence file not found: {evidence_path}") from None
    except OSError as e:
        raise OSError(f"Failed to read evidence file {evidence_path}: {e}") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in evidence file {evidence_path}: {e}") from e

    initial_kb = data.get("evidence", {})

    query_plan, observations, search_trace = beam_search_query_planning(
        initial_kb=initial_kb,
        witness_knowledge=witness_knowledge,
        query_budget=query_budget,
        beam_width=beam_width,
    )

    # Build KB after applying observations (add True answers and selected NOT_ facts).
    final_kb = dict(initial_kb)
    for obs in observations:
        action = obs.get("action", "")
        value = obs.get("result")
        if value is True:
            final_kb[action] = True
        elif value is False:
            if action.startswith("KeyFound_") or action.startswith("At_"):
                final_kb[f"NOT_{action}"] = True

    # Optional closure step: re-run Module 1 inference after new evidence arrives,
    # and build a hypothesis summary over culprit/weapon/room.
    hypothesis_summary: Dict[str, Any] | None = None
    effective_rules_path = Path(rules_path) if rules_path is not None else _default_rules_path()
    rules_data: dict | None = None
    if effective_rules_path is not None and effective_rules_path.exists():
        try:
            from src import module_1

            rules_data = module_1.read_rules(effective_rules_path)
            grounded = module_1.ground_all_rules(rules_data["rules"], rules_data["game_constraints"])
            module_1.infer(final_kb, grounded)
            hypothesis_summary = _summarize_hypotheses(final_kb, rules_data.get("game_constraints", {}))
        except Exception:
            # Keep module_2 robust: if closure or summarisation fails, we still return beam-search outputs.
            hypothesis_summary = None

    goal_reached = _is_goal_state(final_kb)

    write_search_outputs(query_plan, observations, search_trace, output_dir)

    # Persist hypothesis summary for downstream modules (if available).
    if hypothesis_summary is not None:
        try:
            _write_hypothesis_summary(output_dir, hypothesis_summary, query_plan, observations)
        except Exception:
            pass

    # Update evidence_found.json in place so downstream modules can consume enriched KB.
    try:
        _write_updated_evidence_file(evidence_path, data, final_kb, observations)
    except Exception:
        # Don't fail the search run if persistence fails.
        pass

    if show_case_view and rules_path is not None:
        from src.case_viewer import (
            get_solution_from_evidence,
            get_solution_from_metadata,
            show_case_view as show_view,
        )
        rules_path = Path(rules_path)
        with open(rules_path, encoding="utf-8") as f:
            rules_data = json.load(f)
        gc = rules_data.get("game_constraints", {})
        rooms = gc.get("rooms", [])
        time_points = gc.get("time_points", ["8pm", "9pm", "10pm"])
        solution = get_solution_from_metadata(data.get("metadata", {}))
        if solution.get("culprit") is None:
            solution = get_solution_from_evidence(final_kb)
        extra = [f"Goal reached: {goal_reached}", f"Queries used: {len(query_plan)}"]
        show_view(
            module_id=2,
            title="Module 2 — Query plan & evidence",
            solution=solution,
            evidence=final_kb,
            rooms=rooms,
            time_points=time_points,
            extra_lines=extra,
        )

    return {
        "query_plan": query_plan,
        "observations": observations,
        "search_trace": search_trace,
        "goal_reached": goal_reached,
        "hypothesis_summary": hypothesis_summary,
    }

