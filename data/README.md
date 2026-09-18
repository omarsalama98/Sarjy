# Data

## `reference/` — committed

Fetched once from the upstream API and committed deliberately. **Never re-fetch these**; the free tier is 120 requests total and these are permanent reference data.

| File | Source | Requests spent | Fetched |
|---|---|---|---|
| `passports.json` | Travel Buddy `GET /Passports` | 1 | 2026-09-18 |
| `destinations.json` | Travel Buddy `GET /Destinations` | 1 | _TBD_ |
| `visa-map/<CC>.json` | Travel Buddy `POST /VisaMap` — all 211 destinations per passport | 1 each | _TBD_ |
| `colour-legend.json` | Derived, **verified** against `POST /VisaRequirements` | ~6 | _TBD_ |
| `passport-index.csv` | [ilyankou/passport-index-dataset](https://github.com/ilyankou/passport-index-dataset) (MIT, Jan 2025) | 0 | _TBD_ |

### The colour legend is verified, not inferred

`VisaMap` returns destinations bucketed into four colours, but `CustomPassportRank` enumerates **eight** rule types — so the mapping is lossy, and only `blue = eVisa` is confirmed. Every entry in `colour-legend.json` must carry the `VisaRequirements` response that proved it.

A guessed mapping inside a product whose thesis is "never state what you can't source" would be self-defeating.

### Known artifact

A passport appears in its own `red` bucket (SA in SA's red list). Self-reference, not a claim. Filter it.

## `cache/` — gitignored

Runtime cache of live `VisaRequirements` lookups, keyed by passport+destination, each stored with its `generated_at`. Warm, not authoritative — every served answer states which layer answered and how fresh it is.
