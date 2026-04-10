## Module Rubric Report — Module 2

**Project:** Detective AI  
**Module:** 2 (Search / Informed Beam Search)  
**Rubric:** [AI System Module Rubric](https://csc-343.path.app/projects/project-2-ai-system/ai-system.rubric.md)

---

## Summary

Module 2 is complete and aligned with the README spec for the Search module: it implements an informed beam search that chooses which witness facts to query next, produces a query plan, logs observations, and writes a human-readable search trace. Inputs and outputs are clear and testable, and unit tests thoroughly cover priority scoring, beam search behavior, file outputs, and the `run_search` entry point. Topic engagement with search and heuristics is strong, and overall code elegance matches the Checkpoint 1 report. GitHub practices are not evaluated here and are left for instructor review.

---

## Part 1: Source Code Review (src/module_2.py)

### 1.1 Functionality (8 points)

**Score: 8**

- **Evidence:** `beam_search_query_planning` implements beam search over KB states, using a heuristic that rewards progress toward identifying culprit, weapon, and room and respects a configurable `beam_width` and `query_budget`. `_is_goal_state` checks for the presence of at least one Culprit, MurderLocation, and Weapon fact. `write_search_outputs` generates `query_plan.json`, `observations.json`, and `search_trace.txt` in a clear, documented format. `run_search` loads `evidence_found.json`, runs the search, computes whether the goal was reached, writes outputs, and returns a result dict.
- **Assessment:** Module 2 delivers all promised functionality for the search module. Edge cases like empty witness knowledge, zero query budget, and missing `evidence` keys are handled or tested, and file outputs match the spec.

---

### 1.2 Code Elegance and Quality (7 points)

**Score: 7**

- **Evidence:** See `checkpoint_1_elegance_report.md` and the earlier Module 2 elegance analysis; `module_2.py` scores 3–4 on all elegance criteria (naming, function design, abstraction, style, hygiene, control flow, idioms, error handling). The search loop is readable, helpers encapsulate key logic, and constants avoid magic numbers.
- **Assessment:** Code quality for Module 2 is exemplary and fully consistent with the overall checkpoint elegance score.

---

### 1.3 Documentation (4 points)

**Score: 4**

- **Evidence:** Module-level docstring explains Module 2’s role (“informed search for next best query”). Public functions (`get_priority_score`, `beam_search_query_planning`, `write_search_outputs`, `run_search`) all have docstrings describing purpose, Args, Returns, and behavior (e.g., goal condition, what `search_trace` contains). Type hints are present on function signatures and internal helpers, clarifying expected types.
- **Assessment:** Documentation meets the “excellent” bar: docstrings and types make behavior understandable without reading tests, and the search trace file is self-describing.

---

### 1.4 I/O Clarity (3 points)

**Score: 3**

- **Evidence:** Inputs: `run_search` takes `evidence_path`, `witness_knowledge`, `query_budget`, `output_dir`, and `beam_width`. Outputs: JSON files `query_plan.json` (`{"actions": [...]}`) and `observations.json` (`{"observations": [...]}`), plus a human-readable `search_trace.txt`. These structures are enforced by `write_search_outputs` and validated in `TestWriteSearchOutputs` and `TestRunSearch`. The README module table summarizes Module 2’s file-level I/O.
- **Assessment:** I/O is explicit, structured, and easily verifiable via tests and inspection of the output files.

---

### 1.5 Topic Engagement (5 points)

**Score: 5**

- **Evidence:** Module 2 uses beam search rather than a simple greedy heuristic: it maintains a beam of alternative KB states, scores them with `_heuristic_value`, and explores multiple candidate query sequences. The heuristic encodes domain-aware priorities (Culprit_, MurderLocation_, Weapon_, Alibi_, etc.) and progress toward the goal, plus a tie-breaking jitter. Search traces (heuristics, queries per step, goal reached flag) make the search process inspectable for teaching search and heuristics.
- **Assessment:** Strong engagement with search topics: informed search, heuristics, goal tests, and beam-width tradeoffs are all represented concretely.

---

**Part 1 Subtotal: 27 / 27**

---

## Part 2: Testing Review (unit_tests/test_module_2.py and integration)

### 2.1 Test Coverage and Design (6 points)

**Score: 6**

- **Evidence:** `TestGetPriorityScore` covers known/unknown prefixes and relative ordering. `TestBeamSearchQueryPlanning` checks empty inputs, budget respect, observations matching queries, KB updates, search trace structure, and beam-width enforcement. `TestWriteSearchOutputs` verifies all three files are created and have correct structure/content. `TestRunSearch` verifies that evidence is loaded, search is run, outputs are created, and behavior is correct even when `evidence` is missing from the JSON. Integration tests for Module 2 (in `integration_tests/module_2`) exercise the module with more realistic data and outputs.
- **Assessment:** Tests cover core functionality and important edge cases; they clearly distinguish between pure search logic and file-writing behavior.

---

### 2.2 Test Quality and Correctness (5 points)

**Score: 5**

- **Evidence:** Tests assert meaningful behavior (length of query plans vs. budget, mapping of observations to queries, presence of keys in JSON files) rather than internal implementation details. Temporary directories are used for file outputs to keep tests isolated. Assertions are specific and would fail on genuine regressions (e.g., if search ignored beam width or did not write outputs correctly).
- **Assessment:** Test design is robust and aligned with the rubric’s expectations for correctness and isolation.

---

### 2.3 Test Documentation and Organization (4 points)

**Score: 4**

- **Evidence:** Test class and method names describe intent (`TestBeamSearchQueryPlanning`, `test_beam_width_limits_states_kept`, `test_observations_match_queries`). A top-level module docstring explains the scope (“beam-search query planning and run_search entry point”). Structure mirrors the implementation, making it easy to locate tests for each function.
- **Assessment:** Tests are well-organized and self-documenting.

---

**Part 2 Subtotal: 15 / 15**

---

## Part 3: GitHub Practices (8 points)

**Score: Not assessed from codebase**

- **Evidence:** Commit history, branches, pull requests, and collaboration practices are not visible from the code snapshot.
- **Assessment:** 3.1 (Commit Quality) and 3.2 (Collaboration Practices) should be evaluated by the instructor using the GitHub repository.

---

## Scoring Summary

| Section                          | Points | Notes                    |
|----------------------------------|--------|--------------------------|
| **Participation Requirement**    | Gate   | Must pass (instructor)   |
| **Part 1: Source Code Review**   | 27/27  | Module 2 only            |
| **Part 2: Testing Review**       | 15/15  | Module 2 tests           |
| **Part 3: GitHub Practices**     | —/8    | Instructor assessment    |
| **Total (from this review)**     | **42** | + up to 8 from Part 3   |

---

## Action Items

- [ ] Optionally add a short “heuristic configuration” paragraph in `module_2`’s docstring or README, explaining `_HEURISTIC_GOAL_PROGRESS`, `_HEURISTIC_GOAL_BOOST`, and `_HEURISTIC_TIE_BREAKER_MAX`.  
- [ ] Optionally mention the random tie-breaking jitter in documentation so students understand small run-to-run variations in search traces.  
- [ ] (Optional) Add a brief example of `search_trace.txt` to the README or checkpoint writeup to illustrate how to interpret the heuristics and queries per step.

---

## Questions

- None specific to Module 2; rubric-relevant behavior is fully observable from the code and tests. GitHub practices remain for instructor evaluation.
