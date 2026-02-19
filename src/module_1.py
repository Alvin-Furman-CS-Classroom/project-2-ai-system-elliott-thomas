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
import random
from pathlib import Path
from typing import Any

# Placeholder names in rule templates; order matters for substitution (longer first to avoid ROOM matching inside ROOM1)
_PLACEHOLDERS = ("ROOM1", "ROOM2", "PERSON", "ROOM", "TIME", "WEAPON")

_CONTRADICTION_KEY = "CONTRADICTION"
_CONTRADICTION_GROUNDED_RULES_KEY = "_CONTRADICTION_GROUNDED_RULES"  # List of full grounded rules that fired CONTRADICTION (id + if + then).

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
    """Load case initial data from a JSON file and split into two equal-sized dicts.

    Reads the evidence dictionary (from "initial_evidence" key), randomly assigns
    each (proposition, value) pair to one of two dicts, and returns both.
    The second dict (witness_knowledge) is not used yet.

    Args:
        path: File path to case_init.json (str or Path).

    Returns:
        dict with keys kb_evidence, witness_knowledge, metadata. kb_evidence and
        witness_knowledge are equal-sized (or differ by one) random splits.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file exists but is not valid JSON or has unexpected structure.
    """
    path = Path(path)
    try:
        with open(path, encoding="utf-8") as file_handle:
            raw = json.load(file_handle)
    except FileNotFoundError:
        raise
    except OSError as e:
        raise OSError(f"Failed to read case_init file {path}: {e}") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in case_init file {path}: {e}") from e

    if not isinstance(raw, dict):
        raise ValueError(f"case_init file {path} must contain a JSON object (dict), got {type(raw).__name__}")

    evidence = raw.get("initial_evidence", raw)
    if not isinstance(evidence, dict):
        evidence = {}
    items = list(evidence.items())
    random.shuffle(items)
    mid = len(items) // 2
    kb_evidence = dict(items[:mid])
    witness_knowledge = dict(items[mid:])
    return {
        "metadata": raw.get("metadata", {}),
        "kb_evidence": kb_evidence,
        "witness_knowledge": witness_knowledge,
    }


def read_rules(path: str | Path) -> dict:
    """Load rules from a JSON file.

    Args:
        path: File path to rules.json (str or Path).

    Returns:
        dict with keys rules (list of {id, if, then}), game_constraints, metadata.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file exists but is not valid JSON or has unexpected structure.
    """
    path = Path(path)
    try:
        with open(path, encoding="utf-8") as file_handle:
            data = json.load(file_handle)
    except FileNotFoundError:
        raise
    except OSError as e:
        raise OSError(f"Failed to read rules file {path}: {e}") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in rules file {path}: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"rules file {path} must contain a JSON object (dict), got {type(data).__name__}")

    return data


# --- Random case generation (Clue-style) ---


