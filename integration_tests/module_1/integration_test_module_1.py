# Integration tests for module_1: they run the full pipeline (read case_init + rules,
# build KB, ground rules, infer) on real data files in this directory and check that
# the module behaves correctly as a whole.
#
# Difference from unit tests:
# - Unit tests (in unit_tests/test_module_1.py) exercise each function in isolation
#   with small, controlled inputs and assert on that function's return value or
#   side effects only.
# - Integration tests here exercise the whole module together with real JSON inputs
#   and assert on the overall result (e.g. KB state after inference, whether run()
#   completes, contradiction flag). They catch bugs in how the pieces are wired
#   together, not just in a single method.
