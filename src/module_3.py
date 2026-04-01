"""Module 3: First-Order Logic evidence store and inference.

Turns the game's flat proposition names (like ``At_ColonelMustard_Study_9pm``) into
structured facts (predicate plus arguments), then runs forward chaining: it repeatedly
applies rules from ``rules.json`` to derive any new facts that logically follow,
recording how each new fact was proved. Optional outputs are a full FOL knowledge
base file and an inferred-facts file with proof steps for downstream modules.
"""
# Thomas Corbin and Elliott Chmil
# Written with the help of Cursor Agent

import json
from pathlib import Path

_NOT_PREFIX = "NOT_"
_CONTRADICTION = "CONTRADICTION"
_ROOM1_EQ_ROOM2 = "ROOM1_EQ_ROOM2"


def _fol_fact_key(fol: dict) -> str:
    """Build a single string that uniquely identifies this fact for duplicate checks.

    The key is the predicate followed by every argument, separated by colons, so two
    facts match if and only if they are the same ground atom.
    """
    pred = fol.get("predicate", "")
    args = fol.get("args", [])
    return pred + ":" + ":".join(str(a) for a in args)


def _is_positive_fact(fol: dict) -> bool:
    """Return whether this entry counts as a normal ``true`` fact we can chain from.

    Negative literals (``negated``) and unknown values are not treated as usable premises.
    """
    return fol.get("value") is True and not fol.get("negated")


def _parse_proposition(proposition: str) -> tuple[str, list[str], bool]:
    """Split a Module-1-style proposition string into predicate, arguments, and negation.

    Underscores separate the predicate from its arguments. A leading ``NOT_`` means the
    literal is negated; the returned ``negated`` flag captures that.

    Examples:
        ``At_ColonelMustard_Study_9pm`` → predicate ``At``, args
        ``[ColonelMustard, Study, 9pm]``, not negated.
        ``NOT_Culprit_MissScarlet_9pm`` → predicate ``Culprit``, args ``[MissScarlet, 9pm]``,
        negated.
    """
    negated = proposition.startswith(_NOT_PREFIX)
    if negated:
        proposition = proposition[len(_NOT_PREFIX) :]
    parts = proposition.split("_")
    if not parts:
        return ("", [], negated)
    predicate = parts[0]
    args = parts[1:] if len(parts) > 1 else []
    return (predicate, args, negated)


def _to_fol_form(predicate: str, args: list[str], negated: bool) -> dict:
    """Package a predicate and its argument list into the small dict shape the rest of the module expects.

    Sets ``negated`` only when the literal is negative.
    """
    fol = {"predicate": predicate, "args": args}
    if negated:
        fol["negated"] = True
    return fol


def create_fol_propositions(
    evidence: dict,
    output_path: str | Path | None = None,
) -> list[dict]:
    """Walk every fact in the evidence dictionary and convert it to structured FOL records.

    Each key is a proposition name from earlier modules; each value should be ``True`` for
    known facts. The function attaches ``value`` and the original string as ``propositional``
    so you can trace a row back to the KB. If ``output_path`` is given, the full list is
    also written as JSON (for example ``kb_fol.json``).

    Args:
        evidence: Dict of proposition name -> True (KB facts).
        output_path: Optional path to write FOL propositions as JSON.

    Returns:
        List of FOL proposition dicts: {predicate, args, negated?, value}
    """
    fol_propositions = []
    for prop_name, value in evidence.items():
        predicate, args, negated = _parse_proposition(prop_name)
        fol = _to_fol_form(predicate, args, negated)
        fol["value"] = value
        fol["propositional"] = prop_name  # keep original for traceability
        fol_propositions.append(fol)

    if output_path is not None:
        _write_json({"fol_propositions": fol_propositions}, output_path)

    return fol_propositions


def _parse_rule_template(template: str) -> tuple[str, list[str], bool, bool]:
    """Turn a rule's template string from ``rules.json`` into its logical pieces.

    Templates use underscores: the first token is the predicate name, the rest are
    variable names (placeholders like ``PERSON``) that will later be filled from
    matching facts. The fourth return value marks special inequality constraints
    (``ROOM1`` must differ from ``ROOM2``) rather than ordinary premises.

    Examples:
        ``At_PERSON_ROOM_TIME`` → predicate ``At``, arg names ``[PERSON, ROOM, TIME]``.
        ``NOT_Culprit_PERSON_TIME`` → negated ``Culprit`` with two variables.
        ``NOT_ROOM1_EQ_ROOM2`` → constraint template for two different rooms.
    """
    negated = template.startswith(_NOT_PREFIX)
    if negated:
        template = template[len(_NOT_PREFIX) :]
    if template == _ROOM1_EQ_ROOM2:
        return (_ROOM1_EQ_ROOM2, ["ROOM1", "ROOM2"], True, True)
    parts = template.split("_")
    if not parts:
        return ("", [], negated, False)
    predicate = parts[0]
    arg_names = parts[1:] if len(parts) > 1 else []
    return (predicate, arg_names, negated, False)


