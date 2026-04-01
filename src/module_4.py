"""Module 4: Rank who did it, with what, where, and when.

The module searches over combinations of culprit, weapon, room, and time. It scores each
candidate against Module 3's FOL facts and inferred facts using simple weighted evidence
(and penalties for things like alibis). It usually explores with a genetic algorithm; when
the total number of combinations is small, it scores every combination exactly so the ranking
is deterministic. Results are written for later modules plus a human-readable log.

Inputs:
    - ``kb_fol.json`` from Module 3
    - ``inferred_facts.json`` from Module 3

Outputs:
    - ``hypotheses_ranked.json``
    - ``optimization_log.txt``
"""
# Thomas Corbin and Elliott Chmil
# Written with the help of Cursor Agent

from __future__ import annotations

import json
import itertools
import random
from pathlib import Path
from typing import Any, Dict, Iterable

# --- Scoring and search hyperparameters (avoid magic numbers in `_score_hypothesis`) ---

_LIKELY_PRIOR_WEIGHT = 35.0  # Bonus when a slot matches Module 2 Likely* priors
_GLOBAL_NOT_CULPRIT_PENALTY = 8.0  # Per NOT_Culprit entry in KB for this person
_GLOBAL_ALIBI_PENALTY = 6.0  # Per Alibi fact for this person (soft tie-break)
_EXACT_ENUM_MAX = 50_000  # Above this joint size, skip full enumeration

_SCORE_KB_CONTRADICTION = -1000.0  # KB marked inconsistent; all hypotheses bad
_SCORE_HARD_NOT_AT = -100.0  # Explicit NOT At(culprit, room, time)
_SCORE_HARD_NOT_CULPRIT_TIME = -100.0  # Explicit NOT Culprit(culprit, time)
_SCORE_HARD_ALIBI_TIME = -75.0  # Alibi(culprit, time) rules out culprit at that time
_SCORE_MATCH_AT = 30.0  # Positive At(culprit, room, time)
_SCORE_MATCH_WEAPON = 30.0  # Positive Weapon(weapon, room)
_SCORE_MATCH_CULPRIT = 30.0  # Positive Culprit(culprit, time) if present
_SCORE_BODY_DRAGGED_FROM = 40.0  # Strongest room signal when present
_SCORE_MURDER_LOCATION = 30.0  # MurderLocation(room)
_SCORE_VICTIM_FOUND = 5.0  # Weaker room hint (partially fixed in Module 1)
_SCORE_INFERRED_AT = 20.0  # Module 3 inferred At (possibly with TIME wildcard)


# --- FOL / KB indexing ---