def generate_random_case(
    rules_path: str | Path,
    seed: int | None = None,
    kb_ratio: float = 0.5,
    murder_time: str | None = None,
) -> dict:
    """Generate a random Clue case following board game initialization rules.

    Per AIgent Proposal: Module 1 takes case_init.json with initial evidence.
    This function generates such a case randomly:
    1. Randomly selects culprit, weapon, room (the "case file" - hidden solution)
    2. Randomly places weapons in rooms
    3. Randomly assigns people to locations at different times
    4. Generates consistent facts (fingerprints, alibis, etc.)
    5. Randomly splits facts into kb_evidence (known) and witness_knowledge (queryable)

    Args:
        rules_path: Path to rules.json (to get game_constraints).
        seed: Optional random seed for reproducibility.
        kb_ratio: Fraction of facts to put in kb_evidence (rest go to witness_knowledge).
        murder_time: Optional specific time for murder (default: random from time_points).

    Returns:
        dict with keys kb_evidence, witness_knowledge, metadata.
        Same structure as read_case_init() for compatibility.
        Metadata includes _solution_culprit, _solution_weapon, _solution_room.
    """
    if seed is not None:
        random.seed(seed)

    rules = read_rules(rules_path)
    constraints = rules.get("game_constraints", {})
    suspects = constraints.get("suspects", [])
    weapons = constraints.get("weapons", [])
    rooms = constraints.get("rooms", [])
    time_points = constraints.get("time_points", ["8pm", "9pm", "10pm"])

    if not suspects or not weapons or not rooms:
        raise ValueError("game_constraints must include suspects, weapons, and rooms")

    # Step 1: Create the "case file" - randomly select culprit, weapon, room
    culprit = random.choice(suspects)
    weapon = random.choice(weapons)
    room = random.choice(rooms)
    if murder_time is None:
        murder_time = random.choice(time_points)

    # Step 2: Randomly place weapons in rooms (murder weapon goes to murder room)
    weapon_locations: dict[str, str] = {}
    available_rooms = rooms.copy()
    for w in weapons:
        if w == weapon:
            weapon_locations[w] = room  # Murder weapon in murder room
        else:
            if available_rooms:
                loc = random.choice(available_rooms)
                weapon_locations[w] = loc
                # Don't place multiple weapons in same room (optional rule)
                available_rooms.remove(loc)
                if not available_rooms:
                    available_rooms = rooms.copy()

    # Step 3: Generate all possible facts with correct truth values
    all_facts: dict[str, bool] = {}

    # VictimFound: only in murder room
    for r in rooms:
        all_facts[f"VictimFound_{r}"] = r == room

    # BloodStains: only in murder room
    for r in rooms:
        all_facts[f"BloodStains_{r}"] = r == room

    # Weapon locations
    for w, r in weapon_locations.items():
        for room_option in rooms:
            all_facts[f"Weapon_{w}_{room_option}"] = room_option == r

    # Culprit facts: only true for the actual culprit at murder time
    for s in suspects:
        for t in time_points:
            all_facts[f"Culprit_{s}_{t}"] = s == culprit and t == murder_time
            # Alibi: true if person is NOT the culprit at that time
            all_facts[f"Alibi_{s}_{t}"] = not (s == culprit and t == murder_time)

    # At(person, room, time): randomly assign locations, but ensure consistency
    # Each person is in exactly one room at each time
    person_locations: dict[tuple[str, str], str] = {}
    for person in suspects:
        for time in time_points:
            # Randomly pick a room for this person at this time
            loc = random.choice(rooms)
            person_locations[(person, time)] = loc
            for r in rooms:
                all_facts[f"At_{person}_{r}_{time}"] = r == loc

    # Fingerprints: if person was in room, they might have left fingerprints
    # (random chance, but higher if they were actually there)
    for person in suspects:
        for r in rooms:
            # Check if person was ever in this room
            was_there = any(
                person_locations.get((person, t)) == r for t in time_points
            )
            # Higher probability if they were there, but not guaranteed
            all_facts[f"Fingerprints_{r}_{person}"] = was_there and random.random() > 0.3

    # DoorLocked: random, but more likely in murder room at murder time
    for r in rooms:
        for t in time_points:
            if r == room and t == murder_time:
                all_facts[f"DoorLocked_{r}_{t}"] = random.random() > 0.2  # 80% chance
            else:
                all_facts[f"DoorLocked_{r}_{t}"] = random.random() > 0.7  # 30% chance

    # NoiseHeard: more likely in murder room at murder time
    for r in rooms:
        for t in time_points:
            if r == room and t == murder_time:
                all_facts[f"NoiseHeard_{r}_{t}"] = random.random() > 0.3  # 70% chance
            else:
                all_facts[f"NoiseHeard_{r}_{t}"] = random.random() > 0.8  # 20% chance

    # KeyFound: random
    for r in rooms:
        all_facts[f"KeyFound_{r}"] = random.random() > 0.8  # 20% chance

    # Step 4: Remove case file facts (culprit, weapon, room) - these are hidden
    # Remove all Culprit facts (they reveal the solution)
    case_file_facts = {
        k for k in all_facts.keys() if k.startswith("Culprit_")
    }

    # Step 5: Randomly split remaining facts into kb_evidence and witness_knowledge
    queryable_facts = {
        k: v for k, v in all_facts.items() if k not in case_file_facts
    }
    fact_items = list(queryable_facts.items())
    random.shuffle(fact_items)

    kb_size = int(len(fact_items) * kb_ratio)
    kb_evidence = dict(fact_items[:kb_size])
    witness_knowledge = dict(fact_items[kb_size:])

    return {
        "kb_evidence": kb_evidence,
        "witness_knowledge": witness_knowledge,
        "metadata": {
            "case_id": f"RANDOM_CASE_{random.randint(1000, 9999)}",
            "timestamp": "2024-01-15T21:00:00Z",
            "investigator": "Detective_AI",
            "generated": True,
            "_solution_culprit": culprit,
            "_solution_weapon": weapon,
            "_solution_room": room,
            "_solution_time": murder_time,
            "_solution_note": "Reference only - modules do not use these fields. For manual verification after system runs.",
        },
    }


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
        if _CONTRADICTION_GROUNDED_RULES_KEY not in kb:
            kb[_CONTRADICTION_GROUNDED_RULES_KEY] = []
        # Store a copy of the grounded rule (id + concrete if/then with person, time, place, etc.).
        kb[_CONTRADICTION_GROUNDED_RULES_KEY].append({
            "id": grounded_rule.get("id", "?"),
            "if": list(grounded_rule["if"]),
            "then": grounded_rule["then"],
        })
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
                    # Keep going this pass so we record every contradiction rule that fires.
                    pass
        if not changed:
            break  # No rule fired this pass; we're done.
        if has_contradiction(kb):
            break  # Contradiction found; stop after this pass (report will list all that fired).