def _unify(ground_fact: dict, predicate: str, arg_names: list[str]) -> dict | None:
    """If this concrete fact matches the template's predicate and arity, return variable bindings.

    Bindings map each template variable (e.g. ``PERSON``) to the actual constant from the
    fact (e.g. ``MissScarlet``). If the predicate or length of arguments does not match,
    return ``None``.
    """
    if ground_fact.get("predicate") != predicate:
        return None
    args = ground_fact.get("args", [])
    if len(args) != len(arg_names):
        return None
    return dict(zip(arg_names, args))


def _merge_substitutions(sub1: dict, sub2: dict) -> dict | None:
    """Combine two partial bindings from different premises into one mapping.

    If the same variable would be bound to two different constants, the merge fails and
    the function returns ``None`` so that rule application can discard that combination.
    """
    merged = dict(sub1)
    for k, v in sub2.items():
        if k in merged:
            if merged[k] != v:
                return None
        else:
            merged[k] = v
    return merged


def _apply_substitution(predicate: str, arg_names: list[str], substitution: dict) -> dict:
    """Instantiate a template (predicate plus variable names) to one fully ground fact.

    Each variable name in ``arg_names`` is replaced by its value from ``substitution``;
    any name still missing is left as-is (rare in practice).
    """
    args = [substitution.get(a, a) for a in arg_names]
    return {"predicate": predicate, "args": args}


def _constraint_satisfied(template_predicate: str, substitution: dict) -> bool:
    """Return whether side constraints for a rule are met given the current bindings.

    For example, a ``ROOM1_EQ_ROOM2`` constraint under negation requires the two room
    slots to be different actual room names; otherwise the rule should not fire.
    """
    if template_predicate == _ROOM1_EQ_ROOM2:
        room1, room2 = substitution.get("ROOM1"), substitution.get("ROOM2")
        return room1 is not None and room2 is not None and room1 != room2
    return True


def _make_inferred_fol_entry(fact: dict) -> dict:
    """Format a newly derived ground fact so it can be appended to the live FOL list.

    Marks it as ``inferred`` and synthesizes a propositional-style name from predicate
    and arguments for readability.
    """
    pred, args = fact["predicate"], fact["args"]
    return {
        "predicate": pred,
        "args": args,
        "value": True,
        "propositional": "_".join([pred] + args),
        "inferred": True,
    }


def _make_inferred_proof(
    conclusion: dict, rule_id: str, bindings: dict, premise_facts: list[dict]
) -> dict:
    """Record how a conclusion was obtained: which rule fired, with what bindings and premises.

    Used for the ``inferred_facts`` output so you can audit or explain each derivation.
    """
    return {
        "fact": conclusion,
        "rule_id": rule_id,
        "variable_bindings": bindings,
        "premise_facts": [{"predicate": f["predicate"], "args": f["args"]} for f in premise_facts],
    }


