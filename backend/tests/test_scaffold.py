"""Proves the test harness actually runs.

Block 0 found `make lint` and `make test` had never executed — ruff and mypy
were declared but not installed, and pytest collected nothing. The Stop hook
was therefore passing on an empty set. This file exists so that an empty
`tests/` can never be mistaken for a green run again; Block 6 replaces it with
the gate's real Tier A suite.
"""


def test_harness_runs() -> None:
    assert True
