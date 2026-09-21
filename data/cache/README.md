"""Runtime cache of live visa lookups.

Gitignored on purpose — these files are written by the running app after a
live RapidAPI call succeeds (`TravelBuddyTool._write_cache`). They are not
reference data and must not be committed.

An empty directory is the committed default. That means every pair not
already in `data/reference/` falls through to the map/CSV layers, which
only carry a category label. Warming happens after the quota ledger is
unlocked — see `docs/outbound/2026-09-21-quota-unlock.md`.
"""
