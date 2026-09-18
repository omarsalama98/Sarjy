---
description: "Quota-aware vendor client — 120 requests total, resolution order, reserve rule"
paths:
  - "**/vendor/**"
  - "**/clients/**"
  - "**/providers/**"
  - "**/tools/**"
  - "backend/**"
  - "src/**"
---

# The vendor client

The upstream visa API free tier is **120 requests in total** — not per month, not per day. Every request is spent permanently. This is why the client is a first-class component rather than plumbing, and it is the part of this codebase closest to Sarj's own daily work.

## Resolution order

Never skip a layer. Never reorder them.

```
cached VisaMap (category, zero cost)
  → warm cache (detail, previously fetched)
    → vendored passport-index CSV (offline, unlimited)
      → live VisaRequirements (1 request — only on a miss, only above reserve)
```

**Every answer states which layer served it and how fresh that layer is.** That sentence is the product, not a debug line.

## The reserve is inviolable

`QUOTA_RESERVE` requests are held back for the demo and the reviewer's own exploration. Below that threshold the client **stops calling live and serves from the CSV, saying so.**

**A reviewer must never see a quota error.** Degrade, never die. A 429 in front of the reviewer is a failed submission regardless of how good the rest is.

Remaining quota is surfaced in the UI. It costs nothing and it shows the system was built to be operated.

## Reference data is fetched once, ever

`Destinations`, `Passports`, and each passport's `VisaMap` are committed under `data/reference/`. **Never re-fetch them.** If a test needs them, read the file.

Adding a request to a hot path is a blocking review issue. Count the requests a change costs before writing it.

## The colour legend is verified, not inferred

`VisaMap` buckets destinations into four colours, but the API enumerates **eight** rule types — so the mapping is lossy. Only `blue = eVisa` is confirmed by observation.

Every entry in `colour-legend.json` ships with the `VisaRequirements` response that proved it. **A guessed mapping inside a product whose thesis is "never state what you can't source" would be self-defeating**, and it is the first thing a sharp reviewer would probe.

Known artifact: a passport appears in its own `red` bucket. Self-reference, not a claim — filter it.

## Failure is part of the contract

Every call has a timeout and a defined result for failure, timeout, empty, and malformed. A hang is worse than an error. On any failure the next layer down answers, and the user is told.

## Other sources

- **Wikipedia REST** — set a compliant `User-Agent` (`Sarjy/0.1 (<repo>; <email>)`) on every call. Wikimedia rate-limits generic agents and may block them outright. Cache aggressively; place data barely changes.
- **Aladhan** — **by-coordinate endpoint only.** `timingsByCity` returns placeholder coordinates for every city, so its response cannot be traced to a location. Take coordinates from the Wikipedia lookup.

## Anti-patterns

- A live call where a cached layer would have answered
- Re-fetching reference data
- Spending below the reserve
- A call with no timeout
- Serving a stale answer without saying it is stale
- Inferring the colour legend instead of verifying it
