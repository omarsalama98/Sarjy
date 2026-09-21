---
name: reference-side-effect-audit
description: How to prove a Sarjy test run or script cannot touch a live modal.Dict or spend a provider/RapidAPI request — the tripwire plugin, and the known unguarded construction sites
metadata:
  type: reference
---

Local Modal credentials make `modal.Dict.from_name(...)` **succeed from a laptop**, so any code
path that builds a store reaches the *production* dict unless something stops it. Two incidents
already: eight test records written into the real `sarjy-memory`, and `sarjy-quota` seeded to
`spent=120` by an unknown local process. Verify, do not assume.

## The tripwire (safe, read-only, ~2 s)

Write a pytest plugin to the scratchpad that replaces `modal.Dict.from_name` and
`socket.socket.connect` / `socket.create_connection` with functions that **record the stack and
raise** (never perform the call), then:

```
cd backend && PYTHONPATH=<scratchpad> uv run pytest -q -p tripwire
```

Allow `127.0.0.1`/`localhost` through so `fastapi.testclient` still works. A `pytest_sessionfinish`
hook prints the hits. "NO attempt to reach modal.Dict or an external socket" is the only passing
answer. The same guards installed in a plain `python -c` script answer the question for
non-pytest entry points (`make dev`, `scripts/`, `eval/`, a REPL).

## What guards what (verify before trusting)

- `backend/tests/conftest.py` — autouse, guards **`app.memory.store` only**.
- `backend/tests/test_quota.py` — guards itself per call site (a fake `modal` module in
  `sys.modules`, or a patched `_ModalDictStore`). Nothing global.
- `backend/tests/test_ws.py` — autouse `_default_tool` patches `factory.get_tool` only;
  `get_llm`/`get_stt`/`get_tts` are per-test.

## The construction sites that reach a live dict with no guard

`QuotaLedger(...)` without `store=`, `factory.get_tool()`, `scripts/fetch_reference.py::_ledger()`
(called by the read-only-sounding `--status`), and `app.memory.store.get_store()` outside pytest.
`quota.py` seeds with `put(skip_if_exists=True)` and has **no override**, so the first touch locks
the number in permanently.

Related: [[reference-voice-gate-verification]].