def _load_json(path: str | Path) -> dict:
    """Read a JSON file as UTF-8 and return the top-level object (expected to be a dict)."""
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _index_fol_entries(fol_propositions: list[dict]) -> tuple[dict, dict]:
    """Split all FOL rows into "positive" and "negative" lookup tables for fast scoring.

    For each predicate you get a map from the tuple of arguments to the original proposition
    string (for traceability). Negated literals go in the negative index; everything else in
    the positive one.

    Returns:
        ``(pos_index, neg_index)`` — each maps predicate → (args tuple → propositional string).
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
    """Turn Module 3 proof entries into a set of (predicate, arguments) pairs we can test quickly.

    Used to give a small bonus when inference derived ``At`` (including wildcard time).
    """
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
    """Gather every distinct constant appearing in slot ``arg_idx`` for a given predicate.

    Example: predicate ``At`` with index ``0`` collects all people mentioned in ``At`` facts.
    """
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
    """Collect possible clock times from three-argument ``At`` facts (person, room, time).

    Ignores the placeholder string ``TIME`` because that marks an unknown time in some encodings,
    not a real candidate instant.
    """
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
    """Pull Module 2 "best guess" priors from ``LikelyCulprit``, ``LikelyWeapon``, ``LikelyRoom`` facts.

    Those predicates store single-argument tuples; this flattens them to plain sets of names
    for culprit, weapon, and room so scoring can reward matching hypotheses.
    """
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
    """Add human-readable evidence lines to the running list, without duplicates or blanks."""
    for it in items:
        if it and it not in support:
            support.append(it)


# --- Hypothesis scoring ---


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
    """Judge one full hypothesis: award points for KB and inferred evidence, subtract for conflicts.

    In plain terms: matching ``At``, ``Weapon``, room clues, and Module 2 ``Likely*`` guesses
    increases the score; explicit ``NOT`` facts or an alibi at the chosen time can return a
    strongly negative score so bad candidates sink to the bottom.

    Returns:
        ``(score, supporting_fact_strings)`` — higher is better; large negatives mean "reject."
    """
    culprit = hyp["culprit"]
    weapon = hyp["weapon"]
    room = hyp["room"]
    time = hyp["time"]

    if has_contradiction:
        return (_SCORE_KB_CONTRADICTION, ["CONTRADICTION in KB"])

    score = 0.0
    support: list[str] = []

    # Soft preferences from Module 2 hypothesis summary.
    if culprit in likely_culprits:
        score += _LIKELY_PRIOR_WEIGHT
        _add_support(support, [pos_index.get("LikelyCulprit", {}).get((culprit,))])
    if weapon in likely_weapons:
        score += _LIKELY_PRIOR_WEIGHT
        _add_support(support, [pos_index.get("LikelyWeapon", {}).get((weapon,))])
    if room in likely_rooms:
        score += _LIKELY_PRIOR_WEIGHT
        _add_support(support, [pos_index.get("LikelyRoom", {}).get((room,))])

    # Light global penalties to break ties among culprits that otherwise have
    # similar local support in (room, weapon, time).
    neg_culprit_count = sum(
        1
        for args in neg_index.get("Culprit", {})
        if len(args) >= 1 and args[0] == culprit
    )
    if neg_culprit_count:
        score -= _GLOBAL_NOT_CULPRIT_PENALTY * float(neg_culprit_count)
        support.append(f"Global NOT_Culprit penalty x{neg_culprit_count}")
    alibi_count = sum(
        1
        for args in pos_index.get("Alibi", {})
        if len(args) >= 1 and args[0] == culprit
    )
    if alibi_count:
        score -= _GLOBAL_ALIBI_PENALTY * float(alibi_count)
        support.append(f"Global Alibi penalty x{alibi_count}")

    # Hard contradictions from NOT_ facts.
    if neg_index.get("At", {}).get((culprit, room, time)):
        return (_SCORE_HARD_NOT_AT, ["NOT At(con, room, time) in KB"])
    if neg_index.get("Culprit", {}).get((culprit, time)):
        return (_SCORE_HARD_NOT_CULPRIT_TIME, ["NOT Culprit(person, time) in KB"])
    # If Alibi is explicitly present, the person cannot be the culprit at that time.
    # (Even if NOT_Culprit hasn't been derived/recorded yet.)
    if pos_index.get("Alibi", {}).get((culprit, time)):
        return (_SCORE_HARD_ALIBI_TIME, ["Alibi(person, time) in KB"])

    # Positive matches.
    at_key = (culprit, room, time)
    if pos_index.get("At", {}).get(at_key):
        score += _SCORE_MATCH_AT
        _add_support(support, [pos_index["At"][at_key]])

    weap_key = (weapon, room)
    if pos_index.get("Weapon", {}).get(weap_key):
        score += _SCORE_MATCH_WEAPON
        _add_support(support, [pos_index["Weapon"][weap_key]])

    # MurderLocation may be absent in some runs; VictimFound can still be informative.
    if pos_index.get("BodyDraggedFrom", {}).get((room,)):
        score += _SCORE_BODY_DRAGGED_FROM
        _add_support(support, [pos_index["BodyDraggedFrom"][(room,)]])
    elif pos_index.get("MurderLocation", {}).get((room,)):
        score += _SCORE_MURDER_LOCATION
        _add_support(support, [pos_index["MurderLocation"][(room,)]])
    elif pos_index.get("VictimFound", {}).get((room,)):
        # Body discovery room is partially fixed in Module 1, so treat it as weaker evidence.
        score += _SCORE_VICTIM_FOUND
        _add_support(support, [pos_index["VictimFound"][(room,)]])

    # Positive Culprit is usually absent (culprit hidden), but handle it if inferred.
    if pos_index.get("Culprit", {}).get((culprit, time)):
        score += _SCORE_MATCH_CULPRIT
        _add_support(support, [pos_index["Culprit"][(culprit, time)]])

    # Light use of inferred facts (proof-carrying) for additional score.
    # Module 3 inference sometimes uses TIME as a wildcard string.
    inferred_at = (
        ("At", (culprit, room, "TIME")) in inferred_keys
        or ("At", (culprit, room, time)) in inferred_keys
    )
    if inferred_at:
        score += _SCORE_INFERRED_AT
        # No stable propositional for inferred facts, so keep support short.
        support.append("Inferred At(culprit, room, time)")

    return (score, support)


# --- Genetic algorithm operators ---


def _random_hypothesis(
    rng: random.Random,
    culprits: list[str],
    weapons: list[str],
    rooms: list[str],
    times: list[str],
) -> dict[str, str]:
    """Pick one random culprit, weapon, room, and time—each choice is independent and uniform."""
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
    """Seed the genetic algorithm with many random guesses before evolution begins."""
    return [
        _random_hypothesis(rng, culprits, weapons, rooms, times)
        for _ in range(max(population_size, 1))
    ]


def _tournament_select(
    rng: random.Random,
    scored_population: list[dict[str, Any]],
    tournament_size: int = 3,
) -> dict[str, str]:
    """Parent selection: draw a few individuals at random and keep the one with the best score."""
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
    """Mix two parents: with probability ``crossover_rate``, each field (culprit, weapon, …)
    comes from either parent at random; otherwise the child is a copy of the first parent.
    """
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
    """Randomly perturb a hypothesis: each of culprit, weapon, room, and time may be replaced
    with a fresh random choice, independently, with probability ``mutation_rate``.
    """
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
    """Compute fitness (score + supporting lines) for every hypothesis and sort best to worst.

    Ties break in a fixed lexical order on culprit, weapon, room, time so runs are stable.
    """
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
    scored.sort(
        key=lambda p: (
            -float(p["score"]),
            str(p["hypothesis"]["culprit"]),
            str(p["hypothesis"]["weapon"]),
            str(p["hypothesis"]["room"]),
            str(p["hypothesis"]["time"]),
        )
    )
    return scored


def _evaluate_exhaustive_candidates(
    *,
    culprits: list[str],
    weapons: list[str],
    rooms: list[str],
    times: list[str],
    pos_index: dict,
    neg_index: dict,
    inferred_keys: set[tuple[str, tuple[str, ...]]],
    likely_culprits: set[str],
    likely_weapons: set[str],
    likely_rooms: set[str],
    has_contradiction: bool,
) -> list[dict[str, Any]] | None:
    """If there are not too many combinations, score every (culprit, weapon, room, time) exactly.

    When the product of domain sizes exceeds a cap, return ``None`` so the caller keeps the
    genetic algorithm's approximate ranking instead.
    """
    total = len(culprits) * len(weapons) * len(rooms) * len(times)
    if total <= 0 or total > _EXACT_ENUM_MAX:
        return None

    population = [
        {"culprit": c, "weapon": w, "room": r, "time": t}
        for c, w, r, t in itertools.product(culprits, weapons, rooms, times)
    ]
    return _evaluate_population(
        population=population,
        pos_index=pos_index,
        neg_index=neg_index,
        inferred_keys=inferred_keys,
        likely_culprits=likely_culprits,
        likely_weapons=likely_weapons,
        likely_rooms=likely_rooms,
        has_contradiction=has_contradiction,
    )


# --- Public entry point ---


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
    """Run the full hypothesis-ranking pipeline and save results next to other module outputs.

    Loads structured facts from Module 3, builds searchable domains for each slot, evolves a
    population with selection/crossover/mutation, then—if the full cross product is small—
    replaces the GA output with an exact sort of every candidate. Writes both a JSON bundle
    (configuration, stats, ranked list) and a short text log.

    Args:
        kb_fol_path: Path to `kb_fol.json` (Module 3).
        inferred_facts_path: Path to `inferred_facts.json` (Module 3).
        output_dir: Directory for `hypotheses_ranked.json` and `optimization_log.txt`.
        hypothesis_schema_path: Reserved for future validation hooks.
        scoring_rules_path: Reserved for externalized scoring rules.
        top_k: Number of distinct top hypotheses to keep in output.
        population_size: GA population size.
        generations: Number of GA generations.
        mutation_rate: Per-gene mutation probability.
        crossover_rate: Probability of combining two parents vs cloning one.
        elitism_count: Top individuals copied unchanged each generation.
        random_seed: Seed for reproducible GA sampling (None = non-deterministic).

    Returns:
        Payload dict matching `hypotheses_ranked.json`: summary, ga_config,
        search_stats, fitness_progress, hypotheses_ranked.
    """
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

    # --- Build culprit / weapon / room / time domains (broad unions; Likely* as backstop) ---

    # Candidate sets derived from what's present. Prefer broad, observable domains
    # so we don't accidentally exclude the true answer when "Likely*" is narrow.
    culprits = (
        _extract_unique_args(fol_propositions, "Culprit", 0)
        | _extract_unique_args(fol_propositions, "At", 0)
        | _extract_unique_args(fol_propositions, "Alibi", 0)
        | _extract_unique_args(fol_propositions, "Fingerprints", 1)
    ) or likely_culprits
    rooms = (
        _extract_unique_args(fol_propositions, "At", 1)
        | _extract_unique_args(fol_propositions, "VictimFound", 0)
        | _extract_unique_args(fol_propositions, "BloodStains", 0)
        | _extract_unique_args(fol_propositions, "MurderLocation", 0)
        | _extract_unique_args(fol_propositions, "BodyDraggedFrom", 0)
    )
    weapons = (
        _extract_unique_args(fol_propositions, "Weapon", 0)
        | _extract_unique_args(fol_propositions, "HadAccess", 1)
        | likely_weapons
    ) or {"Dagger"}
    times = (
        _extract_time_candidates_from_at(fol_propositions)
        | _extract_unique_args(fol_propositions, "MurderTime", 0)
    )

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

    # --- Genetic algorithm (may be superseded by exhaustive ranking below) ---

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

    # --- Exact enumeration when |C×W×R×T| is small (deterministic top ranking) ---

    # When the joint search space is reasonably small, evaluate all candidates
    # exactly so ranking quality does not depend on GA sampling luck.
    exhaustive_scored = _evaluate_exhaustive_candidates(
        culprits=culprits_l,
        weapons=weapons_l,
        rooms=rooms_l,
        times=times_l,
        pos_index=pos_index,
        neg_index=neg_index,
        inferred_keys=inferred_keys,
        likely_culprits=likely_culprits,
        likely_weapons=likely_weapons,
        likely_rooms=likely_rooms,
        has_contradiction=has_contradiction,
    )
    if exhaustive_scored is not None:
        final_scored = exhaustive_scored

    # --- Dedup and take top_k for JSON payload ---

    hypotheses: list[dict[str, Any]] = [
        {
            **item["hypothesis"],
            "method": "module4_ga_v2",
            "score": item["score"],
            "supporting_facts": item["supporting_facts"],
        }
        for item in final_scored
    ]
    hypotheses.sort(
        key=lambda h: (
            -float(h["score"]),
            str(h["culprit"]),
            str(h["weapon"]),
            str(h["room"]),
            str(h["time"]),
        )
    )
    # Keep top_k distinct hypotheses; GA may produce duplicates.
    ranked: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for hyp in hypotheses:
        key = (
            str(hyp["culprit"]),
            str(hyp["weapon"]),
            str(hyp["room"]),
            str(hyp["time"]),
        )
        if key in seen:
            continue
        seen.add(key)
        ranked.append(hyp)
        if len(ranked) >= max(top_k, 1):
            break

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

