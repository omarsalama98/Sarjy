---
name: travel-buddy-api
description: Travel Buddy visa API — verified endpoint shapes and the published colour legend, researched 2026-09-20; no raw response is committed in the repo
metadata:
  type: reference
---

Travel Buddy visa API (`visa-requirement.p.rapidapi.com`), verified from
<https://travel-buddy.ai/api/> on 2026-09-20. **No raw response body is committed anywhere in
this repo** — `TDD.md` §Quota claims `data/reference/visa-map/SA.json` exists, and it does not.
Anything about response shape must come from a live body or that page, not from the TDD.

- `POST /v2/visa/check` — body `{"passport":"CN","destination":"ID"}`. Response:
  `data.visa_rules.primary_rule{name,duration,color}`, `data.destination{passport_validity,embassy_url,…}`,
  `data.mandatory_registration{name,link}`, `data.visa_rules.exception_rule.full_text`, `meta.generated_at`.
- `POST /v2/visa/map` — body `{"passport":"CN"}`. Response `data.colors{red,green,blue,yellow}`,
  each a comma-separated list of destination ISO codes.
- Fallback CSV: `visualpharm/visa-free-dataset`, `passport-index-tidy-iso2.csv`
  (`raw.githubusercontent.com/visualpharm/visa-free-dataset/master/`). Values are day counts,
  or one of `visa free` / `visa on arrival` / `eta` / `e-visa` / `visa required` / `no admission`;
  `-1` means passport == destination.

⚠️ **The colour legend contradicts the TDD.** The TDD and `.claude/rules/tools/vendor-client.md`
both say *"only blue = eVisa is confirmed."* The vendor's own published legend says
**blue = visa on arrival *or* eVisa** — blue is ambiguous, so a map-layer answer can never state
"eVisa". The legend is published by the vendor, which means it is citable and does not need
~6 requests of verification.

Quota is **120 requests total, ever** — not per month. `data/README.md` tracks what has been
spent; check the RapidAPI dashboard before assuming a count.
