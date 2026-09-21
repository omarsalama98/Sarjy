# Data

## `reference/` — committed

Fetched once from the upstream API and committed deliberately. **Never re-fetch these**; the free tier is 120 requests total and these are permanent reference data.

| File | Source | Requests spent | Fetched |
|---|---|---|---|
| `passports.json` | Travel Buddy (200 passports) | 1 | 2026-09-18 |
| `destinations.json` | **Derived** from `visa_map_SA.json`'s 211 destination codes, names cross-referenced against `passports.json` + 12 dependent-territory codes filled by hand (see the file's own `_derived_from`/`_manually_supplemented_codes` fields) | 0 | 2026-09-20 |
| `visa_map_SA.json` | Travel Buddy `POST /v2/visa/map {"passport":"SA"}` — all 211 destinations for one passport | 1 | 2026-09-19/20 (see Upstream correction #1, `docs/plans/blocks/A-grounded-answers.md`) |
| `visa_reqs_SA_JP.json` | Travel Buddy `POST /v2/visa/check {"passport":"SA","destination":"JP"}` — the shape check the normaliser is written against | 1 | 2026-09-20 |
| `colour-legend.json` | The vendor's own **published** legend (travel-buddy.ai/api/), cited directly — D8. One observation cross-checked against `visa_reqs_SA_JP.json` (blue→eVisa for this pair). The 6 additional spot-check requests the block plan budgeted were **not spent** — see `colour-legend.json`'s own `_not_yet_spot_checked` field | 0 additional | 2026-09-20 |
| `passport-index-tidy-iso2.csv` | [visualpharm/visa-free-dataset](https://github.com/visualpharm/visa-free-dataset) (MIT, maintained fork, corrections to 2026-06-14) | 0 | 2026-09-20 |

### The colour legend is a citable vendor statement, not an inference

The vendor publishes red/green/blue/yellow directly on their own page — blue means *"visa on arrival or eVisa"*, genuinely ambiguous by the vendor's own words. `normalise.normalise_map()` never claims a specific visa type from a colour alone; it emits `visa.category` with the vendor's own wording verbatim. See `.claude/rules/tools/vendor-client.md`'s "colour legend" section and D8/D7 in the block plan for the full argument.

### Known artifact

A passport appears in its own `red` bucket (SA in SA's red list). Self-reference, not a claim. Filter it.

## `cache/` — gitignored

Runtime cache of live `VisaRequirements` lookups, keyed by passport+destination, each stored with its `generated_at`. Warm, not authoritative — every served answer states which layer answered and how fresh it is.