def has_contradiction(kb: dict) -> bool:
    """Return True if we have inferred that a contradiction occurred.

    KB stores only True; CONTRADICTION is stored as kb["CONTRADICTION"] = True
    when a contradiction rule fires. Return True if that key is present.
    """
    return kb.get(_CONTRADICTION_KEY) is True  # Set by apply_rule when a contradiction rule fires.


# --- Entry point ---


def run_random_case(
    rules_path: str | Path,
    output_dir: str | Path,
    seed: int | None = None,
    kb_ratio: float = 0.5,
    murder_time: str | None = None,
) -> dict:
    """Generate a random case and run Module 1 pipeline on it.

    Convenience function that combines generate_random_case() and run() logic.
    Useful for testing and exploration with varied cases.

    Args:
        rules_path: Path to rules.json.
        output_dir: Directory where evidence_found.json and questionable_evidence_report.txt
            will be written.
        seed: Optional random seed for reproducibility.
        kb_ratio: Fraction of facts to put in kb_evidence.
        murder_time: Optional specific time for murder.

    Returns:
        dict with case data (kb_evidence, witness_knowledge, metadata) and solution info.
    """
    case = generate_random_case(rules_path, seed=seed, kb_ratio=kb_ratio, murder_time=murder_time)
    rules = read_rules(rules_path)
    kb = build_kb(case["kb_evidence"])
    all_rules = ground_all_rules(rules["rules"], rules["game_constraints"])
    infer(kb, all_rules)

    # Write outputs
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = output_dir / "evidence_found.json"
    report_path = output_dir / "questionable_evidence_report.txt"

    # Write evidence_found.json
    evidence_dict: dict[str, Any] = {"evidence": {}, "metadata": case["metadata"]}
    for proposition_name in kb:
        if proposition_name not in (_CONTRADICTION_KEY, _CONTRADICTION_GROUNDED_RULES_KEY):
            evidence_dict["evidence"][proposition_name] = True

    with open(evidence_path, "w", encoding="utf-8") as f:
        json.dump(evidence_dict, f, indent=2)

    # Write questionable_evidence_report.txt
    has_contradiction_flag = has_contradiction(kb)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("Questionable Evidence Report\n")
        f.write("=" * 25 + "\n\n")
        f.write(f"Contradiction detected: {has_contradiction_flag}\n")
        true_props = [p for p in kb if p not in (_CONTRADICTION_KEY, _CONTRADICTION_GROUNDED_RULES_KEY)]
        f.write(f"Total propositions (true): {len(true_props)}\n")
        if has_contradiction_flag:
            f.write("\nGrounded rules that produced a contradiction:\n")
            for gr in kb.get(_CONTRADICTION_GROUNDED_RULES_KEY, []):
                rule_id = gr.get("id", "?")
                premises = gr.get("if", [])
                f.write(f"  - {rule_id}: Contradiction: Person cannot have alibi \n")
                f.write(f"    and be culprit at same time\n")
                f.write(f"    Grounded premises: {premises}\n")

    return case


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
    kb = build_kb(case["kb_evidence"])
    all_rules = ground_all_rules(rules["rules"], rules["game_constraints"])
    infer(kb, all_rules)
    contradiction_found = has_contradiction(kb)

    # Write outputs next to case_init (in output_test_files subdir).
    out_dir = Path(case_init_path).parent
    output_subdir = out_dir / "output_test_files"
    output_subdir.mkdir(parents=True, exist_ok=True)  # Create dir if it doesn't exist.
    evidence_path = output_subdir / "evidence_found.json"
    report_path = output_subdir / "questionable_evidence_report.txt"

    # KB may contain CONTRADICTION and _CONTRADICTION_GROUNDED_RULES; exclude from evidence output.
    evidence_propositions = {
        proposition_name: True
        for proposition_name in kb
        if proposition_name not in (_CONTRADICTION_KEY, _CONTRADICTION_GROUNDED_RULES_KEY)
    }
    with open(evidence_path, "w", encoding="utf-8") as evidence_file:
        json.dump({"evidence": evidence_propositions, "metadata": case.get("metadata", {})}, evidence_file, indent=2)

    # Build id -> description map from rules for the report.
    rule_id_to_description = {r["id"]: r.get("description", "") for r in rules["rules"]}

    with open(report_path, "w", encoding="utf-8") as report_file:
        report_file.write("Questionable Evidence Report\n")
        report_file.write("==========================\n\n")
        report_file.write(f"Contradiction detected: {contradiction_found}\n")
        report_file.write(f"Total propositions (true): {len(evidence_propositions)}\n")
        if contradiction_found:
            report_file.write("\nGrounded rules that produced a contradiction:\n")
            for gr in kb.get(_CONTRADICTION_GROUNDED_RULES_KEY, []):
                rule_id = gr.get("id", "?")
                description = rule_id_to_description.get(rule_id, "(no description)")
                premises = ", ".join(gr.get("if", []))
                report_file.write(f"  - {rule_id}: {description}\n")
                report_file.write(f"    Grounded premises: {premises}\n")
    return None
