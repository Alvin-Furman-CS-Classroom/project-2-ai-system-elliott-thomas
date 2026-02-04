"""Module 1: Propositional logic knowledge base and inference for Detective AI."""
# Thomas Corbin and Elliott Chmil
# Written with the help of Cursor Agent
# 1/29/2026
#
# KB design: the knowledge base stores only TRUE values. A proposition that is
# not in the KB is treated as false; false propositions cannot imply or chain
# to become true.

import itertools
import json
from pathlib import Path

# Placeholder names in rule templates; order matters for substitution (longer first to avoid ROOM matching inside ROOM1)
_PLACEHOLDERS = ("ROOM1", "ROOM2", "PERSON", "ROOM", "TIME", "WEAPON")

_CONTRADICTION_KEY = "CONTRADICTION"

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
        return json.load(file_handle)  # Parse JSON into a Python dict


def read_rules(path: str | Path) -> dict:
    """Load rules from a JSON file.

    Args:
        path: File path to rules.json (str or Path).

    Returns:
        dict with keys rules (list of {id, if, then}), game_constraints, metadata.
    """
    with open(path, encoding="utf-8") as file_handle:
        return json.load(file_handle)  # Same as read_case_init; returns rules + game_constraints


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
    grounded_rules = []
    our_placeholders_set = set()
    # 1) Identify which placeholders (PERSON, ROOM, etc.) appear in this rule.
    for if_statement in rule["if"]:
        current_if_statement = if_statement.split("_")  # e.g. "At_PERSON_ROOM_TIME" -> ["At","PERSON","ROOM","TIME"]
        for placeholder in _PLACEHOLDERS:
            if placeholder in current_if_statement:
                our_placeholders_set.add(placeholder)

    # rule["then"] is a single string, not a list
    then_parts = rule["then"].split("_")
    for placeholder in _PLACEHOLDERS:
        if placeholder in then_parts:
            our_placeholders_set.add(placeholder)

    # Keep _PLACEHOLDERS order so ROOM1 is replaced before ROOM (avoids wrong substitution).
    our_placeholders = [placeholder for placeholder in _PLACEHOLDERS if placeholder in our_placeholders_set]

    # 2) For each placeholder, get the list of allowed values (e.g. suspects, rooms).
    our_placeholder_values = {}
    for our_placeholder in our_placeholders:
        placeholder_key = _PLACEHOLDER_TO_KEY[our_placeholder]
        placeholder_values = game_constraints[placeholder_key]
        our_placeholder_values[our_placeholder] = placeholder_values

    # 3) Cartesian product: each combination picks one value per placeholder (e.g. one person, one room, one time).
    value_lists = [our_placeholder_values[ph] for ph in our_placeholders]
    for combination in itertools.product(*value_lists):
        substitution_map = dict(zip(our_placeholders, combination))  # e.g. {"PERSON":"Alice","ROOM":"Study"}
        # R011-style rules require two different rooms; skip when ROOM1 == ROOM2.
        if "ROOM1" in substitution_map and "ROOM2" in substitution_map and substitution_map["ROOM1"] == substitution_map["ROOM2"]:
            continue
        # 4) Replace every placeholder in each "if" string and in "then" with values from this combination.
        grounded_if = []
        for if_str in rule["if"]:
            current_if_str = if_str
            for placeholder in _PLACEHOLDERS:
                if placeholder in substitution_map:
                    current_if_str = current_if_str.replace(placeholder, substitution_map[placeholder])
            grounded_if.append(current_if_str)
        grounded_then = rule["then"]
        for placeholder in _PLACEHOLDERS:
            if placeholder in substitution_map:
                grounded_then = grounded_then.replace(placeholder, substitution_map[placeholder])
        grounded_rules.append({  # One concrete rule per combination
            "id": rule["id"],
            "if": grounded_if,
            "then": grounded_then,
        })
    return grounded_rules


def ground_all_rules(rules: list[dict], game_constraints: dict) -> list[dict]:
    """Ground every rule in the rules list.

    The rules list is the one from rules.json (rules["rules"] in run, where
    rules comes from read_rules(rules_path)). game_constraints is
    rules["game_constraints"]. Calls ground_rule (above) for each rule and
    collects all concrete rules into one list for infer (below).
    """
    full_grounded_rules = []
    for rule in rules:
        grounded_for_this_rule = ground_rule(rule, game_constraints)
        full_grounded_rules.extend(grounded_for_this_rule)  # Append all concrete rules from this template
    return full_grounded_rules


def build_kb(initial_evidence: dict) -> dict:
    """Build the starting knowledge base from the case's initial evidence.

    The KB stores only TRUE values; absence means false (cannot imply or chain).
    We copy only propositions that are True in initial_evidence into a new dict.
    This dict is then passed to infer and may be checked by has_contradiction.
    """
    # Only store propositions that are True; absence in KB means false.
    return {proposition_name: True for proposition_name, truth_value in initial_evidence.items() if truth_value is True}


