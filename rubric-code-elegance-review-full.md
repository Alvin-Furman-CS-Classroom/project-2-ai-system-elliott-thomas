# Code Hygiene Rubric Review — Full Project (Overwrite)

**Rubric source:** [Code Elegance Rubric](https://csc-343.path.app/rubrics/code-elegance.rubric.md), Criterion 5 (Code Hygiene)  
**Reference file:** `AGENTS.md`  
**Scope reviewed:** `src/*.py` (project-wide hygiene pass)  
**Date:** 2026-04-09

---

## Summary

Hygiene has improved from the previous pass: major UI magic numbers were centralized in `src/case_viewer.py`, and `src/module_5.py` now uses named constants for sampling/grid behavior plus clearer JSON load failure messages. Remaining hygiene gaps are mostly structural (duplicate parser patterns across modules and duplicated demo/pipeline logic in long files), not correctness bugs.

**Code Hygiene score (Criterion 5): `3 / 4`**  
This aligns with “Mostly clean. Minor instances of duplication or a few magic numbers.”

---

## Evidence-Based Hygiene Result

### What is now clean
- **Magic-number reduction in viewer UI**
  - `src/case_viewer.py` now defines constants like `MAP_CELL_PX`, `TIMELINE_HEIGHT`, `FADE_ALPHA_STEP`, `MAX_EXTRA_LINES`.
- **Magic-number reduction in Module 5**
  - `src/module_5.py` now defines constants like `MODULE2_OBS_SAMPLE_LIMIT`, `GRID_DIMENSION`, `ASCII_ROW_PERSON_LIMIT`.
- **No obvious commented-out dead code blocks**
  - No large disabled blocks found in `src/*.py`.
- **No meaningless zero-status noise lines in walkthrough output**
  - Module 5 now suppresses “0 learned facts” boilerplate.

### Remaining hygiene issues
1. **Duplication in proposition parsing helpers**
   - `src/case_viewer.py` contains many near-parallel parser functions (`_parse_at`, `_parse_weapon`, `_parse_door_locked`, etc.).
   - This is understandable for readability, but still a duplication hotspot.

2. **Repeated literal/style tokens still present**
   - Colors and labels are better but still repeated in some branches (`"#f3f6fb"`, similar marker strings).
   - Some display/sample limits remain hardcoded in older code paths (especially demo `__main__` sections).

3. **Large demo pipeline block in `case_viewer.py`**
   - The `if __name__ == "__main__":` section is long and duplicates orchestration responsibilities found elsewhere.
   - Not dead code, but maintainability hygiene is affected.

4. **Broad exception swallow sites remain**
   - While primarily an error-handling rubric issue, blanket `except Exception: ... pass` also contributes to hygiene clutter by hiding operational context.

---

## Final Criterion 5 Score

| Criterion | Score | Rationale |
|---|---:|---|
| Code Hygiene | **3/4** | Codebase is mostly clean and improved, but still has notable duplication and a few scattered literals/monolithic sections. |

---

## Action Items to Reach 4/4 Hygiene

- [ ] Create shared parser utilities (or table-driven parser map) to reduce repetitive proposition parsing code.
- [ ] Consolidate remaining repeated UI tokens (colors/labels) into top-level constants.
- [ ] Move demo orchestration from `case_viewer.py` `__main__` into a dedicated script/entrypoint.
- [ ] Replace `except Exception: pass` sites with narrower exceptions and minimal context logging.

---

## Notes

- This overwrite is intentionally focused on **Code Hygiene only** (Criterion 5), as requested.
- Other rubric dimensions (naming, abstraction, error handling, etc.) were not rescored here.
