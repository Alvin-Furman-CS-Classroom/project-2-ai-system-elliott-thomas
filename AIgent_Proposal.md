# Proposal

## Detective AI (Game)

_Detective AI_ is a turn-based "case solving" system that starts from an
initial Knowledge Base (KB) of facts and rules, then queries a standalone
scenario program (the "world") to collect new evidence. After each query, the
system adds the observation to its KB, performs logical inference to derive
additional facts, and uses search/optimization to decide what to query next.
The final output is (1) a reproducible query and reasoning log and (2) a
conclusion stating what happened (e.g., culprit, timeline) with key supporting
inferences.

This theme fits the course because detective work naturally requires formal
knowledge representation (facts/rules), inference, and planning under limited
actions (query budget). The system is designed to be testable: given the same
initial case and query budget, it should produce the same conclusion and trace.

## Modules

### Module 1: Propositional Logic KB (Case Facts + Game Rules)

**Topics:** Propositional Logic (knowledge bases, entailment, CNF, resolution
or chaining)

**Input:**
- `case_init.json`: initial evidence as propositions (e.g.,
  `"At_Alice_Kitchen_8pm": true`, `"DoorLocked_8pm": true`, only some information given, the rest is found through queries to the game)
- `rules.json`: propositional rules/constraints (e.g., `If DoorLocked_8pm
  AND NoKeyFound THEN ForcedEntry`)

**Output:**
- `evidence_found.json`: normalized propositional KB (facts + rules, consistent symbol
  naming)
- `questionable_evidence_report.txt`: flags contradictions in the KB and tracks misinformation; includes normalization summary

**How it works:** This module establishes the foundation by organizing initial clues into a structured knowledge base. It parses the case file, extracting atomic propositions (e.g., "DoorLocked_8pm: true") and converting them to a standardized format. The system then loads game rules expressed as logical implications (e.g., "if door locked AND no key found, then forced entry"). Using propositional logic techniques, it converts rules to Conjunctive Normal Form (CNF) for efficient processing and performs consistency checking via resolution to detect contradictions. The normalization process ensures consistent symbol naming across all facts and rules, creating a clean, queryable knowledge base for subsequent modules.

**Integration:** Defines the base KB format used across the system; Modules 2–4
consume this KB (directly or via summaries).

**Prerequisites:** None.

---

### Module 2: Informed Search for "Next Best Query"

**Topics:** Search (heuristics, A* / IDA* / Beam Search)

**Input:**
- `evidence_found.json` from Module 1
- `rules.json` from Module 1
- `actions.json`: available query actions (e.g., `CHECK(location, evidence_id)`,
  `ASK(person, question_id)`)
- Scenario program interface (CLI/API): given an action, returns an observation
- `query_budget` (integer): maximum number of actions till game end

**Output:**
- `query_plan.json`: selected sequence of actions that were executed
- `observations.json`: raw observations returned by executing each action in the plan
- `search_trace.txt`: expanded states and heuristic/cost values for
  reproducibility

**How it works:** This module acts as the strategic planner, deciding which evidence to gather under a limited query budget. The search algorithm models the investigation as a state space where each state represents the current knowledge base after executing queries. Starting from the initial KB state, it expands nodes by considering all legal actions (e.g., CHECK("kitchen", "fingerprints") or ASK("Alice", "whereabouts")). For each candidate action, it executes the query against the scenario program to obtain observations, then evaluates the resulting state using a heuristic function that estimates information value (e.g., how many unknown facts might be resolved). The algorithm uses A* (or IDA* for memory efficiency, or Beam Search for speed) to explore the most promising paths first, balancing exploration of high-value queries against the budget constraint. It outputs the optimal query sequence along with all collected observations and a detailed trace.

**Integration:** Uses search to select and execute actions that gather evidence;
collected observations are passed to Module 3 for richer representation and
inference.

**Prerequisites:** Module 1.

---

