# Module Rubric Report — Checkpoint 1

**Project:** Detective AI  
**Checkpoint:** 1 (Modules 1 & 2)  
**Rubric:** [AI System Module Rubric](https://csc-343.path.app/projects/project-2-ai-system/ai-system.rubric.md)

---

## Summary

Modules 1 and 2 are complete and aligned with the README spec: Module 1 implements propositional KB, rule grounding, and forward chaining with contradiction detection; Module 2 implements heuristic-based witness fact selection and evidence writing. Inputs and outputs are clear and testable. Documentation and test coverage are strong. Topic engagement (propositional logic, search/heuristics) is evident in the implementation. GitHub practices (commit quality, collaboration) are not assessable from the code alone and are left for instructor review.

---

## Part 1: Source Code Review (src/)

### 1.1 Functionality (8 points)

**Score: 8**

- **Evidence:** Module 1: `run()` reads case_init and rules, builds KB, grounds rules, runs inference, writes `evidence_found.json` and `questionable_evidence_report.txt`; contradiction rules (e.g. R011, R012) are applied and reported. Module 2: `select_and_add_witness_facts` ranks by priority, selects top n, adds only True facts to KB; `write_questions_to_evidence` creates/updates JSON with `witness_queries_added`. Integration tests use real data and assert on file contents and KB updates.
- **Assessment:** All specified features work. Edge cases (empty witness_knowledge, n ≤ 0, missing file) are handled. No observed crashes or unexpected behavior.

---

### 1.2 Code Elegance and Quality (7 points)

**Score: 7**

- **Evidence:** See Code Elegance Report. Average elegance score 3.75/4 (all criteria 3–4). Structure, naming, abstraction, and idioms are strong.
- **Assessment:** Exemplary code quality; clear structure and naming, appropriate abstraction.

---

### 1.3 Documentation (4 points)

**Score: 4**

- **Evidence:** Module-level docstrings in both modules explain purpose and design (e.g. KB stores only True). Every public function has a docstring with purpose, Args, and Returns (e.g. `read_case_init`, `ground_rule`, `select_and_add_witness_facts`, `write_questions_to_evidence`). Type hints used on function signatures (`path: str | Path`, `-> list[str]`). Inline comments explain non-obvious steps (e.g. ROOM1 before ROOM, “only True added to KB”).
- **Assessment:** Documentation meets “excellent” bar: docstrings, types, and targeted comments for complex logic.

---

### 1.4 I/O Clarity (3 points)

**Score: 3**

- **Evidence:** Module 1: inputs are `case_init.json` and `rules.json` (paths); outputs are `evidence_found.json` (evidence dict + metadata) and `questionable_evidence_report.txt` (contradiction flag, proposition count, rule list). Module 2: inputs are KB dict, witness_knowledge dict, evidence path, optional n; output is updated evidence file and mutated KB. README module table and docstrings describe I/O. Integration tests and `output_test_files` allow direct verification.
- **Assessment:** Inputs and outputs are clearly defined and easy to verify.

---

### 1.5 Topic Engagement (5 points)

**Score: 5**

- **Evidence:** Module 1: propositional knowledge base (only-True semantics), rule templates with placeholders, grounding via Cartesian product, forward chaining until fixpoint or CONTRADICTION, NOT_ handling and contradiction reporting—all core propositional-logic/KB concepts. Module 2: heuristic (priority list) for selecting which facts to “query” next; prioritization by proposition type (Alibi_, At_, Weapon_, etc.) that feeds inference—clear informed-search/heuristic design.
- **Assessment:** Deep engagement with propositional logic (Module 1) and search/heuristics (Module 2); implementation reflects the stated topics.

---

**Part 1 Subtotal: 27 / 27**

---

## Part 2: Testing Review (unit_tests/ and integration_tests/)

### 2.1 Test Coverage and Design (6 points)

**Score: 6**

- **Evidence:** Unit tests: `test_module_1.py` covers read_case_init, read_rules, ground_rule, ground_all_rules, build_kb, rule_premises_met, apply_rule, infer, has_contradiction (including edge cases: missing file, empty KB, contradiction rule). `test_module_2.py` covers get_priority_score (known/unknown prefix, relative priority), select_and_add_witness_facts (empty, n≤0, only-True in KB, priority order), write_questions_to_evidence (new file, preserve existing keys). Integration: module_1 full `run()` with Path and str; module_2 full pipeline (case_init → KB + witness_knowledge → select → write) with assertions on selected list, KB updates, and written JSON.
- **Assessment:** Broad coverage of core behavior and edge cases; clear separation between unit and integration tests.

---

### 2.2 Test Quality and Correctness (5 points)

**Score: 5**

- **Evidence:** Tests assert behavior (return shapes, KB contents, file contents) rather than implementation details. Isolation: unit tests use minimal fixtures (`_tiny_constraints`, small dicts) or temp dirs (module_2 write tests). Integration tests use real case_init and defined output paths. No trivial or redundant assertions; tests would fail if behavior regressed.
- **Assessment:** Tests are meaningful, correctly implemented, and passing; they verify actual behavior with good isolation.

---

### 2.3 Test Documentation and Organization (4 points)

**Score: 4**

- **Evidence:** Tests grouped by function (e.g. `TestReadCaseInit`, `TestGetPriorityScore`). Test method names describe the scenario (`test_returns_empty_list_when_no_witness_knowledge`, `test_adds_only_true_values_to_kb`). Docstrings state what is being tested. Integration test docstrings explain run instructions and where output files are written.
- **Assessment:** Organization is clear; names and docstrings make intent and scope obvious.

---

**Part 2 Subtotal: 15 / 15**

---

## Part 3: GitHub Practices (8 points)

**Score: Not assessed from codebase**

- **Evidence:** Commit history, branches, pull requests, and collaboration are not visible from the files alone.
- **Assessment:** 3.1 (Commit Quality) and 3.2 (Collaboration Practices) must be evaluated by the instructor using the repository history and GitHub UI.

---

## Scoring Summary

| Section                          | Points | Notes                    |
|----------------------------------|--------|--------------------------|
| **Participation Requirement**    | Gate   | Must pass (instructor)   |
| **Part 1: Source Code Review**    | 27/27  |                          |
| **Part 2: Testing Review**       | 15/15  |                          |
| **Part 3: GitHub Practices**     | —/8    | Instructor assessment    |
| **Total (from this review)**     | **42** | + up to 8 from Part 3   |

---

## Action Items

- [ ] Ensure all team members have meaningful commits and collaboration (participation requirement).
- [ ] (Optional) Add integration test that runs module_1 then module_2 on the same case and checks that evidence_found.json from module_1 can be extended by module_2’s `write_questions_to_evidence` (full pipeline).
- [ ] (Optional) In README “Running” / “Testing,” add exact commands to run unit and integration tests for modules 1 and 2.

---

## Questions

- None. Module specs in the README and proposal are sufficient to evaluate checkpoint 1 scope.
