"""Module 2: Informed search for next best query (witness knowledge selection).

This module picks which witness facts to "ask" next and adds them to the
knowledge base. It uses a simple priority list so we ask about the most
useful facts first (e.g. alibis, locations, weapons) for finding suspects.
"""
# Thomas Corbin and Elliott Chmil
# Written with the help of Cursor Agent

import json
from pathlib import Path

# How many witness facts to select when n is not specified (avoids magic number in signature).
DEFAULT_NUM_FACTS_TO_SELECT = 5

# Key written to evidence_found.json for the list of witness queries we added.
_EVIDENCE_KEY_WITNESS_QUERIES = "witness_queries_added"

# Order of proposition prefixes: earlier in the list = higher priority to query.
# We prefer facts that help infer suspects/culprits (alibi, location, weapon, etc.).
_QUERY_PRIORITY = (
    "Alibi_",         # Directly affects NOT_Culprit
    "At_",            # Location; used by Suspect, HadAccess, UsedWeapon rules
    "Weapon_",        # Weapon location; used by HadAccess, Suspect rules
    "Fingerprints_",  # Can imply At_ via rules (e.g. R002)
    "VictimFound_",
    "BloodStains_",
    "NoiseHeard_",
    "DoorLocked_",
    "KeyFound_",
    "Culprit_",
)


# --- Scoring and selection ---


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


def select_and_add_witness_facts(
    kb: dict,
    witness_knowledge: dict,
    rules_path: str | Path | None = None,
    n: int = DEFAULT_NUM_FACTS_TO_SELECT,
) -> list[str]:
    """Choose n facts from witness_knowledge to query, add them to the KB, and return the list.

    Uses a heuristic: we rank facts by type (alibi, location, weapon, etc.) and
    pick the top n. Only propositions with value True are added to the KB
    (same as module_1: KB stores only True).

    Args:
        kb: Knowledge base dict (updated in place).
        witness_knowledge: Dict of proposition name -> bool (facts not yet in kb).
        rules_path: Optional path to rules.json; reserved for future use.
        n: How many facts to select (default 5).

    Returns:
        List of the n proposition names that were selected (and added to kb if True).
    """
    if not witness_knowledge or n <= 0:
        return []

    # Score each proposition; higher score = we want to query it sooner.
    scored_propositions = [
        (proposition, get_priority_score(proposition))
        for proposition in witness_knowledge
    ]
    # Sort by score descending; use proposition name to break ties.
    scored_propositions.sort(key=lambda item: (-item[1], item[0]))

    # Take the top n proposition names.
    selected = [proposition for proposition, _ in scored_propositions[:n]]

    # Add selected facts to the KB only when their value is True (KB stores only True).
    for proposition in selected:
        if witness_knowledge.get(proposition) is True:
            kb[proposition] = True

    return selected


# --- Writing evidence output ---


def write_questions_to_evidence(
    evidence_path: str | Path,
    questions: list[str],
    witness_knowledge: dict,
) -> None:
    """Write the questions we added (and their values) into evidence_found.json.

    Reads the existing file, adds a "witness_queries_added" key with a list of
    {question, value} entries, then writes the file back.

    Args:
        evidence_path: Path to evidence_found.json.
        questions: List of proposition names that were queried and added to the KB.
        witness_knowledge: Dict mapping proposition -> bool (where we get the values).
    """
    path = Path(evidence_path)
    data = {}
    if path.exists():
        try:
            with open(path, encoding="utf-8") as file_handle:
                data = json.load(file_handle)
        except OSError as e:
            raise OSError(f"Failed to read evidence file {path}: {e}") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in evidence file {path}: {e}") from e
        if not isinstance(data, dict):
            raise ValueError(f"evidence file {path} must contain a JSON object (dict), got {type(data).__name__}")

    # Build the list of {question, value} for each selected question.
    queries_added = [
        {"question": question, "value": witness_knowledge.get(question)}
        for question in questions
    ]
    data[_EVIDENCE_KEY_WITNESS_QUERIES] = queries_added

    try:
        with open(path, "w", encoding="utf-8") as file_handle:
            json.dump(data, file_handle, indent=2)
    except OSError as e:
        raise OSError(f"Failed to write evidence file {path}: {e}") from e
