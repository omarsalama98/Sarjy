"""Session-wide fixtures.

Autouse, not a per-test opt-in: app.memory.store.get_store() successfully
constructs a REAL modal.Dict in any environment with local Modal credentials
configured -- the same F3 discovery app/tools/quota.py documents ("`import
modal` DOES succeed..."), confirmed live here too. Without this fixture, any
memory test that doesn't explicitly inject a store would silently read and
write the real "sarjy-memory" Modal Dict -- found running this block's own
test suite, not assumed: a handful of test-only records (fake sign-in names)
landed in the real dict before this fixture existed. app.tools.quota's own
tests dodge this per call site (every QuotaLedger() there takes an explicit
`store=`); app.memory.store's tests go through the module-level get_store()
everywhere, so one autouse fixture is the single place to guarantee it.
"""

import pytest

from app.memory import store as store_module


class _AlwaysFailsModalDict:
    """Stands in for modal.Dict for the WHOLE test suite. Forcing
    construction to fail is what makes get_store()'s own fallback path
    (M1) the thing under test, rather than a mock pretending to be one."""

    def __init__(self, *a: object, **k: object) -> None:
        raise RuntimeError("modal.Dict is never touched by the test suite")


@pytest.fixture(autouse=True)
def _isolated_memory_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Forces every test onto the in-process fallback, and clears it before
    each test so fake names from one test (e.g. "Bob Ws") can never collide
    with or leak into another.

    No post-yield cleanup needed: monkeypatch's own teardown restores the
    real `get_store` (undoing the `_ModalDictStore` patch too) once this
    test ends, and the NEXT test's setup calls `cache_clear()` again before
    it runs -- a test here that replaces `get_store` itself with a plain
    lambda (test_memory.py's M2 test) would otherwise leave a lambda with
    no `.cache_clear()` for a post-yield call here to find.
    """
    monkeypatch.setattr(store_module, "_ModalDictStore", _AlwaysFailsModalDict)
    store_module.get_store.cache_clear()
    store_module._in_process_records.clear()