### Module 3: First-Order Logic Evidence Store + Inference

**Topics:** First-Order Logic (predicates, quantifiers, unification,
inference/chaining)

**Input:**
- `observations.json` from Module 2: raw observations collected from executing
  query actions
- `rules_fol.txt`: FOL rules using predicates (e.g., `At(person, place, time)`,
  `HasMotive(person)`)

**Output:**
- `kb_fol.json`: relational KB (facts + rules)
- `inferred_facts.json`: derived facts with proof steps (rule used + variable
  bindings)

**How it works:** This module elevates the investigation from simple propositional facts to rich relational knowledge. It parses raw observations from Module 2 (e.g., "Found fingerprints on door handle") and converts them into structured first-order predicates like FingerprintsOn("door_handle", "kitchen"). The module then loads FOL rules expressing general patterns, such as "if someone is at place X at time T but not at time T+1, then they moved." Using forward chaining or resolution-based inference, the system applies these rules to derive new facts. For example, given At("Alice", "kitchen", 8) and At("Alice", "bedroom", 9), it infers Moved("Alice", 8, 9). The unification algorithm matches rule variables to concrete entities, and each inferred fact includes a proof trace showing which rule was applied and what variable bindings were used. This relational representation enables reasoning about entities and their relationships, providing richer context for hypothesis generation.

**Integration:** Converts raw "world query" results into structured relations
and derives new facts that improve hypothesis scoring and future query
selection.

**Prerequisites:** Modules 1–2.

---

### Module 4: Advanced Search / Optimization over Case Hypotheses

**Topics:** Advanced Search (optimization, hill climbing / simulated annealing /
genetic algorithms)

**Input:**
- `kb_fol.json` and `inferred_facts.json`
- `hypothesis_schema.json`: hypothesis fields (culprit, timeline, method, etc.)
- `scoring_rules.json`: how to score consistency with the KB (penalties for
  contradictions, bonuses for explained evidence)

**Output:**
- `hypotheses_ranked.json`: top \(k\) candidate hypotheses with scores
- `optimization_log.txt`: iterations and best score progression

**How it works:** This module generates and evaluates competing explanations, treating hypothesis construction as an optimization problem. It starts by creating an initial population of candidate hypotheses, each specifying values for key fields like culprit, timeline, and method. The scoring function evaluates each hypothesis against the knowledge base: it awards points for explaining observed evidence (e.g., if the hypothesis says Alice was in the kitchen and fingerprints were found there), but penalizes contradictions (e.g., if the hypothesis claims Alice was elsewhere when the KB shows she was in the kitchen). The optimization algorithm (hill climbing, simulated annealing, or genetic algorithms) then searches the hypothesis space. Hill climbing starts with a random hypothesis and iteratively makes small mutations to find better-scoring neighbors. Simulated annealing allows occasional "downhill" moves to escape local optima. Genetic algorithms maintain a population, combining high-scoring hypotheses through crossover and introducing mutations. The algorithm continues until convergence or a time limit, outputting the top k hypotheses ranked by score.

**Integration:** Produces the current best explanation; the top hypothesis feeds
the final conclusion and can guide what to query next (Module 2).

**Prerequisites:** Module 3.

---

### Module 5: Reinforcement Learning to Improve Query Strategy

**Topics:** Reinforcement Learning (MDP, policy/value functions, Q-learning)

**Input:**
- Scenario program environment (episodes = cases) with the same action set as
  Module 2
- State representation derived from KB summaries (e.g., uncertainty level,
  contradiction count, top-hypothesis margin)
- Reward function (e.g., +100 correct conclusion, -1 per query, -20 incorrect
  conclusion)

**Output:**
- `policy.json` (or Q-table): learned action-selection policy
- `training_curve.csv`: reward/success rate over episodes

