"""Module 2: Informed search for next best query (witness knowledge selection)."""
# Thomas Corbin and Elliott Chmil
# Written with the help of Cursor Agent

import json
from pathlib import Path

# Priority order for proposition prefixes (higher index = higher priority to query).
# Propositions that drive suspect/culprit inference are prioritized.
_QUERY_PRIORITY = (
    "Alibi_",       # Directly affects NOT_Culprit
    "At_",          # Location; premises for Suspect, HadAccess, UsedWeapon
    "Weapon_",      # Weapon location; premises for HadAccess, Suspect
    "Fingerprints_",  # Implies At_ via R002
    "VictimFound_", "BloodStains_", "NoiseHeard_", "DoorLocked_",
    "KeyFound_", "Culprit_",
)


def _score_proposition(proposition: str) -> int:
    """Return a score for prioritization; higher = more valuable to query."""
    for i, prefix in enumerate(_QUERY_PRIORITY):
        if proposition.startswith(prefix):
            return len(_QUERY_PRIORITY) - i
    return 0


def select_and_add_witness_facts(
    kb: dict,
    witness_knowledge: dict,
    rules_path: str | Path | None = None,
    n: int = 5,
) -> list[str]:
    """Decide which n facts from witness_knowledge to query, add them to kb, return the chosen list.

    Uses a heuristic based on rules.json proposition types: prioritizes facts that
    drive suspect/culprit inference (Alibi, At_, Weapon, Fingerprints, etc.).
    Only propositions with value True are added to the KB (KB stores only True).

    Args:
        kb: Knowledge base dict (mutated in place).
        witness_knowledge: Dict of proposition name -> bool (facts not yet in kb).
        rules_path: Optional path to rules.json; used for rule-aware scoring (future).
        n: Number of facts to select (default 5).

    Returns:
        List of the n proposition names that were selected (and added to kb if True).
    """
    if not witness_knowledge or n <= 0:
        return []

    # Score each proposition; higher score = more valuable.
    scored = [(prop, _score_proposition(prop)) for prop in witness_knowledge]
    # Sort by score descending, then by proposition name for tie-breaking.
    scored.sort(key=lambda x: (-x[1], x[0]))

    chosen = [prop for prop, _ in scored[:n]]

    # Add chosen facts to kb (only True values; KB stores only True).
    for prop in chosen:
        if witness_knowledge.get(prop) is True:
            kb[prop] = True

    return chosen


def write_questions_to_evidence(
    evidence_path: str | Path,
    questions: list[str],
    witness_knowledge: dict,
) -> None:
    """Append the questions (and their values) added to the KB into evidence_found.json.

    Reads the existing evidence_found.json, adds a "witness_queries_added" key
    with a list of {question, value} entries, and writes the file back.

    Args:
        evidence_path: Path to evidence_found.json.
        questions: List of proposition names that were queried and added.
        witness_knowledge: Dict mapping proposition -> bool (source of values).
    """
    path = Path(evidence_path)
    data: dict = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    queries_added = [
        {"question": q, "value": witness_knowledge.get(q)}
        for q in questions
    ]
    data["witness_queries_added"] = queries_added
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