_NOT_PREFIX = "NOT_"


def rule_premises_met(grounded_rule: dict, kb: dict) -> bool:
    """Check whether all 'if' conditions of a grounded rule are true in the KB.

    KB stores only True; absence means false. For each premise in grounded_rule["if"]:
    if it starts with NOT_, the rest must be false (absent or not True in kb);
    otherwise the proposition must be in kb (i.e. true). Returns True only if
    all premises are satisfied.
    """
    for premise in grounded_rule["if"]:
        if premise.startswith(_NOT_PREFIX):
            # NOT_X is satisfied only if X is false (absent or not True in KB).
            proposition_name = premise[len(_NOT_PREFIX) :]
            if kb.get(proposition_name) is True:
                return False
        else:
            # Positive premise: must be present and True in KB.
            if kb.get(premise) is not True:
                return False
    return True


def apply_rule(grounded_rule: dict, kb: dict) -> bool:
    """If the rule's premises are met, add its conclusion to the KB.

    KB stores only True. If rule_premises_met is True, add grounded_rule["then"]
    to kb as True (or record CONTRADICTION). Returns True if something was
    added or contradiction found, False otherwise.
    """
    if not rule_premises_met(grounded_rule, kb):
        return False  # Premises not all true; rule does not fire.
    conclusion = grounded_rule["then"]
    if conclusion == _CONTRADICTION_KEY:
        kb[_CONTRADICTION_KEY] = True
        return True  # Contradiction rule fired; infer will stop.
    if kb.get(conclusion) is True:
        return False  # Conclusion already in KB; nothing new added.
    kb[conclusion] = True
    return True  # New fact added.


def infer(kb: dict, grounded_rules: list[dict]) -> None:
    """Repeatedly apply all grounded rules until no new facts are derived.

    kb is the knowledge base from build_kb. grounded_rules is the list from
    ground_all_rules. In a loop, call apply_rule for each grounded rule; when
    a rule adds a fact, that may let other rules fire. Stop when no rule adds
    anything new, or when apply_rule returns True for a CONTRADICTION. Modifies
    kb in place (same dict that has_contradiction can later check).
    """
    # Forward chaining: keep applying rules until no new facts or a contradiction.
    while True:
        changed = False
        for rule in grounded_rules:
            if apply_rule(rule, kb):
                changed = True
                if has_contradiction(kb):
                    return  # Stop immediately on contradiction.
        if not changed:
            break  # No rule fired this pass; we're done.


def has_contradiction(kb: dict) -> bool:
    """Return True if we have inferred that a contradiction occurred.

    KB stores only True; CONTRADICTION is stored as kb["CONTRADICTION"] = True
    when a contradiction rule fires. Return True if that key is present.
    """
    return kb.get(_CONTRADICTION_KEY) is True  # Set by apply_rule when a contradiction rule fires.


# --- Entry point ---


def run(case_init_path: str | Path, rules_path: str | Path) -> None:
    """Read inputs, build KB, run inference, and write evidence_found.json and questionable_evidence_report.txt.

    Output files are written to a subdirectory output_test_files under the same directory as case_init_path.

    Args:
        case_init_path: Path to case_init.json.
        rules_path: Path to rules.json.

    Returns:
        None.
    """
    case = read_case_init(case_init_path)
    rules = read_rules(rules_path)
    kb = build_kb(case["initial_evidence"])
    all_rules = ground_all_rules(rules["rules"], rules["game_constraints"])
    infer(kb, all_rules)
    contradiction_found = has_contradiction(kb)

    # Write outputs next to case_init (in output_test_files subdir).
    out_dir = Path(case_init_path).parent
    output_subdir = out_dir / "output_test_files"
    output_subdir.mkdir(parents=True, exist_ok=True)  # Create dir if it doesn't exist.
    evidence_path = output_subdir / "evidence_found.json"
    report_path = output_subdir / "questionable_evidence_report.txt"

    # KB may contain CONTRADICTION; exclude it from evidence output.
    evidence_propositions = {proposition_name: True for proposition_name in kb if proposition_name != _CONTRADICTION_KEY}
    with open(evidence_path, "w", encoding="utf-8") as evidence_file:
        json.dump({"evidence": evidence_propositions, "metadata": case.get("metadata", {})}, evidence_file, indent=2)

    with open(report_path, "w", encoding="utf-8") as report_file:
        report_file.write("Questionable Evidence Report\n")
        report_file.write("==========================\n\n")
        report_file.write(f"Contradiction detected: {contradiction_found}\n")
        report_file.write(f"Total propositions (true): {len(evidence_propositions)}\n")  # Excludes CONTRADICTION
    return None