**How it works:** This module learns optimal query strategies by training on many detective cases, treating investigation as a Markov Decision Process (MDP). Each episode represents a complete case: the agent starts with initial evidence, selects queries (actions), receives observations, and reaches a terminal state (solving or running out of queries). The state representation captures investigation status: uncertainty level, contradiction count, top-hypothesis margin, and other statistics. The reward function provides sparse feedback: +100 for correct culprit, -1 per query (encouraging efficiency), -20 for incorrect conclusion. Using Q-learning, the agent maintains a Q-table (or neural network) estimating expected future reward for each action-state pair. During training, it explores using ε-greedy exploration, updates Q-values via the Bellman equation, and shifts from exploration to exploitation. Over hundreds of episodes, it learns patterns like prioritizing location queries when uncertainty is high, or asking about alibis when suspects are equally likely. The learned policy can replace or enhance Module 2's heuristic.

**Integration:** Learns from many cases to improve "which query next?"
decisions; can seed or replace Module 2's heuristic policy.

**Prerequisites:** Modules 2–4 (actions + hypothesis scoring to define
states/rewards).

---

### Module 6: Evaluation Metrics + Final Report

**Topics:** Evaluation Metrics (accuracy-style measures, error analysis);
optional templated reporting

**Input:**
- `solution.json`: ground-truth outcome from the scenario program (for testing)
- System outputs: `query_plan.json`, `search_trace.txt`, `inferred_facts.json`,
  `hypotheses_ranked.json`, `training_curve.csv`

**Output:**
- `evaluation_report.md`: solve accuracy, avg queries-to-solve, contradiction
  rate, plus failure examples
- `final_conclusion.txt`: printed conclusion and key supporting facts/inferences
  (the "detective's report")

**How it works:** This module serves as both quality assurance and final output generator. For evaluation, it compares the system's top-ranked hypothesis against the ground-truth solution, computing metrics like accuracy (did we identify the correct culprit?), efficiency (average queries needed to solve), and reliability (how often does the system produce contradictions?). It performs error analysis by examining failure cases: when the system gets it wrong, it traces back through the reasoning chain to identify where things went astray (e.g., missing query, faulty inference, or poor hypothesis score). For the final report, it takes the top hypothesis and generates a human-readable detective's report. The report template includes sections for the conclusion (who did it, how, when), key supporting evidence, the reasoning chain (showing how inferences built upon each other), and the query log. This provides both a verifiable audit trail and an interpretable explanation of the system's reasoning process.

**Integration:** Validates the system end-to-end and produces the announced
conclusion plus a reproducible reasoning log.

**Prerequisites:** Modules 2–5.

---

## Feasibility Study

_A timeline showing that each module's prerequisites align with the course
schedule. Verify that you are not planning to implement content before it is
taught._

| Module | Required Topic(s) | Topic Covered By | Checkpoint Due |
| ------ | ----------------- | ---------------- | -------------- |
| 1      | Propositional Logic | Weeks 1–1.5 | Checkpoint 1 |
| 2      | Search (A*/IDA*/Beam) | Weeks 1.5–3 | Checkpoint 1 |
| 3      | First-Order Logic | Weeks 3–4.5 | Checkpoint 2 |
| 4      | Advanced Search / Optimization | Week 5–6 | Checkpoint 3 |
| 5      | Reinforcement Learning | Weeks 7.5–9 | Checkpoint 4–5 |
| 6      | Evaluation Metrics | Remaining weeks | Final Demo |

## Coverage Rationale

This theme naturally connects course topics: evidence and rules fit knowledge
bases and inference (Modules 1 and 3), case-solving requires planning which
information to gather under a query budget (Module 2), and selecting the best
explanation can be treated as optimization over hypotheses (Module 4).
Reinforcement learning is a realistic extension that improves query selection
over many cases (Module 5). Finally, evaluation is necessary to justify
correctness and feasibility (Module 6). Trade-off: this proposal prioritizes
explainable reasoning (logic + traces) over black-box prediction, keeping
outputs testable and interpretable.
