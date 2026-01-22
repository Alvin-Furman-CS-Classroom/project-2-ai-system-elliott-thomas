# Detective AI (Game)

## Overview

_Detective AI_ is a turn-based mystery-solving game where an AI detective investigates cases by gathering evidence, reasoning about clues, and solving crimes. The system starts with initial case information (like crime scene details and witness statements) and a limited number of questions it can ask. The AI uses logical reasoning to understand what happened, searches for the best questions to ask next, and builds up evidence to identify the culprit and explain what happened.

This theme fits the course because detective work naturally requires organizing facts and rules (knowledge representation), drawing conclusions from evidence (logical inference), and deciding what information to gather next (search and planning). The system uses **Propositional Logic** to encode case facts and rules into a knowledge base that can be queried and checked for contradictions. **Search algorithms** help the detective decide which questions to ask next by exploring different investigation paths and choosing the most promising ones. **First-Order Logic** allows the system to reason about relationships between people, places, and times (e.g., "Alice was in the kitchen at 8pm"). **Advanced Search and Optimization** techniques help evaluate competing theories about what happened, finding the best explanation that fits all the evidence. **Reinforcement Learning** can improve the detective's strategy over many cases by learning which types of questions are most effective. The detective domain provides concrete, testable problems where the system must produce explainable conclusions with clear success criteria (correctly identifying the culprit and explaining the reasoning). The system is designed to be testable: given the same initial case and query budget, it should produce the same conclusion and trace.

## Team

- Thomas Corbin
- Elliot Chamil

## Proposal

See [AIgent_Proposal.md](AIgent_Proposal.md) for the full proposal.

**Summary:** Detective AI is a turn-based mystery-solving system that uses propositional and first-order logic for knowledge representation and inference, search algorithms for query planning, optimization techniques for hypothesis evaluation, and reinforcement learning to improve query strategies over multiple cases.

## Module Plan

Your system must include 5-6 modules. Fill in the table below as you plan each module.

| Module | Topic(s) | Inputs | Outputs | Depends On | Checkpoint |
| ------ | -------- | ------ | ------- | ---------- | ---------- |
| 1 | Propositional Logic (knowledge bases, entailment, CNF, resolution or chaining) | `case_init.json`, `rules.json` | `evidence_found.json`, `questionable_evidence_report.txt` | None | Checkpoint 1 |
| 2 | Search (heuristics, A* / IDA* / Beam Search) | `evidence_found.json`, `rules.json`, `actions.json`, scenario program interface, `query_budget` | `query_plan.json`, `observations.json`, `search_trace.txt` | Module 1 | Checkpoint 1 |
| 3 | First-Order Logic (predicates, quantifiers, unification, inference/chaining) | `observations.json`, `rules_fol.txt` | `kb_fol.json`, `inferred_facts.json` | Modules 1-2 | Checkpoint 2 |
| 4 | Advanced Search (optimization, hill climbing / simulated annealing / genetic algorithms) | `kb_fol.json`, `inferred_facts.json`, `hypothesis_schema.json`, `scoring_rules.json` | `hypotheses_ranked.json`, `optimization_log.txt` | Module 3 | Checkpoint 3 |
| 5 | Reinforcement Learning (MDP, policy/value functions, Q-learning) | Scenario program environment, state representation, reward function | `policy.json` (or Q-table), `training_curve.csv` | Modules 2-4 | Checkpoint 4-5 |
| 6 | Evaluation Metrics (accuracy-style measures, error analysis); optional templated reporting | `solution.json`, system outputs from Modules 2-5 | `evaluation_report.md`, `final_conclusion.txt` | Modules 2-5 | Final Demo |

## Repository Layout

```
your-repo/
├── src/                              # main system source code
├── unit_tests/                       # unit tests (parallel structure to src/)
├── integration_tests/                # integration tests (new folder for each module)
├── .claude/skills/code-review/SKILL.md  # rubric-based agent review
├── AGENTS.md                         # instructions for your LLM agent
└── README.md                         # system overview and checkpoints
```

## Setup

List dependencies, setup steps, and any environment variables required to run the system.

## Running

Provide commands or scripts for running modules and demos.

## Testing

**Unit Tests** (`unit_tests/`): Mirror the structure of `src/`. Each module should have corresponding unit tests.

**Integration Tests** (`integration_tests/`): Create a new subfolder for each module beyond the first, demonstrating how modules work together.

Provide commands to run tests and describe any test data needed.

## Checkpoint Log

| Checkpoint | Date | Modules Included | Status | Evidence |
| ---------- | ---- | ---------------- | ------ | -------- |
| 1 |  |  |  |  |
| 2 |  |  |  |  |
| 3 |  |  |  |  |
| 4 |  |  |  |  |

## Required Workflow (Agent-Guided)

Before each module:

1. Write a short module spec in this README (inputs, outputs, dependencies, tests).
2. Ask the agent to propose a plan in "Plan" mode.
3. Review and edit the plan. You must understand and approve the approach.
4. Implement the module in `src/`.
5. Unit test the module, placing tests in `unit_tests/` (parallel structure to `src/`).
6. For modules beyond the first, add integration tests in `integration_tests/` (new subfolder per module).
7. Run a rubric review using the code-review skill at `.claude/skills/code-review/SKILL.md`.

Keep `AGENTS.md` updated with your module plan, constraints, and links to APIs/data sources.

## References

List libraries, APIs, datasets, and other references used by the system.
