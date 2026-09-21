"""QuotaLedger -- reserve arithmetic, the barge-spent case, the
modal.Dict -> in-process fallback (V11), and the durable seed-once behaviour
(F3). No network, no real Modal app -- the F3 tests below fake `modal.Dict`
itself (via sys.modules) rather than hitting the real durable dict, since
seeding the REAL "sarjy-quota" dict from a test run would be exactly the
irreversible mistake F3 exists to prevent."""

import sys
import types
from typing import Any

import pytest

from app.tools import quota as quota_module
from app.tools.quota import QuotaLedger, _InProcessStore, _ModalDictStore


def _ledger(*, total: int = 120, reserve: int = 40, seed: int = 0) -> QuotaLedger:
    # Passing an explicit `store` skips the modal.Dict attempt entirely --
    # deterministic in tests, and exactly the fallback path V11 describes.
    return QuotaLedger(total=total, reserve=reserve, store=_InProcessStore(seed))


def test_status_reflects_seed_and_reserve() -> None:
    ledger = _ledger(seed=9)
    status = ledger.status()
    assert status.total == 120
    assert status.spent == 9
    assert status.reserve == 40
    assert status.remaining == 120 - 9 - 40


def test_spend_increments_the_spent_count() -> None:
    ledger = _ledger(seed=0)
    ledger.spend(1)
    ledger.spend(1)
    assert ledger.status().spent == 2


def test_remaining_never_goes_negative_past_the_reserve() -> None:
    """A spend below the reserve is refused BY THE CALLER (can_spend()
    gates it) -- the ledger itself just reports remaining=0, never negative."""
    ledger = _ledger(total=120, reserve=40, seed=120)
    assert ledger.status().remaining == 0


def test_can_spend_false_once_remaining_hits_the_reserve() -> None:
    ledger = _ledger(total=120, reserve=40, seed=80)  # remaining == 0
    assert ledger.can_spend() is False


def test_can_spend_true_above_the_reserve() -> None:
    ledger = _ledger(total=120, reserve=40, seed=79)  # remaining == 1
    assert ledger.can_spend() is True


def test_a_spend_that_is_then_interrupted_still_counts() -> None:
    """V7 -- spend() is called BEFORE a live request's result is used, so a
    barge that cancels the coroutine after spend() already ran must not
    un-count it. Proven here at the ledger level: spend() has no rollback
    path at all."""
    ledger = _ledger(seed=0)
    ledger.spend(1)  # simulates "the request fired" -- caller never rolls this back
    # ... imagine the caller's coroutine gets cancelled right here ...
    assert ledger.status().spent == 1


def test_falls_back_to_in_process_when_modal_dict_construction_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V11 -- modal.Dict unreachable at runtime falls back to the
    in-process store rather than crashing the whole tool."""

    class _AlwaysFails:
        def __init__(self, *a: object, **k: object) -> None:
            raise RuntimeError("modal.Dict unavailable in this environment")

    monkeypatch.setattr(quota_module, "_ModalDictStore", _AlwaysFails)

    ledger = QuotaLedger(total=120, reserve=40)  # no explicit store -- tries modal.Dict first
    status = ledger.status()  # must not raise
    assert status.spent == 0


# ---------------------------------------------------------------------------
# F3 -- the durable ledger seeds exactly once, and never on a later restart.
# ---------------------------------------------------------------------------


class _FakeDict:
    """Stands in for `modal.Dict` -- just enough of its surface for
    `_ModalDictStore` to drive: `.get()` and `.put(skip_if_exists=...)`,
    the same atomic-set-if-absent primitive the real client exposes."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def put(self, key: str, value: Any, *, skip_if_exists: bool = False) -> bool:
        if skip_if_exists and key in self._data:
            return False
        self._data[key] = value
        return True


@pytest.fixture
def fake_modal(monkeypatch: pytest.MonkeyPatch) -> _FakeDict:
    """Installs a fake `modal` module in `sys.modules` so `_ModalDictStore`'s
    deferred `import modal` (the REAL code, not mocked out) resolves to a
    fake `Dict.from_name()` backed by one shared `_FakeDict`. This exercises
    quota.py's actual seeding logic against a fake backend, rather than
    reimplementing that logic a second time inside the test -- and it never
    touches the real "sarjy-quota" dict, which a test run must not seed."""
    shared = _FakeDict()

    class _FakeDictClass:
        @staticmethod
        def from_name(name: str, create_if_missing: bool = True) -> _FakeDict:
            return shared

    monkeypatch.setitem(sys.modules, "modal", types.SimpleNamespace(Dict=_FakeDictClass))
    return shared


def test_f3_modal_dict_store_seeds_on_first_touch(fake_modal: _FakeDict) -> None:
    ledger = QuotaLedger(total=120, reserve=40, seed_spent=57)
    assert ledger.status().spent == 57


def test_f3_modal_dict_store_never_reseeds_on_a_container_restart(fake_modal: _FakeDict) -> None:
    """The exact scenario F3 exists to prevent: a container restarts (a NEW
    QuotaLedger, built with whatever seed_spent its own default computes to)
    after real spend has already accumulated in the durable dict. The
    accumulated count must win, never the restart's default."""
    first = QuotaLedger(total=120, reserve=40, seed_spent=57)
    first.spend(3)
    assert first.status().spent == 60

    second = QuotaLedger(total=120, reserve=40, seed_spent=999)  # a fresh container's own default
    assert second.status().spent == 60  # NOT reset to 999


def test_f3_seeding_is_skip_if_exists_not_an_unconditional_write(fake_modal: _FakeDict) -> None:
    """Direct proof against `_ModalDictStore` itself (not the ledger
    wrapping it): a second construction never touches "spent" once it's
    already present, even if real spend happened in between."""
    _ModalDictStore("sarjy-quota", 57)
    assert fake_modal.get("spent") == 57

    fake_modal.put("spent", 60)  # simulates real spend having happened since
    _ModalDictStore("sarjy-quota", 999)  # a second container starting up
    assert fake_modal.get("spent") == 60