def infer_fol(
    fol_propositions: list[dict],
    rules: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Repeatedly apply inference rules until no new positive facts appear (fixpoint).

    In plain terms: for each rule, the code looks for combinations of already-known facts
    that match all ``if`` clauses at once, with the same person/room/time variables tied
    together across clauses. When that happens and any ``not`` or inequality checks pass,
    it adds the rule's ``then`` conclusion to the knowledge base. Proof records are built
    every time a new fact is added.

    Args:
        fol_propositions: List of FOL dicts with predicate, args, value (true).
        rules: List of rule dicts with id, if, then from rules.json.

    Returns:
        (extended_fol_propositions, inferred_facts)
        - extended_fol_propositions: original + newly inferred facts
        - inferred_facts: list of {fact, rule_id, variable_bindings, premise_facts}
    """
    known_keys: set[str] = {_fol_fact_key(f) for f in fol_propositions if _is_positive_fact(f)}
    inferred_with_proofs: list[dict] = []
    fol_list = list(fol_propositions)

    changed = True
    while changed:
        changed = False
        for rule in rules:
            rule_id = rule.get("id", "")
            if_templates = rule.get("if", [])
            then_template = rule.get("then", "")
            if then_template == _CONTRADICTION:
                continue
            then_pred, then_args, then_negated, _ = _parse_rule_template(then_template)
            if then_negated:
                continue

            pos_premises: list[tuple[str, list[str]]] = []
            neg_premises: list[tuple[str, list[str]]] = []
            constraint_premises: list[tuple[str, list[str]]] = []

            for template in if_templates:
                pred, arg_names, neg, is_const = _parse_rule_template(template)
                if is_const:
                    constraint_premises.append((pred, arg_names))
                elif neg:
                    neg_premises.append((pred, arg_names))
                else:
                    pos_premises.append((pred, arg_names))

            candidates_per_premise: list[list[tuple[dict, dict]]] = []
            for pred, arg_names in pos_premises:
                cands = [
                    (fol, sub)
                    for fol in fol_list
                    if _is_positive_fact(fol) and (sub := _unify(fol, pred, arg_names)) is not None
                ]
                candidates_per_premise.append(cands)

            if not candidates_per_premise:
                continue

            def try_combinations(idx: int, acc_sub: dict, acc_facts: list[dict]) -> None:
                nonlocal changed
                if idx == len(pos_premises):
                    for c_pred, c_args in constraint_premises:
                        if not _constraint_satisfied(c_pred, acc_sub):
                            return
                    for n_pred, n_args in neg_premises:
                        neg_fact = _apply_substitution(n_pred, n_args, acc_sub)
                        if _fol_fact_key(neg_fact) in known_keys:
                            return
                    conclusion = _apply_substitution(then_pred, then_args, acc_sub)
                    conclusion_key = _fol_fact_key(conclusion)
                    if conclusion_key not in known_keys:
                        known_keys.add(conclusion_key)
                        fol_entry = _make_inferred_fol_entry(conclusion)
                        fol_list.append(fol_entry)
                        inferred_with_proofs.append(_make_inferred_proof(conclusion, rule_id, acc_sub, acc_facts))
                        changed = True
                    return
                for fol, sub in candidates_per_premise[idx]:
                    merged = _merge_substitutions(acc_sub, sub) if acc_sub else sub
                    if merged is not None:
                        try_combinations(idx + 1, merged, acc_facts + [fol])

            try_combinations(0, {}, [])

    return fol_list, inferred_with_proofs


def _write_json(data: dict, path: str | Path) -> None:
    """Save ``data`` as pretty-printed UTF-8 JSON, creating any missing parent folders."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def write_inferred_facts(inferred_facts: list[dict], output_path: str | Path) -> None:
    """Persist every inferred fact and its proof metadata to ``inferred_facts.json`` (or similar).

    At the top level the file includes a short ``summary`` (counts per predicate) so a
    human can skim the file, plus the full ``inferred_facts`` list with rule ids and premises.

    Args:
        inferred_facts: List of {fact, rule_id, variable_bindings, premise_facts}.
        output_path: Path to write inferred_facts.json.
    """
    # Summarise counts by predicate for a quick human-readable overview.
    predicate_counts: dict[str, int] = {}
    for entry in inferred_facts:
        fact = entry.get("fact", {})
        pred = fact.get("predicate")
        if not pred:
            continue
        predicate_counts[pred] = predicate_counts.get(pred, 0) + 1

    payload = {
        "summary": {
            "num_inferred": len(inferred_facts),
            "predicates": predicate_counts,
        },
        "inferred_facts": inferred_facts,
    }
    _write_json(payload, output_path)


def load_evidence_and_rules(
    evidence_path: str | Path,
    rules_path: str | Path,
) -> dict:
    """Read the case evidence file and the rule set, and return one combined dictionary.

    This keeps all inputs to Module 3 in one place: facts Module 1/2 already collected,
    any witness-query trace, game metadata, and the full rules plus constraints from ``rules.json``.

    Args:
        evidence_path: Path to evidence_found.json (written by module_1 + module_2).
        rules_path: Path to rules.json.

    Returns:
        dict with keys:
            - evidence: dict of proposition -> True (facts in KB)
            - witness_queries_added: list of {question, value} (from module_2)
            - metadata: case metadata from evidence file
            - rules: list of rule dicts from rules.json
            - game_constraints: suspects, rooms, weapons, time_points from rules.json
            - rules_metadata: metadata from rules.json
    """
    evidence_path = Path(evidence_path)
    rules_path = Path(rules_path)

    with open(evidence_path, encoding="utf-8") as f:
        evidence_data = json.load(f)

    with open(rules_path, encoding="utf-8") as f:
        rules_data = json.load(f)

    return {
        "evidence": evidence_data.get("evidence", {}),
        "witness_queries_added": evidence_data.get("witness_queries_added", []),
        "metadata": evidence_data.get("metadata", {}),
        "rules": rules_data.get("rules", []),
        "game_constraints": rules_data.get("game_constraints", {}),
        "rules_metadata": rules_data.get("metadata", {}),
    }


def run(
    evidence_path: str | Path,
    rules_path: str | Path,
    kb_fol_path: str | Path | None = None,
    inferred_facts_path: str | Path | None = None,
    show_case_view: bool = False,
) -> dict:
    """End-to-end Module 3: load evidence and rules, build FOL, run inference, optionally save and visualize.

    Steps in order: merge in ``Likely*`` priors from a Module 2 ``hypothesis_summary.json`` when
    present; convert the evidence map to FOL rows; run forward chaining; write the extended KB
    and/or inferred facts when paths are provided; optionally open the case viewer.

    Args:
        evidence_path: Path to ``evidence_found.json`` (facts from earlier modules).
        rules_path: Path to ``rules.json`` (inference rules and game constraints).
        kb_fol_path: If set, write the full FOL KB (including inferred rows) here.
        inferred_facts_path: If set, write proof-carrying inferred facts here.
        show_case_view: If true, launch the interactive case viewer for this state.

    Returns:
        Dictionary with ``fol_propositions`` (all facts after inference), ``inferred_facts``
        (proof steps only), and ``metadata`` copied from the evidence file.
    """
    data = load_evidence_and_rules(evidence_path, rules_path)

    # If Module 2 wrote a hypothesis summary, convert its best guess into
    # additional propositional facts so FOL rules can use them.
    evidence_for_fol = dict(data["evidence"])
    evidence_path_obj = Path(evidence_path)
    hypothesis_summary_path = evidence_path_obj.parent / "hypothesis_summary.json"
    if hypothesis_summary_path.exists():
        try:
            with open(hypothesis_summary_path, encoding="utf-8") as f:
                hyp_data = json.load(f)
            summary = hyp_data.get("summary", {})
            best = summary.get("best_guess", {})
            culprit = best.get("culprit")
            weapon = best.get("weapon")
            room = best.get("room")
            if culprit:
                evidence_for_fol[f"LikelyCulprit_{culprit}"] = True
            if weapon:
                evidence_for_fol[f"LikelyWeapon_{weapon}"] = True
            if room:
                evidence_for_fol[f"LikelyRoom_{room}"] = True
        except Exception:
            # Keep Module 3 robust if hypothesis file is malformed or unreadable.
            pass

    fol_propositions = create_fol_propositions(evidence_for_fol)
    fol_extended, inferred_facts = infer_fol(fol_propositions, data["rules"])

    if kb_fol_path is not None:
        # Group by predicate and add a brief summary to make the FOL KB easier
        # to inspect by hand while preserving the raw list of propositions.
        predicate_counts: dict[str, int] = {}
        grouped_by_predicate: dict[str, list[dict]] = {}
        for fol in fol_extended:
            pred = fol.get("predicate", "")
            predicate_counts[pred] = predicate_counts.get(pred, 0) + 1
            grouped_by_predicate.setdefault(pred, []).append(fol)

        kb_payload = {
            "summary": {
                "num_facts": len(fol_extended),
                "predicates": predicate_counts,
            },
            "fol_propositions": fol_extended,
            "by_predicate": grouped_by_predicate,
        }
        _write_json(kb_payload, kb_fol_path)

    if inferred_facts_path is not None:
        write_inferred_facts(inferred_facts, inferred_facts_path)

    if show_case_view:
        from src.case_viewer import get_solution_from_evidence, show_case_view as show_view
        gc = data.get("game_constraints", {})
        rooms = gc.get("rooms", [])
        time_points = gc.get("time_points", ["8pm", "9pm", "10pm"])
        evidence_for_view = dict(evidence_for_fol)
        for fol in fol_extended:
            if fol.get("value") is True and not fol.get("negated"):
                prop = fol.get("propositional")
                if prop:
                    evidence_for_view[prop] = True
        solution = get_solution_from_evidence(evidence_for_view)
        show_view(
            module_id=3,
            title="Module 3 — FOL KB & inferred facts",
            solution=solution,
            evidence=evidence_for_view,
            rooms=rooms,
            time_points=time_points,
            extra_lines=[f"Inferred facts: {len(inferred_facts)}", f"Total FOL propositions: {len(fol_extended)}"],
        )

    return {
        "fol_propositions": fol_extended,
        "inferred_facts": inferred_facts,
        "metadata": data.get("metadata", {}),
    }
