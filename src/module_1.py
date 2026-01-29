"""Module 1: Propositional logic knowledge base and inference for Detective AI."""
# Thomas Corbin and Elliott Chmil
# Written with the help of Cursor Agent
# 1/29/2026

import itertools
import json
from pathlib import Path

# Placeholder names in rule templates; order matters for substitution (longer first to avoid ROOM matching inside ROOM1)
_PLACEHOLDERS = ("ROOM1", "ROOM2", "PERSON", "ROOM", "TIME", "WEAPON")

# Which key in game_constraints each placeholder uses
_PLACEHOLDER_TO_KEY = {
    "PERSON": "suspects",
    "ROOM": "rooms",
    "ROOM1": "rooms",
    "ROOM2": "rooms",
    "TIME": "time_points",
    "WEAPON": "weapons",
}


# --- Read methods ---


def read_case_init(path: str | Path) -> dict:
    """Load case initial data from a JSON file.

    Args:
        path: File path to case_init.json (str or Path).

    Returns:
        dict with keys initial_evidence (proposition name -> true/false), metadata.
    """
    with open(path, encoding="utf-8") as file_handle:
        return json.load(file_handle)


def read_rules(path: str | Path) -> dict:
    """Load rules from a JSON file.

    Args:
        path: File path to rules.json (str or Path).

    Returns:
        dict with keys rules (list of {id, if, then}), game_constraints, metadata.
    """
    with open(path, encoding="utf-8") as file_handle:
        return json.load(file_handle)


# --- Logic: grounding and inference ---


def ground_rule(rule: dict, game_constraints: dict) -> list[dict]:
    """Turn one rule template into a list of concrete rules.

    The rule dict has keys 'if' and 'then' (same shape as each entry in
    rules.json under the "rules" key, loaded by read_rules). The
    game_constraints dict is the one from rules.json (e.g. rules["game_constraints"]
    from run). It uses placeholders PERSON, ROOM, TIME, etc. (see _PLACEHOLDERS
    and _PLACEHOLDER_TO_KEY at top of file). Replaces those with every allowed
    value from game_constraints so one template becomes many concrete rules.
    """
    # TODO: implement
    return []


def ground_all_rules(rules: list[dict], game_constraints: dict) -> list[dict]:
    """Ground every rule in the rules list.

    The rules list is the one from rules.json (rules["rules"] in run, where
    rules comes from read_rules(rules_path)). game_constraints is
    rules["game_constraints"]. Calls ground_rule (above) for each rule and
    collects all concrete rules into one list for infer (below).
    """
    # TODO: implement
    return []


def build_kb(initial_evidence: dict) -> dict:
    """Build the starting knowledge base from the case's initial evidence.

    The initial_evidence dict is from case_init.json (case["initial_evidence"] in
    run, where case comes from read_case_init(case_init_path)). The returned KB
    is a dict from proposition name to True or False; we copy initial_evidence
    into it. This dict is then passed to infer and may be checked by has_contradiction.
    """
    # TODO: implement
    return {}


def rule_premises_met(grounded_rule: dict, kb: dict) -> bool:
    """Check whether all 'if' conditions of a grounded rule are true in the KB.

    grounded_rule has 'if' and 'then' keys (output of ground_rule). kb is the
    knowledge base dict (from build_kb, updated by apply_rule). A rule can fire
    only when every proposition in grounded_rule["if"] is already in kb with
    value True. Returns True if that is the case.
    """
    # TODO: implement
    return False


def apply_rule(grounded_rule: dict, kb: dict) -> bool:
    """If the rule's premises are met, add its conclusion to the KB.

    grounded_rule and kb same as in rule_premises_met. Uses rule_premises_met to
    check; if every grounded_rule["if"] condition is in kb as True, add
    grounded_rule["then"] to kb. If the conclusion is the literal "CONTRADICTION"
    (as in rules like R011, R012 in rules.json), record it and return True so
    infer can stop. Returns True if something was added or contradiction found,
    False otherwise.
    """
    # TODO: implement
    return False


def infer(kb: dict, grounded_rules: list[dict]) -> None:
    """Repeatedly apply all grounded rules until no new facts are derived.

    kb is the knowledge base from build_kb. grounded_rules is the list from
    ground_all_rules. In a loop, call apply_rule for each grounded rule; when
    a rule adds a fact, that may let other rules fire. Stop when no rule adds
    anything new, or when apply_rule returns True for a CONTRADICTION. Modifies
    kb in place (same dict that has_contradiction can later check).
    """
    # TODO: implement
    pass


def has_contradiction(kb: dict) -> bool:
    """Return True if we have inferred that a contradiction occurred.

    kb is the same dict built by build_kb and updated by infer. In rules.json,
    some rules (e.g. R011, R012) have "then": "CONTRADICTION"; if apply_rule
    fired one of those, that key will be in kb. Return True if so, so run (or
    report writing) can flag it (e.g. in questionable_evidence_report.txt).
    """
    # TODO: implement
    return False


# --- Entry point ---


def run(case_init_path: str | Path, rules_path: str | Path) -> None:
    """Read both inputs for Module 1. (Inference and report writing to be added.)

    Args:
        case_init_path: Path to case_init.json.
        rules_path: Path to rules.json.

    Returns:
        None.
    """
    case = read_case_init(case_init_path)
    rules = read_rules(rules_path)
    # TODO: build KB, infer, check contradictions, write evidence_found.json and questionable_evidence_report.txt
    return None
