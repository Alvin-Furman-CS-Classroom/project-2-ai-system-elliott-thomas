"""Module 4: Basic hypothesis generator over culprit/weapon/room/time.

This is an initial "optimization-lite" module intended to feed later modules
(Advanced Search / RL) with a ranked set of candidate hypotheses.

Inputs:
- `kb_fol.json` produced by Module 3
- `inferred_facts.json` produced by Module 3

Outputs:
- `hypotheses_ranked.json`
- `optimization_log.txt`
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


def _load_json(path: str | Path) -> dict:
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _index_fol_entries(fol_propositions: list[dict]) -> tuple[dict, dict]:
    """Index FOL entries by predicate and negation.

    Returns:
        (pos_index, neg_index)
        where each index is: predicate -> args_tuple -> propositional_string
    """
    pos_index: dict[str, dict[tuple[str, ...], str]] = {}
    neg_index: dict[str, dict[tuple[str, ...], str]] = {}
    for fol in fol_propositions:
        pred = fol.get("predicate")
        if not pred:
            continue
        args = fol.get("args", [])
        args_key = tuple(str(a) for a in args)
        propositional = fol.get("propositional", pred)
        negated = bool(fol.get("negated"))
        target = neg_index if negated else pos_index
        target.setdefault(pred, {})[args_key] = propositional
    return pos_index, neg_index


def _index_inferred_facts(inferred_facts: list[dict]) -> set[tuple[str, tuple[str, ...]]]:
    inferred_keys: set[tuple[str, tuple[str, ...]]] = set()
    for entry in inferred_facts:
        fact = entry.get("fact", {})
        pred = fact.get("predicate")
        args = fact.get("args", [])
        if not pred:
            continue
        inferred_keys.add((str(pred), tuple(str(a) for a in args)))
    return inferred_keys


def _extract_unique_args(fol_propositions: list[dict], predicate: str, arg_idx: int) -> set[str]:
    out: set[str] = set()
    for fol in fol_propositions:
        if fol.get("predicate") != predicate:
            continue
        args = fol.get("args", [])
        if arg_idx < 0 or arg_idx >= len(args):
            continue
        out.add(str(args[arg_idx]))
    return out


def _extract_time_candidates_from_at(fol_propositions: list[dict]) -> set[str]:
    times: set[str] = set()
    for fol in fol_propositions:
        if fol.get("predicate") != "At":
            continue
        args = fol.get("args", [])
        if len(args) != 3:
            continue
        t = str(args[2])
        # Module 3 sometimes uses the literal "TIME" string as a wildcard.
        # Hypothesis time should come from the actual discrete time points.
        if t != "TIME":
            times.add(t)
    return times


def _extract_likely_constants(
    pos_index: dict,
) -> tuple[set[str], set[str], set[str]]:
    likely_culprits = set(pos_index.get("LikelyCulprit", {}).keys())
    likely_weapons = set(pos_index.get("LikelyWeapon", {}).keys())
    likely_rooms = set(pos_index.get("LikelyRoom", {}).keys())

    def _args0(keys: set[tuple[str, ...]]) -> set[str]:
        out: set[str] = set()
        for k in keys:
            if len(k) >= 1:
                out.add(k[0])
        return out

    return _args0(likely_culprits), _args0(likely_weapons), _args0(likely_rooms)


def _add_support(support: list[str], items: Iterable[str]) -> None:
    for it in items:
        if it and it not in support:
            support.append(it)


def _score_hypothesis(
    hyp: dict[str, str],
    pos_index: dict,
    neg_index: dict,
    inferred_keys: set[tuple[str, tuple[str, ...]]],
    likely_culprits: set[str],
    likely_weapons: set[str],
    likely_rooms: set[str],
    has_contradiction: bool,
) -> tuple[float, list[str]]:
    culprit = hyp["culprit"]
    weapon = hyp["weapon"]
    room = hyp["room"]
    time = hyp["time"]

    # If KB itself has a contradiction, penalize everything heavily.
    if has_contradiction:
        return (-1000.0, ["CONTRADICTION in KB"])

    score = 0.0
    support: list[str] = []

    # Soft preferences from Module 2 hypothesis summary.
    if culprit in likely_culprits:
        score += 50.0
        _add_support(support, [pos_index.get("LikelyCulprit", {}).get((culprit,))])
    if weapon in likely_weapons:
        score += 50.0
        _add_support(support, [pos_index.get("LikelyWeapon", {}).get((weapon,))])
    if room in likely_rooms:
        score += 50.0
        _add_support(support, [pos_index.get("LikelyRoom", {}).get((room,))])

    # Hard contradictions from NOT_ facts.
    if neg_index.get("At", {}).get((culprit, room, time)):
        return (-100.0, ["NOT At(con, room, time) in KB"])
    if neg_index.get("Culprit", {}).get((culprit, time)):
        return (-100.0, ["NOT Culprit(person, time) in KB"])
    # If Alibi is explicitly present, the person cannot be the culprit at that time.
    # (Even if NOT_Culprit hasn't been derived/recorded yet.)
    if pos_index.get("Alibi", {}).get((culprit, time)):
        return (-75.0, ["Alibi(person, time) in KB"])

    # Positive matches.
    at_key = (culprit, room, time)
    if pos_index.get("At", {}).get(at_key):
        score += 30.0
        _add_support(support, [pos_index["At"][at_key]])

    weap_key = (weapon, room)
    if pos_index.get("Weapon", {}).get(weap_key):
        score += 30.0
        _add_support(support, [pos_index["Weapon"][weap_key]])

    # MurderLocation may be absent in some runs; VictimFound can still be informative.
    if pos_index.get("BodyDraggedFrom", {}).get((room,)):
        score += 40.0
        _add_support(support, [pos_index["BodyDraggedFrom"][(room,)]])
    elif pos_index.get("MurderLocation", {}).get((room,)):
        score += 30.0
        _add_support(support, [pos_index["MurderLocation"][(room,)]])
    elif pos_index.get("VictimFound", {}).get((room,)):
        # Body discovery room is partially fixed in Module 1, so treat it as weaker evidence.
        score += 5.0
        _add_support(support, [pos_index["VictimFound"][(room,)]])

    # Positive Culprit is usually absent (culprit hidden), but handle it if inferred.
    if pos_index.get("Culprit", {}).get((culprit, time)):
        score += 30.0
        _add_support(support, [pos_index["Culprit"][(culprit, time)]])

    # Light use of inferred facts (proof-carrying) for additional score.
    # Module 3 inference sometimes uses TIME as a wildcard string.
    inferred_at = (
        ("At", (culprit, room, "TIME")) in inferred_keys
        or ("At", (culprit, room, time)) in inferred_keys
    )
    if inferred_at:
        score += 20.0
        # No stable propositional for inferred facts, so keep support short.
        support.append("Inferred At(culprit, room, time)")

    return (score, support)


def _random_hypothesis(
    rng: random.Random,
    culprits: list[str],
    weapons: list[str],
    rooms: list[str],
    times: list[str],
) -> dict[str, str]:
    return {
        "culprit": rng.choice(culprits),
        "weapon": rng.choice(weapons),
        "room": rng.choice(rooms),
        "time": rng.choice(times),
    }


def _build_initial_population(
    *,
    rng: random.Random,
    population_size: int,
    culprits: list[str],
    weapons: list[str],
    rooms: list[str],
    times: list[str],
) -> list[dict[str, str]]:
    return [
        _random_hypothesis(rng, culprits, weapons, rooms, times)
        for _ in range(max(population_size, 1))
    ]


def _tournament_select(
    rng: random.Random,
    scored_population: list[dict[str, Any]],
    tournament_size: int = 3,
) -> dict[str, str]:
    k = min(max(tournament_size, 1), len(scored_population))
    competitors = rng.sample(scored_population, k=k)
    competitors.sort(key=lambda p: float(p["score"]), reverse=True)
    return dict(competitors[0]["hypothesis"])


def _crossover(
    rng: random.Random,
    parent_a: dict[str, str],
    parent_b: dict[str, str],
    crossover_rate: float,
) -> dict[str, str]:
    if rng.random() >= crossover_rate:
        return dict(parent_a)
    child: dict[str, str] = {}
    for gene in ["culprit", "weapon", "room", "time"]:
        child[gene] = parent_a[gene] if rng.random() < 0.5 else parent_b[gene]
    return child


def _mutate(
    rng: random.Random,
    hyp: dict[str, str],
    mutation_rate: float,
    culprits: list[str],
    weapons: list[str],
    rooms: list[str],
    times: list[str],
) -> dict[str, str]:
    out = dict(hyp)
    if rng.random() < mutation_rate:
        out["culprit"] = rng.choice(culprits)
    if rng.random() < mutation_rate:
        out["weapon"] = rng.choice(weapons)
    if rng.random() < mutation_rate:
        out["room"] = rng.choice(rooms)
    if rng.random() < mutation_rate:
        out["time"] = rng.choice(times)
    return out


def _evaluate_population(
    *,
    population: list[dict[str, str]],
    pos_index: dict,
    neg_index: dict,
    inferred_keys: set[tuple[str, tuple[str, ...]]],
    likely_culprits: set[str],
    likely_weapons: set[str],
    likely_rooms: set[str],
    has_contradiction: bool,
) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for hyp in population:
        score, support = _score_hypothesis(
            hyp=hyp,
            pos_index=pos_index,
            neg_index=neg_index,
            inferred_keys=inferred_keys,
            likely_culprits=likely_culprits,
            likely_weapons=likely_weapons,
            likely_rooms=likely_rooms,
            has_contradiction=has_contradiction,
        )
        scored.append({"hypothesis": hyp, "score": score, "supporting_facts": support})
    scored.sort(key=lambda p: float(p["score"]), reverse=True)
    return scored


def run(
    kb_fol_path: str | Path,
    inferred_facts_path: str | Path,
    output_dir: str | Path,
    hypothesis_schema_path: str | Path | None = None,
    scoring_rules_path: str | Path | None = None,
    top_k: int = 3,
    population_size: int = 64,
    generations: int = 40,
    mutation_rate: float = 0.15,
    crossover_rate: float = 0.8,
    elitism_count: int = 4,
    random_seed: int | None = None,
) -> Dict[str, Any]:
    """Run Module 4 and write `hypotheses_ranked.json` and `optimization_log.txt`."""
    _ = hypothesis_schema_path  # Reserved for future expansion (Modules 4/5).
    _ = scoring_rules_path  # Reserved for future expansion.

    kb_fol_path = Path(kb_fol_path)
    inferred_facts_path = Path(inferred_facts_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    kb_payload = _load_json(kb_fol_path)
    fol_propositions: list[dict] = kb_payload.get("fol_propositions", [])
    pos_index, neg_index = _index_fol_entries(fol_propositions)

    inferred_payload = _load_json(inferred_facts_path)
    inferred_facts = inferred_payload.get("inferred_facts", [])
    inferred_keys = _index_inferred_facts(inferred_facts)

    has_contradiction = bool(pos_index.get("CONTRADICTION"))

    likely_culprits, likely_weapons, likely_rooms = _extract_likely_constants(pos_index)

    # Candidate sets derived from what's present.
    culprits = _extract_unique_args(fol_propositions, "Culprit", 0) or likely_culprits
    rooms = (
        _extract_unique_args(fol_propositions, "At", 1)
        | _extract_unique_args(fol_propositions, "VictimFound", 0)
    )
    weapons = _extract_unique_args(fol_propositions, "Weapon", 0) or likely_weapons
    times = _extract_time_candidates_from_at(fol_propositions)

    # Fallbacks.
    culprits = culprits or likely_culprits or {"MrsWhite"}
    weapons = weapons or likely_weapons or {"Dagger"}
    rooms = rooms or likely_rooms or {"Study"}
    times = times or {"8pm", "9pm", "10pm"}

    culprits_l = sorted(culprits)
    weapons_l = sorted(weapons)
    rooms_l = sorted(rooms)
    times_l = sorted(times)
    rng = random.Random(random_seed)

    population = _build_initial_population(
        rng=rng,
        population_size=population_size,
        culprits=culprits_l,
        weapons=weapons_l,
        rooms=rooms_l,
        times=times_l,
    )

    fitness_progress: list[dict[str, float]] = []
    total_evaluations = 0
    final_scored: list[dict[str, Any]] = []
    for generation_idx in range(max(generations, 1)):
        scored = _evaluate_population(
            population=population,
            pos_index=pos_index,
            neg_index=neg_index,
            inferred_keys=inferred_keys,
            likely_culprits=likely_culprits,
            likely_weapons=likely_weapons,
            likely_rooms=likely_rooms,
            has_contradiction=has_contradiction,
        )
        final_scored = scored
        total_evaluations += len(population)

        best = float(scored[0]["score"])
        avg = sum(float(item["score"]) for item in scored) / max(len(scored), 1)
        fitness_progress.append(
            {"generation": float(generation_idx), "best_score": best, "avg_score": avg}
        )

        elite_count = min(max(elitism_count, 0), len(scored))
        next_population = [
            dict(scored[i]["hypothesis"])
            for i in range(elite_count)
        ]

        while len(next_population) < max(population_size, 1):
            parent_a = _tournament_select(rng, scored)
            parent_b = _tournament_select(rng, scored)
            child = _crossover(rng, parent_a, parent_b, crossover_rate)
            child = _mutate(
                rng,
                child,
                mutation_rate,
                culprits_l,
                weapons_l,
                rooms_l,
                times_l,
            )
            next_population.append(child)
        population = next_population

    hypotheses: list[dict[str, Any]] = [
        {
            **item["hypothesis"],
            "method": "module4_ga_v2",
            "score": item["score"],
            "supporting_facts": item["supporting_facts"],
        }
        for item in final_scored
    ]
    hypotheses.sort(key=lambda h: float(h["score"]), reverse=True)
    ranked = hypotheses[: max(top_k, 1)]

    best_score = ranked[0]["score"] if ranked else None
    payload = {
        "summary": {
            "top_k": top_k,
            "num_candidates": len(final_scored),
            "best_score": best_score,
        },
        "ga_config": {
            "population_size": max(population_size, 1),
            "generations": max(generations, 1),
            "mutation_rate": mutation_rate,
            "crossover_rate": crossover_rate,
            "elitism_count": max(elitism_count, 0),
            "random_seed": random_seed,
        },
        "search_stats": {
            "evaluations": total_evaluations,
            "converged": bool(len(fitness_progress) > 1 and fitness_progress[-1]["best_score"] == fitness_progress[-2]["best_score"]),
        },
        "fitness_progress": fitness_progress,
        "hypotheses_ranked": ranked,
    }

    with open(output_dir / "hypotheses_ranked.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    with open(output_dir / "optimization_log.txt", "w", encoding="utf-8") as f:
        f.write("Module 4 genetic algorithm log\n")
        f.write("=" * 33 + "\n")
        f.write(f"Population size: {max(population_size, 1)}\n")
        f.write(f"Generations: {max(generations, 1)}\n")
        f.write(f"Mutation rate: {mutation_rate}\n")
        f.write(f"Crossover rate: {crossover_rate}\n")
        f.write(f"Elitism count: {max(elitism_count, 0)}\n")
        f.write(f"Candidates per generation: {len(final_scored)}\n")
        f.write(f"Total evaluations: {total_evaluations}\n")
        f.write(f"Top k: {top_k}\n")
        if ranked:
            f.write(f"Best score: {best_score}\n")
            f.write(
                "Best hypothesis: "
                + ", ".join(
                    [
                        f"{h}={ranked[0][h]}"
                        for h in ["culprit", "weapon", "room", "time"]
                    ]
                )
                + "\n"
            )
        f.write("\nBest/avg by generation:\n")
        for row in fitness_progress:
            f.write(
                f"gen={int(row['generation'])} "
                f"best={row['best_score']:.2f} avg={row['avg_score']:.2f}\n"
            )

    return payload

